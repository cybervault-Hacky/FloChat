"""Phase 05 verification: synthetic grants/chats and mocked writes ONLY.

No real network is permitted. Run with the installed venv's Python.
"""

from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import sqlite3
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from flochat import youtube as integration_module
from flochat.comments import SubmissionRequest, submit, validate_comment
from flochat.config import AppConfig
from flochat.database import (
    LOCAL_SCHEMA_SQL,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    YOUTUBE_SCHEMA_SQL,
    Database,
)
from flochat.errors import FloChatError
from flochat.platform import detect
from flochat.safety import SafetyBlocked, SafetyEngine, _exclusive, console
from flochat.youtube import WRITE_SCOPES


def _hold_lock(path, ready, release):
    with Database(Path(path)) as db, patch("socket.socket", side_effect=AssertionError("network")):
        db.initialize()
        with _exclusive(db):
            ready.set()
            release.wait(10)


def _race_submit(path, ready, go, result):
    """Two real processes; simulated terminal approval and mocked official POST."""
    with Database(Path(path)) as db, patch("socket.socket", side_effect=AssertionError("network")):
        db.initialize()
        credentials = SimpleNamespace(
            token="fixture-private-token",
            refresh_token="fixture-private-refresh",
            has_scopes=lambda scopes: scopes == WRITE_SCOPES,
        )
        yt = SimpleNamespace(
            config=AppConfig(cooldown_seconds=5),
            _credentials=lambda: (None, credentials),
            _account=lambda creds: {"accounts": [{"channel_id": "account", "title": "Fixture"}]},
            _video=lambda *args: {
                "availability": "live_chat_available",
                "live_chat_id": "chat",
                "video_id": "video",
                "title": "Fixture",
            },
            _usage=lambda *args: None,
        )
        engine = SafetyEngine(db, yt)
        engine.control("start")
        view = engine.prepare()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch("sys.stdout.isatty", return_value=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="SEND " + view["approval_id"]),
        ):
            request, approval = engine.confirm()
        ready.set()
        go.wait(10)
        writes = 0

        def post(session, url, **kwargs):
            nonlocal writes
            writes += 1
            time.sleep(0.15)
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(
                {"id": "mock-id", "snippet": kwargs["json"]["snippet"]}
            ).encode()
            return response

        with patch("requests.Session.post", autospec=True, side_effect=post):
            try:
                outcome = submit(request, engine=engine, approval_id=approval)["decision"]
            except SafetyBlocked as exc:
                outcome = exc.decision
        result.put((outcome, writes))


def main():
    count = 0

    def check(value, label):
        nonlocal count
        if not value:
            raise AssertionError(label)
        count += 1

    def blocked(code, action):
        try:
            action()
        except SafetyBlocked as exc:
            check(exc.decision == code, f"{code}: {exc.decision}")
        else:
            raise AssertionError(f"Expected {code}")

    with (
        tempfile.TemporaryDirectory(prefix="flochat-safety-") as directory,
        patch("socket.socket", side_effect=AssertionError("real network forbidden")),
    ):
        path = Path(directory) / "data.sqlite3"
        with Database(path) as db:
            db.initialize()
            check(db.check()["schema_version"] == SCHEMA_VERSION, "schema")
            config = AppConfig(data_dir=Path(directory), cooldown_seconds=5)
            credentials = SimpleNamespace(
                token="fixture-private-token",
                refresh_token="fixture-private-refresh",
                has_scopes=lambda scopes: scopes == WRITE_SCOPES,
            )
            yt = SimpleNamespace(
                config=config,
                _credentials=lambda: (None, credentials),
                _account=lambda creds: {
                    "accounts": [{"channel_id": "account", "title": "Fixture account"}]
                },
                _video=lambda video, creds: {
                    "availability": "live_chat_available",
                    "live_chat_id": "chat",
                    "video_id": "video",
                    "title": "Fixture live",
                },
                _usage=Mock(),
            )

            def reset(text="Hello 👩‍💻"):
                with db.transaction() as c:
                    c.execute("DELETE FROM safety_attempts")
                    c.execute("DELETE FROM safety_clock")
                    c.execute("DELETE FROM editor")
                    c.execute("DELETE FROM youtube_selection")
                    c.execute("INSERT INTO editor VALUES(1,?,NULL,NULL,'time')", (text,))
                    c.execute(
                        "INSERT INTO youtube_selection "
                        "VALUES(1,'video','chat','title','account','time')"
                    )
                e = SafetyEngine(db, yt)
                e.control("start")
                return e

            def approved(engine):
                view = engine.prepare()
                check(view["text"] == engine.pending.text, "exact preview")
                with (
                    patch("sys.stdin.isatty", return_value=True),
                    patch("builtins.input", return_value="SEND " + view["approval_id"]),
                    contextlib.redirect_stdout(io.StringIO()),
                    patch("sys.stdout.isatty", return_value=True),
                ):
                    return engine.confirm()

            def accepted(session, url, **kwargs):
                check(url.endswith("/youtube/v3/liveChat/messages"), "official insert path")
                check(kwargs["params"] == {"part": "snippet"}, "official part")
                check(
                    kwargs["timeout"] == 20 and kwargs["allow_redirects"] is False,
                    "timeout/no redirects",
                )
                check(session.trust_env is False, "no credential injection")
                r = requests.Response()
                r.status_code = 200
                r._content = json.dumps(
                    {"id": "accepted-id", "snippet": kwargs["json"]["snippet"]}
                ).encode()
                return r

            with patch("requests.Session.post", autospec=True, side_effect=accepted) as post:
                e = reset()
                blocked(
                    "REQUIRES_APPROVAL",
                    lambda: submit(SubmissionRequest("Hello", "chat", True), engine=e),
                )
                r, a = approved(e)
                result = submit(r, engine=e, approval_id=a)
                check(result["accepted"] and result["decision"] == "ACCEPTED", "mock accepted")
                check(post.call_count == 1, "one write")
                blocked("REQUIRES_APPROVAL", lambda: submit(r, engine=e, approval_id=a))
                blocked("DUPLICATE", e.prepare)
                e = SafetyEngine(db, yt)
                check(e.state == "IDLE", "restart no session restored")
                blocked("SESSION_STOPPED", e.prepare)
                e.control("start")
                blocked("DUPLICATE", e.prepare)
                # Canonical duplicate protection, never altering the actual posted message.
                with db.transaction() as c:
                    c.execute("UPDATE editor SET text='Hello  👩‍💻' WHERE id=1")
                e.control("start")
                blocked("DUPLICATE", e.prepare)
                with db.transaction() as c:
                    c.execute("UPDATE editor SET text='different' WHERE id=1")
                e.control("start")
                blocked("COOLDOWN_ACTIVE", e.prepare)
                with db.transaction() as c:
                    c.execute(
                        "UPDATE safety_attempts SET "
                        "started=started-10,monotonic_started=monotonic_started-10"
                    )
                e.control("start")
                check(e.prepare()["decision"] == "REQUIRES_APPROVAL", "elapsed cooldown")
                # Repeated approvals, mutated content/destination and expired approvals.
                for mode in (
                    "text",
                    "chat",
                    "editor",
                    "destination",
                    "account",
                    "grant",
                    "scope",
                    "availability",
                    "expired",
                    "stop",
                    "pause",
                    "restart",
                ):
                    e = reset()
                    r, a = approved(e)
                    before = post.call_count
                    saved_video = yt._video
                    if mode == "scope":
                        credentials.has_scopes = lambda scopes: False
                    elif mode == "availability":
                        yt._video = lambda *args: {"availability": "stream_ended"}
                    elif mode == "text":
                        r = replace(r, comment_text=r.comment_text + "!")
                    elif mode == "chat":
                        r = replace(r, live_chat_id="other")
                    elif mode == "editor":
                        with db.transaction() as c:
                            c.execute("UPDATE editor SET text=text||'!' WHERE id=1")
                    elif mode == "destination":
                        with db.transaction() as c:
                            c.execute(
                                "UPDATE youtube_selection SET selected_at='changed' WHERE id=1"
                            )
                    elif mode == "account":
                        yt._account = lambda creds: {
                            "accounts": [{"channel_id": "other", "title": "Other"}]
                        }
                    elif mode == "grant":
                        credentials.refresh_token = "different-grant"
                    elif mode == "expired":
                        e.pending = replace(e.pending, expires=time.monotonic() - 1)
                    elif mode == "restart":
                        e = SafetyEngine(db, yt)
                        e.control("start")
                    else:
                        e.control(mode)
                    blocked(
                        {
                            "account": "NO_ACCOUNT",
                            "scope": "AUTHORIZATION_REQUIRED",
                            "availability": "CHAT_UNAVAILABLE",
                        }.get(mode, "REQUIRES_APPROVAL"),
                        lambda r=r, e=e, a=a: submit(r, engine=e, approval_id=a),
                    )
                    check(post.call_count == before, "invalid approval no write: " + mode)
                    yt._account = lambda creds: {
                        "accounts": [{"channel_id": "account", "title": "Fixture account"}]
                    }
                    credentials.refresh_token = "fixture-private-refresh"
                    credentials.has_scopes = lambda scopes: scopes == WRITE_SCOPES
                    yt._video = saved_video
                check(bool(validate_comment("\ud800")), "invalid Unicode rejected before SQLite")
                for text in ("", "   ", "a\x00b", " leading ", "x" * 201):
                    e = reset(text)
                    blocked("INVALID_COMMENT", e.prepare)
                e = reset()
                credentials.has_scopes = lambda scopes: False
                blocked("AUTHORIZATION_REQUIRED", e.prepare)
                credentials.has_scopes = lambda scopes: scopes == WRITE_SCOPES
                e = reset()
                with db.transaction() as c:
                    c.execute("DELETE FROM youtube_selection")
                blocked("NO_SELECTED_CHAT", e.prepare)
                e = reset()
                original_video = yt._video
                yt._video = lambda *args: {"availability": "stream_ended"}
                blocked("CHAT_UNAVAILABLE", e.prepare)
                yt._video = original_video
                e = reset()
                e.control("pause")
                blocked("SESSION_PAUSED", e.prepare)
                e.control("resume")
                check(e.state == "READY" and e.pending is None, "resume never approves")
                e.prepare()
                blocked("REQUIRES_APPROVAL", e.confirm)
                # Different failures, no automatic write retry, unknown blocks globally.
                for failure in (
                    requests.ReadTimeout(),
                    requests.ConnectionError(),
                    requests.Timeout(),
                    requests.ConnectTimeout(),
                ):
                    e = reset()
                    r, a = approved(e)
                    before = post.call_count
                    post.side_effect = failure
                    outcome = submit(r, engine=e, approval_id=a)
                    unknown = not isinstance(failure, requests.ConnectTimeout)
                    check(
                        outcome["decision"] == ("OUTCOME_UNKNOWN" if unknown else "REJECTED"),
                        "timeout distinction",
                    )
                    check(post.call_count == before + 1, "no write retries")
                    if unknown:
                        e.control("start")
                        blocked("OUTCOME_UNKNOWN", e.prepare)
                        e.resolve(outcome["attempt_id"], "REVIEWED " + outcome["attempt_id"])
                        check(e.state == "STOPPED", "review stops session")
                        e.control("start")
                        blocked("DUPLICATE", e.prepare)
                for status in (400, 401, 403, 404, 429, 500, 302, 200):
                    e = reset()
                    r, a = approved(e)
                    response = requests.Response()
                    response.status_code = status
                    response._content = json.dumps(
                        {"error": {"message": "fixture-private-token"}}
                    ).encode()
                    post.side_effect = lambda *args, response=response, **kwargs: response
                    outcome = submit(r, engine=e, approval_id=a)
                    check(not outcome["accepted"], "bad API response not accepted")
                    check(
                        outcome["decision"]
                        == (
                            "REJECTED" if status in (400, 401, 403, 404, 429) else "OUTCOME_UNKNOWN"
                        ),
                        "rejection vs uncertainty",
                    )
                    check("fixture-private-token" not in json.dumps(outcome), "redacted")
                for reason, expected in (
                    ("quotaExceeded", "quota_exceeded"),
                    ("rateLimitExceeded", "rate_limited"),
                    ("forbidden", "permission_denied"),
                    ("messageTextInvalid", "invalid_comment"),
                ):
                    e = reset()
                    r, a = approved(e)
                    response = requests.Response()
                    response.status_code = 403
                    response._content = json.dumps(
                        {"error": {"errors": [{"reason": reason}]}}
                    ).encode()
                    post.side_effect = lambda *args, response=response, **kwargs: response
                    check(
                        submit(r, engine=e, approval_id=a)["category"] == expected,
                        "write category " + reason,
                    )
                e = reset()
                post.side_effect = accepted
                commands = iter(("start", "submit", "status", "quit"))

                def terminal_input(prompt):
                    return (
                        "SEND " + prompt.split()[2]
                        if prompt.startswith("Type SEND ")
                        else next(commands)
                    )

                transcript = io.StringIO()
                before = post.call_count
                with (
                    contextlib.redirect_stdout(transcript),
                    patch("sys.stdout.isatty", return_value=True),
                    patch("sys.stdin.isatty", return_value=True),
                    patch("builtins.input", side_effect=terminal_input),
                ):
                    check(console(db, yt) == 0, "complete mocked terminal workflow")
                check(
                    post.call_count == before + 1 and "ACCEPTED" in transcript.getvalue(),
                    "console sends once after own review",
                )
                e = reset()
                commands = iter(("start", "submit", "quit"))
                transcript = io.StringIO()
                post.side_effect = RuntimeError("fixture-private-error-body")
                with (
                    contextlib.redirect_stdout(transcript),
                    patch("sys.stdout.isatty", return_value=True),
                    patch("sys.stdin.isatty", return_value=True),
                    patch("builtins.input", side_effect=terminal_input),
                ):
                    check(
                        console(db, yt) == 0,
                        "unexpected transport interruption closes without retry",
                    )
                check(
                    "fixture-private-error-body" not in transcript.getvalue(),
                    "unexpected errors never expose raw bodies",
                )
                check(
                    db.connection.execute("SELECT state FROM safety_attempts").fetchone()[0]
                    == "OUTCOME_UNKNOWN",
                    "unexpected transport failure persists unknown",
                )
                # Stop while a request may be in flight is not cancellation.
                e = reset()
                r, a = approved(e)

                def stop_in_flight(session, url, **kwargs):
                    check(e.control("stop")["session"] == "SUBMITTING", "accurate in-flight stop")
                    return accepted(session, url, **kwargs)

                post.side_effect = stop_in_flight
                check(
                    submit(r, engine=e, approval_id=a)["accepted"] and e.state == "STOPPED",
                    "accepted despite in-flight stop",
                )
                e = reset()
                r, a = approved(e)
                before = post.call_count
                yt._usage.side_effect = lambda operation: e.control("stop")
                check(
                    submit(r, engine=e, approval_id=a)["category"]
                    == "cancelled_before_transmission",
                    "stop before transport",
                )
                check(post.call_count == before, "pretransmission stop no write")
                yt._usage.side_effect = None
                e = reset()
                yt.config = config.model_copy(update={"cooldown_seconds": 0})
                blocked("BLOCKED", e.prepare)
                yt.config = config
                e = reset()
                with db.transaction() as c:
                    c.execute(
                        "INSERT INTO comment_history"
                        "(live_chat_id,draft_text,comment_text,state,created_at) "
                        "VALUES ('chat','ignored',?,'confirmed','date')",
                        ("Hello 👩‍💻",),
                    )
                blocked("DUPLICATE", e.prepare)
                with db.transaction() as c:
                    c.execute("DELETE FROM comment_history")
                e = reset()
                r, a = approved(e)
                post.side_effect = accepted
                submit(r, engine=e, approval_id=a)
                with db.transaction() as c:
                    c.execute("UPDATE editor SET text='different'")
                with patch("flochat.safety.time.time", return_value=time.time() + 3600):
                    blocked("COOLDOWN_ACTIVE", e.prepare)
                # Durable reservation blocks a second process and survives a crash.
                e = reset()
                r, a = approved(e)
                ctx = multiprocessing.get_context("spawn")
                ready, release = ctx.Event(), ctx.Event()
                process = ctx.Process(target=_hold_lock, args=(str(path), ready, release))
                process.start()
                check(ready.wait(10), "real subprocess acquired lock")
                before = post.call_count
                blocked("SUBMISSION_IN_PROGRESS", lambda: submit(r, engine=e, approval_id=a))
                check(post.call_count == before, "parallel reservation refused")
                release.set()
                process.join(10)
                check(process.exitcode == 0, "subprocess exits cleanly")
                e = reset()
                r, a = approved(e)
                post.side_effect = accepted
                yt._usage.side_effect = RuntimeError("injected interruption before transport")
                try:
                    submit(r, engine=e, approval_id=a)
                except RuntimeError:
                    check(True, "interrupted reserved attempt")
                yt._usage.side_effect = None
                e = SafetyEngine(db, yt)
                e.control("start")
                blocked("OUTCOME_UNKNOWN", e.prepare)
                check(
                    db.connection.execute("SELECT state FROM safety_attempts").fetchone()[0]
                    == "OUTCOME_UNKNOWN",
                    "orphan classification persisted despite blocked policy",
                )
                e = reset()
                ctx = multiprocessing.get_context("spawn")
                first_ready, second_ready, go, result = (
                    ctx.Event(),
                    ctx.Event(),
                    ctx.Event(),
                    ctx.Queue(),
                )
                first = ctx.Process(target=_race_submit, args=(str(path), first_ready, go, result))
                second = ctx.Process(
                    target=_race_submit, args=(str(path), second_ready, go, result)
                )
                first.start()
                check(first_ready.wait(10), "first process approved")
                second.start()
                check(second_ready.wait(10), "second process approved")
                go.set()
                outcomes = [result.get(timeout=15), result.get(timeout=15)]
                first.join(10)
                second.join(10)
                check(
                    sum(writes for _, writes in outcomes) == 1,
                    "two concurrent processes: exactly one mocked POST",
                )
                check(
                    sum(state == "ACCEPTED" for state, _ in outcomes) == 1, "one confirmed result"
                )
                check(
                    first.exitcode == 0 and second.exitcode == 0, "both race processes exit cleanly"
                )
                e = reset()
                with db.transaction() as c:
                    c.execute("INSERT INTO safety_clock VALUES(1,?)", (time.time() + 3600,))
                blocked("BLOCKED", e.prepare)
                e = reset()
                e.prepare()
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    patch("sys.stdout.isatty", return_value=True),
                    patch("sys.stdin.isatty", return_value=True),
                    patch("builtins.input", return_value="yes"),
                ):
                    blocked("REQUIRES_APPROVAL", e.confirm)
                check(
                    e.state == "PAUSED" and e.pending is None, "cancel clears approval and pauses"
                )
                backend = type("Keyring", (), {"__module__": "keyring.backends.SecretService"})()
                write_credentials = integration_module.Credentials(
                    token="fixture-private-token",
                    refresh_token="fixture-private-refresh",
                    token_uri=integration_module.TOKEN_URI,
                    client_id="fixture-client",
                    client_secret="fixture-private-client",
                    scopes=WRITE_SCOPES,
                )
                backend.get_password = Mock(return_value=write_credentials.to_json())
                backend.set_password = Mock()
                flow = Mock()
                flow.run_local_server.return_value = write_credentials
                service = integration_module.YouTubeIntegration(db, config, detect())
                with (
                    patch("keyring.get_keyring", return_value=backend),
                    patch("flochat.youtube._client_configuration", return_value={}),
                    patch.object(
                        service, "_account", return_value={"connection_state": "connected"}
                    ),
                    patch.object(
                        integration_module._TimedFlow, "from_client_config", return_value=flow
                    ) as factory,
                ):
                    stored = integration_module.CredentialStore().load()
                    check(
                        stored.has_scopes(WRITE_SCOPES),
                        "write grant roundtrip in synthetic approved keyring",
                    )
                    backend.get_password.return_value = None
                    connected = service.run("connect", local_browser=True, allow_posting=True)
                    check(
                        factory.call_args.kwargs["scopes"] == WRITE_SCOPES,
                        "explicit write opt-in scope",
                    )
                    check(
                        connected["authorized_scopes"] == list(WRITE_SCOPES),
                        "reported requested scope",
                    )
                    check(
                        flow.run_local_server.call_args.kwargs["prompt"] == "consent",
                        "official consent requested",
                    )
                    check(
                        json.loads(backend.set_password.call_args.args[2])["scopes"]
                        == list(WRITE_SCOPES),
                        "stored scoped grant",
                    )
                    readonly = integration_module.Credentials(
                        token="fixture-private-token",
                        refresh_token="fixture-private-refresh",
                        token_uri=integration_module.TOKEN_URI,
                        client_id="fixture-client",
                        client_secret="fixture-private-client",
                        scopes=integration_module.SCOPES,
                    )
                    backend.get_password.return_value = readonly.to_json()
                    before = factory.call_count
                    try:
                        service.run("connect", local_browser=True, allow_posting=True)
                    except FloChatError:
                        check(
                            factory.call_count == before,
                            "no silent escalation/replacement of stored grant",
                        )
                    else:
                        raise AssertionError("Existing grant must be explicitly disconnected first")
                dump = "\n".join(db.connection.iterdump())
                check(
                    "fixture-private-token" not in dump and "fixture-private-refresh" not in dump,
                    "no credentials in metadata",
                )
        old = Path(directory) / "v3.sqlite3"
        with sqlite3.connect(old) as c:
            c.executescript(SCHEMA_SQL + LOCAL_SCHEMA_SQL + YOUTUBE_SCHEMA_SQL)
            c.execute("PRAGMA user_version=3")
            c.execute("INSERT INTO username_profile VALUES(1,'retained','date')")
            c.execute("INSERT INTO drafts VALUES('id','title','text',NULL,'date','date')")
            c.execute("INSERT INTO editor VALUES(1,'text',NULL,'id','date')")
            c.execute("INSERT INTO local_history VALUES('event','id','draft_created','date',4)")
            c.execute(
                "INSERT INTO youtube_selection VALUES(1,'video','chat','title','account','date')"
            )
            c.execute("INSERT INTO youtube_usage VALUES('date','videos.list',1)")
        with Database(old) as migrated:
            migrated.initialize()
            check(migrated.check()["schema_version"] == 4, "schema 3 to 4")
            for table in (
                "username_profile",
                "drafts",
                "editor",
                "local_history",
                "youtube_selection",
                "youtube_usage",
            ):
                check(
                    migrated.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1,
                    "retained " + table,
                )
    print(f"PASS: {count} executed safety checks; all API writes MOCKED, no real posting.")


if __name__ == "__main__":
    main()
