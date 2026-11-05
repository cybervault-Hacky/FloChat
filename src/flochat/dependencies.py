"""Runtime dependency declarations, checked before heavier imports.

Check configuration and Phase 04 transport/OAuth/keyring packages before heavy imports.

``pyproject.toml`` remains the source of truth for installation; this module is
the source of truth for *diagnosis*, and ``flochat doctor`` reports both.
"""

from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version

#: distribution name -> import name -> minimum version, one entry per dependency.
RUNTIME_DEPENDENCIES: dict[str, tuple[str, str, str]] = {
    "pydantic": ("pydantic", "2.6", "3"),
    "google-auth": ("google.auth", "2.38", "3"),
    "google-auth-oauthlib": ("google_auth_oauthlib", "1.2", "2"),
    "requests": ("requests", "2.33.0", "3"),
    "keyring": ("keyring", "25.6", "26"),
}


def _parse(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split("."):
        digits = "".join(char for char in piece if char.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def dependency_status() -> dict[str, dict[str, object]]:
    """Check every runtime dependency. Never imports FloChat's config layer."""
    report: dict[str, dict[str, object]] = {}
    for distribution, (module_name, minimum, maximum) in RUNTIME_DEPENDENCIES.items():
        try:
            importlib.import_module(module_name)
            present = version(distribution)
        except (ImportError, PackageNotFoundError, OSError, RuntimeError, ValueError) as exc:
            # Broken native/binary dependencies must be diagnosed without a traceback
            # or arbitrary import-exception content in ordinary diagnostic output.
            report[distribution] = {
                "available": False,
                "required": f">={minimum},<{maximum}",
                "error": f"{type(exc).__name__}: dependency could not be loaded",
            }
            continue
        satisfied = _parse(minimum) <= _parse(present) < _parse(maximum)
        report[distribution] = {
            "available": True,
            "present": present,
            "required": f">={minimum},<{maximum}",
            "satisfied": satisfied,
        }
    return report


def missing_runtime_dependencies() -> dict[str, dict[str, object]]:
    """Dependencies that are absent or too old. Empty means the environment is usable."""
    return {
        name: status
        for name, status in dependency_status().items()
        if not status.get("available") or not status.get("satisfied", False)
    }


def install_hint() -> str:
    """The exact command a user can run to repair the environment."""
    return "python -m pip install -e ."
