"""Phase 07 Linux certification probes. Native GUI absence is BLOCKED, never mocked as native.

Run alongside the four existing verifiers; their assertions are not recounted here.
All destructive fixtures live in TemporaryDirectory; every child is reaped.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import select
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from pydantic import ValidationError

from flochat.cli import build_parser
from flochat.comments import CommentManager, SubmissionRequest, submit
from flochat.config import AppConfig
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.ipc import MAX_FRAME, Client, encode_frame, read_endpoint, runtime_path, transmit
from flochat.roadmap import CURRENT_PHASE, PHASES
from flochat.runtime import CoreRuntime, owner_status
from flochat.safety import SafetyEngine
from flochat.youtube import WRITE_SCOPES

ROOT = Path(__file__).resolve().parent.parent


class Certification:
    def __init__(self):
        self.counts = Counter()
        self.labels = set()
        self.metrics = {}

    def check(self, value, label, phase="07"):
        if label in self.labels:
            raise AssertionError("Duplicate certification assertion ID: " + label)
        self.labels.add(label)
        if not value:
            raise AssertionError(label)
        self.counts[phase] += 1

    def denied(self, action, label, phase="07"):
        try:
            action()
        except FloChatError as exc:
            self.check("Traceback" not in str(exc), label, phase)
        else:
            raise AssertionError(label + " unexpectedly succeeded")

    @staticmethod
    def cli(home, *args, python=sys.executable, extra=None, cwd=ROOT):
        environment = {
            **os.environ,
            "FLOCHAT_HOME": str(home),
            "FLOCHAT_DB": str(Path(home) / "flochat.sqlite3"),
            **(extra or {}),
        }
        return subprocess.run(
            [python, "-m", "flochat.cli", *args],
            env=environment,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20,
        )


def foundation(cert, home):
    for args in (
        ("--help",),
        ("--version",),
        ("--json", "version"),
        ("--json", "state"),
        ("--json", "settings"),
        ("--json", "status"),
        ("--json", "doctor"),
        ("--json", "config", "show"),
        ("--json", "config", "validate"),
        ("--json", "platform"),
    ):
        result = cert.cli(home, *args)
        label = "foundation/" + " ".join(args)
        cert.check(result.returncode == 0, label + "/exit", "01")
        cert.check(
            bool(result.stdout) and "Traceback" not in result.stderr, label + "/output", "01"
        )
    cert.check(len(PHASES) == 8 and CURRENT_PHASE == 8, "foundation/roadmap", "01")
    cert.check(
        build_parser().parse_args(["status"]).command == "status", "foundation/argparse", "01"
    )
    for invalid in (0, -1, 601, "invalid"):
        try:
            AppConfig(cooldown_seconds=invalid)
        except ValidationError:
            cert.check(True, "foundation/cooldown/" + str(invalid), "01")
        else:
            raise AssertionError("Unsafe configuration accepted")
    cert.denied(
        lambda: submit(SubmissionRequest("exact", "chat", approved=True)),
        "foundation/boolean-is-not-consent",
        "01",
    )
    result = cert.cli(home, "--json", "safety")
    cert.check(
        result.returncode != 0 and "Traceback" not in result.stderr,
        "foundation/noninteractive-consent-refused",
        "01",
    )


def installation(cert, temporary):
    clone = temporary / "checkout with spaces and 'apostrophe"
    clone.mkdir()
    for name in (
        "README.md",
        "pyproject.toml",
        ".env.example",
        ".gitignore",
        "src",
        "scripts",
        "native",
        "install.sh",
        "start.sh",
        "install.ps1",
        "start.ps1",
    ):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(
                source, clone / name, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info")
            )
        else:
            shutil.copy2(source, clone / name)
    home = temporary / "installed-data"
    environment = {
        **os.environ,
        "FLOCHAT_HOME": str(home),
        "FLOCHAT_DB": str(home / "flochat.sqlite3"),
    }
    launch = subprocess.run(
        ["bash", str(clone / "start.sh")], env=environment, capture_output=True, text=True
    )
    cert.check(launch.returncode == 2, "install/missing-venv", "02")
    # Interrupt the real installer after venv creation, before its package installation completes.
    process = subprocess.Popen(
        ["bash", str(clone / "install.sh")],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    reached = False
    try:
        deadline = time.monotonic() + 40
        pending = b""
        while time.monotonic() < deadline and process.poll() is None:
            if select.select([process.stdout], [], [], 1)[0]:
                pending += os.read(process.stdout.fileno(), 65536)
                if b"Installing FloChat and its dependencies" in pending:
                    reached = True
                    break
        cert.check(reached, "install/interruption-stage-reached", "02")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
        process.stdout.close()
    cert.check(process.returncode != 0, "install/actual-interruption", "02")
    interpreter = clone / ".venv/bin/python"
    cert.check(interpreter.exists(), "install/interruption-keeps-repairable-venv", "02")
    missing = cert.cli(
        home,
        "--json",
        "status",
        python=str(interpreter),
        cwd=clone,
        extra={"PYTHONPATH": str(clone / "src")},
    )
    cert.check(
        missing.returncode != 0 and "pydantic" in missing.stdout + missing.stderr,
        "install/missing-dependency-diagnostic",
        "02",
    )
    cert.check(
        "Traceback" not in missing.stdout + missing.stderr,
        "install/missing-dependency-no-traceback",
        "02",
    )
    # A genuinely clean fresh install (not just repair/repeat) in the same private copy.
    shutil.rmtree(clone / ".venv")
    for index in range(2):
        installed = subprocess.run(
            ["bash", str(clone / "install.sh")],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
        cert.check(installed.returncode == 0, f"install/run/{index}", "02")
        cert.check("Verified:" in installed.stdout, f"install/verified/{index}", "02")
        if index:
            cert.check(
                "Reusing the existing environment" in installed.stdout, "install/venv-reused", "02"
            )
    launched = subprocess.run(
        ["bash", str(clone / "start.sh"), "--json", "doctor"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    cert.check(
        launched.returncode == 0 and json.loads(launched.stdout)["status"] == "ok",
        "install/launcher-doctor",
        "02",
    )
    cert.check(
        subprocess.run(
            [
                str(interpreter),
                "-c",
                "import importlib.util; assert importlib.util.find_spec('PySide6') is None",
            ],
            capture_output=True,
        ).returncode
        == 0,
        "install/qt-remains-optional",
        "02",
    )
    corrupt = temporary / "corrupt-dependency"
    corrupt.mkdir()
    for failure in ("ImportError", "RuntimeError", "OSError"):
        (corrupt / "pydantic.py").write_text(
            f"raise {failure}('synthetic-sensitive-import-sentinel')\n"
        )
        broken = cert.cli(
            home,
            "--json",
            "status",
            python=str(interpreter),
            cwd=clone,
            extra={"PYTHONPATH": str(corrupt) + os.pathsep + str(clone / "src")},
        )
        cert.check(
            broken.returncode != 0 and "pydantic" in broken.stdout + broken.stderr,
            "install/broken-dependency-diagnostic/" + failure,
            "02",
        )
        cert.check(
            "Traceback" not in broken.stdout + broken.stderr,
            "install/broken-dependency-no-traceback/" + failure,
            "02",
        )
        cert.check(
            "synthetic-sensitive-import-sentinel" not in broken.stdout + broken.stderr,
            "install/broken-dependency-sanitized/" + failure,
            "02",
        )
    interpreter.rename(interpreter.with_name("saved-python"))
    try:
        broken = subprocess.run(["bash", str(clone / "start.sh")], capture_output=True, text=True)
        cert.check(
            broken.returncode == 2 and "incomplete" in broken.stderr,
            "install/broken-venv-refused",
            "02",
        )
    finally:
        interpreter.with_name("saved-python").rename(interpreter)
    # Uninstall the package, not the user's database or a global installation.
    removed = subprocess.run(
        [str(interpreter), "-m", "pip", "uninstall", "-y", "flochat"],
        cwd=temporary,
        capture_output=True,
        text=True,
        timeout=20,
    )
    cert.check(removed.returncode == 0, "install/local-uninstall", "02")
    cert.check((home / "flochat.sqlite3").exists(), "install/uninstall-preserves-data", "02")
    for shell, files in (
        ("bash", ["install.sh", "start.sh", "scripts/install_lib.sh"]),
        ("dash", ["start.sh", "scripts/install_lib.sh"]),
    ):
        checked = subprocess.run([shell, "-n", *files], cwd=ROOT, capture_output=True)
        cert.check(checked.returncode == 0, "install/syntax/" + shell, "02")
    powershell = (ROOT / "install.ps1").read_text()
    cert.check(
        not re.search(r"\$iswindows\s*=", powershell, re.I),
        "install/ps7-readonly-regression-static",
        "02",
    )
    cert.check("Set-ExecutionPolicy" not in powershell, "install/no-policy-change-static", "02")


def database_failures(cert, directory):
    path = directory / "db.sqlite3"
    with Database(path) as db:
        db.initialize()
        manager = CommentManager(db)
        manager.comment("edit", text="Retained exact private editor")
        try:
            with db.transaction() as connection:
                connection.execute("UPDATE editor SET text='interrupted' WHERE id=1")
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            pass
        cert.check(
            manager.comment("show")["text"] == "Retained exact private editor",
            "database/interrupted-transaction-rollback",
        )
        lock = sqlite3.connect(path)
        lock.execute("BEGIN IMMEDIATE")
        db.connection.execute("PRAGMA busy_timeout=50")
        try:
            cert.denied(
                lambda: manager.comment("edit", text="must not commit"), "database/locked-refusal"
            )
        finally:
            lock.rollback()
            lock.close()
        cert.check(
            manager.comment("show")["text"] == "Retained exact private editor",
            "database/locked-no-partial-write",
        )
        manager.comment("edit", text="Explicit recovery")
        cert.check(
            manager.comment("show")["text"] == "Explicit recovery", "database/lock-release-recovery"
        )
        core = CoreRuntime(db, AppConfig(data_dir=directory, mode="persistent"))
        core.enqueue(
            {"instance": core.instance, "client": "a" * 32, "command": "stop", "args": {}}
        ).result()
        cert.check(
            core.snapshot("a" * 32)["safety"]["stop_requested"],
            "recovery/stop-flag-is-live-not-cached",
        )
        history = json.dumps(manager.history("list"))
        cert.check(
            "Retained exact private editor" not in history and "Explicit recovery" not in history,
            "database/history-has-no-text-snapshots",
        )
    with Database(path) as db:
        db.initialize()
        cert.check(
            CommentManager(db).comment("show")["text"] == "Explicit recovery",
            "database/restart-retains-editor",
        )
    for name, payload in (("malformed", b"not a database"),):
        invalid = directory / (name + ".sqlite3")
        invalid.write_bytes(payload)
        with Database(invalid) as db:
            cert.denied(db.initialize, "database/" + name + "-refused")
        cert.check(invalid.read_bytes() == payload, "database/" + name + "-unchanged")
    future = directory / "future.sqlite3"
    with sqlite3.connect(future) as connection:
        connection.execute("PRAGMA user_version=999")
    before = future.read_bytes()
    with Database(future) as db:
        cert.denied(db.initialize, "database/future-schema-refused")
    cert.check(future.read_bytes() == before, "database/future-schema-unchanged")
    parent_file = directory / "not-a-directory"
    parent_file.write_text("retained")
    with Database(parent_file / "data.sqlite3") as db:
        cert.denied(db.initialize, "database/unavailable-directory")
    cert.check(parent_file.read_text() == "retained", "database/unavailable-no-data-loss")


def ipc_and_processes(cert, home):
    config = AppConfig(data_dir=home, mode="persistent")
    environment = {
        **os.environ,
        "FLOCHAT_HOME": str(home),
        "FLOCHAT_DB": str(config.resolved_db_path),
    }
    children = []

    def wait_for(predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError("Actual local process deadline")

    def start_owner(mode):
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, "-m", "flochat.cli", "panel", "serve", "--mode", mode],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        children.append(process)
        wait_for(lambda: owner_status(config)["availability"] == "RUNNING")
        cert.metrics.setdefault("startup_seconds", round(time.monotonic() - started, 3))
        return process

    try:
        owner = start_owner("persistent")
        client = Client(config)
        metadata, key = read_endpoint(config)
        cert.check(client.call("status")["safety"]["session"] == "IDLE", "process/starts-idle")
        competitor = cert.cli(home, "panel", "serve", "--mode", "persistent")
        cert.check(
            competitor.returncode != 0 and "Traceback" not in competitor.stderr,
            "process/competing-owner-refused",
        )
        cert.check(
            read_endpoint(config)[0]["instance"] == metadata["instance"],
            "process/competitor-keeps-owner",
        )
        for action in ("start", "stop"):
            result = cert.cli(home, "--json", action, extra={"FLOCHAT_MODE": "persistent"})
            cert.check(
                result.returncode == 0 and "Traceback" not in result.stderr, "process/cli-" + action
            )
        other = Client(config)
        client.call("attach")
        other.call("attach")
        cert.check(
            not client.call("status")["owns_review"] and other.call("status")["owns_review"],
            "ipc/two-clients-single-review-owner",
        )
        payload = {
            "instance": metadata["instance"],
            "client": other.identity,
            "command": "status",
            "args": {},
        }

        def raw(frame):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as wire:
                wire.settimeout(5)
                wire.connect(metadata["endpoint"])
                try:
                    transmit(wire, frame)
                    return wire.recv(MAX_FRAME)
                except (ConnectionResetError, BrokenPipeError):
                    return b""

        valid, _ = encode_frame(key, payload)
        cert.check(bool(raw(valid)), "ipc/authenticated-frame")
        cert.check(not raw(valid), "ipc/duplicate-request-nonce-refused")
        for name, request in (
            ("wrong-owner", {**payload, "instance": "wrong"}),
            ("unknown-field", {**payload, "approved": True}),
            ("missing-field", {k: v for k, v in payload.items() if k != "client"}),
            ("unknown-command", {**payload, "command": "post"}),
        ):
            frame, _ = encode_frame(key, request)
            response = json.loads(raw(frame))
            cert.check(bool(response), "ipc/" + name + "-handled")
            # Decoding the reply proves this is a rejection, not simply any response.
            from flochat.ipc import decode_frame

            decoded, _ = decode_frame(key, json.dumps(response).encode())
            cert.check(decoded["ok"] is False, "ipc/" + name + "-denied")
        cert.check(not raw(b"x" * (MAX_FRAME + 1) + b"\n"), "ipc/oversized-wire-input")
        cert.check(not raw(b"[" * 2000 + b"0" + b"]" * 2000 + b"\n"), "ipc/deep-wire-json")
        cert.check(
            client.call("status")["availability"] == "RUNNING", "ipc/invalid-input-no-owner-crash"
        )
        cert.check(runtime_path(config).stat().st_mode & 0o077 == 0, "ipc/capability-user-only")
        cert.check(Path(metadata["endpoint"]).stat().st_mode & 0o077 == 0, "ipc/socket-user-only")
        client.call("attach")
        client.call("edit", text="Persistent process editor 👩‍💻")
        stat = Path(f"/proc/{owner.pid}/stat")
        status = Path(f"/proc/{owner.pid}/status")
        before_cpu = sum(map(int, stat.read_text().split()[13:15]))
        before_rss = int(re.search(r"VmRSS:\s+(\d+)", status.read_text())[1])
        before_fds = len(list(Path(f"/proc/{owner.pid}/fd").iterdir()))
        before_size = config.resolved_db_path.stat().st_size
        for _ in range(40):
            actor = Client(config)
            actor.call("attach")
            actor.call("start")
            actor.call("pause")
            actor.call("resume")
            actor.call("stop")
            actor.call("detach")
        time.sleep(1)
        after_rss = int(re.search(r"VmRSS:\s+(\d+)", status.read_text())[1])
        after_fds = len(list(Path(f"/proc/{owner.pid}/fd").iterdir()))
        cert.check(after_fds <= before_fds + 4, "resources/repeated-client-fds-bounded")
        cert.check(after_rss - before_rss < 32768, "resources/memory-growth-bounded")
        cert.check(
            config.resolved_db_path.stat().st_size - before_size < 1048576,
            "resources/database-growth-bounded",
        )
        idle_before = sum(map(int, stat.read_text().split()[13:15]))
        time.sleep(2)
        idle_ticks = sum(map(int, stat.read_text().split()[13:15])) - idle_before
        cert.check(idle_ticks / os.sysconf("SC_CLK_TCK") < 0.5, "resources/idle-cpu-bounded")
        cert.metrics.update(
            rss_growth_kib=after_rss - before_rss,
            fd_growth=after_fds - before_fds,
            idle_cpu_seconds=idle_ticks / os.sysconf("SC_CLK_TCK"),
            cycles_cpu_ticks=idle_before - before_cpu,
        )
        cert.check(
            client.call("status")["safety"]["session"] == "STOPPED", "resources/no-phantom-session"
        )
        Path(metadata["endpoint"]).unlink()
        cert.denied(lambda: client.call("status"), "recovery/disappeared-socket-safe")
        owner.kill()
        owner.wait(timeout=5)
        cert.check(
            owner_status(config)["availability"] == "INTERRUPTED",
            "recovery/sigkill-stale-capability",
        )
        owner = start_owner("persistent")
        fresh, fresh_key = read_endpoint(config)
        cert.check(
            fresh["instance"] != metadata["instance"] and fresh_key != key,
            "recovery/rotated-capability",
        )
        state = client.call("status")
        cert.check(
            state["safety"]["session"] == "IDLE" and not state["safety"]["approval_pending"],
            "recovery/no-restored-session-or-approval",
        )
        cert.check(
            state["editor"]["text"] == "Persistent process editor 👩‍💻",
            "recovery/persistent-user-data",
        )
        metadata = fresh
        stale, _ = encode_frame(key, payload)
        cert.check(not raw(stale), "recovery/stale-key-rejected-by-new-process")
        for mode in ("persistent", "manual"):
            client.call("mode", value=mode)
            actor = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "from flochat.config import load_config; from flochat.ipc import Client; "
                    "import time; c=Client(load_config()); c.call('attach'); c.call('start'); "
                    "print('attached',flush=True); time.sleep(60)",
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            children.append(actor)
            cert.check(
                actor.stdout.readline().strip() == b"attached",
                "recovery/independent-client/" + mode,
            )
            actor.kill()
            actor.wait(timeout=5)
            if mode == "persistent":
                wait_for(lambda: client.call("status")["safety"]["session"] == "STOPPED", 20)
                cert.check(
                    owner.poll() is None and not client.call("status")["ui_attached"],
                    "recovery/persistent-real-lease-expiry",
                )
            else:
                owner.wait(timeout=20)
                cert.check(owner.returncode == 0, "recovery/manual-real-lease-expiry")
        cert.check(
            not runtime_path(config).exists() and not Path(metadata["endpoint"]).exists(),
            "cleanup/manual-endpoint-and-socket",
        )
        owner = start_owner("persistent")
        client.call("shutdown")
        owner.wait(timeout=5)
        cert.check(
            owner_status(config)["availability"] == "NOT_RUNNING", "cleanup/explicit-shutdown"
        )
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            if child.stdout:
                child.stdout.close()
            if child.stderr:
                child.stderr.close()
    cert.check(all(child.poll() is not None for child in children), "cleanup/all-children-reaped")


def corrupted_ipc(cert, home):
    home.mkdir(mode=0o700)
    config = AppConfig(data_dir=home)
    path = runtime_path(config)
    path.write_text("[" * 1500 + "0" + "]" * 1500)
    path.chmod(0o600)
    cert.denied(lambda: Client(config).call("status"), "ipc/corrupt-deep-endpoint-sanitized")
    key = b"s" * 32  # Synthetic capability, never production credentials.
    for index, reply in enumerate(
        (
            {},
            {"ok": True},
            {"ok": 1, "result": {}},
            {"ok": False, "error": {"private": "fixture"}},
            {"ok": True, "result": {}, "extra": True},
        )
    ):
        frame, _ = encode_frame(key, {**reply, "request_nonce": "fixture-nonce"})
        with (
            patch(
                "flochat.ipc.read_endpoint",
                return_value=(
                    {"family": "unix", "endpoint": "/fixture", "instance": "fixture"},
                    key,
                ),
            ),
            patch("flochat.ipc.socket.socket"),
            patch("flochat.ipc.encode_frame", return_value=(b"fixture", "fixture-nonce")),
            patch("flochat.ipc.receive", return_value=frame),
        ):
            cert.denied(
                lambda: Client(config).call("status"), f"ipc/malformed-authenticated-reply/{index}"
            )


def callbacks(cert):
    # Execute the actual production callback AST against stand-ins. This is MOCKED
    # callback logic, NOT Qt widget execution, not a headless/native GUI pass.
    tree = ast.parse((ROOT / "src/flochat/panel.py").read_text())
    method = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "complete"
    )
    namespace = {"json": json}
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "actual-panel-callback", "exec"),
        namespace,
    )
    complete = namespace["complete"]
    window = SimpleNamespace(
        generation=2,
        busy=True,
        polling=True,
        notice=Mock(),
        status=Mock(),
        review=None,
        poll=Mock(),
        open_review=Mock(),
        review_observed_at=20,
    )
    complete(window, "start", {"session": "READY"}, None, 1)
    cert.check(not window.notice.setText.called, "ui-mocked/late-start-cannot-overwrite-stop")
    complete(window, "prepare", {"approval_id": "expired"}, None, 1)
    cert.check(not window.open_review.called, "ui-mocked/late-review-cannot-reopen")
    complete(window, "status", {"observed_at": 10}, None, 2)
    cert.check(not window.status.setPlainText.called, "ui-mocked/pre-review-status-ignored")
    complete(window, "start", None, "old error", 1)
    cert.check(
        not window.status.setPlainText.called, "ui-mocked/stale-error-does-not-destroy-new-state"
    )
    complete(window, "stop", {"session": "STOPPED", "observed_at": 30}, None, 2)
    cert.check("STOPPED" in window.notice.setText.call_args.args[0], "ui-mocked/current-stop-shown")
    cert.check(window.review_observed_at == 30, "ui-mocked/stop-ack-advances-status-floor")
    complete(window, "status", {"observed_at": 25}, None, 2)
    cert.check(
        not window.status.setPlainText.called, "ui-mocked/same-generation-pre-stop-status-ignored"
    )
    complete(window, "confirm", {"decision": "OUTCOME_UNKNOWN"}, None, 1)
    cert.check(
        "OUTCOME_UNKNOWN" in window.notice.setText.call_args.args[0],
        "ui-mocked/late-write-outcome-not-hidden",
    )


def network_faults(cert, directory, *, release=False):
    check = partial(cert.check, phase="08" if release else "07")
    denied = partial(cert.denied, phase="08" if release else "07")
    sentinel = "synthetic-sensitive-sentinel"
    cases = (
        ("dns", requests.ConnectionError(sentinel), "OUTCOME_UNKNOWN"),
        ("read-timeout", requests.ReadTimeout(sentinel), "OUTCOME_UNKNOWN"),
        (
            "connection-reset",
            requests.ConnectionError(ConnectionResetError(sentinel)),
            "OUTCOME_UNKNOWN",
        ),
        ("connect-timeout", requests.ConnectTimeout(sentinel), "REJECTED"),
        ("server", 503, "OUTCOME_UNKNOWN"),
        ("rate-limit", 429, "REJECTED"),
        ("quota", 403, "REJECTED"),
        ("corrupt-response", 200, "OUTCOME_UNKNOWN"),
    )
    if release:
        cases = (("deep-response", RecursionError(sentinel), "OUTCOME_UNKNOWN"),)
    for name, fault, expected in cases:
        config = AppConfig(data_dir=directory / name, cooldown_seconds=5)
        with Database(config.resolved_db_path) as db:
            db.initialize()
            manager = CommentManager(db)
            manager.comment("edit", text="Synthetic exact comment 👩‍💻")
            with db.transaction() as connection:
                connection.execute(
                    "INSERT INTO youtube_selection "
                    "VALUES(1,'video','chat','Synthetic live','account','selected')"
                )
            credentials = SimpleNamespace(
                token=sentinel,
                refresh_token=sentinel,
                has_scopes=lambda scopes: scopes == WRITE_SCOPES,
            )
            youtube = SimpleNamespace(
                config=config,
                _credentials=lambda credentials=credentials: (None, credentials),
                _account=lambda creds: {
                    "accounts": [{"channel_id": "account", "title": "Synthetic"}]
                },
                _video=lambda *args: {
                    "availability": "live_chat_available",
                    "live_chat_id": "chat",
                    "video_id": "video",
                    "title": "Synthetic live",
                },
                _usage=Mock(),
            )
            engine = SafetyEngine(db, youtube)
            engine.control("start")
            view = engine.prepare()
            request, approval = engine.confirm_panel(
                view["approval_id"], "SEND " + view["approval_id"]
            )
            response = requests.Response()
            response.status_code = fault if isinstance(fault, int) else 200
            response._content = json.dumps(
                {"error": {"errors": [{"reason": "quotaExceeded"}], "message": sentinel}}
            ).encode()
            if release:
                response.json = Mock(side_effect=fault)
            output = io.StringIO()
            with (
                patch(
                    "requests.Session.post",
                    side_effect=fault if isinstance(fault, Exception) and not release else None,
                    return_value=response,
                ) as post,
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
            ):
                result = submit(request, engine=engine, approval_id=approval)
                check(result["decision"] == expected, "network-mocked/outcome/" + name)
                denied(
                    partial(submit, request, engine=engine, approval_id=approval),
                    "network-mocked/consumed/" + name,
                )
                check(post.call_count == 1, "network-mocked/no-retry/" + name)
            dump = "\n".join(db.connection.iterdump())
            check(
                sentinel not in dump + output.getvalue() + json.dumps(result),
                "security/no-sensitive-output/" + name,
            )
            with db.transaction() as connection:
                row = connection.execute("SELECT state FROM safety_attempts").fetchone()
            check(row[0] == expected, "network-mocked/durable-outcome/" + name)
            # Fresh engine must not restore consent or submit during recovery.
            restarted = SafetyEngine(db, youtube)
            check(
                restarted.state == "IDLE" and restarted.pending is None,
                "network-mocked/restart-idle/" + name,
            )
            if expected == "OUTCOME_UNKNOWN":
                restarted.control("start")
                denied(restarted.prepare, "network-mocked/unknown-blocks-retry/" + name)


def release_audit(cert, directory):
    """Phase 08 controlled input/diagnostic/version regressions; no live services."""
    from importlib.metadata import version

    from flochat import __version__
    from flochat.controller import Controller
    from flochat.platform import detect
    from flochat.youtube import YouTubeError, YouTubeIntegration, _api_error, _client_configuration

    check = partial(cert.check, phase="08")
    directory.mkdir()
    payloads = {
        "invalid-utf8": b"\xff",
        "deep-json": ("[" * 1500 + "0" + "]" * 1500).encode(),
        "oversized-json": b" " * 65537,
        "invalid-path-type": b'{"token_file":42}',
        "invalid-path-character": b'{"token_file":"/invalid\\u0000path"}',
    }
    for name, payload in payloads.items():
        home = directory / name
        home.mkdir()
        config = home / "config.json"
        config.write_bytes(payload)
        for command in ("settings", "doctor", "status", "state"):
            result = cert.cli(home, "--json", command)
            check(
                result.returncode == (1 if command == "doctor" else 2)
                and "Traceback" not in result.stdout + result.stderr
                and config.read_bytes() == payload
                and not (home / "flochat.sqlite3").exists(),
                "release/input/" + name + "/" + command,
            )
    sentinel = "synthetic-sensitive-invalid-environment"
    home = directory / "environment"
    for command in ("settings", "doctor", "status", "state"):
        result = cert.cli(home, "--json", command, extra={"FLOCHAT_CLIENT_SECRET": sentinel})
        check(
            result.returncode == (1 if command == "doctor" else 2)
            and sentinel not in result.stdout + result.stderr
            and "Traceback" not in result.stdout + result.stderr,
            "release/redacted-environment/" + command,
        )
    result = cert.cli(home, "--json", "doctor", extra={"FLOCHAT_COOLDOWN_SECONDS": "0"})
    findings = json.loads(result.stdout)["findings"]
    check(
        result.returncode == 1
        and findings["configuration"]["status"] == "fail"
        and findings["database"]["status"] == "skip",
        "release/doctor-invalid-environment-not-healthy",
    )
    home.mkdir()
    config = home / "config.json"
    config.write_text('{"mode":"manual"}')
    before = config.read_bytes()
    result = cert.cli(home, "--json", "settings")
    check(
        result.returncode == 0
        and config.read_bytes() == before
        and not (home / "flochat.sqlite3").exists(),
        "release/settings-read-only",
    )
    check(version("flochat") == __version__ == "0.1.0", "release/installed-version-consistent")
    project = (ROOT / "pyproject.toml").read_text()
    gradle = (ROOT / "native/android/build.gradle.kts").read_text()
    check(
        'version = {attr = "flochat.__version__"}' in project
        and "versionName = flochatVersion" in gradle
        and "../../src/flochat/__init__.py" in gradle,
        "release/version-single-source-static",
    )
    check(
        "setuptools>=84.1.0" in project
        and "requests>=2.33.0,<3" in project
        and "pip>=26.2" in (ROOT / "install.ps1").read_text()
        and "pip>=26.2" in (ROOT / "scripts/install_lib.sh").read_text(),
        "release/packaging-security-floor-static",
    )
    fixture = directory / "client.json"
    fixture.write_text("[" * 1500 + "0" + "]" * 1500)
    try:
        _client_configuration(fixture)
    except YouTubeError as exc:
        check(exc.code == "configuration", "release/deep-oauth-config-controlled")
    else:
        raise AssertionError("Deep client configuration accepted")
    with Database(directory / "api.sqlite3") as db:
        db.initialize()
        integration = YouTubeIntegration(db, AppConfig(), detect())
        response = Mock(status_code=200)
        response.json.side_effect = RecursionError(sentinel)
        with patch("requests.Session.get", return_value=response) as get:
            try:
                integration._get("channels", {}, SimpleNamespace(token=sentinel))
            except YouTubeError as exc:
                check(
                    exc.code == "invalid_response"
                    and sentinel not in str(exc)
                    and get.call_count == 1,
                    "release/deep-api-response-controlled",
                )
            else:
                raise AssertionError("Deep API response accepted")
        response.status_code = 503
        check(_api_error(response).code == "server", "release/deep-api-error-controlled")
        controller = Controller.create(use_env=False, platform=detect())
        with (
            patch(
                "flochat.runtime.owner_status",
                return_value={
                    "availability": "RUNNING",
                    "editor": {
                        "text": sentinel,
                        "username": sentinel,
                        "character_count": len(sentinel),
                    },
                    "safety": {"session": "IDLE"},
                },
            ),
            patch.object(controller, "_database_check", return_value={"healthy": True}),
        ):
            check(
                sentinel not in json.dumps(controller.status_report()),
                "release/status-does-not-dump-editor-or-profile",
            )


def main():
    if not sys.platform.startswith("linux") or hasattr(sys, "getandroidapilevel"):
        raise SystemExit(
            "BLOCKED: these real process/install probes require Linux; no platform simulation"
        )
    cert = Certification()
    with (
        tempfile.TemporaryDirectory(prefix="flochat-phase07-") as root,
        patch("requests.Session.request", side_effect=AssertionError("Live HTTP forbidden")),
    ):
        temporary = Path(root)
        foundation(cert, temporary / "foundation")
        installation(cert, temporary)
        database_failures(cert, temporary / "database")
        corrupted_ipc(cert, temporary / "corrupt-ipc")
        callbacks(cert)
        network_faults(cert, temporary / "network")
        ipc_and_processes(cert, temporary / "process")
        release_audit(cert, temporary / "release")
        network_faults(cert, temporary / "release-network", release=True)
    print(
        json.dumps(
            {
                "passed_by_phase": dict(cert.counts),
                "passed": sum(cert.counts.values()),
                "failed": 0,
                "metrics": cert.metrics,
                "boundary": "Linux runtime; callback/API mocks are not native GUI or live API",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
