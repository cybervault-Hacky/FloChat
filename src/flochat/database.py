"""Local SQLite storage boundary.

Phase 01 implements the boundary and the schema, not the comment workflow:
nothing in this module writes comment history during Phase 01. Every later
component that needs persistence goes through :class:`Database` so that the
storage rules (location, versioning, integrity checks) stay in one place.

Deliberate choices:

* The schema version lives in ``PRAGMA user_version`` rather than in a table, so
  the database stays a single file with a single source of truth.
* ``comment_history`` records the approved text verbatim. Phase 05 (Safety
  Engine) reads this table for duplicate detection and cooldowns; Phase 04 fills
  ``youtube_comment_id`` only when the API confirmed the submission.
* No credentials are ever written here. See SECURITY in the root README.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flochat.errors import StorageError

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS comment_history (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    live_chat_id       TEXT    NOT NULL,
    live_chat_title    TEXT,
    draft_text         TEXT    NOT NULL,
    comment_text       TEXT    NOT NULL,
    state              TEXT    NOT NULL CHECK (state IN (
                           'prepared', 'approved', 'submitted', 'confirmed', 'failed'
                       )),
    created_at         TEXT    NOT NULL,
    approved_at        TEXT,
    submitted_at       TEXT,
    youtube_comment_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_comment_history_chat
    ON comment_history (live_chat_id, submitted_at);
"""


def utc_now() -> str:
    """Timestamp format used by the schema: UTC, second precision, ISO 8601."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    """Owns the SQLite connection for the current session."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise StorageError("The database is not open.", hint="Call initialize() first.")
        return self._connection

    def initialize(self) -> None:
        """Create the directory, open the database, and apply the schema."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA_SQL)
            current = self._user_version(connection)
            if current > SCHEMA_VERSION:
                connection.close()
                raise StorageError(
                    f"The database at {self.path} uses schema version {current}, "
                    f"but this build supports {SCHEMA_VERSION}.",
                    hint="Use a matching FloChat version or move the database aside.",
                )
            if current < SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except (sqlite3.Error, OSError) as exc:
            raise StorageError(
                f"Could not initialize the database at {self.path}.",
                hint=f"{type(exc).__name__}: {exc}",
            ) from exc
        self._connection = connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def check(self) -> dict[str, object]:
        """Report the real state of the database file. Never assumes a healthy file."""
        connection = self.connection
        try:
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
            tables = [
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            version = self._user_version(connection)
            rows = connection.execute("SELECT COUNT(*) FROM comment_history").fetchone()[0]
        except sqlite3.Error as exc:
            raise StorageError(f"Database check failed for {self.path}.", hint=str(exc)) from exc
        return {
            "path": str(self.path),
            "schema_version": version,
            "tables": tables,
            "integrity": integrity,
            "comment_history_rows": rows,
            "healthy": integrity == "ok" and version == SCHEMA_VERSION,
        }

    @staticmethod
    def _user_version(connection: sqlite3.Connection) -> int:
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0
