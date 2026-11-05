"""Environment diagnosis behind ``flochat doctor``.

Every check here observes something real and reports what it found. A check that
cannot be performed reports ``skip`` with the reason, never ``ok``. The whole
command makes no network requests or credential changes; its storage check
may initialize/migrate the local database. OAuth setup is checked without unlocking tokens.

The intended use is the one that actually helps a stuck user: run it *after* an
installer fails, or when ``flochat`` behaves unexpectedly, and get a numbered list
of what is wrong with a specific next step for each finding.
"""

from __future__ import annotations

import importlib
import os
import platform
import sqlite3
import sys
import sysconfig
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from flochat import __version__
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.platform import MIN_SQLITE, PlatformInfo
from flochat.roadmap import CURRENT_PHASE, IMPLEMENTED_OPERATIONS, phase_label
from flochat.settings import config_file_health

if TYPE_CHECKING:
    from flochat.config import AppConfig

MIN_PYTHON = (3, 10)

OK = "ok"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

_ORDER = {FAIL: 0, WARN: 1, OK: 2, SKIP: 3}


@dataclass
class Finding:
    """One observed fact about the environment."""

    check: str
    status: str
    detail: str
    remedy: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = {"status": self.status, "detail": self.detail}
        if self.remedy:
            payload["remedy"] = self.remedy
        return payload


@dataclass
class Diagnosis:
    findings: dict[str, Finding] = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings[finding.check] = finding

    @property
    def worst(self) -> str:
        return min((f.status for f in self.findings.values()), key=_ORDER.__getitem__, default=OK)

    @property
    def problems(self) -> list[Finding]:
        """Failures and warnings, worst first: this is the actionable list."""
        return sorted(
            (f for f in self.findings.values() if f.status in {FAIL, WARN}),
            key=lambda f: _ORDER[f.status],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.worst,
            "problems": [f.check for f in self.problems],
            "findings": {name: finding.to_dict() for name, finding in self.findings.items()},
        }


def _check_platform_runtime() -> Finding:
    """Interpreter identity and runtime versions, useful when reporting a bug."""
    from flochat.platform import describe

    detail = describe()
    return Finding(
        "runtime",
        OK,
        f"FloChat {detail['flochat_version']}, Python {detail['python']}, "
        f"SQLite {detail['sqlite']} at {detail['interpreter']}",
    )


def _check_python() -> Finding:
    current = sys.version_info[:3]
    version = platform.python_version()
    if current < MIN_PYTHON:
        return Finding(
            "python",
            FAIL,
            f"Python {version} is older than the required {MIN_PYTHON[0]}.{MIN_PYTHON[1]}.",
            f"Install Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, then re-run install.",
        )
    where = sys.executable or "unknown"
    if not Path(where).exists():
        return Finding(
            "python",
            WARN,
            f"Python {version} is running but sys.executable does not exist: {where}",
            "Recreate the environment: remove .venv, then run the installer again.",
        )
    return Finding("python", OK, f"Python {version} at {where}")


def _check_dependencies() -> list[Finding]:
    from flochat.dependencies import dependency_status, install_hint

    findings = []
    for name, status in dependency_status().items():
        healthy = status.get("available") and status.get("satisfied")
        findings.append(
            Finding(
                f"dependency:{name}",
                OK if healthy else FAIL,
                f"{name}: {status.get('present', 'missing')}; requires {status['required']}",
                "" if healthy else install_hint(),
            )
        )
    findings.append(_check_package_origin())
    return findings


def _check_package_origin() -> Finding:
    """Is FloChat importable, and from where? A stale copy is a real failure mode."""
    try:
        module = importlib.import_module("flochat")
    except ImportError as exc:  # pragma: no cover - cannot happen while running
        return Finding("package", FAIL, f"flochat is not importable: {exc}")
    location = getattr(module, "__file__", None) or "unknown"
    return Finding("package", OK, f"flochat {__version__} imported from {location}")


def _is_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(
        os.environ.get("CONDA_PREFIX")
    )


def _inside_repository() -> bool:
    """True when the running package lives inside the project's own src tree."""
    module = sys.modules.get("flochat")
    location = getattr(module, "__file__", None)
    if not location:
        return False
    path = Path(location).resolve()
    return path.parent.name == "flochat" and path.parent.parent.name == "src"


def _check_environment() -> Finding:
    """An editable install must be inside a virtual environment.

    Running ``pip install`` against a system interpreter is exactly what the
    installers avoid, so report it rather than quietly accepting it.
    """
    if _is_virtualenv():
        return Finding("environment", OK, f"Isolated environment active ({sys.prefix})")
    if _inside_repository():
        return Finding(
            "environment",
            FAIL,
            "FloChat is running from the repository without a virtual environment.",
            "Run ./install.sh (or .\\install.ps1) to create .venv, then use ./start.sh.",
        )
    return Finding(
        "environment",
        WARN,
        f"Not running inside a virtual environment (interpreter: {sys.prefix}).",
        "Install into a virtual environment; see the installation section of README.md.",
    )


def _check_sqlite() -> Finding:
    version = sqlite3.sqlite_version
    try:
        parsed = tuple(int(part) for part in version.split(".")[:3])
    except ValueError:  # pragma: no cover - defensive
        return Finding("sqlite", WARN, f"Could not parse SQLite version {version!r}.")
    if parsed < MIN_SQLITE:
        return Finding(
            "sqlite",
            FAIL,
            f"SQLite {version} is older than the required {'.'.join(map(str, MIN_SQLITE))}.",
            "Use a newer Python build, which bundles a newer SQLite.",
        )
    return Finding("sqlite", OK, f"SQLite {version}")


def _check_storage(config: AppConfig) -> Finding:
    """Verify the database opens and its directory is writable.

    Opening the database applies the schema, the same operation ``status``
    performs. Nothing here invents data or hides a failure.
    """
    path = config.resolved_db_path
    parent = path.parent
    if parent.exists() and not os.access(parent, os.W_OK):
        return Finding(
            "storage",
            FAIL,
            f"The data directory {parent} is not writable.",
            "Fix ownership or choose another directory with FLOCHAT_HOME.",
        )
    try:
        with Database(path) as database:
            database.initialize()
            check = database.check()
    except FloChatError as exc:
        return Finding(
            "database",
            FAIL,
            str(exc),
            "Move the file aside to start fresh, or fix permissions on its directory.",
        )
    if not check.get("healthy"):
        return Finding(
            "database",
            FAIL,
            f"Database integrity check failed: {check.get('integrity')}",
            "Back up and remove the file so FloChat can rebuild it.",
        )
    return Finding("database", OK, f"{path} (schema v{check.get('schema_version')})")


def _check_configuration(platform_info: PlatformInfo) -> Finding:
    """Validate the configuration file; imports pydantic only because it is needed here."""
    try:
        from flochat.config import ConfigurationError as _ConfigError  # noqa: F401
    except ImportError:
        return Finding(
            "configuration",
            FAIL,
            "Cannot validate configuration because pydantic is not importable.",
            "Re-run the installer, or pip install 'pydantic>=2.6,<3' in this environment.",
        )
    return _check_configuration_file(platform_info)


def _check_configuration_file(platform_info: PlatformInfo) -> Finding:
    health = config_file_health(platform_info)
    if not health.get("valid"):
        return Finding(
            "configuration",
            FAIL,
            f"{health['path']}: {health.get('error')}",
            "Fix or remove the config file; `flochat settings` shows the expected shape.",
        )
    if not health["exists"]:
        return Finding("configuration", OK, "No config file; defaults and environment apply.")
    return Finding("configuration", OK, f"{health['path']} is valid")


def _check_platform(platform_info: PlatformInfo) -> Finding:
    if not platform_info.supported:
        return Finding(
            "platform",
            FAIL,
            f"{platform_info.system} is not one of the four supported targets.",
            "FloChat supports Android/Termux, Windows, Linux, and macOS terminals.",
        )
    label = f"{platform_info.label} ({platform_info.system} {platform_info.release})"
    if platform_info.key.value == "android" and not platform_info.is_termux:
        return Finding(
            "platform",
            WARN,
            f"{label}: Android without Termux markers.",
            "Termux is the supported Android terminal; other terminals are unverified.",
        )
    return Finding("platform", OK, label)


def _check_venv_support() -> Finding:
    """A missing ensurepip/venv module is the usual cause of install failure."""
    try:
        venv.EnvBuilder(with_pip=True)
    except Exception as exc:
        return Finding(
            "venv_support",
            FAIL,
            f"Python cannot create a virtual environment with pip: {exc}",
            "On Debian/Ubuntu install python3-venv; on Termux run pkg install python.",
        )
    schemedir = sysconfig.get_paths().get("stdlib")
    if not schemedir:
        return Finding("venv_support", WARN, "Standard library path is unknown to sysconfig.")
    return Finding("venv_support", OK, "Python can create an isolated environment with pip")


def _check_cli_surface() -> Finding:
    """The parser must expose exactly the operations this build claims to provide.

    This is what caught the Phase 01 drift where ``status`` listed six operations
    and omitted ``state``.
    """
    import argparse

    from flochat.cli import build_parser

    def leaves(parser, prefix=""):
        subactions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subactions:
            return {prefix.strip()}
        return {
            leaf
            for action in subactions
            for name, child in action.choices.items()
            for leaf in leaves(child, f"{prefix}{name} ")
        }

    actual = leaves(build_parser())
    declared = set(IMPLEMENTED_OPERATIONS)
    if actual != declared:
        return Finding(
            "cli_surface",
            FAIL,
            f"CLI mismatch: missing {sorted(declared - actual)}, "
            f"unlisted {sorted(actual - declared)}.",
            "Fix the parser or roadmap so every action agrees.",
        )
    return Finding("cli_surface", OK, f"{len(actual)} declared CLI actions match the parser.")


def _check_documentation() -> Finding:
    """The phase label in the README must match the code's current phase."""
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    if not readme.exists():
        return Finding("documentation", SKIP, "README.md not found beside the package.")
    text = readme.read_text(encoding="utf-8", errors="ignore")
    label = phase_label()
    if f"Phase 0{CURRENT_PHASE}" in text and "Completion Report" in text:
        return Finding("documentation", OK, f"README.md documents {label} and a completion report.")
    return Finding(
        "documentation",
        WARN,
        "README.md does not appear to document the current phase.",
        "Update the root README.md; it is the single source of documentation.",
    )


def _check_safety_gate() -> Finding:
    """Prove the submission gate still refuses unsafe calls.

    This deliberately tests only refusal without a bound SafetyEngine approval.
    It is not a live write test or a full SafetyEngine audit; verify_safety.py
    exercises the gate with mocked API writes. Doctor never grants approval.
    """
    from flochat.comments import SubmissionRequest, submit
    from flochat.errors import ApprovalRequiredError, NotSupportedYetError

    try:
        submit(SubmissionRequest("test", "chat", approved=False))
    except ApprovalRequiredError:
        pass
    except Exception as exc:
        return Finding(
            "safety_gate",
            FAIL,
            f"Unapproved submission raised {type(exc).__name__} instead of being blocked.",
            "Stop and report this; the approval guard is not working.",
        )
    else:
        return Finding(
            "safety_gate",
            FAIL,
            "An unapproved submission was accepted.",
            "Stop and report this; the approval guard is not working.",
        )

    try:
        submit(SubmissionRequest("test", "chat", approved=True))
    except NotSupportedYetError:
        return Finding(
            "safety_gate",
            OK,
            (
                "Unapproved input is blocked; approved input still refuses to send"
                " (no bound safety approval supplied)."
            ),
        )
    except Exception as exc:
        return Finding("safety_gate", WARN, f"Unexpected result from submit: {type(exc).__name__}")
    return Finding("safety_gate", WARN, "An approved submission did not report as unimplemented.")


def _check_launch_scripts() -> Finding:
    """The launch scripts are the documented entry point after installation."""
    root = Path(__file__).resolve().parent.parent.parent
    expected = ("install.sh", "start.sh", "install.ps1", "start.ps1", "scripts/install_lib.sh")
    missing = [name for name in expected if not (root / name).exists()]
    if len(missing) == len(expected):
        return Finding(
            "launch_scripts",
            SKIP,
            "No repository scripts found; this looks like a packaged install.",
        )
    if missing:
        return Finding(
            "launch_scripts",
            WARN,
            f"Missing from {root}: {', '.join(missing)}",
            "Re-clone the repository; the launch scripts are tracked files.",
        )
    return Finding("launch_scripts", OK, "Installer and launcher scripts are present")


def _check_youtube_setup(config: AppConfig) -> Finding:
    """Configuration/backend inspection only; never unlock credentials or use network."""
    from flochat.youtube import CredentialStore, YouTubeError, _client_configuration

    if config.token_file is not None:
        return Finding(
            "youtube_setup",
            WARN,
            "Legacy token-file authentication is disabled.",
            "Unset FLOCHAT_TOKEN_FILE; use youtube connect with an OS keyring.",
        )
    if config.client_secret is None:
        return Finding(
            "youtube_setup",
            SKIP,
            "Optional YouTube authorization not configured; local manager unaffected.",
        )
    try:
        _client_configuration(config.client_secret)
        CredentialStore()
    except YouTubeError as exc:
        return Finding("youtube_setup", FAIL, str(exc), "See Phase 04 setup in README.md.")
    return Finding(
        "youtube_setup",
        OK,
        "Desktop client file and approved backend found; live authorization NOT verified.",
    )


def diagnose(
    config: AppConfig, *, platform_info: PlatformInfo, configuration_error: str | None = None
) -> Diagnosis:
    """Run every check and collect the findings."""
    diagnosis = Diagnosis()
    diagnosis.add(_check_platform(platform_info))
    diagnosis.add(_check_python())
    diagnosis.add(_check_platform_runtime())
    for finding in _check_dependencies():
        diagnosis.add(finding)
    diagnosis.add(_check_environment())
    diagnosis.add(_check_venv_support())
    diagnosis.add(_check_sqlite())
    if configuration_error is None:
        diagnosis.add(_check_storage(config))
        diagnosis.add(_check_configuration(platform_info))
    else:
        diagnosis.add(
            Finding("database", SKIP, "Invalid configuration; no fallback database opened.")
        )
        diagnosis.add(
            Finding("configuration", FAIL, configuration_error, "Fix settings and rerun doctor.")
        )
    diagnosis.add(_check_launch_scripts())
    diagnosis.add(_check_safety_gate())
    diagnosis.add(_check_youtube_setup(config))
    from flochat.runtime import panel_capability

    panel = panel_capability(platform_info)
    diagnosis.add(
        Finding(
            "floating_panel",
            OK if panel["launchable"] else SKIP,
            "UI launch prerequisites present, native window behavior still unverified."
            if panel["launchable"]
            else "Optional UI unavailable here (Qt libraries/display or Android "
            "companion required); CLI remains usable.",
        )
    )
    diagnosis.add(_check_cli_surface())
    diagnosis.add(_check_documentation())
    return diagnosis


def render(diagnosis: Diagnosis) -> str:
    """Human-readable report: every check, then the actionable list."""
    lines: list[str] = []
    width = max(len(name) for name in diagnosis.findings)
    for name, finding in diagnosis.findings.items():
        marker = {OK: "ok", WARN: "WARN", FAIL: "FAIL", SKIP: "skip"}[finding.status]
        lines.append(f"{marker:<4} {name:<{width}}  {finding.detail}")
    problems = diagnosis.problems
    if problems:
        lines.append("")
        lines.append("What to do next:")
        for index, finding in enumerate(problems, start=1):
            lines.append(f"  {index}. {finding.check}: {finding.detail}")
            if finding.remedy:
                lines.append(f"     {finding.remedy}")
    else:
        lines.append("")
        lines.append("No problems found. FloChat is installed correctly for a terminal session.")
    return "\n".join(lines)


def exit_code(diagnosis: Diagnosis) -> int:
    """0 when healthy, 1 when anything is wrong, 3 when the platform is unsupported."""
    platform_finding = diagnosis.findings.get("platform")
    if platform_finding and platform_finding.status == FAIL:
        return 3
    return 0 if diagnosis.worst == OK else 1
