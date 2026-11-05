"""Official installed-app OAuth and YouTube discovery; explicit write-grant opt-in.

Discovery methods never post. Only SafetyEngine may insert an approved message.
Credentials never enter SQLite, output or logs.
Loopback OAuth requires a browser on the same desktop as the CLI, not an Arena
preview, remote container browser, Android desktop-client workaround or OOB flow.
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import keyring
import requests
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from flochat.database import Database
from flochat.errors import FloChatError
from flochat.state import AppState

SCOPES = ("https://www.googleapis.com/auth/youtube.readonly",)
WRITE_SCOPES = ("https://www.googleapis.com/auth/youtube.force-ssl",)
API_ROOT = "https://youtube.googleapis.com/youtube/v3/"
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
HTTP_TIMEOUT = 20
SERVICE = "FloChat.YouTubeOAuth"
# Exact implementations, never an arbitrary plugin, plaintext, null or chained fallback.
SECURE_BACKENDS = {
    ("keyring.backends.macOS", "Keyring"),
    ("keyring.backends.Windows", "WinVaultKeyring"),
    ("keyring.backends.SecretService", "Keyring"),
}

ERRORS = {
    "authorization_required": (
        AppState.AUTHENTICATION_REQUIRED,
        False,
        "Authorization required. Run youtube connect on a supported desktop.",
    ),
    "authorization_expired": (
        AppState.SESSION_EXPIRED,
        False,
        "Authorization expired and cannot refresh. Connect again.",
    ),
    "authorization_invalid": (
        AppState.AUTHENTICATION_REQUIRED,
        False,
        "Authorization is invalid, revoked or expired. Connect again.",
    ),
    "permission_denied": (
        AppState.PERMISSION_REQUIRED,
        False,
        "Access denied. Check consent, channel access and API enablement.",
    ),
    "cancelled": (
        AppState.PENDING,
        False,
        "Authorization cancelled, denied or timed out; connection not established.",
    ),
    "configuration": (
        AppState.FAILURE,
        False,
        (
            "Invalid or missing Desktop OAuth client file. Set "
            "FLOCHAT_CLIENT_SECRET outside the clone."
        ),
    ),
    "secure_storage": (
        AppState.FAILURE,
        False,
        (
            "Secure credential storage unavailable or locked. Unlock/configure"
            " an OS keyring; no plaintext fallback is used."
        ),
    ),
    "credentials_invalid": (
        AppState.AUTHENTICATION_REQUIRED,
        False,
        "Stored credentials are invalid. Disconnect locally and connect again.",
    ),
    "quota_exceeded": (
        AppState.TEMPORARY_INTERRUPTION,
        True,
        (
            "YouTube quota exhausted. Stop requests and check the project's "
            "Google quota console; no automatic retry."
        ),
    ),
    "rate_limited": (
        AppState.TEMPORARY_INTERRUPTION,
        True,
        "Requests are rate limited. Wait before explicitly trying again.",
    ),
    "timeout": (
        AppState.TEMPORARY_INTERRUPTION,
        True,
        "The request timed out. Try again later; no automatic API retry.",
    ),
    "network": (
        AppState.TEMPORARY_INTERRUPTION,
        True,
        "Network connection interrupted. Check connectivity and try later.",
    ),
    "server": (
        AppState.TEMPORARY_INTERRUPTION,
        True,
        "Google service temporarily unavailable. Try later.",
    ),
    "not_found": (
        AppState.LIVE_CHAT_UNAVAILABLE,
        False,
        "Resource missing or inaccessible to this account.",
    ),
    "chat_unavailable": (
        AppState.LIVE_CHAT_UNAVAILABLE,
        False,
        "This stream has no currently available live chat.",
    ),
    "stream_ended": (
        AppState.DISCONNECTED,
        False,
        "The stream has ended. Select another active stream.",
    ),
    "invalid_request": (
        AppState.FAILURE,
        False,
        "Invalid request. Check the supplied video ID or page token.",
    ),
    "invalid_response": (
        AppState.FAILURE,
        False,
        "Google returned an unexpected response. No success or selection recorded.",
    ),
    "account_missing": (
        AppState.DISCONNECTED,
        False,
        (
            "No YouTube channel is available for this authorization. Check the"
            " selected Google/Brand account."
        ),
    ),
    "invalid_comment": (
        AppState.FAILURE,
        False,
        "YouTube rejected comment content or length. Review the exact text before a new approval.",
    ),
    "api_failure": (
        AppState.FAILURE,
        False,
        "The official API request failed. Check access and project configuration.",
    ),
}


class YouTubeError(FloChatError):
    """Whitelisted, redacted errors: never retain raw server bodies/exceptions."""

    def __init__(self, code: str) -> None:
        self.code = code if code in ERRORS else "api_failure"
        self.state, self.temporary, message = ERRORS[self.code]
        super().__init__(message)


@contextmanager
def _quiet_credentials():
    # OAuth libraries can log response bodies at DEBUG. The single-process CLI
    # suppresses logging during sensitive library calls, restoring it afterwards.
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)


class CredentialStore:
    """One OS-protected authorization per OS user, shared by FloChat clones."""

    def __init__(self) -> None:
        try:
            self.backend = keyring.get_keyring()
            identity = (type(self.backend).__module__, type(self.backend).__name__)
            if identity not in SECURE_BACKENDS:
                raise YouTubeError("secure_storage")
        except Exception:
            raise YouTubeError("secure_storage") from None

    def load(self) -> Credentials | None:
        try:
            with _quiet_credentials():
                raw = self.backend.get_password(SERVICE, "default")
            if raw is None:
                return None
            data = json.loads(raw)
            if (
                not isinstance(data, dict)
                or data.get("token_uri") != TOKEN_URI
                or data.get("scopes") not in (list(SCOPES), list(WRITE_SCOPES))
            ):
                raise ValueError
            # Never trust an endpoint taken from the credential payload.
            credentials = Credentials.from_authorized_user_info(data, scopes=data["scopes"])
            if not credentials.token:
                raise ValueError
            if not (credentials.has_scopes(SCOPES) or credentials.has_scopes(WRITE_SCOPES)):
                raise ValueError
            return credentials
        except YouTubeError:
            raise
        except (ValueError, TypeError, KeyError):
            raise YouTubeError("credentials_invalid") from None
        except Exception:
            raise YouTubeError("secure_storage") from None

    def save(self, credentials: Credentials) -> None:
        try:
            with _quiet_credentials():
                self.backend.set_password(SERVICE, "default", credentials.to_json())
        except Exception:
            raise YouTubeError("secure_storage") from None

    def delete(self) -> None:
        try:
            with _quiet_credentials():
                if self.backend.get_password(SERVICE, "default") is not None:
                    self.backend.delete_password(SERVICE, "default")
        except Exception:
            raise YouTubeError("secure_storage") from None


class _TimedFlow(InstalledAppFlow):
    def fetch_token(self, **kwargs):
        kwargs["timeout"] = HTTP_TIMEOUT
        kwargs["allow_redirects"] = False
        return super().fetch_token(**kwargs)


def _client_configuration(path: Path | None) -> dict:
    try:
        root = Path(__file__).resolve().parents[2]
        if path is None or path.resolve().is_relative_to(root):
            raise ValueError
        data = json.loads(path.read_text(encoding="utf-8"))
        installed = data["installed"]
        if not isinstance(installed, dict):
            raise ValueError
        if (
            installed.get("auth_uri") != AUTH_URI
            or installed.get("token_uri") != TOKEN_URI
            or not isinstance(installed.get("client_id"), str)
            or not installed["client_id"].endswith(".apps.googleusercontent.com")
            or not isinstance(installed.get("client_secret"), str)
            or not installed["client_secret"].strip()
        ):
            raise ValueError
        # Pass only required validated fields, never arbitrary credential endpoints.
        return {
            "installed": {
                k: installed[k] for k in ("client_id", "client_secret", "auth_uri", "token_uri")
            }
        }
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        raise YouTubeError("configuration") from None


def _identifier(value: str, *, response: bool = False) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
        raise YouTubeError("invalid_response" if response else "invalid_request")
    return value


def _text(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
    ):
        raise YouTubeError("invalid_response")
    return value


def _api_error(response: requests.Response) -> YouTubeError:
    reasons = set()
    try:
        error = response.json().get("error", {})
        if isinstance(error, dict):
            reasons = {
                entry.get("reason") for entry in error.get("errors", []) if isinstance(entry, dict)
            }
    except (ValueError, AttributeError, TypeError, RecursionError):
        pass
    mapping = {
        "quotaExceeded": "quota_exceeded",
        "dailyLimitExceeded": "quota_exceeded",
        "rateLimitExceeded": "rate_limited",
        "userRateLimitExceeded": "rate_limited",
        "messageTextInvalid": "invalid_comment",
        "liveChatIdInvalid": "not_found",
        "liveChatEnded": "stream_ended",
        "liveChatDisabled": "chat_unavailable",
        "liveChatNotFound": "not_found",
        "insufficientPermissions": "permission_denied",
        "forbidden": "permission_denied",
        "authError": "authorization_invalid",
        "youtubeSignupRequired": "account_missing",
    }
    for reason, code in mapping.items():
        if reason in reasons:
            return YouTubeError(code)
    status_code = response.status_code
    code = {
        400: "invalid_request",
        401: "authorization_invalid",
        403: "permission_denied",
        404: "not_found",
        429: "rate_limited",
    }.get(status_code)
    return YouTubeError(code or ("server" if status_code >= 500 else "api_failure"))


class YouTubeIntegration:
    """Read-only API operations; all requests explicit, bounded, and counted."""

    def __init__(self, database: Database, config, platform) -> None:
        self.database = database
        self.config = config
        self.platform = platform

    def _clear_selection(self) -> None:
        with self.database.transaction() as c:
            c.execute("DELETE FROM youtube_selection")

    def _usage(self, operation: str) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        with self.database.transaction() as c:
            c.execute(
                "INSERT INTO youtube_usage VALUES (?,?,1) ON CONFLICT(utc_day,operation) "
                "DO UPDATE SET requests=requests+1",
                (day, operation),
            )

    def _refresh(self, credentials: Credentials, store: CredentialStore) -> None:
        if credentials.valid:
            return
        if not credentials.refresh_token:
            self._clear_selection()
            raise YouTubeError("authorization_expired")
        # Explicit bounded transport; Google's library manages the token exchange.
        with requests.Session() as session:
            session.trust_env = False
            request = Request(session=session)
            attempted = False

            def bounded_request(*args, **kwargs):
                nonlocal attempted
                if attempted:
                    raise TransportError("Automatic refresh retry disabled.")
                attempted = True
                kwargs["timeout"] = HTTP_TIMEOUT
                kwargs["allow_redirects"] = False
                result = request(*args, **kwargs)
                status = getattr(result, "status", None)
                if isinstance(status, int) and status == 429:
                    raise YouTubeError("rate_limited")
                if isinstance(status, int) and status >= 500:
                    raise YouTubeError("server")
                return result

            try:
                self._usage("oauth.refresh")
                with _quiet_credentials():
                    credentials.refresh(bounded_request)
                store.save(credentials)
            except RefreshError as exc:
                if getattr(exc, "retryable", False):
                    raise YouTubeError("server") from None
                self._clear_selection()
                raise YouTubeError("authorization_invalid") from None
            except requests.Timeout:
                raise YouTubeError("timeout") from None
            except (TransportError, requests.RequestException) as exc:
                code = "timeout" if isinstance(exc.__cause__, requests.Timeout) else "network"
                raise YouTubeError(code) from None

    def _get(self, resource: str, params: dict, credentials: Credentials) -> dict:
        # No arbitrary resource URL, POST, headers supplied by users, or writes.
        if resource not in ("channels", "liveBroadcasts", "videos"):
            raise YouTubeError("invalid_request")
        self._usage(resource + ".list")
        try:
            with requests.Session() as session, _quiet_credentials():
                session.trust_env = False
                response = session.get(
                    API_ROOT + resource,
                    params=params,
                    headers={"Authorization": "Bearer " + credentials.token},
                    timeout=HTTP_TIMEOUT,
                    allow_redirects=False,
                )
            if response.status_code != 200:
                error = _api_error(response)
                if error.code in ("authorization_invalid", "permission_denied"):
                    self._clear_selection()
                raise error
            data = response.json()
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("items"), list)
                or any(not isinstance(item, dict) for item in data["items"])
            ):
                raise YouTubeError("invalid_response")
            return data
        except requests.Timeout:
            raise YouTubeError("timeout") from None
        except (ValueError, RecursionError):
            raise YouTubeError("invalid_response") from None
        except requests.RequestException:
            raise YouTubeError("network") from None

    def _account(self, credentials: Credentials) -> dict:
        data = self._get(
            "channels", {"part": "snippet", "mine": "true", "maxResults": 50}, credentials
        )
        if not data["items"]:
            raise YouTubeError("account_missing")
        accounts = []
        for item in data["items"]:
            snippet = item.get("snippet")
            if not isinstance(snippet, dict):
                raise YouTubeError("invalid_response")
            accounts.append(
                {
                    "channel_id": _identifier(_text(item.get("id")), response=True),
                    "title": _text(snippet.get("title")),
                }
            )
        return {
            "connection_state": "connected",
            "accounts": accounts,
            "message": "Account verified by channels.list now. Chat access is not guaranteed.",
        }

    def _credentials(self) -> tuple[CredentialStore, Credentials]:
        if self.config.token_file is not None:
            raise YouTubeError("credentials_invalid")
        store = CredentialStore()
        credentials = store.load()
        if credentials is None:
            raise YouTubeError("authorization_required")
        self._refresh(credentials, store)
        return store, credentials

    def connect(self, *, local_browser: bool = False, allow_posting: bool = False) -> dict:
        if not local_browser or self.platform.key.value == "android" or not self.platform.supported:
            raise FloChatError(
                "OAuth requires a supported desktop and browser on the same machine.",
                hint=(
                    "Run youtube connect --local-browser locally. Termux/remote "
                    "callbacks are unsupported; no OOB or plaintext fallback."
                ),
            )
        if self.config.token_file is not None:
            raise YouTubeError("credentials_invalid")
        scopes = WRITE_SCOPES if allow_posting is True else SCOPES
        client = _client_configuration(self.config.client_secret)
        store = CredentialStore()  # Fail BEFORE browser/consent if secure backend is missing.
        if store.load() is not None:
            raise FloChatError(
                "Authorization already stored. Use account to verify or disconnect"
                " before changing accounts or permission scopes."
            )
        self._clear_selection()
        try:
            with _quiet_credentials():
                flow = _TimedFlow.from_client_config(
                    client, scopes=scopes, autogenerate_code_verifier=True
                )
                flow.oauth2session.trust_env = False
                credentials = flow.run_local_server(
                    host="127.0.0.1",
                    bind_addr="127.0.0.1",
                    port=0,
                    open_browser=True,
                    authorization_prompt_message=None,
                    success_message=(
                        "Authorization callback received. Return to FloChat to check the result."
                    ),
                    timeout_seconds=180,
                    access_type="offline",
                    prompt="consent",
                )
            if (
                not credentials.valid
                or not credentials.refresh_token
                or not credentials.has_scopes(scopes)
                or (
                    credentials.granted_scopes is not None
                    and not set(scopes).issubset(credentials.granted_scopes)
                )
            ):
                raise YouTubeError("permission_denied")
            account = self._account(credentials)
            # Success only AFTER profile verification and the keyring write.
            store.save(credentials)
            return {**account, "authorized_scopes": list(scopes), "posting_enabled": False}
        except (YouTubeError, FloChatError):
            raise
        except requests.Timeout:
            raise YouTubeError("timeout") from None
        except requests.RequestException:
            raise YouTubeError("network") from None
        except KeyboardInterrupt:
            raise YouTubeError("cancelled") from None
        except Exception as exc:
            # Includes denial, state mismatch, callback timeout, invalid client,
            # browser failures. Never echo OAuth exception text/code/URL/body.
            code = {
                "access_denied": "permission_denied",
                "invalid_client": "configuration",
                "invalid_grant": "authorization_invalid",
                "mismatching_state": "authorization_invalid",
            }.get(getattr(exc, "error", None), "cancelled")
            raise YouTubeError(code) from None

    def disconnect(self, *, yes: bool = False, revoke: bool = False) -> dict:
        if yes is not True:
            raise FloChatError(
                "Nothing disconnected. Repeat with --yes to remove local authorization."
            )
        # Invalidate the selected target even if credentials are malformed.
        self._clear_selection()
        store = CredentialStore()
        revoked = False
        revoke_error = None
        try:
            credentials = store.load() if revoke else None
            if credentials is not None:
                self._usage("oauth.revoke")
                with requests.Session() as session, _quiet_credentials():
                    session.trust_env = False
                    response = session.post(
                        REVOKE_URI,
                        data={"token": credentials.refresh_token or credentials.token},
                        timeout=HTTP_TIMEOUT,
                        allow_redirects=False,
                    )
                revoked = response.status_code == 200
                if not revoked:
                    revoke_error = (
                        "Google revocation not confirmed. Review Google account "
                        "permissions manually."
                    )
        except Exception:
            revoke_error = (
                "Google revocation unavailable. Review Google account permissions manually."
            )
        finally:
            store.delete()  # Always attempt local cleanup, even when revocation fails.
        return {
            "connection_state": "disconnected",
            "local_credentials_removed": True,
            "google_revocation_confirmed": revoked,
            "revocation_error": revoke_error,
            "message": "Local authorization removed. Drafts, editor and profile were not changed.",
            "operation_ok": revoke_error is None,
        }

    def _video(self, video_id: str, credentials: Credentials) -> dict:
        data = self._get(
            "videos",
            {"id": _identifier(video_id), "part": "snippet,liveStreamingDetails"},
            credentials,
        )
        if not data["items"]:
            raise YouTubeError("not_found")
        if len(data["items"]) != 1:
            raise YouTubeError("invalid_response")
        item = data["items"][0]
        snippet = item.get("snippet")
        details = item.get("liveStreamingDetails", {})
        if (
            not isinstance(snippet, dict)
            or not isinstance(details, dict)
            or item.get("id") != video_id
        ):
            raise YouTubeError("invalid_response")
        title = _text(snippet.get("title"))
        for field in ("actualStartTime", "actualEndTime"):
            if field in details:
                try:
                    parsed = datetime.fromisoformat(_text(details[field]).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError
                except ValueError:
                    raise YouTubeError("invalid_response") from None
        if details.get("actualEndTime"):
            availability = "stream_ended"
        elif details.get("actualStartTime") and details.get("activeLiveChatId"):
            availability = "live_chat_available"
        else:
            availability = "live_chat_unavailable"
        chat_id = (
            _text(details["activeLiveChatId"]) if availability == "live_chat_available" else None
        )
        return {
            "video_id": video_id,
            "title": title,
            "live_chat_id": chat_id,
            "availability": availability,
            "submitted": False,
        }

    def run(self, action: str, **options) -> dict:
        if action == "connect":
            return self.connect(**options)
        if action == "disconnect":
            return self.disconnect(**options)
        if action == "status":
            result = describe(self.config.client_secret, self.config.token_file)
            try:
                if self.config.token_file is not None:
                    raise YouTubeError("credentials_invalid")
                credentials = CredentialStore().load()
                result["stored_scopes"] = (
                    []
                    if credentials is None
                    else list(WRITE_SCOPES if credentials.has_scopes(WRITE_SCOPES) else SCOPES)
                )
                result["connection_state"] = (
                    "not_connected"
                    if credentials is None
                    else "authorization_expired"
                    if not credentials.valid
                    else "stored_unverified"
                )
            except YouTubeError as exc:
                result.update(
                    connection_state="authorization_required",
                    error=str(exc),
                    code=exc.code,
                    operation_ok=False,
                )
            with self.database.transaction() as c:
                row = c.execute("SELECT * FROM youtube_selection WHERE id=1").fetchone()
                result["selection"] = dict(row) if row else None
                result["usage"] = [
                    dict(r)
                    for r in c.execute(
                        "SELECT * FROM youtube_usage ORDER BY utc_day DESC,operation LIMIT 100"
                    )
                ]
            result["message"] = (
                "Local status only; stored credentials/selection are not proof of "
                "current access. Use account or select to verify."
            )
            return result
        _, credentials = self._credentials()
        if action == "account":
            return self._account(credentials)
        if action == "streams":
            params = {
                "part": "snippet,status",
                "mine": "true",
                "broadcastType": "all",
                "maxResults": 50,
            }
            page_token = options.get("page_token")
            if page_token:
                if len(page_token) > 4096 or any(
                    ord(c) < 32 or 127 <= ord(c) <= 159 for c in page_token
                ):
                    raise YouTubeError("invalid_request")
                params["pageToken"] = page_token
            data = self._get("liveBroadcasts", params, credentials)
            streams = []
            for item in data["items"]:
                snippet, status = item.get("snippet"), item.get("status")
                if not isinstance(snippet, dict) or not isinstance(status, dict):
                    raise YouTubeError("invalid_response")
                lifecycle = _text(status.get("lifeCycleStatus"))
                chat = snippet.get("liveChatId")
                availability = (
                    "stream_ended"
                    if lifecycle in ("complete", "revoked")
                    else "live_chat_available"
                    if lifecycle == "live" and chat
                    else "live_chat_unavailable"
                )
                streams.append(
                    {
                        "video_id": _identifier(_text(item.get("id")), response=True),
                        "title": _text(snippet.get("title")),
                        "lifecycle": lifecycle,
                        "live_chat_id": _text(chat) if chat else None,
                        "availability": availability,
                    }
                )
            token = data.get("nextPageToken")
            if token is not None:
                token = _text(token)
            return {
                "streams": streams,
                "active_chat_count": sum(
                    s["availability"] == "live_chat_available" for s in streams
                ),
                "next_page_token": token,
                "message": "No eligible broadcasts found on this page."
                if not streams
                else "Broadcasts owned by the authorized account. Nothing selected automatically.",
            }
        if action in ("inspect", "select"):
            video_id = _identifier(options.get("video_id", ""))
            if action == "select":
                self._clear_selection()  # A failed explicit selection must not leave an old target.
            video = self._video(video_id, credentials)
            if action == "inspect":
                return video
            if video["availability"] != "live_chat_available":
                raise YouTubeError(
                    "stream_ended"
                    if video["availability"] == "stream_ended"
                    else "chat_unavailable"
                )
            account = self._account(credentials)
            if len(account["accounts"]) != 1:
                raise FloChatError(
                    "Authorization returned multiple channels; select a single "
                    "Google/Brand account when reconnecting."
                )
            now = datetime.now(timezone.utc).isoformat()
            with self.database.transaction() as c:
                c.execute(
                    "INSERT INTO youtube_selection VALUES (1,?,?,?,?,?) ON CONFLICT(id) "
                    "DO UPDATE SET video_id=excluded.video_id,live_chat_id=excluded.live_chat_id,"
                    "title=excluded.title,account_channel_id=excluded.account_channel_id,"
                    "selected_at=excluded.selected_at",
                    (
                        video_id,
                        video["live_chat_id"],
                        video["title"],
                        account["accounts"][0]["channel_id"],
                        now,
                    ),
                )
            return {
                **video,
                "selected": True,
                "message": (
                    "Explicit live chat selection verified now. "
                    "No comment sent. Use the interactive safety console for individual approval."
                ),
            }
        raise YouTubeError("invalid_request")


def describe(client_secret: Path | None, token_file: Path | None) -> dict:
    """No network or keyring unlock during ordinary status/doctor/local workflows."""
    return {
        "client_secret_configured": client_secret is not None,
        "legacy_plaintext_token_path_configured": token_file is not None,
        "connection_state": "not_checked",
        "requested_scopes": list(SCOPES),
        "credential_storage": "OS keyring only; no plaintext fallback",
        "requests_sent": 0,
        "posting_enabled": False,
        "posting_policy": "Interactive SafetyEngine with a fresh per-comment approval only",
        "message": (
            "Run youtube status for local authorization state, "
            "or youtube account for live verification."
        ),
    }
