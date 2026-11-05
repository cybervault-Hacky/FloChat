"""Session manager: live-owner binding plus legacy in-process status compatibility.

The runtime binds one SafetyEngine. Native clients never own another manager.
Standalone compatibility snapshots cannot submit; CLI actions route to the owner.
Persistent availability is explicit and never restores approval or submits.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """Compatibility snapshot; live owner session state comes from its bound SafetyEngine."""

    mode: SessionMode = "manual"
    state: SessionState = SessionState.IDLE
    started_at: str | None = None
    stopped_at: str | None = None

    @property
    def active(self) -> bool:
        return self.state is SessionState.RUNNING

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "state": self.state.value,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
        }


class SessionManager:
    """Owns the current session for this process."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._session = Session(mode=config.mode)

    def bind(self, database, youtube):
        """The running owner has exactly one SafetyEngine, never a platform engine."""
        from flochat.safety import SafetyEngine

        if not hasattr(self, "safety"):
            self.safety = SafetyEngine(database, youtube)
        return self.safety

    def transition(self, action):
        return self.safety.control(action)

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
                    "No owner is bound to this compatibility object. Use panel start "
                    "or start to launch real shared availability."
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
                "Use youtube commands for discovery; individual posting requires flochat safety.",
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
                "CLI/panel operations use the live owner instead of this compatibility snapshot.",
            ),
        )

    def recover(self) -> StatusReport:
        """Descriptive status only; actual recovery is explicit through the live owner."""
        return StatusReport(
            state=AppState.PENDING,
            detail="Use session recover on the live owner to verify "
            "account/chat; then start explicitly.",
            notes=("No automatic recovery, approval restoration or resubmission.",),
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
            "available": True,
            "meaning": "Explicit local core availability; native OS may suspend or terminate it.",
            "requires": [
                "explicit launch",
                "platform UI prerequisites",
                "Android permission/battery guidance where applicable",
            ],
            "restriction": "Never unattended; never resubmits on reconnect.",
        },
    }
