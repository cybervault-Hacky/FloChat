"""Executable Phase 03 regression checks; isolated temporary data, stdlib only.

Run from the clone with: .venv/bin/python scripts/verify_comments.py
No account, network request, or user data directory is used.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flochat.adapters import adapter_reports
from flochat.comments import (
    CommentManager,
    SubmissionRequest,
    ensure_approved,
    normalize_text,
    submit,
    validate_comment,
)
from flochat.config import AppConfig
from flochat.database import LOCAL_SCHEMA_SQL, SCHEMA_SQL, SCHEMA_VERSION, Database
from flochat.dependencies import missing_runtime_dependencies
from flochat.errors import ApprovalRequiredError, FloChatError, NotSupportedYetError, StorageError
from flochat.lifecycle import SessionManager
from flochat.platform import detect
from flochat.state import AppState, StatusReport
from flochat.youtube import describe as youtube_description


def main() -> None:
    count = 0

    def check(condition, label):
        nonlocal count
        if not condition:
            raise AssertionError(label)
        count += 1

    def refuses(operation, error=FloChatError):
        try:
            operation()
        except error:
            check(True, "expected refusal")
        else:
            raise AssertionError("Operation unexpectedly succeeded")

    with tempfile.TemporaryDirectory(prefix="flochat-verify-") as directory:
        home = Path(directory)
        path = home / "manager.sqlite3"
        # All local operations must work with networking and submission disabled.
        with (
            patch("socket.socket", side_effect=AssertionError("network attempted")),
            patch("flochat.comments.submit", side_effect=AssertionError("submission attempted")),
            Database(path) as db,
        ):
            db.initialize()
            check(db.check()["healthy"], "fresh initialization")
            db.initialize()
            m = CommentManager(db)
            check(m.username("show")["profile"] is None, "missing profile")
            check(m.drafts("list")["drafts"] == [], "empty drafts")
            check(m.history("list")["events"] == [], "empty history")
            refuses(lambda: m.username("set", " \t\n "))
            refuses(lambda: m.username("set", "two\nlines"))
            refuses(lambda: m.username("set", "bad\x1bname"))
            check(
                m.username("set", " @Sarthak123 ")["profile"]["username"] == "@Sarthak123",
                "create trim",
            )
            m.username("set", "ordinary यूज़र")
            check(m.username("show")["profile"]["username"] == "ordinary यूज़र", "update Unicode")
            check(
                db.connection.execute("SELECT count(*) FROM username_profile").fetchone()[0] == 1,
                "singleton",
            )
            check(not m.comment("preview")["valid"], "empty preview")
            refuses(lambda: m.comment("new", "   "))
            refuses(lambda: m.comment("new", "bad\x00text"))
            text = "Hello  👩‍💻\n\n\n\tनमस्ते '); DROP TABLE drafts;--"
            view = m.comment("new", " \r\n" + text + " \n")
            check(view["text"] == text, "format and SQL literal preserved")
            check(view["character_count"] == len(text), "Unicode code point count")
            check(view["username"] is None, "no silent username use")
            check(view["saved"] is False, "unsaved")
            refuses(lambda: m.comment("generate"))
            refuses(lambda: m.comment("new", "replace"))
            check(m.comment("show")["text"] == text, "refusal preserves text")
            before = m.comment("show")
            preview = m.comment("preview")
            check(preview["text"] == before["text"], "preview exact")
            check(preview["submitted"] is False and preview["valid"], "local preview only")
            check(m.comment("show") == before, "preview does not mutate editor")
            first = m.drafts("save", title=" First ")["draft"]
            first_id = first["id"]
            check(first["title"] == "First", "title trim")
            check(m.comment("show")["saved"], "saved status")
            m.comment("edit", "edited " + "🌍" * 220)
            check(not m.comment("show")["saved"], "editing dirties draft")
            updated = m.drafts("save")["draft"]
            check(updated["id"] == first_id, "save updates open draft")
            check(updated["created_at"] == first["created_at"], "creation preserved")
            check(updated["updated_at"] >= first["updated_at"], "update timestamp")
            check(len(updated["text"]) > 200, "no artificial local length limit")
            check(
                m.drafts("rename", first_id, title="renamed")["draft"]["title"] == "renamed",
                "rename",
            )
            refuses(lambda: m.drafts("rename", first_id, title=" "))
            refuses(lambda: m.drafts("open", first_id))
            check(m.drafts("open", first_id, replace=True)["text"] == updated["text"], "open exact")
            m.comment("generate", template="entry", replace=True)
            check(
                m.comment("show")["text"] == "Please consider my entry: ordinary यूज़र",
                "explicit template",
            )
            check(m.comment("show")["username"] == "ordinary यूज़र", "username snapshot")
            second = m.drafts("save", title="second")["draft"]
            check(second["id"] != first_id, "unique draft IDs")
            check(len(m.drafts("list")["drafts"]) == 2, "multiple drafts")
            m.username("set", "changed")
            check(
                m.comment("show")["username"] == "ordinary यूज़र",
                "profile change does not rewrite editor",
            )
            refuses(lambda: m.username("delete"))
            m.username("delete", yes=True)
            check(m.username("show")["profile"] is None, "profile deletion")
            refuses(lambda: m.comment("generate", replace=True))
            check(m.comment("show")["text"] == second["text"], "missing profile preserves text")
            m.comment("edit", "ordinary edited comment")
            check(m.comment("show")["username"] is None, "arbitrary edit drops stale association")
            refuses(lambda: m.comment("clear"))
            refuses(lambda: m.drafts("delete", first_id))
            refuses(lambda: m.drafts("open", "missing", replace=True))
            refuses(lambda: m.drafts("delete", "'; DROP TABLE drafts;--", yes=True))
            events = m.history("list", limit=1000)["events"]
            kinds = {e["event_type"] for e in events}
            check(
                {
                    "comment_prepared",
                    "comment_edited",
                    "draft_created",
                    "draft_edited",
                    "draft_renamed",
                    "draft_opened",
                    "comment_previewed",
                }
                <= kinds,
                "meaningful events",
            )
            check(len({e["id"] for e in events}) == len(events), "unique events")
            check(all(datetime.fromisoformat(e["created_at"]).tzinfo for e in events), "UTC times")
            check(
                all(
                    set(e) == {"id", "draft_id", "event_type", "created_at", "character_count"}
                    for e in events
                ),
                "history has no text or username snapshots",
            )
            check(len(m.history("list", limit=2)["events"]) == 2, "history limit")
            refuses(lambda: m.history("list", limit=0))
            refuses(lambda: m.history("clear"))
            # Fail AFTER the draft/editor writes: verify the whole operation rolls back.
            original = m.comment("show")
            original_draft = m.drafts("list")
            db.connection.execute(
                "CREATE TEMP TRIGGER fail_history BEFORE INSERT ON local_history "
                "BEGIN SELECT RAISE(ABORT, 'injected write failure'); END"
            )
            refuses(lambda: m.drafts("save", title="must roll back"), StorageError)
            check(m.comment("show") == original, "rollback editor")
            check(m.drafts("list") == original_draft, "rollback draft")
            db.connection.execute("DROP TRIGGER fail_history")
            m.drafts("delete", second["id"], yes=True)
            check(m.comment("show")["text"] == original["text"], "delete retains editor")
            check(m.comment("show")["draft_id"] is None, "delete detaches editor")
            check(not m.comment("show")["saved"], "deleted draft now unsaved")
            check(m.history("list")["events"][0]["event_type"] == "draft_deleted", "delete event")
            m.comment("clear", yes=True)
            check(m.comment("show")["text"] == "", "clear editor")
            check(len(m.drafts("list")["drafts"]) == 1, "clear keeps drafts")
            refuses(lambda: m.drafts("save"))
            m.history("clear", yes=True)
            check(m.history("list")["events"] == [], "history cleared")
            check(len(m.drafts("list")["drafts"]) == 1, "history clear keeps drafts")
            check(db.check()["comment_history_rows"] == 0, "no fake submissions")
        with Database(path) as db:
            db.initialize()
            check(
                CommentManager(db).drafts("list")["drafts"][0]["id"] == first_id,
                "reopen persistence",
            )
        # Schema 1 -> 2 preserves existing future-submission records.
        legacy = home / "legacy.db"
        with sqlite3.connect(legacy) as c:
            c.executescript(SCHEMA_SQL)
            c.execute("PRAGMA user_version=1")
            c.execute(
                "INSERT INTO comment_history"
                "(live_chat_id,draft_text,comment_text,state,created_at) "
                "VALUES ('chat','legacy','legacy','prepared','2020-01-01')"
            )
        with Database(legacy) as db:
            db.initialize()
            check(db.check()["schema_version"] == SCHEMA_VERSION, "migration version")
            check(db.check()["comment_history_rows"] == 1, "legacy row retained")
        # Broken, unknown and partially migrated schemas must fail without mutation.
        for kind in ("garbage", "future", "unversioned", "partial", "constraints"):
            bad = home / (kind + ".db")
            if kind == "garbage":
                bad.write_bytes(b"not a SQLite file")
            else:
                with sqlite3.connect(bad) as c:
                    if kind == "future":
                        c.execute("PRAGMA user_version=999")
                    elif kind == "unversioned":
                        c.execute("CREATE TABLE unrelated (value TEXT)")
                    elif kind == "partial":
                        c.executescript(SCHEMA_SQL)
                        c.execute("PRAGMA user_version=1")
                        c.execute("CREATE TABLE drafts(broken TEXT)")
                    else:
                        c.executescript(
                            SCHEMA_SQL + LOCAL_SCHEMA_SQL.replace("CHECK (id = 1)", "", 1)
                        )
                        c.execute("PRAGMA user_version=2")
            before = bad.read_bytes()
            with Database(bad) as db:
                refuses(db.initialize, StorageError)
            check(bad.read_bytes() == before, f"{kind} untouched on failure")
        # Real CLI subprocesses use a separate temporary home (restart every command).
        env = dict(os.environ, FLOCHAT_HOME=str(home / "cli"), PYTHONUTF8="1")
        env.pop("FLOCHAT_DB", None)

        def cli(*args, code=0, stdin=None):
            result = subprocess.run(
                [sys.executable, "-m", "flochat.cli", "--json", *args],
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            check(result.returncode == code, f"CLI {args}: {result.stderr}")
            return json.loads(result.stdout or result.stderr)

        cli("username", "set", "@local")
        cli("comment", "generate")
        draft_id = cli("drafts", "save", "--title", "restart")["draft"]["id"]
        check(cli("comment", "preview")["saved"], "CLI restart editor persistence")
        diagnostics = json.dumps(cli("doctor"))
        check(
            "@local" not in diagnostics and "My username is" not in diagnostics,
            "doctor does not leak stored text/profile",
        )
        cli("drafts", "rename", draft_id, "new title")
        cli("comment", "new", "--text", "blocked", code=1)
        cli("comment", "new", "--stdin", "--replace", stdin="\nUnicode 👩‍💻\n\nline\n")
        check(cli("comment", "preview")["text"] == "Unicode 👩‍💻\n\nline", "UTF-8 stdin")
        cli("comment", "clear", "--yes")
        cli("comment", "preview", code=1)
        cli("drafts", "open", draft_id)
        cli("drafts", "delete", draft_id, "--yes")
        cli("history", "list")
        cli("history", "clear", "--yes")
        cli("username", "delete", "--yes")
        for args in (
            ("version",),
            ("status",),
            ("state",),
            ("settings",),
            ("doctor",),
            ("platform",),
            ("config", "show"),
            ("config", "validate"),
            ("start",),
            ("stop",),
        ):
            cli(*args)
        cli("start", "--mode", "persistent")
        cli("panel", "stop")
        for args in (
            ("--help",),
            ("--version",),
            ("comment",),
            ("unknown",),
            ("comment", "new"),
            ("comment", "new", "--text", "x", "--stdin"),
        ):
            r = subprocess.run(
                [sys.executable, "-m", "flochat.cli", *args], capture_output=True, env=env
            )
            check(r.returncode == (0 if args[0].startswith("--") else 2), "usage exit codes")
        cli("comment", "new", "--stdin", "--replace", stdin="bad\x00text", code=1)
        (home / "cli" / "config.json").write_text("{broken", encoding="utf-8")
        cli("settings", code=2)
        check(cli("doctor", code=1)["findings"], "doctor survives corrupt config")
        # Permission failures are real on this non-root Linux verification host.
        readonly = home / "readonly"
        readonly.mkdir(mode=0o500)
        try:
            if os.name == "posix" and os.geteuid() != 0:
                with Database(readonly / "blocked.db") as db:
                    refuses(db.initialize, StorageError)
        finally:
            readonly.chmod(0o700)
        # Prove the unchanged AST guard is non-vacuous in a disposable tree.
        root = Path(__file__).resolve().parent.parent
        incomplete = subprocess.run(
            [sys.executable, "-S", "-m", "flochat.cli", "--json", "doctor"],
            capture_output=True,
            text=True,
            env=dict(env, PYTHONPATH=str(root / "src")),
        )
        check(
            incomplete.returncode == 4 and "dependencies" in json.loads(incomplete.stderr),
            "missing dependency exit 4, not traceback",
        )
        # Use a valid config for this targeted input check.
        (home / "cli" / "config.json").unlink()
        invalid_utf8 = subprocess.run(
            [sys.executable, "-m", "flochat.cli", "comment", "new", "--stdin", "--replace"],
            input=b"\xff",
            capture_output=True,
            env=env,
        )
        check(
            invalid_utf8.returncode == 1 and b"UTF-8" in invalid_utf8.stderr,
            "invalid stdin encoding fails clearly",
        )
        clone = home / "guard-copy"
        shutil.copytree(
            root,
            clone,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "__pycache__", ".ruff_cache", "*.egg-info"
            ),
        )
        orphan = "phase_three_" + "orphan_for_guard"
        (clone / "src" / "flochat" / "orphan.py").write_text(
            f"def {orphan}():\n    return 123\n", encoding="utf-8"
        )
        guard = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_repository.py"), "--root", str(clone)],
            capture_output=True,
            text=True,
        )
        check(
            guard.returncode == 1 and f"Dead code: {orphan}" in guard.stdout,
            "AST guard detects genuine unused definition",
        )
        check(not missing_runtime_dependencies(), "dependency guard healthy")
        check(youtube_description(None, None)["requests_sent"] == 0, "zero API requests")
        check(
            all(
                not report.capabilities.overlay and not report.to_dict()["runtime_verified"]
                for report in adapter_reports(detect())
            ),
            "no unverified native runtime claims",
        )
        # Existing approval and lifecycle invariants.
        check(not StatusReport.of(AppState.SUCCESS).ok, "unconfirmed success not ok")
        for value in (False, 1, "yes", None):
            refuses(lambda v=value: ensure_approved(v), ApprovalRequiredError)
        refuses(lambda: submit(SubmissionRequest("test", "chat")), ApprovalRequiredError)
        refuses(
            lambda: submit(SubmissionRequest("test", "chat", approved=True)), NotSupportedYetError
        )
        check(normalize_text("a\n\n\t👩‍💻") == "a\n\n\t👩‍💻", "shared exact normalization")
        check(not validate_comment("x" * 10000), "unlimited local text")
        check(bool(validate_comment("x" * 201, max_length=200)), "explicit future submission limit")
        sessions = SessionManager(AppConfig())
        check(sessions.start().ok and sessions.stop().ok, "manual lifecycle")
        check(sessions.recover().state is AppState.PENDING, "no recovery or resubmission")
    print(f"PASS: {count} executed checks (local operations, migration, rollback, CLI and safety).")


if __name__ == "__main__":
    main()
