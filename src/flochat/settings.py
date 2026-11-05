"""Effective settings and their provenance.

``flochat settings`` must answer three questions a user actually has:

1. What is in effect right now?
2. Where did each value come from — environment, config file, or default?
3. What is the safe next action to change it?

Phase 02 answers them read-only. Writing configuration belongs to a later phase;
this module deliberately does not touch the file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from flochat.config import (
    ENV_VARIABLES,
    AppConfig,
    config_file_path,
    env_overrides,
    load_config,
)
from flochat.errors import ConfigurationError
from flochat.platform import PlatformInfo

#: field name -> environment variable, derived once so both agree.
FIELD_ENV: dict[str, str] = {field: variable for variable, field in ENV_VARIABLES.items()}

#: field name -> (environment variable, human description, how to change it)
FIELDS: dict[str, tuple[str, str, str]] = {
    "mode": (
        FIELD_ENV["mode"],
        "Operating mode: manual starts and stops a session; persistent is Phase 06.",
        "Edit the config file or set FLOCHAT_MODE=manual|persistent",
    ),
    "log_level": (
        FIELD_ENV["log_level"],
        "Verbosity of FloChat's own log output on stderr.",
        "Edit the config file or set FLOCHAT_LOG_LEVEL=debug|info|warning|error",
    ),
    "data_dir": (
        FIELD_ENV["data_dir"],
        "Directory holding the local database and config file.",
        "Set FLOCHAT_HOME to an absolute path",
    ),
    "db_path": (
        FIELD_ENV["db_path"],
        "SQLite database file. Defaults to <data_dir>/flochat.sqlite3.",
        "Set FLOCHAT_DB to an absolute path",
    ),
    "client_secret": (
        FIELD_ENV["client_secret"],
        "Path to a Desktop Google OAuth client file, outside the clone; never the value.",
        "Set FLOCHAT_CLIENT_SECRET to a path outside the repository",
    ),
    "token_file": (
        FIELD_ENV["token_file"],
        "Legacy token-file option: unsupported for authentication; tokens use OS keyring only.",
        "Unset FLOCHAT_TOKEN_FILE; youtube connect uses the OS keyring",
    ),
    "cooldown_seconds": (
        FIELD_ENV["cooldown_seconds"],
        "Local minimum gap between attempts; enforced by Safety "
        "Engine, not an official API rate limit.",
        "Set FLOCHAT_COOLDOWN_SECONDS to an integer between 5 and 600",
    ),
    "max_comment_length": (
        FIELD_ENV["max_comment_length"],
        "Longest comment FloChat accepts.",
        "Set FLOCHAT_MAX_COMMENT_LENGTH to an integer between 1 and 1500",
    ),
}


@dataclass(frozen=True)
class Setting:
    """One configuration field, its effective value, and its origin."""

    name: str
    value: str | None
    source: str
    env_var: str
    description: str
    change_hint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "source": self.source,
            "env_var": self.env_var,
            "description": self.description,
            "change_hint": self.change_hint,
        }


def _file_keys(target: Path) -> set[str]:
    """Keys the config file actually sets, so provenance reflects the file, not defaults."""
    import json

    if not target.exists():
        return set()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return set(raw) if isinstance(raw, dict) else set()


def _render(config: AppConfig, field_name: str) -> str | None:
    explicit = getattr(config, field_name, None)
    if field_name == "data_dir":
        return str(config.resolved_data_dir)
    if field_name == "db_path":
        return str(config.resolved_db_path)
    if explicit is None:
        return None
    return str(explicit)


def describe_settings(
    config: AppConfig, *, platform: PlatformInfo, path: Path | None = None
) -> dict[str, object]:
    """Every effective setting with the origin of its value.

    Provenance is computed by re-reading each layer rather than guessing from the
    final value, so a value that happens to equal the default is still reported as
    coming from the file when it does.
    """
    target = path or config_file_path(platform)
    file_keys = _file_keys(target)
    overrides = env_overrides()

    settings: dict[str, object] = {}
    for field_name, (env_var, description, change_hint) in FIELDS.items():
        if field_name in overrides:
            source = f"environment variable {env_var}"
        elif field_name in file_keys:
            source = f"config file {target}"
        elif field_name in {"data_dir", "db_path"}:
            source = "platform default"
        else:
            source = "built-in default"
        settings[field_name] = Setting(
            name=field_name,
            value=_render(config, field_name),
            source=source,
            env_var=env_var,
            description=description,
            change_hint=change_hint,
        ).to_dict()

    return {
        "config_file": str(target),
        "config_file_exists": target.exists(),
        "precedence": [
            "FLOCHAT_* environment variables",
            f"config file at {target}",
            "built-in defaults",
        ],
        "settings": settings,
        "secrets_policy": (
            "This file holds paths only. Credential values are never stored here and never printed."
        ),
        "read_only": (
            "Phase 02 exposes settings read-only; it writes no configuration. "
            "Edit the file or set an environment variable to change a value."
        ),
    }


def config_file_health(platform: PlatformInfo) -> dict[str, object]:
    """Whether the config file is present, readable, and valid. Used by doctor."""
    target = config_file_path(platform)
    report: dict[str, object] = {"path": str(target), "exists": target.exists()}
    if not target.exists():
        report["valid"] = True
        report["note"] = "No config file; built-in defaults and environment apply."
        return report
    try:
        load_config(env=False, platform=platform, path=target)
    except ConfigurationError as exc:
        report["valid"] = False
        report["error"] = str(exc)
        return report
    report["valid"] = True
    report["readable"] = os.access(target, os.R_OK)
    return report
