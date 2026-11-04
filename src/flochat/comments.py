"""Comment safety boundary.

Phase 03 (Comment Manager) will add drafting, preview, and history. What Phase 01
ships is the part that must exist *before* any submission code: normalisation,
validation, and the approval guard, all reachable through a single entry point.

:func:`submit` is deliberately the only submission path, and it refuses. That is
the architectural guarantee, in code: even when Phase 04 adds an API client, text
that is empty, too long, or unapproved cannot reach it, because the guard runs
first. Nothing here contacts YouTube.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from flochat.errors import ApprovalRequiredError, FloChatError, NotSupportedYetError

#: Zero-width and bidirectional control characters are stripped, not rejected,
#: because they are usually accidental paste artifacts.
_INVISIBLE = dict.fromkeys(
    map(ord, "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"), None
)


@dataclass(frozen=True)
class SubmissionRequest:
    """What a caller must supply to attempt a submission."""

    comment_text: str
    live_chat_id: str
    approved: bool = False


def normalize_text(text: str) -> str:
    """Collapse accidental whitespace and strip invisible control characters.

    Run before validation and before preview so that the string the user reads is
    exactly the string that would be sent.
    """
    cleaned = text.translate(_INVISIBLE).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in cleaned.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def validate_comment(text: str, *, max_length: int = 200) -> list[str]:
    """Return human-readable problems. An empty list means locally acceptable.

    YouTube can still reject a comment for reasons FloChat cannot predict, so a
    clean result is never a guarantee of delivery.
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


def ensure_approved(approved: bool) -> None:
    """Refuse anything that is not an explicit, current approval.

    Only the literal value True passes: a truthy non-boolean must not be treated
    as consent.
    """
    if approved is not True:
        raise ApprovalRequiredError()


def submit(request: SubmissionRequest, *, max_length: int = 200) -> None:
    """The single submission entry point. Phase 01 refuses every call, safely.

    Order matters: text is normalised and validated, then approval is checked,
    and only then does the missing integration surface. A caller therefore cannot
    learn anything about submission or bypass the guard.
    """
    text = normalize_text(request.comment_text)
    problems = validate_comment(text, max_length=max_length)
    if problems:
        raise FloChatError("The comment cannot be submitted.", hint=" ".join(problems))
    if not request.live_chat_id:
        raise FloChatError("No live chat was selected.")
    ensure_approved(request.approved)
    raise NotSupportedYetError("Comment submission", "Phase 04 (YouTube Integration)")
