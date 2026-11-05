"""Single local SQLite boundary, with additive, transactional schema migration."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from flochat.errors import StorageError

SCHEMA_VERSION = 4

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


LOCAL_SCHEMA_SQL = """
CREATE TABLE username_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    username TEXT NOT NULL CHECK (length(trim(username)) > 0),
    updated_at TEXT NOT NULL
);
CREATE TABLE drafts (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    username TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE editor (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    text TEXT NOT NULL DEFAULT '',
    username TEXT,
    draft_id TEXT REFERENCES drafts(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE local_history (
    id TEXT PRIMARY KEY NOT NULL,
    draft_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'comment_prepared', 'comment_edited', 'editor_cleared', 'draft_created',
        'draft_edited', 'draft_renamed', 'draft_opened', 'draft_deleted', 'comment_previewed'
    )),
    created_at TEXT NOT NULL,
    character_count INTEGER NOT NULL CHECK (character_count >= 0)
);
CREATE INDEX idx_local_history_time ON local_history(created_at, id);
"""


YOUTUBE_SCHEMA_SQL = """
CREATE TABLE youtube_selection (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    video_id TEXT NOT NULL,
    live_chat_id TEXT NOT NULL,
    title TEXT NOT NULL,
    account_channel_id TEXT NOT NULL,
    selected_at TEXT NOT NULL
);
CREATE TABLE youtube_usage (
    utc_day TEXT NOT NULL,
    operation TEXT NOT NULL,
    requests INTEGER NOT NULL CHECK (requests >= 0),
    PRIMARY KEY (utc_day, operation)
);
"""


SAFETY_SCHEMA_SQL = """
CREATE TABLE safety_attempts (
 id TEXT PRIMARY KEY NOT NULL,
 approval_id TEXT NOT NULL UNIQUE,
 account_id TEXT NOT NULL,
 chat_id TEXT NOT NULL,
 digest TEXT NOT NULL,
 draft_id TEXT,
 character_count INTEGER NOT NULL,
 started REAL NOT NULL,
 monotonic_started REAL NOT NULL,
 state TEXT NOT NULL CHECK (state IN ('IN_PROGRESS','ACCEPTED','REJECTED','OUTCOME_UNKNOWN')),
 category TEXT NOT NULL,
 youtube_id TEXT,
 resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0,1))
);
CREATE INDEX safety_duplicate ON safety_attempts(account_id,chat_id,digest);
CREATE TABLE safety_events (
 id TEXT PRIMARY KEY NOT NULL,
 created REAL NOT NULL,
 event TEXT NOT NULL,
 decision TEXT NOT NULL,
 account_id TEXT,
 chat_id TEXT,
 draft_id TEXT,
 character_count INTEGER NOT NULL,
 attempt_id TEXT
);
CREATE TABLE safety_clock (
 id INTEGER PRIMARY KEY CHECK (id=1),
 last_seen REAL NOT NULL
);
"""


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
        """Check compatibility before writing; migrate atomically without deleting data."""
        if self._connection is not None:
            return
        connection = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with suppress(FileExistsError):
                self.path.touch(mode=0o600, exist_ok=False)
            connection = sqlite3.connect(self.path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            current = self._user_version(connection)
            if current > SCHEMA_VERSION:
                raise StorageError(
                    f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}.",
                    hint="Use a matching FloChat version. The database was not changed.",
                )
            existing = {
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if current == 0 and existing:
                raise StorageError("Unversioned database contains tables; refusing to modify it.")
            if current:
                self._check_schema(connection, current)
            if current == 0:
                for statement in SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
            if current < 2:
                for statement in LOCAL_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
            if current < 3:
                for statement in YOUTUBE_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
            if current < 4:
                for statement in SAFETY_SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
            self._check_schema(connection)
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise StorageError("Database integrity check failed.")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise StorageError("Database contains invalid draft references.")
            if current != SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except (sqlite3.Error, OSError, StorageError) as exc:
            if connection is not None:
                connection.rollback()
                connection.close()
            if isinstance(exc, StorageError):
                raise
            raise StorageError(
                f"Could not initialize the database at {self.path}.",
                hint=f"{type(exc).__name__}: {exc}",
            ) from exc
        self._connection = connection

    @staticmethod
    def _check_schema(connection: sqlite3.Connection, version: int = SCHEMA_VERSION) -> None:
        """Reject altered types, constraints, triggers or indexes, not just bad versions.

        Reference schema exists only in memory for structural comparison; all user
        data continues to live in the single configured file.
        """

        def signature(sql: str) -> tuple[str, ...]:
            # Ignore SQL keyword case/whitespace, but NOT case or spaces inside literals.
            tokens = re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\w+|[^\s]", sql)
            return tuple(t if t.startswith(("'", '"')) else t.lower() for t in tokens)

        reference = sqlite3.connect(":memory:")
        try:
            reference.executescript(
                SCHEMA_SQL
                + (LOCAL_SCHEMA_SQL if version >= 2 else "")
                + (YOUTUBE_SCHEMA_SQL if version >= 3 else "")
                + (SAFETY_SCHEMA_SQL if version >= 4 else "")
            )
            query = (
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
            )
            expected = {(r[0], r[1]): signature(r[2]) for r in reference.execute(query)}
            actual = {(r[0], r[1]): signature(r[2]) for r in connection.execute(query)}
            if actual != expected:
                raise StorageError(
                    "Incompatible database structure; migration rolled back.",
                    hint="Back up the database and use a matching FloChat build.",
                )
        finally:
            reference.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Serialize related local operations; never report success before commit."""
        connection = self.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise StorageError(
                "Local data operation failed; changes were rolled back.",
                hint="Check database permissions, free space, and file integrity.",
            ) from exc
        except BaseException:
            connection.rollback()
            raise

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
