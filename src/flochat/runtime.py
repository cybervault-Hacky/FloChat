"""One explicit, local background owner; UI/CLI are clients, never submission engines."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import queue
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import Future
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from flochat.comments import CommentManager, submit
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.ipc import (
    Client,
    decode_frame,
    encode_frame,
    receive,
    runtime_path,
    transmit,
    write_endpoint,
)
from flochat.lifecycle import SessionManager
from flochat.platform import PlatformKey, detect
from flochat.safety import SafetyBlocked, _exclusive
from flochat.youtube import WRITE_SCOPES, YouTubeError, YouTubeIntegration

# Exact schemas; no arbitrary Python, shell commands, endpoint, account or approved flag.
COMMANDS = {
    name: set()
    for name in (
        "status",
        "attach",
        "detach",
        "start",
        "pause",
        "resume",
        "stop",
        "shutdown",
        "cancel",
        "recover",
        "preview",
        "prepare",
        "drafts",
    )
}
COMMANDS.update(
    edit={"text"},
    draft={"id"},
    confirm={"approval_id", "phrase"},
    mode={"value"},
    resolve={"id", "phrase"},
)


def panel_capability(info=None):
    info = info or detect()
    android = info.key == PlatformKey.ANDROID
    installed = importlib.util.find_spec("PySide6") is not None
    qt_ready = False
    if installed and not android:
        try:
            importlib.import_module("PySide6.QtWidgets")
            qt_ready = True
        except (ImportError, OSError):
            pass
    graphical = info.key != PlatformKey.LINUX or bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )
    return {
        "platform": info.key.value,
        "ui": "Kotlin companion" if android else "Qt native desktop window",
        "desktop_dependency": installed,
        "desktop_runtime_loadable": qt_ready,
        "graphical_session": graphical,
        "launchable": not android and info.supported and qt_ready and graphical,
        "runtime_verified_here": False,
        "display_protocol": (
            "wayland"
            if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland"
            else "x11"
            if os.environ.get("DISPLAY")
            else "none"
        )
        if info.key == PlatformKey.LINUX
        else info.key.value,
        "warning": "Android requires explicit overlay/notification permission "
        "and companion pairing; secure OAuth remains unsupported in"
        " Termux."
        if android
        else "Window stacking depends on the compositor; Wayland may "
        "ignore topmost hints. No global overlay or full-screen "
        "guarantee.",
    }


class CoreRuntime:
    def __init__(self, database, config, *, youtube=None):
        self.database = database
        self.config = config
        self.manager = CommentManager(database)
        self.youtube = youtube or YouTubeIntegration(database, config, detect())
        self.sessions = SessionManager(config)
        self.engine = self.sessions.bind(database, self.youtube)
        self.instance = str(uuid4())
        self.mode = config.mode
        self.closed = threading.Event()
        self.jobs = queue.Queue(maxsize=16)
        self.lock = threading.RLock()
        self.generation = 0
        self.client = None
        self.attachments = 0
        self.last_seen = 0.0
        self.last_seen_wall = 0.0
        self.connection = {
            "state": "UNVERIFIED",
            "reason": "Use Recover to verify account/chat; no automatic network probe.",
            "account": None,
        }
        self.cached = {}
        self.refresh()

    def invalidate(self):
        with self.lock:
            self.generation += 1
            result = self.engine.control("stop")
            result["observed_at"] = time.monotonic()
            return result

    @staticmethod
    def _bounded_editor(view):
        text = view.get("text")
        if isinstance(text, str) and len(text) > 32000:
            return {**view, "text": text[:32000], "truncated": True}
        return view

    def refresh(self):
        with self.database.transaction() as c:
            selected = c.execute("SELECT * FROM youtube_selection WHERE id=1").fetchone()
            approval = self.engine.pending
            if approval:
                editor_snapshot, selection_snapshot = self.engine._snapshots(c)
                if (
                    json.dumps(editor_snapshot, sort_keys=True, ensure_ascii=True)
                    != approval.editor
                    or json.dumps(selection_snapshot, sort_keys=True, ensure_ascii=True)
                    != approval.selection
                ):
                    self.invalidate()
        current_selection = dict(selected) if selected else None
        if self.cached and self.cached.get("selection") != current_selection:
            self.connection = {
                "state": "UNVERIFIED",
                "account": None,
                "reason": "Selected destination changed. Recover or request a fresh review.",
            }
        editor = self._bounded_editor(self.manager.comment("show"))
        with self.lock:
            self.cached = {
                "instance": self.instance,
                "pid": os.getpid(),
                "availability": "RUNNING",
                "mode": self.mode,
                "connection": dict(self.connection),
                "selection": dict(selected) if selected else None,
                "editor": editor,
                "safety": self.engine.control("status"),
                "updated_at": time.time(),
            }

    def snapshot(self, identity):
        with self.lock:
            result = json.loads(json.dumps(self.cached))
            result["safety"]["session"] = self.engine.state
            result["safety"]["approval_pending"] = self.engine.pending is not None
            result["safety"]["stop_requested"] = self.engine.stopping
            result["availability"] = "STOPPING" if self.closed.is_set() else "RUNNING"
            result["owns_review"] = identity == self.client
            result["observed_at"] = time.monotonic()
            result["ui_attached"] = self.client is not None
            result["attachments"] = self.attachments
            return result

    def pulse(self):
        with self.lock:
            if self.client and (
                time.monotonic() - self.last_seen > 15
                or time.time() - self.last_seen_wall > 15
                or time.time() < self.last_seen_wall
            ):
                self.invalidate()
                self.client = None
                if self.mode == "manual":
                    self.closed.set()

    def enqueue(self, request):
        if set(request) != {"instance", "client", "command", "args"}:
            raise FloChatError("Invalid IPC command shape.")
        identity, command, args = (request[k] for k in ("client", "command", "args"))
        if request["instance"] != self.instance:
            raise FloChatError("Core restarted; pair/reopen and review again.")
        if (
            not isinstance(identity, str)
            or len(identity) != 32
            or any(c not in "0123456789abcdef" for c in identity)
        ):
            raise FloChatError("Invalid client identity.")
        if (
            not isinstance(command, str)
            or command not in COMMANDS
            or not isinstance(args, dict)
            or set(args) != COMMANDS[command]
        ):
            raise FloChatError("Unsupported command or arguments.")
        if any(not isinstance(v, str) or len(v) > 32000 for v in args.values()):
            raise FloChatError("Invalid argument type/size.")
        self.pulse()  # Detect sleep/clock gaps BEFORE a new heartbeat refreshes its lease.
        with self.lock:
            if identity == self.client:
                self.last_seen = time.monotonic()
                self.last_seen_wall = time.time()
        future = Future()
        if command == "status":
            future.set_result(self.snapshot(identity))
        elif command in ("stop", "shutdown"):
            # Memory-only SafetyEngine transition is safe while its owner awaits transport.
            result = self.invalidate()
            if command == "shutdown" or (
                command == "stop" and self.mode == "manual" and self.client is None
            ):
                self.closed.set()
            future.set_result(result)
        else:
            try:
                with self.lock:
                    self.jobs.put_nowait((identity, command, args, future, self.generation))
            except queue.Full:
                raise FloChatError(
                    "Core busy; no action queued. Do not automatically retry."
                ) from None
        return future

    def dispatch(self, identity, command, args, generation):
        # A queued Start/Resume predating Stop must not reactivate the session.
        # Hold the same lock through these memory-only transitions as enqueue(Stop).
        if command in ("start", "pause", "resume"):
            with self.lock:
                if generation != self.generation:
                    raise FloChatError("Owner stopped; repeat the action explicitly.")
                if command == "pause":
                    self.generation += 1
                return self.sessions.transition(command)
        if command == "attach":
            self.invalidate()
            with self.lock:
                self.client = identity
                self.attachments += 1
                self.last_seen = time.monotonic()
                self.last_seen_wall = time.time()
            return self.snapshot(identity)
        if command == "detach":
            if identity == self.client:
                self.invalidate()
                self.client = None
                if self.mode == "manual":
                    self.closed.set()
            return {"detached": True}
        if command == "mode":
            if args["value"] not in ("manual", "persistent"):
                raise FloChatError("Invalid operating mode.")
            self.invalidate()
            self.mode = args["value"]
            return {"mode": self.mode, "session": "STOPPED"}
        if command == "resolve":
            return self.engine.resolve(args["id"], args["phrase"])
        if command == "cancel":
            with self.lock:
                self.generation += 1
                return self.engine.control(
                    "pause" if self.engine.state in ("READY", "AWAITING_APPROVAL") else "stop"
                )
        if command in ("prepare", "confirm"):
            if identity != self.client or time.monotonic() - self.last_seen > 15:
                raise SafetyBlocked(
                    "REQUIRES_APPROVAL", "Attach a live panel/terminal and review again."
                )
            if command == "prepare":
                view = self.engine.prepare()
                self.connection = {
                    "state": "VERIFIED_AT_TIME",
                    "verified_at": time.time(),
                    "account": {"channel_id": view["account"], "title": view["account_title"]},
                    "reason": "Verified during review; never a continuous connection guarantee.",
                }
                view["observed_at"] = time.monotonic()
                return view
            request, approval = self.engine.confirm_panel(args["approval_id"], args["phrase"])
            return submit(request, engine=self.engine, approval_id=approval)
        if command in ("edit", "draft"):
            self.invalidate()
            return self._bounded_editor(
                self.manager.comment("edit", text=args["text"])
                if command == "edit"
                else self.manager.drafts("open", draft_id=args["id"])
            )
        if command == "drafts":
            return [
                {"id": d["id"], "title": d["title"][:128]}
                for d in self.manager.drafts("list")["drafts"][:100]
            ]
        if command == "preview":
            return self._bounded_editor(self.manager.comment("preview"))
        if command == "recover":
            self.invalidate()
            with self.lock:
                self.client = identity
                self.last_seen = time.monotonic()
                self.last_seen_wall = time.time()
            _, credentials = self.youtube._credentials()
            account = self.youtube._account(credentials)["accounts"]
            with self.database.transaction() as c:
                selected = c.execute("SELECT * FROM youtube_selection WHERE id=1").fetchone()
            if (
                len(account) != 1
                or not selected
                or account[0]["channel_id"] != selected["account_channel_id"]
            ):
                raise SafetyBlocked("NO_ACCOUNT", "Select the chat again in the terminal.")
            video = self.youtube._video(selected["video_id"], credentials)
            if (
                video["availability"] != "live_chat_available"
                or video["live_chat_id"] != selected["live_chat_id"]
            ):
                raise SafetyBlocked("CHAT_UNAVAILABLE")
            self.connection = {
                "state": "VERIFIED_AT_TIME",
                "verified_at": time.time(),
                "account": account[0],
                "write_grant": credentials.has_scopes(WRITE_SCOPES),
                "reason": "Verified snapshot, not a continuous connection. Start "
                "explicitly; no approval restored.",
            }
            return dict(self.connection)
        raise FloChatError("Unsupported action.")

    def work(self):
        while not self.closed.is_set():
            try:
                identity, command, args, future, generation = self.jobs.get(timeout=0.25)
            except queue.Empty:
                self.refresh()
                continue
            try:
                result = self.dispatch(identity, command, args, generation)
                self.refresh()
                if isinstance(result, dict):
                    result.setdefault("observed_at", time.monotonic())
                future.set_result(result)
            except (FloChatError, YouTubeError) as exc:
                if command in ("prepare", "confirm", "recover"):
                    self.connection = {
                        "state": getattr(exc, "decision", getattr(exc, "code", "ERROR")),
                        "reason": str(exc),
                        "account": None,
                    }
                self.refresh()
                future.set_exception(exc)
            except Exception:
                self.invalidate()
                self.refresh()
                future.set_exception(
                    FloChatError(
                        "Local operation failed. Inspect history/chat before "
                        "another action; no retry."
                    )
                )
        self.invalidate()
        while True:
            try:
                _, _, _, future, _ = self.jobs.get_nowait()
            except queue.Empty:
                break
            future.set_exception(FloChatError("Owner stopped before this queued action ran."))


class LocalServer:
    def __init__(self, core):
        self.core = core
        self.key = secrets.token_bytes(32)
        self.nonces = {}
        self.guard = threading.Lock()
        self.slots = threading.BoundedSemaphore(8)
        self.listener = None
        self.bound = False
        self.published = False
        try:
            path = runtime_path(core.config)
            if os.name == "nt":
                from multiprocessing.connection import Listener

                self.family = "pipe"
                self.endpoint = "\\\\.\\pipe\\FloChat-" + core.instance
                self.listener = Listener(self.endpoint, family="AF_PIPE", authkey=None)
            else:
                android = detect().key == PlatformKey.ANDROID
                self.family = "loopback" if android else "unix"
                self.listener = socket.socket(
                    socket.AF_INET if android else socket.AF_UNIX, socket.SOCK_STREAM
                )
                self.listener.settimeout(0.5)
                directory = Path(tempfile.gettempdir()) / f"flochat-{os.getuid()}"
                if not android:
                    directory.mkdir(mode=0o700, exist_ok=True)
                    info = directory.lstat()
                    if directory.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
                        raise FloChatError("Untrusted local socket directory.")
                self.endpoint = (
                    0
                    if android
                    else str(
                        directory / (hashlib.sha256(str(path).encode()).hexdigest()[:24] + ".sock")
                    )
                )
                if not android and os.path.lexists(self.endpoint):
                    os.unlink(self.endpoint)
                self.listener.bind(("127.0.0.1", 0) if android else self.endpoint)
                self.bound = True
                if android:
                    self.endpoint = self.listener.getsockname()[1]
                else:
                    os.chmod(self.endpoint, 0o600)
                self.listener.listen(8)
            write_endpoint(
                core.config,
                {
                    "instance": core.instance,
                    "pid": os.getpid(),
                    "mode": core.mode,
                    "family": self.family,
                    "endpoint": self.endpoint,
                },
                self.key,
            )
            self.published = True
        except Exception:
            self.close()
            raise

    def serve_client(self, channel):
        try:
            with channel:
                if hasattr(channel, "settimeout"):
                    channel.settimeout(3)
                elif not channel.poll(3):
                    return
                request, nonce = decode_frame(self.key, receive(channel))
                with self.guard:
                    now = time.time()
                    self.nonces = {n: t for n, t in self.nonces.items() if now - t < 35}
                    if nonce in self.nonces or len(self.nonces) >= 4096:
                        return
                    self.nonces[nonce] = now
                try:
                    result = self.core.enqueue(request).result(timeout=240)
                    reply = {"ok": True, "result": result, "request_nonce": nonce}
                except FloChatError as exc:
                    reply = {"ok": False, "error": str(exc), "request_nonce": nonce}
                except Exception:
                    reply = {
                        "ok": False,
                        "error": "Core operation interrupted; inspect history/chat. Never "
                        "retry confirmation automatically.",
                        "request_nonce": nonce,
                    }
                frame, _ = encode_frame(self.key, reply)
                transmit(channel, frame)
        except (OSError, ValueError, TypeError, EOFError, UnicodeError, RecursionError):
            pass  # Unauthenticated/malformed input never reaches the dispatcher or logs.
        finally:
            self.slots.release()

    def accept_clients(self):
        while not self.core.closed.is_set():
            try:
                accepted = self.listener.accept()
                channel = accepted[0] if isinstance(accepted, tuple) else accepted
                if not self.slots.acquire(blocking=False):
                    channel.close()
                    continue
                threading.Thread(target=self.serve_client, args=(channel,), daemon=True).start()
            except TimeoutError:
                pass
            except OSError:
                break
            self.core.pulse()

    def maintain(self):
        while not self.core.closed.wait(0.5):
            self.core.pulse()

    def close(self):
        if self.listener is not None:
            self.listener.close()
        if self.published:
            runtime_path(self.core.config).unlink(missing_ok=True)
            self.published = False
        if self.bound and self.family == "unix":
            Path(self.endpoint).unlink(missing_ok=True)
            self.bound = False


def serve(config):
    config.resolved_db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # A separate owner lock, not the per-attempt reservation lock.
    with (
        _exclusive(SimpleNamespace(path=str(config.resolved_db_path.resolve()) + ".runtime")),
        Database(config.resolved_db_path) as database,
    ):
        database.initialize()
        core = CoreRuntime(database, config)
        server = LocalServer(core)

        def terminate(signum, frame):
            core.invalidate()
            core.closed.set()

        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)
        threading.Thread(target=server.accept_clients, daemon=True).start()
        threading.Thread(target=server.maintain, daemon=True).start()
        try:
            core.work()
        finally:
            server.close()
    return 0


def owner_status(config):
    try:
        return Client(config).call("status")
    except FloChatError:
        return {
            "availability": "INTERRUPTED" if runtime_path(config).exists() else "NOT_RUNNING",
            "session": "STOPPED",
            "message": "No live authenticated core response. No pending approval is recoverable.",
        }


def _end_child(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def launch(config, *, core_only=False):
    capability = panel_capability()
    android = detect().key == PlatformKey.ANDROID
    if not core_only and not android and not capability["launchable"]:
        raise FloChatError(
            "Panel unavailable: install .[desktop] and use a real "
            "graphical desktop. --core-only starts only explicit "
            "background availability."
        )
    status = owner_status(config)
    environment = dict(os.environ)
    from flochat.config import ENV_VARIABLES

    for variable, field in ENV_VARIABLES.items():
        value = getattr(config, field)
        if value is not None:
            environment[variable] = str(value)
    environment["FLOCHAT_DB"] = str(config.resolved_db_path.resolve())
    environment["FLOCHAT_HOME"] = str(config.resolved_data_dir)
    if status["availability"] == "STOPPING":
        raise FloChatError("Owner stopping; wait for the actual result. No automatic restart.")
    core_process = None
    if status["availability"] != "RUNNING":
        command = [sys.executable, "-m", "flochat.cli", "panel", "serve", "--mode", config.mode]
        options = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": environment,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        process = subprocess.Popen(command, **options)
        core_process = process
        for _ in range(40):
            if process.poll() is not None:
                raise FloChatError(
                    "Core startup failed. Run panel serve in the terminal for safe diagnostics."
                )
            status = owner_status(config)
            if status["availability"] == "RUNNING":
                break
            time.sleep(0.1)
        else:
            _end_child(process)
            raise FloChatError("Core readiness unconfirmed; the newly spawned process was stopped.")
    if not core_only and not android:
        panel_process = None
        try:
            previous_attachment = status.get("attachments", 0)
            panel_process = subprocess.Popen(
                [sys.executable, "-m", "flochat.cli", "panel", "view"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                **(
                    {"creationflags": subprocess.CREATE_NO_WINDOW}
                    if os.name == "nt"
                    else {"start_new_session": True}
                ),
            )
            for _ in range(100):
                if panel_process.poll() is not None:
                    raise FloChatError(
                        "Native panel exited before attachment. Run panel view for diagnostics."
                    )
                status = owner_status(config)
                if status.get("ui_attached") and status["attachments"] > previous_attachment:
                    break
                time.sleep(0.1)
            else:
                _end_child(panel_process)
                raise FloChatError("Native panel did not attach; no session was started.")
        except (FloChatError, OSError, subprocess.TimeoutExpired):
            if panel_process is not None:
                _end_child(panel_process)
            # Only clean up a child created here, never a reused owner/panel.
            if core_process is not None and not owner_status(config).get("ui_attached"):
                _end_child(core_process)
            raise
    return {
        **status,
        "capability": capability,
        "message": "Availability started/reused explicitly. Inspect safety.session; "
        "no approval/submission was triggered. Android: build companion and use panel pair.",
    }


def terminal(config):
    client = Client(config)
    launch(config, core_only=True)
    client.call("attach")
    finished = threading.Event()

    def heartbeat():
        while not finished.wait(3):
            try:
                client.call("status")
            except FloChatError:
                break

    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        while True:
            command = input("safety> start/status/pause/resume/stop/submit/recover/quit: ").strip()
            if command == "quit":
                break
            try:
                if command.startswith("resolve "):
                    attempt = command[8:].strip()
                    phrase = input(f"Review the real chat first. Type REVIEWED {attempt}: ")
                    print(json.dumps(client.call("resolve", id=attempt, phrase=phrase), indent=2))
                elif command == "submit":
                    view = client.call("prepare")
                    print(json.dumps(view, ensure_ascii=True, indent=2))
                    phrase = input(
                        f"Type SEND {view['approval_id']} exactly, or anything else to cancel: "
                    )
                    print(
                        json.dumps(
                            client.call("confirm", approval_id=view["approval_id"], phrase=phrase),
                            indent=2,
                        )
                    )
                elif command in ("start", "status", "pause", "resume", "stop", "recover"):
                    print(json.dumps(client.call(command), indent=2))
                else:
                    print("Unknown action.")
            except FloChatError as exc:
                print(str(exc))
    except (EOFError, KeyboardInterrupt):
        print("Session ended; no approval restored.")
    finally:
        finished.set()
        with suppress(FloChatError):
            client.call("detach")
    return 0
