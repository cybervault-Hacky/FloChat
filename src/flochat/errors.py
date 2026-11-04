"""FloChat error hierarchy.

All FloChat errors are catchable through :class:`FloChatError` and carry an
:class:`~flochat.state.AppState` so the CLI and lifecycle layers can present a
clear status instead of a traceback.
"""

from __future__ import annotations

from flochat.state import AppState


class FloChatError(Exception):
    """Base class for expected FloChat failures."""

    state: AppState = AppState.FAILURE

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message} {self.hint}".strip()


class ConfigurationError(FloChatError):
    """Invalid or unusable configuration."""


class PlatformError(FloChatError):
    """The current platform or terminal cannot support the requested operation."""

    state = AppState.UNSUPPORTED_PLATFORM


class StorageError(FloChatError):
    """The local database boundary could not complete an operation."""


class OrientationError(FloChatError):
    """The repository contradicts the approved Phase 01 architecture."""


class AuthenticationRequiredError(FloChatError):
    state = AppState.AUTHENTICATION_REQUIRED


class SessionExpiredError(FloChatError):
    state = AppState.SESSION_EXPIRED


class PermissionRequiredError(FloChatError):
    state = AppState.PERMISSION_REQUIRED


class ApprovalRequiredError(FloChatError):
    """A submission was attempted without explicit user approval."""

    def __init__(
        self, message: str = "Explicit approval is required for every submission."
    ) -> None:
        super().__init__(message, hint="Run the verify command only after the user approves.")


class LiveChatUnavailableError(FloChatError):
    state = AppState.LIVE_CHAT_UNAVAILABLE


class NetworkInterruption(FloChatError):
    state = AppState.TEMPORARY_INTERRUPTION


class NotSupportedYetError(FloChatError):
    """An approved direction that a later phase will implement."""

    def __init__(self, feature: str, phase: str) -> None:
        super().__init__(
            f"{feature} is not implemented yet.",
            hint=f"Planned for {phase}. Phase 01 does not perform this operation.",
        )
