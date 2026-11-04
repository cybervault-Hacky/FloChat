"""YouTube integration boundary.

Nothing in this module performs a network request in Phase 01. Each class states
what a later phase must implement and what the current honest answer is, so the
rest of FloChat can depend on the shape of the boundary without anyone assuming
the integration already works.

Approved direction: official OAuth and official YouTube Data API v3 only.
No scraping, no browser automation, no undocumented endpoints, no CAPTCHA
handling of any kind.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar

from flochat.state import AppState, StatusReport


class AuthState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    AUTHORIZED = "authorized"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class AuthStatus:
    state: AuthState
    detail: str

    def to_report(self) -> StatusReport:
        mapping = {
            AuthState.NOT_CONFIGURED: AppState.AUTHENTICATION_REQUIRED,
            AuthState.AUTHORIZED: AppState.SUCCESS,
            AuthState.EXPIRED: AppState.SESSION_EXPIRED,
            AuthState.REVOKED: AppState.AUTHENTICATION_REQUIRED,
        }
        return StatusReport(
            state=mapping[self.state],
            detail=self.detail,
            confirmed=self.state is AuthState.AUTHORIZED,
            notes=("OAuth flow is not implemented in Phase 01.",),
        )


class OAuthBoundary:
    """Official Google OAuth boundary (authorization code flow with PKCE)."""

    def __init__(self, client_secret: Path | None = None, token_file: Path | None = None) -> None:
        self.client_secret = client_secret
        self.token_file = token_file

    @property
    def client_secret_present(self) -> bool:
        """True only when a *path* is configured; the file itself is never read here."""
        return self.client_secret is not None and os.fspath(self.client_secret) != ""

    @property
    def token_present(self) -> bool:
        return self.token_file is not None and self.token_file.exists()

    def status(self) -> AuthStatus:
        if not self.client_secret_present:
            return AuthStatus(
                AuthState.NOT_CONFIGURED,
                "No Google OAuth client configuration is present. Set FLOCHAT_CLIENT_SECRET "
                "to a local path outside the repository.",
            )
        if self.token_present:
            return AuthStatus(
                AuthState.AUTHORIZED,
                "Authorization material exists at the configured path. Validity is checked "
                "by the live API in Phase 04; it has not been verified here.",
            )
        return AuthStatus(
            AuthState.NOT_CONFIGURED,
            "A client configuration path is set, but no authorization is stored yet.",
        )


@dataclass(frozen=True)
class LiveChatCandidate:
    """A live chat the user could target. Populated by Phase 04, not Phase 01."""

    video_id: str
    live_chat_id: str
    title: str
    confirmed_live: bool


class YouTubeClientBoundary:
    """Official YouTube Data API boundary. No requests are made in Phase 01."""

    QUOTA_NOTE = "The Data API has a daily quota; FloChat must degrade honestly when exhausted."

    def status(self) -> StatusReport:
        return StatusReport(
            state=AppState.PENDING,
            detail="The YouTube API client is not implemented in Phase 01.",
            notes=(self.QUOTA_NOTE, "Planned for Phase 04 (YouTube Integration)."),
        )

    def list_live_chats(self) -> list[LiveChatCandidate]:
        """Always empty in Phase 01: there is no client and no session."""
        return []


class LiveChatIdentificationBoundary:
    """Resolves a live chat for a stream/video, and detects its end."""

    def status(self) -> StatusReport:
        return StatusReport(
            state=AppState.LIVE_CHAT_UNAVAILABLE,
            detail="Live chat identification is not implemented in Phase 01.",
            notes=(
                "Later phases must report ended streams and closed chats explicitly.",
                "Planned for Phase 04 (YouTube Integration).",
            ),
        )


class ApiErrorBoundary:
    """Maps API failures to FloChat states. No network code exists yet."""

    #: Prepared mappings, so error handling is designed before it is needed.
    MAPPINGS: ClassVar[dict[str, AppState]] = {
        "quota_exceeded": AppState.TEMPORARY_INTERRUPTION,
        "rate_limited": AppState.TEMPORARY_INTERRUPTION,
        "unauthorized": AppState.AUTHENTICATION_REQUIRED,
        "forbidden": AppState.PERMISSION_REQUIRED,
        "live_chat_ended": AppState.DISCONNECTED,
        "chat_not_found": AppState.LIVE_CHAT_UNAVAILABLE,
        "network": AppState.TEMPORARY_INTERRUPTION,
    }

    @classmethod
    def classify(cls, code: str) -> StatusReport:
        state = cls.MAPPINGS.get(code.lower(), AppState.FAILURE)
        return StatusReport(
            state=state,
            detail=f"Classified {code!r} without sending a request.",
            notes=("Mappings are prepared; no API call is implemented in Phase 01.",),
        )
