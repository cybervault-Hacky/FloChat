"""Application controller.

The controller is the only place where configuration, platform detection,
storage, lifecycle, and the YouTube boundaries are combined. The CLI stays a
thin argument parser on top of it, which keeps future interfaces (a floating
panel, a companion app) able to reuse exactly the same behaviour.

Phase 01 keeps this intentionally small: every method reports what is real.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flochat import __version__
from flochat.adapters import adapter_reports, current_adapter
from flochat.config import AppConfig, load_config, sample_config
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.lifecycle import SessionManager, describe_mode
from flochat.platform import PlatformInfo, detect
from flochat.state import AppState, StatusReport
from flochat.youtube import OAuthBoundary


@dataclass
class Controller:
    """Coordinates the Phase 01 boundaries."""

    config: AppConfig
    platform: PlatformInfo
    sessions: SessionManager

    @classmethod
    def create(cls, *, use_env: bool = True, platform: PlatformInfo | None = None) -> Controller:
        info = platform or detect()
        config = load_config(env=use_env, platform=info)
        return cls(config=config, platform=info, sessions=SessionManager(config))

    # --- informational -------------------------------------------------

    def version_report(self) -> dict[str, object]:
        return {
            "name": "FloChat",
            "version": __version__,
            "tagline": "Your Live Chat, Always Within Reach.",
            "phase": "Phase 01 - Foundation",
        }

    def status_report(self) -> dict[str, object]:
        """Status built from real observations, not from assumed capabilities."""
        adapter = current_adapter(self.platform)
        auth = OAuthBoundary(self.config.client_secret, self.config.token_file).status()
        database = self._database_check()
        return {
            "flochat": self.version_report(),
            "platform": self.platform.to_dict(),
            "adapter": adapter.report(self.platform).to_dict() if adapter else None,
            "config": self.config.to_public_dict(platform=self.platform),
            "session": self.sessions.session.to_dict(),
            "authentication": auth.to_report().to_dict(),
            "database": database,
            "implemented_operations": [
                "version",
                "status",
                "config show",
                "platform",
                "start",
                "stop",
            ],
            "deferred_operations": [
                "OAuth sign in (Phase 04)",
                "Live chat discovery (Phase 04)",
                "Comment preparation and history (Phase 03)",
                "Submission approval and safety checks (Phase 05)",
                "Overlays and background service (Phase 06)",
            ],
        }

    def config_report(self, *, include_env: bool = True) -> dict[str, object]:
        baseline = load_config(env=False, platform=self.platform)
        return {
            "effective": self.config.to_public_dict(platform=self.platform),
            "persisted": baseline.to_public_dict(platform=self.platform),
            "env_override_active": include_env and self.config != baseline,
            "file_defaults": sample_config(self.platform),
            "modes": describe_mode(self.config),
            "precedence": [
                "FLOCHAT_* environment variables",
                "config.json in the platform data directory",
                "built-in defaults",
            ],
            "secrets": "Never stored here; OAuth material is referenced by path only.",
        }

    def platform_report(self) -> dict[str, object]:
        return {
            "detected": self.platform.to_dict(),
            "adapters": [report.to_dict() for report in adapter_reports(self.platform)],
        }

    # --- lifecycle -----------------------------------------------------

    def override_mode(self, mode: str) -> None:
        """Apply a one-run mode override without touching the stored configuration."""
        self.config = self.config.model_copy(update={"mode": mode})
        self.sessions = SessionManager(self.config)

    def start(self) -> StatusReport:
        if not self.platform.supported:
            return StatusReport(
                state=AppState.UNSUPPORTED_PLATFORM,
                detail=f"Platform {self.platform.system!r} is outside the four documented targets.",
            )
        report = self.sessions.start()
        if self.config.mode == "persistent":
            adapter = current_adapter(self.platform)
            requirements = adapter.requirements if adapter else ()
            return StatusReport(
                state=AppState.PERMISSION_REQUIRED,
                detail=report.detail,
                notes=tuple(requirements) or report.notes,
            )
        return report

    def stop(self) -> StatusReport:
        return self.sessions.stop()

    # --- internal ------------------------------------------------------

    def _database_check(self) -> dict[str, object]:
        """Open the database read-only in spirit: verify it, then close it."""
        path: Path = self.config.resolved_db_path
        existed = path.exists()
        try:
            with Database(path) as database:
                database.initialize()
                check = database.check()
        except FloChatError as exc:
            return {
                "path": str(path),
                "healthy": False,
                "error": str(exc),
                "existed_before": existed,
            }
        check["created"] = not existed
        return check
