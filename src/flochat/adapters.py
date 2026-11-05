"""Platform adapter boundary.

FloChat uses one shared Python core with a thin adapter per platform. This module
defines the contract every adapter must satisfy and the capability report an
adapter must produce.

Source integrations are present. Launch prerequisites and runtime verification
are distinct: no platform is certified merely because its source or dependency exists.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from flochat.platform import Capabilities, PlatformInfo, PlatformKey


class AdapterState(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"


@dataclass(frozen=True)
class AdapterReport:
    """What an adapter can truthfully do right now."""

    platform: PlatformKey
    implemented: bool
    state: AdapterState
    capabilities: Capabilities
    requirements: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    secure_storage_target: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "implemented": self.implemented,
            "runtime_verified": False,
            "state": self.state.value,
            "capabilities": self.capabilities.to_dict(),
            "requirements": list(self.requirements),
            "notes": list(self.notes),
            "secure_storage_target": self.secure_storage_target,
        }


class PlatformAdapter(ABC):
    """Contract for a platform adapter. Implementations arrive in Phase 06."""

    key: PlatformKey

    #: Human-readable platform name used in status output.
    name: str

    #: Operating system permissions an overlay would need. Documented, not requested.
    requirements: tuple[str, ...] = ()

    @abstractmethod
    def report(self, info: PlatformInfo) -> AdapterReport:
        """Describe the adapter's real state for the running environment."""


class BaseAdapter(PlatformAdapter):
    """Separate source presence, launch prerequisites and actual native verification."""

    def report(self, info: PlatformInfo) -> AdapterReport:
        from flochat.runtime import panel_capability

        capability = panel_capability(info)
        matched = info.key is self.key
        return AdapterReport(
            platform=self.key,
            implemented=True,
            state=AdapterState.AVAILABLE
            if matched and capability["launchable"]
            else AdapterState.UNAVAILABLE,
            capabilities=Capabilities(overlay=False, secure_storage=False),
            requirements=self.requirements,
            notes=(
                "UI implementation present; runtime/platform restrictions "
                "still require native verification.",
                capability["warning"],
                "AVAILABLE means launch prerequisites, not verified "
                "stacking or credential vault success.",
            ),
            secure_storage_target=self.secure_storage_note,
        )


class AndroidAdapter(BaseAdapter):
    key = PlatformKey.ANDROID
    name = "Android"
    requirements = (
        "SYSTEM_ALERT_WINDOW (Display over other apps) for a floating overlay",
        "FOREGROUND_SERVICE and a persistent notification for background work",
        "Battery optimisation/Termux process limits; no automatic exemption or indefinite uptime",
        "Notification permission on Android 13 and later",
    )

    @property
    def secure_storage_note(self) -> str:
        return "Credentials belong in the Android Keystore via the companion APK (Phase 06)."


class WindowsAdapter(BaseAdapter):
    key = PlatformKey.WINDOWS
    name = "Windows"
    requirements = (
        "Qt native Windows window, optional desktop extra; no administrator rights",
        "Windows Defender SmartScreen reputation for distributed binaries",
        "No elevation: FloChat must not require administrator rights",
    )

    @property
    def secure_storage_note(self) -> str:
        return "Credentials belong in Windows Credential Manager (DPAPI) in Phase 06."


class LinuxAdapter(BaseAdapter):
    key = PlatformKey.LINUX
    name = "Linux"
    requirements = (
        "Qt panel where a compositor supports always-on-top windows",
        "Wayland restrictions acknowledged; behaviour differs from X11",
        "libsecret/Secret Service for credential storage where available",
    )

    @property
    def secure_storage_note(self) -> str:
        return "Credentials belong in Secret Service via libsecret where available (Phase 06)."


class MacOSAdapter(BaseAdapter):
    key = PlatformKey.MACOS
    name = "macOS"
    requirements = (
        "Qt Cocoa native window and optional desktop extra; no "
        "Accessibility or Screen Recording required",
        "Accessibility or Screen Recording permission only if a feature truly needs it",
        "Gatekeeper notarisation for distributed binaries",
    )

    @property
    def secure_storage_note(self) -> str:
        return "Credentials belong in the macOS Keychain (Phase 06)."


#: Registry used by the CLI and by future phases.
ADAPTERS: dict[PlatformKey, PlatformAdapter] = {
    PlatformKey.ANDROID: AndroidAdapter(),
    PlatformKey.WINDOWS: WindowsAdapter(),
    PlatformKey.LINUX: LinuxAdapter(),
    PlatformKey.MACOS: MacOSAdapter(),
}


def adapter_reports(info: PlatformInfo) -> list[AdapterReport]:
    """Every adapter with its honest state and whether it matches this machine."""
    return [adapter.report(info) for adapter in ADAPTERS.values()]


def current_adapter(info: PlatformInfo) -> PlatformAdapter | None:
    return ADAPTERS.get(info.key)
