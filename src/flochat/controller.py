"""Application controller.

The controller is the only place where configuration, platform detection,
storage, lifecycle, and the YouTube boundaries are combined. The CLI stays a
thin argument parser on top of it, which keeps future interfaces (a floating
panel, a companion app) able to reuse exactly the same behaviour.

This layer is kept small on purpose: every method reports what is real.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flochat import __version__
from flochat.adapters import adapter_reports, current_adapter
from flochat.comments import CommentManager, approval_report
from flochat.config import AppConfig, load_config, sample_config
from flochat.database import Database
from flochat.errors import FloChatError
from flochat.lifecycle import SessionManager, describe_mode
from flochat.platform import PlatformInfo, detect
from flochat.roadmap import deferred_operations, implemented_operations, phase_label
from flochat.state import AppState, StatusReport
from flochat.youtube import YouTubeIntegration
from flochat.youtube import describe as describe_youtube


@dataclass
class Controller:
    """Coordinates the core boundaries."""

    config: AppConfig
    platform: PlatformInfo
    sessions: SessionManager

    @classmethod
    def create(cls, *, use_env: bool = True, platform: PlatformInfo | None = None) -> Controller:
        info = platform or detect()
        config = load_config(env=use_env, platform=info)
        return cls(config=config, platform=info, sessions=SessionManager(config))

    @classmethod
    def degraded(cls, *, platform: PlatformInfo | None = None) -> Controller:
        """Build a controller from built-in defaults without reading any config file.

        Used by ``flochat doctor`` so that a broken configuration is *reported*
        by the diagnostic tool instead of preventing it from running.
        """
        info = platform or detect()
        config = AppConfig()
        return cls(config=config, platform=info, sessions=SessionManager(config))

    # --- informational -------------------------------------------------

    def version_report(self) -> dict[str, object]:
        return {
            "name": "FloChat",
            "version": __version__,
            "tagline": "Your Live Chat, Always Within Reach.",
            "phase": phase_label(),
        }

    def status_report(self) -> dict[str, object]:
        """Status built from real observations, not from assumed capabilities."""
        adapter = current_adapter(self.platform)
        youtube = describe_youtube(self.config.client_secret, self.config.token_file)
        database = self._database_check()
        from flochat.runtime import owner_status

        owner = owner_status(self.config)
        if "editor" in owner:
            owner["editor"] = {
                "character_count": owner["editor"].get("character_count", 0),
                "content_redacted": True,
            }
        return {
            "flochat": self.version_report(),
            "platform": self.platform.to_dict(),
            "adapter": adapter.report(self.platform).to_dict() if adapter else None,
            "config": self.config.to_public_dict(platform=self.platform),
            "session": owner.get("safety", self.sessions.session.to_dict()),
            "runtime": owner,
            "youtube": youtube,
            "recovery": self.recovery_report(),
            "submission_gate": self.approval_gate(),
            "database": database,
            "implemented_operations": implemented_operations(),
            "deferred_operations": deferred_operations(),
        }

    def recovery_report(self) -> dict[str, object]:
        """What recovery would do. Never restores or resubmits anything."""
        report = self.sessions.recover()
        return {
            "state": report.state.value,
            "detail": report.detail,
            "confirmed": report.confirmed,
            "notes": list(report.notes),
            "automatic_resubmission": False,
        }

    def approval_gate(self) -> list[dict[str, object]]:
        """Show that the submission gate refuses unapproved work, without submitting."""
        return [
            {"approved": True, **approval_report(True).to_dict()},
            {"approved": False, **approval_report(False).to_dict()},
        ]

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

    def manage_comments(self, group: str, action: str, **options) -> dict:
        """Open configured local storage, dispatch one atomic operation, then close."""
        with Database(self.config.resolved_db_path) as database:
            database.initialize()
            manager = CommentManager(database)
            operations = {
                "username": manager.username,
                "comment": manager.comment,
                "drafts": manager.drafts,
                "history": manager.history,
            }
            return operations[group](action, **options)

    def manage_youtube(self, action: str, **options) -> dict:
        """One explicit integration action, reusing configured storage and platform."""
        with Database(self.config.resolved_db_path) as database:
            database.initialize()
            return YouTubeIntegration(database, self.config, self.platform).run(action, **options)

    def safety_console(self) -> int:
        """Foreground session, no approvals or READY state restored on restart."""
        from flochat.runtime import terminal

        return terminal(self.config)

    # --- lifecycle -----------------------------------------------------

    def override_mode(self, mode: str) -> None:
        """Apply a one-run mode override without touching the stored configuration."""
        self.config = self.config.model_copy(update={"mode": mode})
        self.sessions = SessionManager(self.config)

    def start(self) -> StatusReport:
        from flochat.ipc import Client
        from flochat.runtime import launch

        status = launch(self.config, core_only=True)
        if status["mode"] != self.config.mode:
            Client(self.config).call("mode", value=self.config.mode)
        Client(self.config).call("start")
        return StatusReport(
            state=AppState.SUCCESS,
            detail="Shared safety session started; no approval or submission.",
            confirmed=True,
        )

    def stop(self) -> StatusReport:
        from flochat.ipc import Client

        result = Client(self.config).call("stop")
        if result["session"] == "SUBMITTING":
            return StatusReport(
                state=AppState.PENDING,
                detail="Stop requested; an in-flight write cannot be recalled. "
                "Await its actual outcome.",
            )
        return StatusReport(
            state=AppState.SUCCESS,
            detail="Shared session stopped; in-flight requests cannot be recalled.",
            confirmed=True,
        )

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
