"""The approved roadmap and the CLI surface this build actually provides.

One source of truth. ``flochat version``, ``flochat status``, and
``flochat doctor`` all read these constants, so the CLI cannot drift from what it
claims to offer — which is exactly what happened in Phase 01, where ``status``
listed six operations and silently omitted ``state``.

``IMPLEMENTED_OPERATIONS`` is checked against the real parser by ``flochat
doctor``, so adding a command without listing it here (or listing one that does
not exist) is reported as a failure rather than discovered later.
"""

from __future__ import annotations

#: The eight approved phases. This tuple is not extensible within a phase.
PHASES: tuple[tuple[str, str, str], ...] = (
    ("01", "Foundation", "complete"),
    ("02", "CLI & Installation", "complete"),
    ("03", "Comment Manager", "complete"),
    ("04", "YouTube Integration", "implemented; live verification blocked"),
    ("05", "Safety Engine", "implemented; live write unverified"),
    (
        "06",
        "Floating & Background Engine",
        "implemented; native verification pending",
    ),
    ("07", "Cross-Platform Testing", "tested; platform verification partially blocked"),
    ("08", "Final Release", "audited; not release ready — project licence unresolved"),
)

#: The phase this build implements.
CURRENT_PHASE = 8

#: Command actions registered in this build, in the spelling used by the CLI.
#: ``config show`` and ``config validate`` count as separate actions.
IMPLEMENTED_OPERATIONS: tuple[str, ...] = (
    "version",
    "status",
    "state",
    "settings",
    "doctor",
    "platform",
    "config show",
    "config validate",
    "start",
    "stop",
    "username set",
    "username show",
    "username delete",
    "comment new",
    "comment edit",
    "comment show",
    "comment clear",
    "comment generate",
    "comment preview",
    "drafts list",
    "drafts save",
    "drafts open",
    "drafts rename",
    "drafts delete",
    "history list",
    "history clear",
    "youtube status",
    "youtube connect",
    "youtube disconnect",
    "youtube account",
    "youtube streams",
    "youtube inspect",
    "youtube select",
    "safety",
    "panel start",
    "panel serve",
    "panel view",
    "panel stop",
    "panel status",
    "panel pair",
    "session",
    "mode",
)

#: Approved work that this build deliberately does not perform, with its phase.
DEFERRED_OPERATIONS: tuple[tuple[str, str], ...] = (("Cross-platform runtime verification", "07"),)


def current_phase() -> tuple[str, str, str]:
    """The active phase as ``(number, name, status)``."""
    return PHASES[CURRENT_PHASE - 1]


def phase_label() -> str:
    """Human-readable label, for example ``Phase 02 - CLI & Installation``."""
    number, name, _ = current_phase()
    return f"Phase {number} - {name}"


def implemented_operations() -> list[str]:
    """Every CLI action this build provides."""
    return list(IMPLEMENTED_OPERATIONS)


def deferred_operations() -> list[str]:
    """Deferred work annotated with the phase that owns it."""
    return [f"{operation} (Phase {phase})" for operation, phase in DEFERRED_OPERATIONS]
