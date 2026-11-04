"""Application states and the state model shared across FloChat boundaries.

The state vocabulary below is the single source of truth for how FloChat reports
its condition to the user. Every boundary (CLI, lifecycle, YouTube) reports
through these values so that failures are never silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AppState(str, Enum):
    """Every state FloChat is allowed to be in."""

    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    AUTHENTICATION_REQUIRED = "authentication_required"
    PERMISSION_REQUIRED = "permission_required"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    TEMPORARY_INTERRUPTION = "temporary_interruption"
    DISCONNECTED = "disconnected"
    SESSION_EXPIRED = "session_expired"
    LIVE_CHAT_UNAVAILABLE = "live_chat_unavailable"

    @property
    def message(self) -> str:
        """Short user-facing text. Deliberately free of hyphens for readability."""
        return _MESSAGES[self]

    def to_dict(self) -> dict[str, str]:
        return {"state": self.value, "message": self.message}


_MESSAGES: dict[AppState, str] = {
    AppState.SUCCESS: "Completed and confirmed.",
    AppState.FAILURE: "The operation failed. See the message for details.",
    AppState.PENDING: "Waiting: this step needs your input or a later phase.",
    AppState.AUTHENTICATION_REQUIRED: "Sign in with your Google account to continue.",
    AppState.PERMISSION_REQUIRED: "FloChat needs an operating system permission to continue.",
    AppState.UNSUPPORTED_PLATFORM: "This platform or terminal is not supported for that operation.",
    AppState.TEMPORARY_INTERRUPTION: (
        "Temporarily interrupted. FloChat will not act until you resume it."
    ),
    AppState.DISCONNECTED: "The session is disconnected.",
    AppState.SESSION_EXPIRED: "The session expired. Sign in again to continue.",
    AppState.LIVE_CHAT_UNAVAILABLE: "The live chat is not available for this stream.",
}


@dataclass(frozen=True)
class StatusReport:
    """A result reported by any FloChat boundary.

    ``confirmed`` exists to enforce the project rule that an operation is never
    reported as successful unless its result was actually observed.
    """

    state: AppState
    detail: str = ""
    confirmed: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def success(cls, detail: str, *, confirmed: bool = True) -> StatusReport:
        return cls(state=AppState.SUCCESS, detail=detail, confirmed=confirmed)

    @classmethod
    def of(cls, state: AppState, detail: str = "") -> StatusReport:
        return cls(state=state, detail=detail, confirmed=False)

    @property
    def ok(self) -> bool:
        """True only for a success that was actually confirmed."""
        return self.state is AppState.SUCCESS and self.confirmed

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "message": self.state.message,
            "detail": self.detail,
            "confirmed": self.confirmed,
            "notes": list(self.notes),
        }
