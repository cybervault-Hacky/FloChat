"""Lifecycle boundary: manual sessions, persistent mode, and recovery.

Phase 01 implements the *modes* honestly: a manual session is a real in-process
object with start/stop semantics, and persistent mode reports
:class:`~flochat.state.AppState.PERMISSION_REQUIRED` because no background
service, overlay, or reboot recovery exists yet.

Rules encoded here:

* Persistent mode never means unattended commenting. Every submission still
  requires explicit per-comment approval (see ``comments.ensure_approved``).
* Reconnecting never resubmits anything. :meth:`SessionManager.recover` only
  reports what the user should do next.
* ``stop()`` ends the session cleanly and releases resources; nothing is left in
  an ambiguous "maybe running" state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from flochat.config import AppConfig
from flochat.state import AppState, StatusReport

SessionMode = Literal["manual", "persistent"]


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Session:
    """A single FloChat session. Only ``manual`` can actually run in Phase 01."""

    mode: SessionMode = "manual"
    state: SessionState = SessionState.IDLE
    started_at: str | None = None
    stopped_at: str | None = None
    interruptions: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.state is SessionState.RUNNING

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "state": self.state.value,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "interruptions": list(self.interruptions),
        }


class SessionManager:
    """Owns the current session for this process."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._session = Session(mode=config.mode)

    @property
    def session(self) -> Session:
        return self._session

    def start(self) -> StatusReport:
        if self._session.active:
            return StatusReport(
                state=AppState.SUCCESS,
                detail=f"A {self._session.mode} session is already running.",
                confirmed=True,
                notes=("No new session was started.",),
            )

        if self._session.mode == "persistent":
            return StatusReport(
                state=AppState.PERMISSION_REQUIRED,
                detail=(
                    "Persistent shell started, but background availability needs an overlay "
                    "and a background service that Phase 01 does not implement."
                ),
                notes=(
                    "No overlay permission has been requested.",
                    "Automatic submission is never performed, even in persistent mode.",
                ),
            )

        self._session.state = SessionState.RUNNING
        self._session.started_at = _now()
        self._session.stopped_at = None
        return StatusReport(
            state=AppState.SUCCESS,
            detail="Manual session started.",
            confirmed=True,
            notes=(
                "YouTube operations are not implemented in Phase 01.",
                "Every future submission needs explicit approval.",
            ),
        )

    def stop(self) -> StatusReport:
        if self._session.state is SessionState.IDLE:
            return StatusReport(
                state=AppState.SUCCESS,
                detail="No session was running.",
                confirmed=True,
                notes=("Nothing was stopped.",),
            )
        if self._session.state is SessionState.STOPPED:
            return StatusReport(
                state=AppState.SUCCESS, detail="The session is already stopped.", confirmed=True
            )

        self._session.state = SessionState.STOPPED
        self._session.stopped_at = _now()
        return StatusReport(
            state=AppState.SUCCESS,
            detail="Session stopped. Any pending approval is discarded.",
            confirmed=True,
            notes=(
                "Nothing is submitted on stop.",
                "Session state is scoped to this terminal process; "
                "Phase 01 has no background service.",
            ),
        )

    def note_interruption(self, reason: str) -> StatusReport:
        """Record an interruption without pretending the session recovered."""
        self._session.interruptions.append(reason)
        return StatusReport(
            state=AppState.TEMPORARY_INTERRUPTION,
            detail=reason,
            notes=("FloChat stays paused until you resume it.",),
        )

    def recover(self) -> StatusReport:
        """Report what recovery would require. Phase 01 does not restore sessions."""
        if self._session.mode == "persistent":
            return StatusReport(
                state=AppState.PERMISSION_REQUIRED,
                detail=(
                    "Session recovery needs a background service that Phase 01 does not implement."
                ),
                notes=(
                    "FloChat never resubmits a comment after reconnecting.",
                    "A recovered session would still require approval for each submission.",
                ),
            )
        return StatusReport(
            state=AppState.PENDING,
            detail="Manual sessions are not restored automatically.",
            notes=("Start a new session when you are ready.",),
        )


def describe_mode(config: AppConfig) -> dict[str, object]:
    """Static summary of both approved modes, for `config show`."""
    return {
        "active": config.mode,
        "manual": {
            "available": True,
            "meaning": "User starts and stops the session; approval is per comment.",
        },
        "persistent": {
            "available": False,
            "meaning": "Background availability is planned for Phase 06.",
            "requires": ["overlay permission", "background service", "battery-exemption guidance"],
            "restriction": "Never unattended; never resubmits on reconnect.",
        },
    }
