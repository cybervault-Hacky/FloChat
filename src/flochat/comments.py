"""Comment safety boundary.

Local editing, usernames, drafts, previews, and metadata-only history share one
SQLite boundary. No manager operation calls submit or contacts a service.

:func:`submit` is the only submission entry point. Bare booleans still refuse.
An active SafetyEngine must bind, display, confirm and revalidate each action.
Local manager operations never call this path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from flochat.database import Database
from flochat.errors import ApprovalRequiredError, FloChatError, NotSupportedYetError
from flochat.state import AppState, StatusReport


@dataclass(frozen=True)
class SubmissionRequest:
    """What a caller must supply to attempt a submission."""

    comment_text: str
    live_chat_id: str
    approved: bool = False


def normalize_text(text: str) -> str:
    """Trim outer whitespace and normalize line endings, preserving Unicode/formatting.

    Shared by the editor and submission boundary so preview text is not rewritten
    differently later. In particular, emoji joiners and blank lines are intentional.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def validate_comment(text: str, *, max_length: int | None = None) -> list[str]:
    """Local validation, without a platform length limit unless explicitly supplied."""
    if not text or not text.strip():
        return ["The comment is empty. Enter text or use 'comment clear --yes'."]
    problems = []
    if max_length is not None and len(text) > max_length:
        problems.append(f"The comment is {len(text)} characters; the limit is {max_length}.")
    if any((ord(char) < 32 and char not in "\n\t") or 127 <= ord(char) <= 159 for char in text):
        problems.append("The comment contains unsupported control characters.")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        problems.append("The comment contains invalid Unicode surrogate characters.")
    return problems


def approval_report(approved: bool) -> StatusReport:
    """Report approval state instead of raising.

    Used by ``flochat doctor`` to show the submission gate is intact without
    attempting a submission. Only the literal True counts as approval.
    """
    if approved is True:
        return StatusReport.of(
            AppState.PENDING, "Boolean consent alone is not a bound, one-time safety approval."
        )
    return StatusReport.of(
        AppState.PENDING,
        "No approval present; submission is blocked until the user approves.",
    )


def ensure_approved(approved: bool) -> None:
    """Refuse anything that is not an explicit, current approval.

    Only the literal value True passes: a truthy non-boolean must not be treated
    as consent.
    """
    if approved is not True:
        raise ApprovalRequiredError()


def submit(request: SubmissionRequest, *, max_length: int = 200, engine=None, approval_id=None):
    """The single submission entry point. This build refuses every call, safely.

    Order matters: text is normalised and validated, then approval is checked,
    and only then does the missing integration surface. A caller therefore cannot
    learn anything about submission or bypass the guard.
    """
    if engine is not None:
        ensure_approved(request.approved)
        return engine.execute(request, approval_id)
    text = normalize_text(request.comment_text)
    problems = validate_comment(text, max_length=max_length)
    if problems:
        raise FloChatError("The comment cannot be submitted.", hint=" ".join(problems))
    if not request.live_chat_id:
        raise FloChatError("No live chat was selected.")
    ensure_approved(request.approved)
    raise NotSupportedYetError(
        "Submission without a bound safety session", "the interactive flochat safety console"
    )


USERNAME_TEMPLATES = {
    "intro": "My username is {username}",
    "hello": "Hello, my username is {username}",
    "entry": "Please consider my entry: {username}",
}


class CommentManager:
    """Local operations, reusable by future interfaces; each operation is atomic.

    One local profile and one persistent editor prevent ambiguous active choices.
    History stores only IDs, event types, times and counts, never text snapshots.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _required(value: str, label: str) -> str:
        value = normalize_text(value)
        problems = validate_comment(value)
        if problems:
            raise FloChatError(
                f"Invalid {label}. Please enter non-empty text without control characters."
            )
        return value

    @staticmethod
    def _confirmed(yes: bool) -> None:
        if yes is not True:
            raise FloChatError(
                "Nothing deleted or cleared.", hint="Review the target and repeat with --yes."
            )

    @staticmethod
    def _editor(connection: sqlite3.Connection) -> dict:
        row = connection.execute("SELECT * FROM editor WHERE id=1").fetchone()
        return dict(row) if row else {"text": "", "username": None, "draft_id": None}

    @staticmethod
    def _draft(connection: sqlite3.Connection, draft_id: str) -> dict:
        row = connection.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise FloChatError(f"No saved draft found with ID {draft_id!r}.")
        return dict(row)

    def _event(self, connection: sqlite3.Connection, event: str, editor: dict) -> None:
        connection.execute(
            "INSERT INTO local_history VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), editor.get("draft_id"), event, self._now(), len(editor["text"])),
        )

    def _write_editor(self, connection: sqlite3.Connection, editor: dict) -> None:
        connection.execute(
            "INSERT INTO editor (id,text,username,draft_id,updated_at) VALUES (1,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET text=excluded.text, username=excluded.username, "
            "draft_id=excluded.draft_id, updated_at=excluded.updated_at",
            (editor["text"], editor["username"], editor["draft_id"], self._now()),
        )

    @staticmethod
    def _replacement(current: dict, replace: bool) -> None:
        if current["text"] and replace is not True:
            raise FloChatError(
                "The editor already contains text.",
                hint="Save it first, or explicitly use --replace.",
            )

    @staticmethod
    def _view(connection: sqlite3.Connection, editor: dict) -> dict:
        draft = None
        if editor["draft_id"]:
            draft = connection.execute(
                "SELECT * FROM drafts WHERE id=?", (editor["draft_id"],)
            ).fetchone()
        saved = bool(
            draft and draft["text"] == editor["text"] and draft["username"] == editor["username"]
        )
        problems = validate_comment(editor["text"])
        return {
            "text": editor["text"],
            "username": editor["username"],
            "character_count": len(editor["text"]),
            "valid": not problems,
            "validation_errors": problems,
            "saved": saved,
            "draft_id": editor["draft_id"],
            "status": "Draft" if saved else ("Prepared" if editor["text"] else "Empty"),
            "submitted": False,
            "message": "Local text only. This comment has not been submitted.",
        }

    def username(self, action: str, value: str | None = None, *, yes: bool = False) -> dict:
        if action not in ("set", "show", "delete"):
            raise FloChatError("Unknown username action.")
        with self.database.transaction() as c:
            if action == "set":
                name = self._required(value or "", "username")
                if "\n" in name or "\t" in name:
                    raise FloChatError("Invalid username. Use a single line without tabs.")
                c.execute(
                    "INSERT INTO username_profile VALUES (1,?,?) ON CONFLICT(id) "
                    "DO UPDATE SET username=excluded.username, updated_at=excluded.updated_at",
                    (name, self._now()),
                )
            elif action == "delete":
                self._confirmed(yes)
                deleted = c.execute("DELETE FROM username_profile WHERE id=1").rowcount
                if not deleted:
                    return {"message": "No saved username found. Nothing deleted."}
                return {"message": "Saved username deleted. Existing comment text is unchanged."}
            row = c.execute(
                "SELECT username, updated_at FROM username_profile WHERE id=1"
            ).fetchone()
            return {
                "profile": dict(row) if row else None,
                "message": "Local username; not verified against YouTube."
                if row
                else "No saved username found.",
            }

    def comment(
        self,
        action: str,
        text: str | None = None,
        *,
        replace: bool = False,
        template: str = "intro",
        yes: bool = False,
    ) -> dict:
        if action not in ("new", "edit", "generate", "show", "preview", "clear"):
            raise FloChatError("Unknown comment action.")
        with self.database.transaction() as c:
            editor = self._editor(c)
            if action in ("new", "edit", "generate"):
                selected = None
                if action == "generate":
                    row = c.execute("SELECT username FROM username_profile WHERE id=1").fetchone()
                    if row is None:
                        raise FloChatError(
                            "No saved username found.", hint="Use 'username set NAME' first."
                        )
                    if template not in USERNAME_TEMPLATES:
                        raise FloChatError("Unknown username template.")
                    selected = row[0]
                    text = USERNAME_TEMPLATES[template].format(username=selected)
                prepared = self._required(text or "", "comment")
                if action != "edit":
                    self._replacement(editor, replace)
                    editor = {"text": prepared, "username": selected, "draft_id": None}
                else:
                    # Edited text is ordinary text; a previous username association is
                    # dropped because arbitrary edits may have removed or replaced it.
                    editor.update(text=prepared, username=None)
                self._write_editor(c, editor)
                self._event(c, "comment_edited" if action == "edit" else "comment_prepared", editor)
            elif action == "clear":
                self._confirmed(yes)
                self._event(c, "editor_cleared", editor)
                c.execute("DELETE FROM editor WHERE id=1")
                editor = self._editor(c)
            elif action == "preview":
                self._event(c, "comment_previewed", editor)
            view = self._view(c, editor)
            if action == "preview":
                view["message"] = "Preview ready. This comment has not been submitted."
            return view

    def drafts(
        self,
        action: str,
        draft_id: str | None = None,
        *,
        title: str | None = None,
        replace: bool = False,
        yes: bool = False,
    ) -> dict:
        with self.database.transaction() as c:
            editor = self._editor(c)
            if action == "list":
                rows = c.execute(
                    "SELECT id,title,length(text) AS character_count,created_at,updated_at "
                    "FROM drafts ORDER BY updated_at DESC,id"
                ).fetchall()
                return {
                    "drafts": [dict(r) for r in rows],
                    "message": f"{len(rows)} saved draft(s)." if rows else "No saved drafts found.",
                }
            if action == "save":
                problems = validate_comment(editor["text"])
                if problems:
                    raise FloChatError("Cannot save draft.", hint=" ".join(problems))
                previous = self._draft(c, editor["draft_id"]) if editor["draft_id"] else None
                name = (
                    self._required(title, "draft title")
                    if title is not None
                    else (previous["title"] if previous else "Untitled draft")
                )
                now = self._now()
                draft_id = editor["draft_id"] or str(uuid4())
                c.execute(
                    "INSERT INTO drafts VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "title=excluded.title,text=excluded.text,username=excluded.username,updated_at=excluded.updated_at",
                    (draft_id, name, editor["text"], editor["username"], now, now),
                )
                editor["draft_id"] = draft_id
                self._write_editor(c, editor)
                self._event(c, "draft_edited" if previous else "draft_created", editor)
                return {
                    "draft": self._draft(c, draft_id),
                    "message": "Draft saved successfully. Not submitted.",
                }
            draft = self._draft(c, draft_id or "")
            event_editor = {"text": draft["text"], "draft_id": draft["id"]}
            if action == "open":
                self._replacement(editor, replace)
                editor = {
                    "text": draft["text"],
                    "username": draft["username"],
                    "draft_id": draft["id"],
                }
                self._write_editor(c, editor)
                self._event(c, "draft_opened", editor)
                return self._view(c, editor)
            if action == "rename":
                name = self._required(title or "", "draft title")
                c.execute(
                    "UPDATE drafts SET title=?,updated_at=? WHERE id=?",
                    (name, self._now(), draft_id),
                )
                self._event(c, "draft_renamed", event_editor)
                return {"draft": self._draft(c, draft["id"]), "message": "Draft renamed."}
            if action == "delete":
                self._confirmed(yes)
                c.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
                self._event(c, "draft_deleted", event_editor)
                return {
                    "message": (
                        "Draft deleted. Editor text is retained as unsaved; "
                        "history retains metadata only."
                    )
                }
            raise FloChatError("Unknown draft action.")

    def history(self, action: str, *, limit: int = 50, yes: bool = False) -> dict:
        if action not in ("list", "clear"):
            raise FloChatError("Unknown history action.")
        with self.database.transaction() as c:
            if action == "clear":
                self._confirmed(yes)
                count = c.execute("DELETE FROM local_history").rowcount
                count += c.execute("DELETE FROM safety_events").rowcount
                return {
                    "message": (
                        f"Cleared {count} local history event(s). Drafts and editor unchanged."
                    )
                }
            if not 1 <= limit <= 1000:
                raise FloChatError("History limit must be between 1 and 1000.")
            rows = c.execute(
                "SELECT * FROM local_history ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
            ).fetchall()
            return {
                "events": [dict(r) for r in rows],
                "safety_events": [
                    dict(r)
                    for r in c.execute(
                        "SELECT e.*, a.category, a.state AS attempt_state FROM "
                        "safety_events e LEFT JOIN safety_attempts a ON "
                        "e.attempt_id=a.id ORDER BY e.created DESC LIMIT ?",
                        (limit,),
                    )
                ],
                "submitted": False,
                "message": "Local management events only; no submission records."
                if rows
                else "No local history found.",
            }
