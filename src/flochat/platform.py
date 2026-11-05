"""Platform detection and capability reporting.

This module answers one question honestly: what can FloChat rely on *here*?
It never assumes that a documented platform integration exists. Overlay and
secure-storage capabilities are reported as unavailable until a later phase
implements and verifies them on real hardware.
"""

from __future__ import annotations

import os
import platform
import sqlite3
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from flochat import __version__

ANDROID_KEYSTORES = ("com.termux", "com.termux.api", "com.android.terminal")


class PlatformKey(str, Enum):
    ANDROID = "android"
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


#: Minimum SQLite version FloChat is willing to rely on (window functions, UPSERT).
MIN_SQLITE = (3, 35, 0)


@dataclass(frozen=True)
class Capabilities:
    """Capabilities that this build can state truthfully.

    These are conservative verification flags, not mere source-presence claims.
    A topmost hint is not proof of global overlay behavior or a working OS vault.
    """

    overlay: bool = False
    secure_storage: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {"overlay": self.overlay, "secure_storage": self.secure_storage}


def _detect_platform() -> PlatformKey:
    if os.name == "nt" or sys.platform == "win32":
        return PlatformKey.WINDOWS
    if sys.platform == "darwin":
        return PlatformKey.MACOS
    if sys.platform.startswith("linux"):
        prefix = os.environ.get("PREFIX", "")
        if "com.termux" in prefix or Path("/system/build.prop").exists():
            return PlatformKey.ANDROID
        if any(key in prefix for key in ANDROID_KEYSTORES) and Path("/system").exists():
            return PlatformKey.ANDROID
        return PlatformKey.LINUX
    return PlatformKey.UNKNOWN


def _detect_shell() -> str | None:
    if os.name == "nt":
        raw = os.environ.get("COMSPEC") or os.environ.get("SHELL") or ""
        return Path(raw).stem.lower() or None
    raw = os.environ.get("SHELL", "")
    return Path(raw).name or None


def _detect_terminal() -> str | None:
    for variable in ("TERM_PROGRAM", "WT_SESSION", "KONSOLE_VERSION", "TERMUX_VERSION"):
        value = os.environ.get(variable)
        if value:
            return value if variable != "WT_SESSION" else "Windows Terminal"
    return os.environ.get("TERM") or None


def _detect_filesystem() -> str:
    """Report whether the relevant filesystem is case sensitive, where knowable."""
    if os.name == "nt" or sys.platform == "darwin":
        return "insensitive"
    return "unknown"


def _sqlite_version() -> tuple[int, int, int]:
    try:
        raw = sqlite3.sqlite_version.split(".")
        return (int(raw[0]), int(raw[1]), int(raw[2]) if len(raw) > 2 else 0)
    except (ValueError, IndexError):  # pragma: no cover - defensive
        return (0, 0, 0)


def _default_data_dir(key: PlatformKey) -> Path:
    if key is PlatformKey.WINDOWS:
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "FloChat"
        return Path.home() / "AppData" / "Roaming" / "FloChat"
    if key is PlatformKey.MACOS:
        return Path.home() / "Library" / "Application Support" / "FloChat"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "flochat"
    return Path.home() / ".config" / "flochat"


@dataclass(frozen=True)
class PlatformInfo:
    """Immutable description of the environment FloChat is running in."""

    key: PlatformKey
    system: str
    release: str
    machine: str
    is_termux: bool
    is_mobile: bool
    shell: str | None
    terminal: str | None
    interactive: bool
    filesystem: str
    capabilities: Capabilities
    notes: tuple[str, ...]

    @property
    def supported(self) -> bool:
        """This build supports the four documented terminal platforms only."""
        return self.key is not PlatformKey.UNKNOWN

    @property
    def label(self) -> str:
        return self.key.value

    def default_data_dir(self) -> Path:
        return _default_data_dir(self.key)

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.key.value,
            "system": self.system,
            "release": self.release,
            "machine": self.machine,
            "is_termux": self.is_termux,
            "is_mobile": self.is_mobile,
            "shell": self.shell,
            "terminal": self.terminal,
            "interactive": self.interactive,
            "filesystem": self.filesystem,
            "supported": self.supported,
            "capabilities": self.capabilities.to_dict(),
            "notes": list(self.notes),
        }


def detect() -> PlatformInfo:
    """Inspect the current environment. Cheap, non-mutating, no side effects."""
    key = _detect_platform()
    is_termux = bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get(
        "PREFIX", ""
    )
    notes: list[str] = [
        "Interfaces: terminal CLI; optional native controls need platform prerequisites.",
        "Overlays: implementation present; native window/compositor verification pending.",
        "Background execution: explicit local owner; no automatic session or consent recovery.",
    ]
    interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())
    try:
        sqlite_ok = _sqlite_version() >= MIN_SQLITE
    except Exception:  # pragma: no cover - defensive
        sqlite_ok = False
    if not sqlite_ok:
        notes.append(
            f"SQLite {sqlite3.sqlite_version} is older than the supported {MIN_SQLITE[0]}."
            f"{MIN_SQLITE[1]}.{MIN_SQLITE[2]}."
        )
    if key is PlatformKey.ANDROID and not is_termux:
        notes.append("Android terminal detected without Termux markers; behaviour is unverified.")

    return PlatformInfo(
        key=key,
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        is_termux=is_termux,
        is_mobile=key is PlatformKey.ANDROID,
        shell=_detect_shell(),
        terminal=_detect_terminal(),
        interactive=interactive,
        filesystem=_detect_filesystem(),
        capabilities=Capabilities(),
        notes=tuple(notes),
    )


def describe() -> dict[str, object]:
    """Runtime details useful in diagnostics: versions, interpreter, and platform."""
    info = detect()
    return {
        "flochat_version": __version__,
        "python": platform.python_version(),
        "interpreter": sys.executable,
        "sqlite": sqlite3.sqlite_version,
        **info.to_dict(),
    }
