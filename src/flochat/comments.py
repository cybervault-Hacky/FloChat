"""Comment manager boundary.

Phase 01 defines the contract and the safe parts of validation. Draft creation,
history browsing, and submission belong to Phase 03 (Comment Manager) and
Phase 05 (Safety Engine). No function here contacts YouTube.

Invariants encoded in this module:

* A comment must be explicitly prepared, previewed, and approved before any
  submission path may be reached.
* Text is normalised (trailing whitespace, invisible control characters) so that
  the previewed text and the submitted text are the same string.
* Validation never decides to send anything; it only refuses unsafe input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from flochat.errors import ApprovalRequiredError, FloChatError, NotSupportedYetError

#: Google accounts allow 3 to 30 characters, letters, numbers, dots, hyphens, underscores.
YOUTUBE_HANDLE_PATTERN = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")

#: Zero-width and bidirectional control characters are stripped, not rejected,
#: because they are usually accidental paste artifacts.
_INVISIBLE = dict.fromkeys(
    map(ord, "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"), None
)


@dataclass(frozen=True)
class CommentDraft:
    """A prepared comment. ``comment_text`` is exactly what would be previewed."""

    comment_text: str
    live_chat_id: str | None = None
    live_chat_title: str | None = None


def normalize_text(text: str) -> str:
    """Collapse accidental whitespace and strip invisible control characters."""
    cleaned = text.translate(_INVISIBLE).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in cleaned.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize_handle(handle: str) -> str:
    """Return a canonical YouTube handle with the leading ``@``."""
    value = handle.strip()
    if not value:
        return value
    return value if value.startswith("@") else f"@{value}"


def is_valid_handle(handle: str) -> bool:
    return bool(YOUTUBE_HANDLE_PATTERN.match(normalize_handle(handle)))


def validate_comment(text: str, *, max_length: int = 200) -> list[str]:
    """Return a list of human-readable problems. An empty list means acceptable.

    This is a local safety check only. YouTube can always reject a comment for
    reasons FloChat cannot predict, so a clean result is never a guarantee.
    """
    problems: list[str] = []
    if not text or not text.strip():
        return ["The comment is empty."]
    if len(text) > max_length:
        problems.append(f"The comment is {len(text)} characters; the limit is {max_length}.")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        problems.append("The comment contains unsupported control characters.")
    if "\n\n\n" in text:
        problems.append("The comment contains more than two consecutive blank lines.")
    return problems


def prepare(text: str, *, handle: str | None = None, max_length: int = 200) -> CommentDraft:
    """Build a draft from user input, refusing unsafe text before it is stored."""
    draft_text = text
    if handle:
        draft_text = (
            f"{text} {normalize_handle(handle)}" if text.strip() else normalize_handle(handle)
        )
    normalized = normalize_text(draft_text)
    problems = validate_comment(normalized, max_length=max_length)
    if problems:
        raise FloChatError("The comment cannot be prepared.", hint=" ".join(problems))
    return CommentDraft(comment_text=normalized)


def ensure_approved(approved: bool) -> None:
    """Guard used by any future submission path. Absence of approval is fatal."""
    if approved is not True:
        raise ApprovalRequiredError()


def submit(*_args: object, **_kwargs: object) -> None:
    """Not implemented in Phase 01. Deliberately refuses to pretend otherwise."""
    raise NotSupportedYetError("Comment submission", "Phase 04 (YouTube Integration)")
