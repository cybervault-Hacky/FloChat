"""Phase 04 mocked integration checks. No real OAuth, keyring mutation or API call.

Run after installation: .venv/bin/python scripts/verify_youtube.py
The mock transport rejects every URL/method outside the three read endpoints and
explicit revocation. All fixtures/data are synthetic, temporary and local.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from flochat import youtube as yt
from flochat.cli import run
from flochat.comments import SubmissionRequest, submit
from flochat.config import AppConfig
from flochat.database import LOCAL_SCHEMA_SQL, SCHEMA_SQL, SCHEMA_VERSION, Database
from flochat.errors import ApprovalRequiredError, FloChatError, NotSupportedYetError, StorageError
from flochat.platform import detect


def main() -> None:
    count = 0

    def check(condition, message):
        nonlocal count
        if not condition:
            raise AssertionError(message)
        count += 1

    def error(code, operation):
        try:
            operation()
        except yt.YouTubeError as exc:
            check(exc.code == code, f"expected {code}, got {exc.code}")
            check("fixture-secret" not in str(exc), "error redaction")
        else:
            raise AssertionError(f"Expected {code}")

    check(yt.API_ROOT == "https://youtube.googleapis.com/youtube/v3/", "official discovery root")
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    credentials = Credentials(
        token="fixture-secret-access",
        refresh_token="fixture-secret-refresh",
        token_uri=yt.TOKEN_URI,
        client_id="fixture.apps.googleusercontent.com",
        client_secret="fixture-secret-client",
        scopes=yt.SCOPES,
        expiry=expiry,
    )
    # Identity simulates Secret Service; no real OS keyring methods are used.
    backend_type = type("Keyring", (), {"__module__": "keyring.backends.SecretService"})
    backend = backend_type()
    backend.raw = None
    backend.get_password = lambda *args: backend.raw

    def set_password(*args):
        backend.raw = args[-1]

    def delete_password(*args):
        backend.raw = None

    backend.set_password = set_password
    backend.delete_password = delete_password

    def response(data, status=200):
        r = requests.Response()
        r.status_code = status
        r._content = json.dumps(data).encode()
        return r

    account = {"items": [{"id": "UCfixture", "snippet": {"title": "Fixture channel"}}]}
    live = {
        "items": [
            {
                "id": "fixtureVideo",
                "snippet": {"title": "Fixture stream"},
                "liveStreamingDetails": {
                    "actualStartTime": "2026-11-04T00:00:00Z",
                    "activeLiveChatId": "opaque-chat=fixture",
                },
            }
        ]
    }
    broadcast = {
        "items": [
            {
                "id": "fixtureVideo",
                "snippet": {"title": "Fixture stream", "liveChatId": "opaque-chat=fixture"},
                "status": {"lifeCycleStatus": "live"},
            }
        ]
    }
    queue = []
    calls = []

    def get(session, url, **kwargs):
        check(
            url in {yt.API_ROOT + name for name in ("channels", "liveBroadcasts", "videos")},
            "only official readonly endpoints",
        )
        check(kwargs["timeout"] == 20 and not kwargs["allow_redirects"], "bounded no redirects")
        check(session.trust_env is False, "no netrc/proxy credential injection")
        check(kwargs["headers"]["Authorization"].startswith("Bearer "), "authorized REST")
        calls.append((url, kwargs))
        if not queue:
            raise AssertionError("Unexpected API call")
        next_response = queue.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    with (
        tempfile.TemporaryDirectory(prefix="flochat-youtube-") as directory,
        patch("keyring.get_keyring", return_value=backend),
        patch("socket.socket", side_effect=AssertionError("real network forbidden")),
        patch("requests.Session.get", new=get),
        patch("requests.Session.post", side_effect=AssertionError("write forbidden")) as post,
    ):
        home = Path(directory)
        client = home / "client.json"
        client.write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": "fixture.apps.googleusercontent.com",
                        "client_secret": "fixture-secret-client",
                        "auth_uri": yt.AUTH_URI,
                        "token_uri": yt.TOKEN_URI,
                    }
                }
            )
        )
        config = AppConfig(data_dir=home, client_secret=client)
        with Database(config.resolved_db_path) as db:
            db.initialize()
            integration = yt.YouTubeIntegration(db, config, detect())
            check(
                integration.run("status")["connection_state"] == "not_connected",
                "disconnected status",
            )
            error("authorization_required", lambda: integration.run("account"))
            for path in (None, home / "missing.json"):
                error("configuration", lambda p=path: yt._client_configuration(p))
            bad = home / "invalid.json"
            for data in ([], {"web": {}}, {"installed": {"auth_uri": "http://evil.invalid"}}):
                bad.write_text(json.dumps(data))
                error("configuration", lambda: yt._client_configuration(bad))
            check(
                yt._client_configuration(client)["installed"]["token_uri"] == yt.TOKEN_URI,
                "validate config",
            )
            check(
                yt.SCOPES == ("https://www.googleapis.com/auth/youtube.readonly",),
                "least privilege",
            )
            for raw in ("{", "[]", json.dumps({"token_uri": "https://evil.invalid"})):
                backend.raw = raw
                error("credentials_invalid", lambda: yt.CredentialStore().load())
            backend.raw = None
            store = yt.CredentialStore()
            store.save(credentials)
            check(store.load().token == credentials.token, "secure serialization round trip")
            check(
                integration.run("status")["connection_state"] == "stored_unverified",
                "no fake live status",
            )
            queue.append(response(account))
            check(
                integration.run("account")["connection_state"] == "connected", "mock account lookup"
            )
            queue.append(response({"items": []}))
            error("account_missing", lambda: integration.run("account"))
            queue.append(response({"items": [{"id": "UCfixture", "snippet": None}]}))
            error("invalid_response", lambda: integration.run("account"))
            queue.append(response(broadcast))
            streams = integration.run("streams")
            check(
                streams["streams"][0]["availability"] == "live_chat_available",
                "mock eligible broadcast",
            )
            check(integration.run("status")["selection"] is None, "never auto select")
            for lifecycle in ("complete", "ready"):
                item = json.loads(json.dumps(broadcast))
                item["items"][0]["status"]["lifeCycleStatus"] = lifecycle
                queue.append(response(item))
                check(
                    integration.run("streams")["streams"][0]["availability"]
                    == ("stream_ended" if lifecycle == "complete" else "live_chat_unavailable"),
                    "lifecycle handling",
                )
            queue.append(response({"items": [], "nextPageToken": "next_fixture"}))
            check(
                integration.run("streams")["next_page_token"] == "next_fixture",
                "explicit pagination",
            )
            queue.append(response({"items": []}))
            integration.run("streams", page_token="next_fixture")
            check(calls[-1][1]["params"]["pageToken"] == "next_fixture", "page token passed")
            for payload in ([], {}, {"items": None}, {"items": [None]}, {"items": [{}]}):
                queue.append(response(payload))
                error("invalid_response", lambda: integration.run("streams"))
            queue.append(response(live))
            check(
                integration.run("inspect", video_id="fixtureVideo")["live_chat_id"]
                == "opaque-chat=fixture",
                "opaque chat id",
            )
            queue.extend([response(live), response(account)])
            check(
                integration.run("select", video_id="fixtureVideo")["selected"], "explicit selection"
            )
            check(
                integration.run("status")["selection"]["video_id"] == "fixtureVideo",
                "selection persisted",
            )
            for details, code in (
                ({}, "chat_unavailable"),
                ({"actualEndTime": "2026-11-04T01:00:00Z"}, "stream_ended"),
            ):
                item = json.loads(json.dumps(live))
                item["items"][0]["liveStreamingDetails"] = details
                queue.append(response(item))
                error(code, lambda: integration.run("select", video_id="fixtureVideo"))
                check(
                    integration.run("status")["selection"] is None, "failed selection clears target"
                )
            queue.append(response({"items": []}))
            error("not_found", lambda: integration.run("inspect", video_id="fixtureVideo"))
            queue.append(response({"items": [{"id": "other", "snippet": {"title": "wrong"}}]}))
            error("invalid_response", lambda: integration.run("inspect", video_id="fixtureVideo"))
            cases = [
                (401, None, "authorization_invalid"),
                (403, None, "permission_denied"),
                (403, "quotaExceeded", "quota_exceeded"),
                (403, "userRateLimitExceeded", "rate_limited"),
                (429, None, "rate_limited"),
                (404, None, "not_found"),
                (400, None, "invalid_request"),
                (503, None, "server"),
                (403, "liveChatEnded", "stream_ended"),
                (403, "liveChatDisabled", "chat_unavailable"),
            ]
            for status, reason, code in cases:
                body = {
                    "error": {
                        "message": "fixture-secret-server-body",
                        "errors": [{"reason": reason}],
                    }
                }
                queue.append(response(body, status))
                error(code, lambda: integration.run("account"))
            for failure, code in (
                (requests.Timeout("fixture-secret"), "timeout"),
                (requests.ConnectionError("fixture-secret"), "network"),
            ):
                queue.append(failure)
                error(code, lambda: integration.run("account"))
            malformed = response({})
            malformed._content = b"not json fixture-secret"
            queue.append(malformed)
            error("invalid_response", lambda: integration.run("account"))
            usage = integration.run("status")["usage"]
            check(sum(r["requests"] for r in usage) == len(calls), "logical API attempt counts")
            check(
                all("fixture-secret" not in json.dumps(row) for row in usage), "no secrets in usage"
            )
            # Refresh success and invalid_grant are mocked, never live calls.
            expired = Credentials(
                token="fixture-secret-expired",
                refresh_token="fixture-secret-refresh",
                token_uri=yt.TOKEN_URI,
                client_id="fixture.apps.googleusercontent.com",
                client_secret="fixture-secret-client",
                scopes=yt.SCOPES,
                expiry=expiry - timedelta(hours=2),
            )
            store.save(expired)
            check(
                integration.run("status")["connection_state"] == "authorization_expired",
                "expiry status",
            )

            def refresh(self, transport):
                self.token = "fixture-secret-renewed"
                self.expiry = expiry

            with patch.object(Credentials, "refresh", new=refresh):
                queue.append(response(account))
                integration.run("account")
                check(store.load().token == "fixture-secret-renewed", "refreshed token saved")
            store.save(expired)
            with patch.object(
                Credentials, "refresh", side_effect=RefreshError("fixture-secret invalid_grant")
            ):
                error("authorization_invalid", lambda: integration.run("account"))
            # OAuth does not run over mocks of user passwords or a deprecated OOB flow.
            store.delete()
            for integration_case, options in (
                (integration, {}),
                (
                    yt.YouTubeIntegration(
                        db,
                        config,
                        SimpleNamespace(supported=True, key=SimpleNamespace(value="android")),
                    ),
                    {"local_browser": True},
                ),
            ):
                try:
                    integration_case.run("connect", **options)
                except FloChatError:
                    check(True, "unsupported callback refused")
                else:
                    raise AssertionError("unsupported callback accepted")
            with patch.object(backend, "get_password", side_effect=RuntimeError("fixture-secret")):
                error("secure_storage", lambda: integration.run("connect", local_browser=True))
            with patch.object(yt.InstalledAppFlow, "fetch_token", return_value={}) as fetch:
                flow = object.__new__(yt._TimedFlow)
                flow.fetch_token(code="fixture-secret-code")
                check(
                    fetch.call_args.kwargs["timeout"] == 20
                    and fetch.call_args.kwargs["allow_redirects"] is False,
                    "bounded token exchange",
                )
            fake_flow = Mock()
            fake_flow.run_local_server.return_value = credentials
            with patch.object(
                yt._TimedFlow, "from_client_config", return_value=fake_flow
            ) as factory:
                queue.append(response(account))
                result = integration.run("connect", local_browser=True)
                check(result["connection_state"] == "connected", "mock OAuth and account")
                check(factory.call_args.kwargs["autogenerate_code_verifier"], "PKCE enabled")
                callback = fake_flow.run_local_server.call_args.kwargs
                check(
                    callback["host"] == "127.0.0.1"
                    and callback["bind_addr"] == "127.0.0.1"
                    and callback["port"] == 0,
                    "loopback only, ephemeral port",
                )
                check(
                    callback["timeout_seconds"] == 180
                    and callback["authorization_prompt_message"] is None,
                    "callback timeout and no auth URL/code in output",
                )
                check(integration.run("status")["selection"] is None, "reconnect never selects")
            for exception, code in (
                (KeyboardInterrupt(), "cancelled"),
                (TimeoutError(), "cancelled"),
                (RuntimeError("fixture-secret"), "cancelled"),
            ):
                store.delete()
                fake_flow.run_local_server.side_effect = exception
                with patch.object(yt._TimedFlow, "from_client_config", return_value=fake_flow):
                    error(code, lambda: integration.run("connect", local_browser=True))
                    check(store.load() is None, "failed auth not persisted")
            for oauth_reason, expected in (
                ("access_denied", "permission_denied"),
                ("invalid_client", "configuration"),
                ("mismatching_state", "authorization_invalid"),
            ):
                store.delete()
                denied = RuntimeError("fixture-secret")
                denied.error = oauth_reason
                fake_flow.run_local_server.side_effect = denied
                with patch.object(yt._TimedFlow, "from_client_config", return_value=fake_flow):
                    error(expected, lambda: integration.run("connect", local_browser=True))
                    check(store.load() is None, "denial/state error not persisted")
            fake_flow.run_local_server.side_effect = None
            fake_flow.run_local_server.return_value = credentials
            with (
                patch.object(yt._TimedFlow, "from_client_config", return_value=fake_flow),
                patch.object(backend, "set_password", side_effect=RuntimeError("fixture-secret")),
            ):
                queue.append(response(account))
                error("secure_storage", lambda: integration.run("connect", local_browser=True))
            check(store.load() is None, "failed credential write does not claim connection")
            # Limit token refresh to one transport attempt even if the Google library retries.
            store.save(expired)

            def retrying_refresh(self, transport):
                transport(url=yt.TOKEN_URI, method="POST")
                transport(url=yt.TOKEN_URI, method="POST")

            with (
                patch.object(Credentials, "refresh", new=retrying_refresh),
                patch("flochat.youtube.Request") as transport_factory,
            ):
                error("network", lambda: integration.run("account"))
                check(
                    transport_factory.return_value.call_count == 1,
                    "no automatic refresh network retries",
                )
            no_refresh = Credentials(
                token="expired", expiry=expiry - timedelta(hours=2), scopes=yt.SCOPES
            )
            error("authorization_expired", lambda: integration._refresh(no_refresh, store))
            store.save(credentials)
            try:
                integration.run("disconnect")
            except FloChatError:
                check(store.load() is not None, "disconnect confirmation")
            else:
                raise AssertionError("disconnect needs confirmation")
            result = integration.run("disconnect", yes=True)
            check(
                result["local_credentials_removed"] and not result["google_revocation_confirmed"],
                "local != revoked",
            )
            check(store.load() is None, "credential cleanup")
            store.save(credentials)
            post.side_effect = requests.Timeout("fixture-secret")
            result = integration.run("disconnect", yes=True, revoke=True)
            check(
                not result["operation_ok"] and store.load() is None,
                "revocation failure still cleans credentials",
            )
            store.save(credentials)
            post.side_effect = None
            post.return_value = response({}, 200)
            check(
                integration.run("disconnect", yes=True, revoke=True)["google_revocation_confirmed"],
                "mock revoke confirmation",
            )
            check(post.call_args.args[0] == yt.REVOKE_URI, "only OAuth revocation POST")
            post.reset_mock()
            post.side_effect = AssertionError("write forbidden")
            with patch("keyring.get_keyring", return_value=Mock()):
                error("secure_storage", yt.CredentialStore)
                check(not integration.run("status")["operation_ok"], "unsupported backend status")
            store.save(credentials)
            with patch.object(backend, "set_password", side_effect=RuntimeError("fixture-secret")):
                error("secure_storage", lambda: store.save(credentials))
            with patch.object(
                backend, "delete_password", side_effect=RuntimeError("fixture-secret")
            ):
                error("secure_storage", store.delete)
            legacy_config = config.model_copy(update={"token_file": home / "plaintext.json"})
            legacy_integration = yt.YouTubeIntegration(db, legacy_config, detect())
            error("credentials_invalid", lambda: legacy_integration.run("account"))
            # Safety is unchanged; approved calls remain blocked for Phase 05.
            for request, expected in (
                (SubmissionRequest("ok", "chat"), ApprovalRequiredError),
                (SubmissionRequest("ok", "chat", approved=True), NotSupportedYetError),
                (SubmissionRequest("", "chat", approved=True), FloChatError),
                (SubmissionRequest("ok", "", approved=True), FloChatError),
            ):
                try:
                    submit(request)
                except expected:
                    check(True, "submission refused")
                else:
                    raise AssertionError("submission unexpectedly accepted")
            check(post.call_count == 0, "no API write during operational/safety tests")
            # CLI returns sanitized errors and renders counts/selection without tokens.
            with patch.dict(os.environ, {"FLOCHAT_HOME": str(home)}, clear=False):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    check(run(["--json", "youtube", "status"]) == 0, "CLI status")
                    queue.append(response({"error": {"message": "fixture-secret-server"}}, 401))
                    check(run(["--json", "youtube", "account"]) == 1, "CLI API failure")
                check(
                    "fixture-secret" not in stream.getvalue()
                    and "connection_state" in stream.getvalue(),
                    "CLI redaction and real capture",
                )
            store.delete()
            check(not queue, "no unused mocked responses")
            dump = "\n".join(db.connection.iterdump())
            check(
                "fixture-secret" not in dump and "refresh_token" not in dump,
                "no credentials in SQLite",
            )
            before_level = logging.root.manager.disable
            with yt._quiet_credentials():
                check(
                    logging.root.manager.disable == logging.CRITICAL,
                    "sensitive library logging disabled",
                )
            check(logging.root.manager.disable == before_level, "logging restored")
        # Real local schema-2 migration with profile/draft/editor/history preserved.
        old = home / "schema2.db"
        with sqlite3.connect(old) as c:
            c.executescript(SCHEMA_SQL + LOCAL_SCHEMA_SQL)
            c.execute("PRAGMA user_version=2")
            c.execute("INSERT INTO username_profile VALUES (1,'retained','2026-11-04')")
            c.execute("INSERT INTO drafts VALUES ('retained','title','text',NULL,'date','date')")
            c.execute("INSERT INTO editor VALUES (1,'text',NULL,'retained','date')")
            c.execute(
                "INSERT INTO local_history VALUES ('event','retained','draft_created','date',4)"
            )
        with Database(old) as db:
            db.initialize()
            check(db.check()["schema_version"] == SCHEMA_VERSION, "real v2 migration")
            for table in ("username_profile", "drafts", "editor", "local_history"):
                check(
                    db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1,
                    "retained " + table,
                )
        broken = home / "schema2-broken.db"
        with sqlite3.connect(broken) as c:
            c.executescript(SCHEMA_SQL + LOCAL_SCHEMA_SQL)
            c.execute("PRAGMA user_version=2")
            c.execute("CREATE TABLE youtube_selection(incompatible TEXT)")
        before = broken.read_bytes()
        with Database(broken) as db:
            try:
                db.initialize()
            except StorageError:
                check(broken.read_bytes() == before, "failed migration untouched")
            else:
                raise AssertionError("incompatible migration accepted")
    print(
        f"PASS: {count} checks. OAuth/API/keyring behavior MOCKED; "
        "local migration/CLI EXECUTED. No live service verification."
    )


if __name__ == "__main__":
    main()
