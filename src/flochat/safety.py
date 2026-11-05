"""Per-action safety shared by terminal/native clients; no saved approvals or retries."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import threading
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import uuid4

import requests

from flochat.comments import SubmissionRequest, normalize_text, validate_comment
from flochat.errors import FloChatError
from flochat.youtube import (
    API_ROOT,
    HTTP_TIMEOUT,
    WRITE_SCOPES,
    YouTubeError,
    _api_error,
    _quiet_credentials,
)


class SafetyBlocked(FloChatError):
    def __init__(self, decision: str, detail: str = "", remaining: float = 0) -> None:
        self.decision = decision
        self.remaining = max(0, remaining)
        super().__init__(f"{decision}: {detail}")


@dataclass(frozen=True)
class _Approval:
    id: str
    text: str
    account: str
    chat: str
    video: str
    title: str
    account_title: str
    selection: str
    editor: str
    grant: str
    expires: float
    digest: str
    draft: str | None
    wall_expires: float


@contextmanager
def _exclusive(database):
    path = str(database.path) + ".submission.lock"
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise SafetyBlocked(
            "BLOCKED", "Cannot open the safety lock; check permissions and file type."
        ) from None
    file = os.fdopen(fd, "r+b")
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(file.fileno()).st_size == 0:
                    file.write(b"0")
                    file.flush()
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise SafetyBlocked(
                "SUBMISSION_IN_PROGRESS", "Another process holds the submission lock."
            ) from None
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        file.close()


class SafetyEngine:
    """One explicitly controlled session; bound approval exists only in memory for 120 seconds."""

    def __init__(self, database, youtube) -> None:
        self.database = database
        self.youtube = youtube
        self.state = "IDLE"
        self.pending = None
        self.confirmed = None
        self.stopping = False
        self.owner = os.getpid()
        self._transition = threading.RLock()
        self.transport_started = False

    def _event(self, c, event, decision, approval=None, attempt=None):
        c.execute(
            "INSERT INTO safety_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                str(uuid4()),
                time.time(),
                event,
                decision,
                approval.account if approval else None,
                approval.chat if approval else None,
                approval.draft if approval else None,
                len(approval.text) if approval else 0,
                attempt,
            ),
        )

    def control(self, action: str) -> dict:
        with self._transition:
            return self._control(action)

    def _control(self, action: str) -> dict:
        if action == "status":
            with self.database.transaction() as c:
                remaining = self._remaining(c, time.time(), time.monotonic())
                attempts = [
                    dict(r)
                    for r in c.execute(
                        "SELECT * FROM safety_attempts ORDER BY started DESC LIMIT 20"
                    )
                ]
            return {
                "session": self.state,
                "stop_requested": self.stopping,
                "approval_pending": self.pending is not None,
                "attempts": attempts,
                "cooldown_seconds": self.youtube.config.cooldown_seconds,
                "cooldown_remaining": remaining,
            }
        if action == "stop":
            with self._transition:
                self.pending = self.confirmed = None
                self.stopping = True
                if self.state != "SUBMITTING":
                    self.state = "STOPPED"
                return {
                    "session": self.state,
                    "message": "Stopped new actions; an in-flight request cannot be recalled.",
                }
        if self.state == "SUBMITTING":
            raise SafetyBlocked("SUBMISSION_IN_PROGRESS")
        if action == "start" and self.state in ("IDLE", "STOPPED", "ERROR", "OUTCOME_UNKNOWN"):
            self.pending = self.confirmed = None
            self.stopping = False
            self.state = "READY"
        elif action == "pause" and self.state in ("READY", "AWAITING_APPROVAL"):
            self.pending = self.confirmed = None
            self.state = "PAUSED"
        elif action == "resume" and self.state == "PAUSED":
            self.state = "READY"
        else:
            raise SafetyBlocked("BLOCKED", "Invalid session transition.")
        return {"session": self.state, "message": "No submission triggered."}

    def _snapshots(self, c):
        editor = c.execute("SELECT * FROM editor WHERE id=1").fetchone()
        selection = c.execute("SELECT * FROM youtube_selection WHERE id=1").fetchone()
        return (dict(editor) if editor else {}, dict(selection) if selection else {})

    def _context(self):
        try:
            return self._verified_context()
        except YouTubeError as exc:
            if exc.code.startswith("authorization_") or exc.code == "credentials_invalid":
                decision = "AUTHORIZATION_REQUIRED"
            elif exc.code == "account_missing":
                decision = "NO_ACCOUNT"
            elif exc.code in ("not_found", "chat_unavailable", "stream_ended"):
                decision = "CHAT_UNAVAILABLE"
            else:
                decision = "API_UNAVAILABLE"
            raise SafetyBlocked(decision, str(exc)) from None

    def _verified_context(self):
        with self.database.transaction() as c:
            editor, selected = self._snapshots(c)
        limit = self.youtube.config.max_comment_length
        if type(limit) is not int or not 1 <= limit <= 1500:
            raise SafetyBlocked("BLOCKED", "Invalid local length policy.")
        text = editor.get("text", "")
        if (
            not isinstance(text, str)
            or normalize_text(text) != text
            or validate_comment(text, max_length=self.youtube.config.max_comment_length)
        ):
            raise SafetyBlocked(
                "INVALID_COMMENT", "Check local validation, normalization and configured length."
            )
        if not selected:
            raise SafetyBlocked("NO_SELECTED_CHAT")
        _, credentials = self.youtube._credentials()
        if not credentials.has_scopes(WRITE_SCOPES):
            raise SafetyBlocked(
                "AUTHORIZATION_REQUIRED",
                "Reconnect explicitly with youtube connect --local-browser --allow-posting.",
            )
        account = self.youtube._account(credentials)["accounts"]
        if len(account) != 1 or account[0]["channel_id"] != selected["account_channel_id"]:
            raise SafetyBlocked("NO_ACCOUNT", "Selected account changed; select the chat again.")
        video = self.youtube._video(selected["video_id"], credentials)
        if (
            video["availability"] != "live_chat_available"
            or video["live_chat_id"] != selected["live_chat_id"]
        ):
            raise SafetyBlocked("CHAT_UNAVAILABLE")

        def exact(v):
            return json.dumps(v, sort_keys=True, ensure_ascii=True)

        canonical = " ".join(unicodedata.normalize("NFC", text).split())
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        grant = hashlib.sha256(
            (credentials.refresh_token or credentials.token).encode()
        ).hexdigest()
        return _Approval(
            secrets.token_hex(12),
            text,
            account[0]["channel_id"],
            video["live_chat_id"],
            video["video_id"],
            video["title"],
            account[0]["title"],
            exact(selected),
            exact(editor),
            grant,
            time.monotonic() + 120,
            digest,
            editor.get("draft_id"),
            time.time() + 120,
        ), credentials

    def _policy(self, c, approval):
        interval = self.youtube.config.cooldown_seconds
        if type(interval) is not int or not 5 <= interval <= 600:
            raise SafetyBlocked(
                "BLOCKED", "Invalid cooldown configuration; protection cannot be disabled."
            )
        now, mono = time.time(), time.monotonic()
        high = c.execute("SELECT last_seen FROM safety_clock WHERE id=1").fetchone()
        if high and now < high[0]:
            raise SafetyBlocked(
                "BLOCKED", "Clock rollback detected; wait for trusted time to catch up."
            )
        c.execute(
            "INSERT INTO safety_clock VALUES (1,?) ON CONFLICT(id) DO "
            "UPDATE SET last_seen=excluded.last_seen",
            (now,),
        )
        if c.execute(
            "SELECT 1 FROM safety_attempts WHERE state IN "
            "('IN_PROGRESS','OUTCOME_UNKNOWN') AND resolved=0"
        ).fetchone():
            raise SafetyBlocked(
                "OUTCOME_UNKNOWN", "Review/resolve the unresolved attempt before another action."
            )
        if c.execute(
            "SELECT 1 FROM safety_attempts WHERE account_id=? AND chat_id=? AND digest=?",
            (approval.account, approval.chat, approval.digest),
        ).fetchone():
            raise SafetyBlocked(
                "DUPLICATE",
                "This account/chat/content already has an attempt. No duplicate override.",
            )
        for legacy in c.execute(
            "SELECT comment_text FROM comment_history WHERE live_chat_id=? "
            "AND state IN ('approved','submitted','confirmed','failed')",
            (approval.chat,),
        ):
            canonical = " ".join(unicodedata.normalize("NFC", legacy[0]).split())
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() == approval.digest:
                raise SafetyBlocked(
                    "DUPLICATE",
                    "Legacy attempt exists; its account is unknown, so block conservatively.",
                )
        remaining = self._remaining(c, now, mono)
        if remaining > 0:
            raise SafetyBlocked(
                "COOLDOWN_ACTIVE", "Wait before another deliberate action.", remaining
            )

    def _remaining(self, c, now, mono):
        last = c.execute(
            "SELECT started,monotonic_started FROM safety_attempts ORDER BY started DESC LIMIT 1"
        ).fetchone()
        if last:
            interval = self.youtube.config.cooldown_seconds
            elapsed = mono - last[1]
            remaining = max(
                last[0] + interval - now, interval - elapsed if elapsed >= 0 else interval
            )
            if remaining > 0:
                return remaining
        return 0

    def _reconcile(self, c):
        for row in c.execute("SELECT * FROM safety_attempts WHERE state='IN_PROGRESS'").fetchall():
            c.execute(
                "INSERT INTO safety_events VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    time.time(),
                    "outcome_unknown",
                    "OUTCOME_UNKNOWN",
                    row["account_id"],
                    row["chat_id"],
                    row["draft_id"],
                    row["character_count"],
                    row["id"],
                ),
            )
        c.execute(
            "UPDATE safety_attempts SET "
            "state='OUTCOME_UNKNOWN',category='interrupted' WHERE "
            "state='IN_PROGRESS'"
        )

    def prepare(self) -> dict:
        if (
            self.state not in ("READY", "AWAITING_APPROVAL")
            or self.stopping
            or self.owner != os.getpid()
        ):
            raise SafetyBlocked("SESSION_PAUSED" if self.state == "PAUSED" else "SESSION_STOPPED")
        self.pending = self.confirmed = None
        approval = None
        try:
            with _exclusive(self.database):
                with self.database.transaction() as c:
                    self._reconcile(c)  # Commit orphan classification even if policy later blocks.
                approval, _ = self._context()
                with self.database.transaction() as c:
                    self._policy(c, approval)
                    self._event(c, "approval_requested", "REQUIRES_APPROVAL", approval)
            with self._transition:
                if self.stopping or self.state not in ("READY", "AWAITING_APPROVAL"):
                    raise SafetyBlocked("SESSION_STOPPED", "Session changed while verifying.")
                self.pending = approval
                self.state = "AWAITING_APPROVAL"
            return self._view(approval)
        except BaseException as exc:
            if self.state not in ("STOPPED", "PAUSED", "SUBMITTING", "OUTCOME_UNKNOWN"):
                self.state = "ERROR"
            with self.database.transaction() as c:
                self._event(c, "blocked", getattr(exc, "decision", "API_UNAVAILABLE"), approval)
            raise

    @staticmethod
    def _view(approval):
        return {
            "decision": "REQUIRES_APPROVAL",
            "approval_id": approval.id,
            "expires_in_seconds": max(
                0, min(approval.expires - time.monotonic(), approval.wall_expires - time.time())
            ),
            "account": approval.account,
            "account_title": approval.account_title,
            "live_chat_id": approval.chat,
            "video_id": approval.video,
            "title": approval.title,
            "text": approval.text,
            "escaped_text": json.dumps(approval.text, ensure_ascii=True),
            "character_count": len(approval.text),
            "utf8_bytes": len(approval.text.encode("utf-8")),
            "message": "Confirming attempts ONE real YouTube submission. Approval "
            "expires in 120 seconds.",
        }

    def confirm(self) -> tuple[SubmissionRequest, str]:
        approval = self.pending
        if not sys.stdin.isatty() or not sys.stdout.isatty() or approval is None:
            self.pending = self.confirmed = None
            raise SafetyBlocked("REQUIRES_APPROVAL", "Interactive terminal approval is mandatory.")
        print(json.dumps(self._view(approval), ensure_ascii=True, indent=2))
        print("Exact comment text begins:\n" + approval.text + "\nExact comment text ends.")
        phrase = input(
            f"Type SEND {approval.id} to attempt this one submission; anything else cancels: "
        )

        return self._approve(approval, phrase)

    def confirm_panel(self, approval_id, phrase):
        """Authenticated owner routes a displayed challenge, NOT a native approval flag.

        Client ownership/liveness is checked by the runtime; all approval semantics,
        final verification and consumption remain here exactly as in terminal mode.
        """
        approval = self.pending
        if approval is None or approval_id != approval.id:
            raise SafetyBlocked("REQUIRES_APPROVAL", "Missing/stale core-issued review.")
        return self._approve(approval, phrase)

    @staticmethod
    def _expired(approval):
        now = time.time()
        return (
            time.monotonic() > approval.expires
            or now > approval.wall_expires
            or now < approval.wall_expires - 120
        )

    def _approve(self, approval, phrase):
        if (
            self.state != "AWAITING_APPROVAL"
            or approval is None
            or approval is not self.pending
            or self.stopping
            or phrase != "SEND " + approval.id
            or self._expired(approval)
        ):
            self.pending = self.confirmed = None
            if self.state == "AWAITING_APPROVAL":
                self.state = "PAUSED"
            with self.database.transaction() as c:
                self._event(c, "blocked", "REQUIRES_APPROVAL", approval)
            raise SafetyBlocked(
                "REQUIRES_APPROVAL", "Cancelled, expired, or incorrect confirmation."
            )
        self.confirmed = approval.id
        with self.database.transaction() as c:
            self._event(c, "approved", "APPROVED", approval)
        return SubmissionRequest(approval.text, approval.chat, approved=True), approval.id

    def execute(self, request: SubmissionRequest, approval_id: str | None) -> dict:
        with self._transition:
            approval = self.pending
            self.pending = None  # One use, including final-check failures.
            confirmed, self.confirmed = self.confirmed, None
            if (
                self.state != "AWAITING_APPROVAL"
                or self.stopping
                or self.owner != os.getpid()
                or approval is None
                or approval_id != approval.id
                or confirmed != approval.id
                or request.approved is not True
                or self._expired(approval)
                or request.comment_text != approval.text
                or request.live_chat_id != approval.chat
            ):
                with self.database.transaction() as c:
                    self._event(c, "blocked", "REQUIRES_APPROVAL", approval)
                raise SafetyBlocked(
                    "REQUIRES_APPROVAL", "Missing, consumed, stale or mismatched approval."
                )
        attempt = str(uuid4())
        try:
            with _exclusive(self.database):
                with self.database.transaction() as c:
                    self._reconcile(c)
                current, credentials = self._context()
                if (
                    current.text,
                    current.chat,
                    current.account,
                    current.grant,
                    current.editor,
                    current.selection,
                ) != (
                    approval.text,
                    approval.chat,
                    approval.account,
                    approval.grant,
                    approval.editor,
                    approval.selection,
                ):
                    raise SafetyBlocked(
                        "REQUIRES_APPROVAL", "Text, target, grant or account changed."
                    )
                if self._expired(approval) or self.stopping or self.state != "AWAITING_APPROVAL":
                    raise SafetyBlocked("REQUIRES_APPROVAL")
                with self.database.transaction() as c:
                    editor, selected = self._snapshots(c)
                    if (
                        json.dumps(editor, sort_keys=True, ensure_ascii=True) != approval.editor
                        or json.dumps(selected, sort_keys=True, ensure_ascii=True)
                        != approval.selection
                    ):
                        raise SafetyBlocked(
                            "REQUIRES_APPROVAL", "Local state changed during verification."
                        )
                    self._policy(c, approval)
                    c.execute(
                        "INSERT INTO safety_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                        (
                            attempt,
                            approval.id,
                            approval.account,
                            approval.chat,
                            approval.digest,
                            approval.draft,
                            len(approval.text),
                            time.time(),
                            time.monotonic(),
                            "IN_PROGRESS",
                            "reserved",
                            None,
                        ),
                    )
                    self._event(c, "submission_attempted", "APPROVED", approval, attempt)
                self.state = "SUBMITTING"
                # Usage must commit BEFORE transport; failure leaves an unresolved reservation.
                self.youtube._usage("liveChatMessages.insert")
                with self._transition:
                    cancelled = self.stopping
                    if not cancelled:
                        self.transport_started = True  # Atomic start boundary vs stop().
                if cancelled:
                    with self.database.transaction() as c:
                        c.execute(
                            "UPDATE safety_attempts SET state='REJECTED', "
                            "category='cancelled_before_transmission' WHERE id=?",
                            (attempt,),
                        )
                        self._event(c, "rejected", "BLOCKED", approval, attempt)
                    self.state = "STOPPED"
                    return {
                        "decision": "BLOCKED",
                        "accepted": False,
                        "attempt_id": attempt,
                        "category": "cancelled_before_transmission",
                    }
                state, category, youtube_id = "OUTCOME_UNKNOWN", "interrupted", None
                try:
                    with requests.Session() as session, _quiet_credentials():
                        session.trust_env = False
                        response = session.post(
                            API_ROOT + "liveChat/messages",
                            params={"part": "snippet"},
                            headers={"Authorization": "Bearer " + credentials.token},
                            json={
                                "snippet": {
                                    "liveChatId": approval.chat,
                                    "type": "textMessageEvent",
                                    "textMessageDetails": {"messageText": approval.text},
                                }
                            },
                            timeout=HTTP_TIMEOUT,
                            allow_redirects=False,
                        )
                    if 200 <= response.status_code < 300:
                        data = response.json()
                        snippet = data.get("snippet", {}) if isinstance(data, dict) else {}
                        if (
                            isinstance(data, dict)
                            and isinstance(data.get("id"), str)
                            and data["id"]
                            and snippet.get("liveChatId") == approval.chat
                            and snippet.get("type") == "textMessageEvent"
                            and snippet.get("textMessageDetails", {}).get("messageText")
                            == approval.text
                        ):
                            state, category, youtube_id = (
                                "ACCEPTED",
                                "confirmed_accepted",
                                data["id"],
                            )
                        else:
                            category = "invalid_response"
                    elif response.status_code in (400, 401, 403, 404, 429):
                        state, category = "REJECTED", _api_error(response).code
                    else:
                        category = "server_or_redirect"
                except requests.ConnectTimeout:
                    state, category = "REJECTED", "connect_timeout_before_transmission"
                except (
                    requests.RequestException,
                    ValueError,
                    TypeError,
                    AttributeError,
                    RecursionError,
                ):
                    category = "transport_or_invalid_response"
                finally:
                    with self.database.transaction() as c:
                        c.execute(
                            "UPDATE safety_attempts SET state=?,category=?,youtube_id=? WHERE id=?",
                            (state, category, youtube_id, attempt),
                        )
                        self._event(
                            c,
                            "confirmed_accepted"
                            if state == "ACCEPTED"
                            else "rejected"
                            if state == "REJECTED"
                            else "outcome_unknown",
                            state,
                            approval,
                            attempt,
                        )
                    self.state = (
                        "OUTCOME_UNKNOWN"
                        if state == "OUTCOME_UNKNOWN"
                        else "STOPPED"
                        if self.stopping
                        else "READY"
                        if state == "ACCEPTED"
                        else "ERROR"
                    )
                return {
                    "decision": state,
                    "attempt_id": attempt,
                    "category": category,
                    "youtube_id": youtube_id,
                    "accepted": state == "ACCEPTED",
                    "message": "YouTube confirmed acceptance."
                    if state == "ACCEPTED"
                    else "Do not retry automatically. Inspect history/chat; unknown "
                    "outcomes require explicit review.",
                }
        except BaseException:
            if self.state != "OUTCOME_UNKNOWN":
                self.state = "ERROR"
            with self.database.transaction() as c:
                self._event(c, "blocked", "BLOCKED", approval, attempt)
            raise

    def resolve(self, attempt_id: str, phrase: str) -> dict:
        if phrase != "REVIEWED " + attempt_id:
            raise SafetyBlocked(
                "BLOCKED", "Explicit chat/outcome inspection acknowledgment required."
            )
        with _exclusive(self.database), self.database.transaction() as c:
            self._reconcile(c)
            row = c.execute(
                "SELECT state FROM safety_attempts WHERE id=?", (attempt_id,)
            ).fetchone()
            if row is None or row[0] != "OUTCOME_UNKNOWN":
                raise SafetyBlocked("BLOCKED", "No unknown outcome found.")
            c.execute("UPDATE safety_attempts SET resolved=1 WHERE id=?", (attempt_id,))
            self._event(c, "uncertainty_reviewed", "OUTCOME_UNKNOWN", attempt=attempt_id)
        self.pending = self.confirmed = None
        self.state = "STOPPED"
        return {
            "message": "Uncertainty acknowledged, NOT marked accepted/rejected. "
            "Same-content duplicate protection remains. Start explicitly "
            "for another action."
        }


def console(database, youtube) -> int:
    """Terminal UI: no --yes, no saved approvals, no bulk action or retry loop."""
    from flochat.comments import submit

    engine = SafetyEngine(database, youtube)
    print(
        "Safety session IDLE. Commands: start, status, pause, resume,"
        " stop, submit, history, resolve ID, quit."
    )
    try:
        while True:
            try:
                command = input("safety> ").strip()
                if command == "quit":
                    break
                if command in ("start", "status", "pause", "resume", "stop"):
                    print(json.dumps(engine.control(command), indent=2))
                elif command == "submit":
                    engine.prepare()
                    request, approval = engine.confirm()
                    print(
                        json.dumps(submit(request, engine=engine, approval_id=approval), indent=2)
                    )
                elif command == "history":
                    with database.transaction() as c:
                        print(
                            json.dumps(
                                [
                                    dict(r)
                                    for r in c.execute(
                                        "SELECT * FROM safety_events ORDER BY created DESC LIMIT 50"
                                    )
                                ],
                                indent=2,
                            )
                        )
                elif command.startswith("resolve "):
                    attempt_id = command[8:].strip()
                    print(
                        "Inspect the real chat/outcome yourself. This does NOT mark a"
                        " post successful or allow the same comment again."
                    )
                    phrase = input(
                        f"Type REVIEWED {attempt_id} only after inspecting the outcome: "
                    )
                    print(json.dumps(engine.resolve(attempt_id, phrase), indent=2))
                else:
                    print(
                        "Unknown action. Use "
                        "start/status/pause/resume/stop/submit/history/resolve "
                        "ID/quit."
                    )
            except SafetyBlocked as exc:
                print(
                    json.dumps(
                        {
                            "decision": exc.decision,
                            "detail": str(exc),
                            "cooldown_remaining": exc.remaining,
                        }
                    )
                )
            except (YouTubeError, FloChatError) as exc:
                engine.control("stop")
                print(json.dumps({"decision": "API_UNAVAILABLE", "error": str(exc)}))
            except EOFError:
                raise
            except Exception:
                decision = (
                    "OUTCOME_UNKNOWN" if engine.state == "OUTCOME_UNKNOWN" else "API_UNAVAILABLE"
                )
                engine.control("stop")
                print(
                    json.dumps(
                        {
                            "decision": decision,
                            "error": "Unexpected local failure. Inspect attempt history and chat "
                            "before another action; no automatic retry.",
                        }
                    )
                )
    except (EOFError, KeyboardInterrupt):
        print(
            "Session ended. No approval retained. Inspect any unresolved attempt before retrying."
        )
    finally:
        engine.control("stop")
    return 0
