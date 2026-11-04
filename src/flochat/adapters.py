"""Platform adapter boundary.

FloChat uses one shared Python core with a thin adapter per platform. This module
defines the contract every adapter must satisfy and the capability report an
adapter must produce.

Phase 01 ships *no* native integration. The adapters below therefore declare
their capabilities as unavailable instead of describing planned features as if
they already worked. ``implemented`` is False everywhere by design: it flips to
True only when a later phase has been verified on real hardware.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from flochat.platform import Capabilities, PlatformInfo, PlatformKey
from flochat.state import AppState, StatusReport


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

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "implemented": self.implemented,
            "state": self.state.value,
            "capabilities": self.capabilities.to_dict(),
            "requirements": list(self.requirements),
            "notes": list(self.notes),
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

    def ensure_available(self) -> StatusReport:
        """Used by future overlay code to fail clearly instead of silently doing nothing."""
        return StatusReport(
            state=AppState.UNSUPPORTED_PLATFORM,
            detail=f"The {self.name} overlay adapter is not implemented in Phase 01.",
            notes=tuple(self.requirements),
        )


class BaseAdapter(PlatformAdapter):
    """Shared behaviour: never report an unverified adapter as available."""

    def report(self, info: PlatformInfo) -> AdapterReport:
        matched = info.key is self.key
        return AdapterReport(
            platform=self.key,
            implemented=False,
            state=AdapterState.NOT_IMPLEMENTED if matched else AdapterState.UNAVAILABLE,
            capabilities=Capabilities(overlay=False, secure_storage=False),
            requirements=self.requirements,
            notes=(
                f"{self.name} adapter boundary defined; no native code ships in Phase 01.",
                "Background and overlay behaviour is unverified on this device.",
            ),
        )


class AndroidAdapter(BaseAdapter):
    key = PlatformKey.ANDROID
    name = "Android"
    requirements = (
        "SYSTEM_ALERT_WINDOW (Display over other apps) for a floating overlay",
        "FOREGROUND_SERVICE and a persistent notification for background work",
        "Battery optimisation exemption, requested with an explanation and revocable",
        "Notification permission on Android 13 and later",
    )

    def secure_storage_note(self) -> str:
        return "Credentials belong in the Android Keystore via the companion APK (Phase 06)."


class WindowsAdapter(BaseAdapter):
    key = PlatformKey.WINDOWS
    name = "Windows"
    requirements = (
        "A WinUI/C# overlay process for always-on-top panels",
        "Windows Defender SmartScreen reputation for distributed binaries",
        "No elevation: FloChat must not require administrator rights",
    )

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

    def secure_storage_note(self) -> str:
        return "Credentials belong in Secret Service via libsecret where available (Phase 06)."


class MacOSAdapter(BaseAdapter):
    key = PlatformKey.MACOS
    name = "macOS"
    requirements = (
        "Swift/AppKit panel for floating or menu-bar access",
        "Accessibility or Screen Recording permission only if a feature truly needs it",
        "Gatekeeper notarisation for distributed binaries",
    )

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
