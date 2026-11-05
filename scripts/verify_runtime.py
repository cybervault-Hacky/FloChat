"""Real local IPC/lifecycle and Qt offscreen; synthetic Google services, NEVER live writes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import replace
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from flochat.comments import CommentManager
from flochat.config import AppConfig
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.ipc import Client, decode_frame, encode_frame, read_endpoint, transmit
from flochat.runtime import CoreRuntime, LocalServer, owner_status, panel_capability
from flochat.youtube import WRITE_SCOPES


def main():
    checks = 0

    def check(value, label):
        nonlocal checks
        if not value:
            raise AssertionError(label)
        checks += 1

    def denied(action, label):
        try:
            action()
        except FloChatError:
            check(True, label)
        else:
            raise AssertionError(label)

    with tempfile.TemporaryDirectory(prefix="flochat-runtime-") as temporary:
        original = {"text": "x" * 33000, "character_count": 33000}
        bounded = CoreRuntime._bounded_editor(original)
        check(
            bounded["truncated"] and len(bounded["text"]) == 32000,
            "oversized UI view marked truncated",
        )
        check(len(original["text"]) == 33000, "UI bounding never mutates original local text")
        # Actual core queue transitions: a pre-Stop action is not a new user Start.
        isolated = AppConfig(data_dir=Path(temporary) / "isolated", mode="persistent")
        isolated.resolved_data_dir.mkdir(mode=0o700)
        with Database(isolated.resolved_db_path) as db:
            db.initialize()
            isolated_core = CoreRuntime(db, isolated)
            request = {
                "instance": isolated_core.instance,
                "client": "a" * 32,
                "command": "start",
                "args": {},
            }
            queued = isolated_core.enqueue(request)
            isolated_core.enqueue({**request, "command": "stop"}).result()
            identity, command, args, future, generation = isolated_core.jobs.get_nowait()
            denied(
                lambda: isolated_core.dispatch(identity, command, args, generation),
                "pre-Stop queued Start cannot rearm",
            )
            check(isolated_core.engine.state == "STOPPED", "queued Start remains stopped")
            check(queued is future and future.cancel(), "unused queued Future released")
            check(
                isolated_core.dispatch(identity, "start", {}, isolated_core.generation)["session"]
                == "READY",
                "a genuinely new explicit Start works",
            )
            isolated_core.invalidate()
            for barrier, arguments in (
                ("attach", {}),
                ("mode", {"value": "persistent"}),
                ("edit", {"text": "Isolated local edit"}),
                ("cancel", {}),
                ("pause", {}),
            ):
                isolated_core.dispatch(identity, "start", {}, isolated_core.generation)
                pending = isolated_core.enqueue({**request, "command": "resume"})
                isolated_core.dispatch(identity, barrier, arguments, isolated_core.generation)
                actor, action, options, _, old_generation = isolated_core.jobs.get_nowait()
                denied(
                    partial(isolated_core.dispatch, actor, action, options, old_generation),
                    "stale queued Resume invalid after " + barrier,
                )
                check(
                    isolated_core.engine.state != "READY" and pending.cancel(),
                    barrier + " does not reactivate an old queued intent",
                )
                isolated_core.invalidate()
            closed_servers = []
            original_close = LocalServer.close

            def record_close(server):
                original_close(server)
                closed_servers.append(server)

            with (
                patch(
                    "flochat.runtime.write_endpoint",
                    side_effect=FloChatError("fixture publish failure"),
                ),
                patch.object(LocalServer, "close", autospec=True, side_effect=record_close),
            ):
                denied(lambda: LocalServer(isolated_core), "failed endpoint publication")
            failed = closed_servers[0]
            check(failed.listener.fileno() == -1, "partial startup releases real socket FD")
            check(not Path(failed.endpoint).exists(), "partial startup removes owned socket")
            failed.close()
            check(
                not isolated.resolved_db_path.with_name("flochat.sqlite3.panel.json").exists(),
                "failed startup does not publish capability",
            )
        config = AppConfig(data_dir=Path(temporary), cooldown_seconds=5, mode="persistent")
        shared = {}
        ready = threading.Event()

        def owner():
            with Database(config.resolved_db_path) as db:
                db.initialize()
                manager = CommentManager(db)
                if not manager.comment("show")["text"]:
                    manager.comment("edit", text="First exact 👩‍💻 comment")
                with db.transaction() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO youtube_selection "
                        "VALUES(1,'video','chat','Fixture "
                        "stream','account','selected')"
                    )
                credentials = SimpleNamespace(
                    token="fixture-private-token",
                    refresh_token="fixture-private-refresh",
                    has_scopes=lambda scopes: scopes == WRITE_SCOPES,
                )
                youtube = SimpleNamespace(
                    config=config,
                    _credentials=lambda: (None, credentials),
                    _account=lambda creds: {
                        "accounts": [{"channel_id": "account", "title": "Fixture"}]
                    },
                    _video=lambda *args: {
                        "availability": "live_chat_available",
                        "live_chat_id": "chat",
                        "video_id": "video",
                        "title": "Fixture stream",
                    },
                    _usage=Mock(),
                )
                core = CoreRuntime(db, config, youtube=youtube)
                server = LocalServer(core)
                shared.update(core=core, credentials=credentials, server=server)
                threading.Thread(target=server.accept_clients, daemon=True).start()
                threading.Thread(target=server.maintain, daemon=True).start()
                ready.set()
                try:
                    core.work()
                finally:
                    server.close()

        def start_owner():
            ready.clear()
            thread = threading.Thread(target=owner)
            thread.start()
            check(ready.wait(5), "real local owner ready")
            return thread

        def response(session, url, **kwargs):
            check(
                url == "https://youtube.googleapis.com/youtube/v3/liveChat/messages",
                "sole official endpoint",
            )
            reply = requests.Response()
            reply.status_code = 200
            reply._content = json.dumps(
                {"id": "fixture-accepted", "snippet": kwargs["json"]["snippet"]}
            ).encode()
            return reply

        with (
            patch("requests.Session.request", side_effect=AssertionError("live HTTP forbidden")),
            patch("requests.Session.post", autospec=True, side_effect=response) as post,
        ):
            thread = start_owner()
            client = Client(config)
            other = Client(config)
            try:
                check(client.call("status")["safety"]["session"] == "IDLE", "no automatic start")
                check(client.call("attach")["owns_review"], "attached UI lease")
                client.call("start")
                check(client.call("status")["safety"]["session"] == "READY", "shared start")
                view = client.call("prepare")
                check(view["text"] == "First exact 👩‍💻 comment", "exact core review")
                check(
                    0 < view["expires_in_seconds"] <= 120,
                    "core reports actual remaining review lifetime",
                )
                check(
                    client.call("status")["observed_at"] >= view["observed_at"],
                    "core UI observation ordering",
                )
                check(
                    client.call("status")["ui_attached"], "authenticated attachment is observable"
                )
                check(post.call_count == 0, "prepare does not write")
                denied(
                    lambda: client.call("confirm", approval_id=view["approval_id"], phrase="yes"),
                    "generic yes refused",
                )
                client.call("resume")
                view = client.call("prepare")
                client.call("pause")
                client.call("resume")
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "pause invalidates",
                )
                view = client.call("prepare")
                other.call("attach")
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "client takeover invalidates",
                )
                client.call("attach")
                client.call("start")
                view = client.call("prepare")
                client.call("edit", text="Changed exact text")
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "editing invalidates",
                )
                client.call("start")
                view = client.call("prepare")
                shared["core"].engine.pending = replace(
                    shared["core"].engine.pending, expires=time.monotonic() - 1
                )
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "panel expiry enforced by engine",
                )
                client.call("resume")
                view = client.call("prepare")
                shared["core"].engine.pending = replace(
                    shared["core"].engine.pending, wall_expires=time.time() - 1
                )
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "suspend/wall expiry enforced by engine",
                )
                client.call("resume")
                view = client.call("prepare")
                client.call("recover")
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "recovery never restores approval",
                )
                check(
                    client.call("status")["safety"]["session"] == "STOPPED",
                    "recovery leaves stopped",
                )
                client.call("start")
                view = client.call("prepare")
                entered = threading.Event()
                release = threading.Event()
                outcomes = []

                def in_flight(session, url, **kwargs):
                    entered.set()
                    release.wait(5)
                    return response(session, url, **kwargs)

                post.side_effect = in_flight

                def confirm_in_thread():
                    outcomes.append(
                        client.call(
                            "confirm",
                            approval_id=view["approval_id"],
                            phrase="SEND " + view["approval_id"],
                        )
                    )

                sending = threading.Thread(target=confirm_in_thread)
                sending.start()
                check(entered.wait(3), "mock insert is really in flight")
                # Queue an actual owner-worker Start behind the blocked mocked insert.
                stale_start = shared["core"].enqueue(
                    {
                        "instance": shared["core"].instance,
                        "client": client.identity,
                        "command": "start",
                        "args": {},
                    }
                )
                check(
                    other.call("stop")["session"] == "SUBMITTING",
                    "IPC stop does not falsely recall in-flight request",
                )
                release.set()
                sending.join(5)
                result = outcomes[0]
                denied(
                    lambda: stale_start.result(timeout=5),
                    "queued Start rejected after in-flight Stop",
                )
                check(stale_start.done(), "queued stale intent completed with refusal, not replay")
                check(
                    client.call("status")["safety"]["session"] == "STOPPED",
                    "in-flight stop honored after actual response",
                )
                post.side_effect = response
                check(
                    result["accepted"] and post.call_count == 1,
                    "one explicitly confirmed mocked insert",
                )
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "one use replay refused",
                )
                client.call("start")
                denied(lambda: client.call("prepare"), "persistent duplicate prevention")
                client.call("edit", text="Second intentional comment")
                client.call("start")
                denied(lambda: client.call("prepare"), "persistent cooldown")
                check(
                    client.call("status")["safety"]["cooldown_remaining"] > 0,
                    "authoritative cooldown display",
                )
                with Database(config.resolved_db_path) as db:
                    db.initialize()
                    with db.transaction() as c:
                        c.execute(
                            "UPDATE safety_attempts SET "
                            "started=started-10,monotonic_started=monotonic_started-10"
                        )
                client.call("start")
                view = client.call("prepare")
                post.side_effect = requests.ReadTimeout()
                result = client.call(
                    "confirm", approval_id=view["approval_id"], phrase="SEND " + view["approval_id"]
                )
                check(result["decision"] == "OUTCOME_UNKNOWN", "unknown survives UI response")
                calls = post.call_count
                client.call("recover")
                client.call("start")
                denied(lambda: client.call("prepare"), "reconnection cannot retry unknown")
                check(post.call_count == calls, "no automatic retry or reconnection write")
                client.call(
                    "resolve", id=result["attempt_id"], phrase="REVIEWED " + result["attempt_id"]
                )
                check(
                    client.call("status")["safety"]["session"] == "STOPPED",
                    "explicit simulated review stops",
                )
                for name, args in (
                    ("write", {}),
                    ("confirm", {"approved": True}),
                    ("edit", {"text": 123}),
                    ("start", {"extra": "x"}),
                ):
                    denied(
                        lambda name=name, args=args: client.call(name, **args),
                        "strict schema " + name,
                    )
                metadata, key = read_endpoint(config)
                check(metadata["family"] == "unix", "no desktop TCP listener")
                check(
                    config.resolved_db_path.with_name("flochat.sqlite3.panel.json").stat().st_mode
                    & 0o077
                    == 0,
                    "endpoint mode 0600",
                )

                def raw(frame):
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                        channel.settimeout(4)
                        channel.connect(metadata["endpoint"])
                        transmit(channel, frame)
                        return channel.recv(524288)

                payload = {
                    "instance": metadata["instance"],
                    "client": client.identity,
                    "command": "status",
                    "args": {},
                }
                frame, _ = encode_frame(key, payload)
                check(bool(raw(frame)), "authenticated frame handled")
                check(not raw(frame), "nonce replay rejected")
                bad, _ = encode_frame(secrets.token_bytes(32), payload)
                check(not raw(bad), "unauthenticated client rejected")
                check(not raw(b'{"bad":1}\n'), "malformed input rejected")
                duplicate_outer = frame.decode().replace("{", '{"at":0,', 1).encode()
                check(not raw(duplicate_outer), "duplicate envelope keys rejected")
                duplicate_body = base64.b64encode(
                    json.dumps(payload).replace("{", '{"command":"start",', 1).encode()
                ).decode()
                crafted = json.loads(frame)
                crafted["nonce"] = secrets.token_hex(16)
                crafted["body"] = duplicate_body
                crafted["mac"] = hmac.new(
                    key,
                    f"{crafted['at']}:{crafted['nonce']}:{duplicate_body}".encode(),
                    hashlib.sha256,
                ).hexdigest()
                check(
                    not raw(json.dumps(crafted).encode() + b"\n"),
                    "authenticated duplicate payload keys rejected",
                )
                for invalid_tag in ("é" * 64, "0" * 63, 123, None):
                    crafted["mac"] = invalid_tag
                    check(not raw(json.dumps(crafted).encode() + b"\n"), "malformed MAC rejected")
                reply, _ = encode_frame(key, {"ok": True, "result": {}, "request_nonce": "wrong"})
                with patch("flochat.ipc.receive", return_value=reply):
                    denied(lambda: client.call("status"), "response bound to requesting nonce")
                failed_socket = Mock()
                failed_socket.connect.side_effect = OSError("fixture refused connection")
                with patch("flochat.ipc.socket.socket", return_value=failed_socket):
                    denied(lambda: client.call("status"), "connection failure is explicit")
                check(
                    failed_socket.close.call_count == 1,
                    "connect failure closes allocated client socket",
                )

                envelope = json.loads(frame)
                envelope["at"] -= 120
                try:
                    decode_frame(key, json.dumps(envelope).encode())
                except ValueError:
                    check(True, "old envelopes rejected")
                else:
                    raise AssertionError("expired frame accepted")
                client.call("attach")
                client.call("start")
                with shared["core"].lock:
                    shared["core"].last_seen = time.monotonic() - 20
                shared["core"].pulse()
                check(
                    client.call("status")["safety"]["session"] == "STOPPED",
                    "lost UI heartbeat stops session",
                )
                client.call("attach")
                client.call("start")
                with shared["core"].lock:
                    shared["core"].last_seen_wall = time.time() - 20
                # First heartbeat after a simulated sleep must NOT revive its old lease.
                check(
                    client.call("status")["safety"]["session"] == "STOPPED",
                    "wall sleep detected before heartbeat refresh",
                )
                check(post.call_count == calls, "liveness never submits")
                env = {
                    **os.environ,
                    "FLOCHAT_HOME": temporary,
                    "FLOCHAT_DB": str(config.resolved_db_path),
                }
                output = subprocess.run(
                    [sys.executable, "-m", "flochat.cli", "--json", "session", "status"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                check(
                    json.loads(output.stdout)["instance"] == metadata["instance"],
                    "CLI and panel same owner",
                )
                # Real Qt widgets/events OFFSCREEN, not compositor/window stacking certification.
                os.environ["QT_QPA_PLATFORM"] = "offscreen"
                try:
                    importlib.import_module("PySide6.QtWidgets")
                except ImportError:
                    qt_result = "BLOCKED: native Qt shared libraries/display unavailable"
                else:
                    qt_result = "EXECUTED: Qt OFFSCREEN only, not a real compositor"
                    from PySide6.QtCore import Qt, QTimer
                    from PySide6.QtWidgets import QApplication, QMainWindow

                    from flochat.panel import show_panel

                    app = QApplication.instance() or QApplication([])

                    def close_panel():
                        windows = [w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)]
                        check(len(windows) == 1, "actual Qt panel instantiated")
                        check(
                            bool(windows[0].windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                            "native window topmost requested, not compositor verified",
                        )
                        windows[0].close()

                    QTimer.singleShot(600, close_panel)
                    check(show_panel(config) == 0, "Qt offscreen graceful close")
                    check(post.call_count == calls, "opening/closing real UI never submits")
                    check(not panel_capability()["launchable"], "headless Linux detected")
                with Database(config.resolved_db_path) as db:
                    db.initialize()
                    dump = "\n".join(db.connection.iterdump())
                    check(
                        "fixture-private-token" not in dump
                        and "fixture-private-refresh" not in dump,
                        "no credentials in database",
                    )
                client.call("shutdown")
                thread.join(5)
                check(not thread.is_alive(), "graceful core shutdown")
                thread = start_owner()
                check(
                    client.call("status")["safety"]["session"] == "IDLE",
                    "restart never restores approval/session",
                )
                client.call("attach")
                denied(
                    lambda: client.call(
                        "confirm",
                        approval_id=view["approval_id"],
                        phrase="SEND " + view["approval_id"],
                    ),
                    "old UI approval invalid after restart",
                )
                check(post.call_count == calls, "restart never writes")
            finally:
                shared["core"].closed.set()
                thread.join(5)
            check(owner_status(config)["availability"] == "NOT_RUNNING", "no stale running claim")
    print(
        f"PASS: {checks} executed runtime assertions. Local IPC/SQLite real; "
        "Google writes MOCKED, no live comments.\n" + qt_result
    )


if __name__ == "__main__":
    main()
