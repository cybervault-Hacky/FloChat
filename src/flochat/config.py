"""Configuration management for FloChat.

This build uses a minimal, explicit configuration surface: a small JSON file plus
`FLOCHAT_*` environment variables (highest precedence). Environment variables
were chosen deliberately: they carry over to `sudo` on Linux and macOS and avoid
the `$env:` scoping pitfall in PowerShell profiles.

Secrets never live in this file. Google OAuth client secrets and tokens are
referenced by path only (or, later, held in platform secure storage).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from flochat.errors import ConfigurationError
from flochat.platform import PlatformInfo, detect

CONFIG_FILENAME = "config.json"

#: Keys whose presence in a configuration file indicates a credential leak.
FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "client_secret",
        "clientsecret",
        "password",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
    }
)


class AppConfig(BaseModel):
    """Validated FloChat configuration. Unknown keys are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["manual", "persistent"] = "manual"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    data_dir: Path | None = None
    db_path: Path | None = None
    client_secret: Path | None = None
    token_file: Path | None = None
    cooldown_seconds: int = Field(default=30, ge=5, le=600)
    max_comment_length: int = Field(default=200, gt=0, le=1500)

    @field_validator("data_dir", "db_path", "client_secret", "token_file", mode="before")
    @classmethod
    def _expand_paths(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        if not isinstance(value, (str, os.PathLike)):
            raise TypeError("expected a filesystem path")
        if any(ord(char) == 0 or 0xD800 <= ord(char) <= 0xDFFF for char in str(value)):
            raise ValueError("path contains invalid characters")
        expanded = Path(value).expanduser()
        if not expanded.is_absolute():
            raise ValueError("path must be absolute; credential values must never be supplied")
        return expanded

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir or detect().default_data_dir()

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or self.resolved_data_dir / "flochat.sqlite3"

    def to_public_dict(self, *, platform: PlatformInfo | None = None) -> dict[str, Any]:
        info = platform or detect()
        return {
            "mode": self.mode,
            "log_level": self.log_level,
            "data_dir": str(self.resolved_data_dir),
            "db_path": str(self.resolved_db_path),
            "client_secret_configured": self.client_secret is not None,
            "token_file_configured": self.token_file is not None,
            "cooldown_seconds": self.cooldown_seconds,
            "max_comment_length": self.max_comment_length,
            "platform": info.label,
        }


#: Environment variable -> configuration field. Public so `flochat settings` can
#: report which variable a value came from instead of guessing.
ENV_VARIABLES: dict[str, str] = {
    "FLOCHAT_MODE": "mode",
    "FLOCHAT_LOG_LEVEL": "log_level",
    "FLOCHAT_HOME": "data_dir",
    "FLOCHAT_DB": "db_path",
    "FLOCHAT_CLIENT_SECRET": "client_secret",
    "FLOCHAT_TOKEN_FILE": "token_file",
    "FLOCHAT_COOLDOWN_SECONDS": "cooldown_seconds",
    "FLOCHAT_MAX_COMMENT_LENGTH": "max_comment_length",
}


def env_overrides() -> dict[str, Any]:
    """Configuration values supplied by the current environment, if any."""
    return {
        field_name: os.environ[variable].strip()
        for variable, field_name in ENV_VARIABLES.items()
        if os.environ.get(variable, "").strip()
    }


def _env_overrides() -> dict[str, Any]:
    """Internal alias kept so call sites read clearly."""
    return env_overrides()


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 65536:
            raise ConfigurationError("Configuration exceeds the 64 KiB size limit.")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(
            f"Cannot read the configuration file at {path}.", hint=str(exc)
        ) from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"The configuration file at {path} is not valid JSON.",
            hint=f"Line {exc.lineno}, column {exc.colno}.",
        ) from exc
    except (UnicodeError, RecursionError):
        raise ConfigurationError(
            "Configuration must be valid UTF-8 JSON with bounded nesting."
        ) from None
    if not isinstance(raw, dict):
        raise ConfigurationError(f"The configuration file at {path} must contain a JSON object.")
    leaked = sorted(FORBIDDEN_SECRET_KEYS.intersection({str(k).lower() for k in raw}))
    if leaked:
        raise ConfigurationError(
            f"The configuration file at {path} contains credential fields: {', '.join(leaked)}.",
            hint="Store secrets outside the repository and reference them by path only.",
        )
    return raw


def config_file_path(platform: PlatformInfo | None = None) -> Path:
    """The config file this process would read, honouring ``FLOCHAT_HOME``."""
    info = platform or detect()
    home = env_overrides().get("data_dir")
    base = Path(home) if home else info.default_data_dir()
    return base / CONFIG_FILENAME


def load_config(
    *,
    env: bool = True,
    platform: PlatformInfo | None = None,
    path: Path | None = None,
) -> AppConfig:
    """Load configuration from defaults, the JSON file, and environment variables.

    ``env=False`` ignores environment overrides; ``settings`` uses that to report the
    persisted baseline separately from live shell overrides.
    """
    overrides = _env_overrides() if env else {}
    # FLOCHAT_HOME moves the whole data directory, so it also moves config.json.
    target = path or config_file_path(platform)
    data = _read_config_file(target)
    data.update(overrides)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(
            f"Invalid configuration ({target}).",
            hint=_describe_validation_error(exc),
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid configuration ({target}).", hint=str(exc)) from exc


def _describe_validation_error(exc: ValidationError) -> str:
    """Turn pydantic output into one short, readable line."""
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "configuration"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def sample_config(platform: PlatformInfo | None = None) -> dict[str, Any]:
    config = AppConfig()
    info = platform or detect()
    return {
        "mode": config.mode,
        "log_level": config.log_level,
        "data_dir": str(info.default_data_dir()),
        "cooldown_seconds": config.cooldown_seconds,
        "max_comment_length": config.max_comment_length,
    }


def configure_logging(level: str = "info") -> logging.Logger:
    """Configure stderr logging once, without touching the caller's other loggers."""
    logger = logging.getLogger("flochat")
    numeric = getattr(logging, level.upper(), logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(numeric)
    logger.propagate = False
    return logger
