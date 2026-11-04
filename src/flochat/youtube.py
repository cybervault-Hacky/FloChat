"""YouTube integration boundary.

Nothing in this module performs a network request in Phase 01. Every boundary
below answers one question and reports the honest answer; ``controller.status``
asks all four so that no boundary is an unexercised stub.

Approved direction: official Google OAuth and official YouTube Data API v3 only.
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
    """How far authorization has actually progressed."""

    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    #: Reserved for Phase 04, when a live token check exists to distinguish these.
    AUTHORIZED = "authorized"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class AuthStatus:
    state: AuthState
    detail: str

    def to_report(self) -> StatusReport:
        """Map authorization progress to an application state.

        Phase 01 cannot validate a token, so a present token is *pending*
        verification rather than success.
        """
        mapping = {
            AuthState.NOT_CONFIGURED: AppState.AUTHENTICATION_REQUIRED,
            AuthState.CONFIGURED: AppState.PENDING,
            AuthState.AUTHORIZED: AppState.SUCCESS,
            AuthState.EXPIRED: AppState.SESSION_EXPIRED,
            AuthState.REVOKED: AppState.AUTHENTICATION_REQUIRED,
        }
        return StatusReport(
            state=mapping[self.state],
            detail=self.detail,
            confirmed=False,
            notes=("The OAuth flow is not implemented in Phase 01; this is configuration only.",),
        )


class OAuthBoundary:
    """Official Google OAuth boundary (authorization code flow with PKCE).

    Reads *paths* only. Credential values are never opened, parsed, or logged.
    """

    SCOPES: ClassVar[tuple[str, ...]] = ("https://www.googleapis.com/auth/youtube.force-ssl",)

    def __init__(self, client_secret: Path | None = None, token_file: Path | None = None) -> None:
        self.client_secret = client_secret
        self.token_file = token_file

    @property
    def client_secret_present(self) -> bool:
        return self.client_secret is not None and os.fspath(self.client_secret) != ""

    @property
    def token_present(self) -> bool:
        return self.token_file is not None and self.token_file.exists()

    def status(self) -> AuthStatus:
        if not self.client_secret_present:
            return AuthStatus(
                AuthState.NOT_CONFIGURED,
                "No Google OAuth client configuration. Set FLOCHAT_CLIENT_SECRET to a local "
                "path outside the repository.",
            )
        if self.token_present:
            return AuthStatus(
                AuthState.CONFIGURED,
                "A client configuration and a token file are present, but the token has not "
                "been validated. Phase 04 performs the real authorization.",
            )
        return AuthStatus(
            AuthState.NOT_CONFIGURED,
            "A client configuration path is set, but no authorization is stored yet.",
        )


class YouTubeClientBoundary:
    """Official YouTube Data API boundary. No requests are made in Phase 01."""

    API_VERSION: ClassVar[str] = "v3"
    QUOTA_NOTE: ClassVar[str] = (
        "The Data API has a daily quota; exhaustion is reported, never worked around."
    )

    def status(self) -> StatusReport:
        return StatusReport(
            state=AppState.PENDING,
            detail=f"The YouTube Data API {self.API_VERSION} client is not implemented.",
            notes=(self.QUOTA_NOTE, "Planned for Phase 04 (YouTube Integration)."),
        )


@dataclass(frozen=True)
class LiveChatCandidate:
    """A live chat the user could target. Populated by Phase 04, not Phase 01."""

    video_id: str
    live_chat_id: str
    title: str
    confirmed_live: bool


class LiveChatIdentificationBoundary:
    """Resolves the live chat for a stream and detects its closure."""

    def status(self) -> StatusReport:
        return StatusReport(
            state=AppState.LIVE_CHAT_UNAVAILABLE,
            detail="Live chat identification is not implemented.",
            notes=(
                "Planned for Phase 04 (YouTube Integration).",
                "Ended streams and closed chats must be reported, never silently ignored.",
            ),
        )

    def candidates(self) -> list[LiveChatCandidate]:
        """Always empty: there is no client and no session to ask."""
        return []


class ApiErrorBoundary:
    """Maps API and network failures to FloChat states.

    The mappings are prepared now so Phase 04 has a target to implement against;
    this class is consulted by ``status`` to prove the mapping is wired.
    """

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
        """Classify one documented failure code. Sends no request."""
        state = cls.MAPPINGS.get(code.lower(), AppState.FAILURE)
        return StatusReport(
            state=state,
            detail=f"Classified {code!r} without sending a request.",
            notes=("No API call is implemented in Phase 01.",),
        )

    @classmethod
    def coverage(cls) -> dict[str, object]:
        """Exercise every documented code so the mapping cannot rot silently."""
        return {code: cls.classify(code).state.value for code in sorted(cls.MAPPINGS)}


def describe(client_secret: Path | None, token_file: Path | None) -> dict[str, object]:
    """Report every YouTube boundary at once."""
    oauth = OAuthBoundary(client_secret, token_file)
    client = YouTubeClientBoundary()
    live_chat = LiveChatIdentificationBoundary()
    return {
        "oauth": {
            "auth_state": oauth.status().state.value,
            "client_secret_configured": oauth.client_secret_present,
            "token_file_present": oauth.token_present,
            "requested_scopes": list(oauth.SCOPES),
            "status": oauth.status().to_report().to_dict(),
        },
        "api_client": {"version": client.API_VERSION, "status": client.status().to_dict()},
        "live_chat": {
            "status": live_chat.status().to_dict(),
            "candidates": len(live_chat.candidates()),
        },
        "error_mappings": ApiErrorBoundary.coverage(),
        "requests_sent": 0,
    }
