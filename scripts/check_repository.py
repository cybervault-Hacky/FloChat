"""Repository orientation guard.

Phase 01 fixes the repository shape so later phases add code without drifting
into ad hoc folders. This script enforces the *structure* rules only: it never
claims that platform integrations work, and it never substitutes for the honest
capability reporting in ``src/flochat/platform.py`` and ``src/flochat/adapters.py``.

Usage:
    python scripts/check_repository.py [--json]

Exit codes: 0 clean, 1 violations found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOP_LEVEL = {
    ".gitignore",
    "README.md",
    ".env.example",
    "pyproject.toml",
    "src",
    "scripts",
}

#: Folders that must never exist: every kind of repository clutter.
FORBIDDEN_TOP_LEVEL = {
    "docs",
    "documentation",
    "reports",
    "examples",
    "tests",
    "test",
    "samples",
    "assets",
    "planned",
    "future",
}

FORBIDDEN_ANYWHERE = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
}

#: Local tooling and sandbox directories that are never part of the repository.
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    ".arena",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
}


def _walk(root: Path) -> list[Path]:
    """Every path under root, skipping local tooling and generated directories."""
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS or part in FORBIDDEN_ANYWHERE for part in parts):
            continue
        found.append(path)
    return found


SECRET_PATTERNS = (
    re.compile(r"ya29\.[A-Za-z0-9_-]{10,}"),  # Google OAuth access token
    re.compile(r"1//[A-Za-z0-9_-]{20,}"),  # Google refresh token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # private key material
    re.compile(r"GOCSPX-[A-Za-z0-9_-]{10,}"),  # Google OAuth client secret
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),  # Google API key
)

REQUIRED_FILES = (
    "README.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "src/flochat/__init__.py",
    "src/flochat/cli.py",
    "src/flochat/controller.py",
    "src/flochat/config.py",
    "src/flochat/errors.py",
    "src/flochat/state.py",
    "src/flochat/platform.py",
    "src/flochat/adapters.py",
    "src/flochat/lifecycle.py",
    "src/flochat/comments.py",
    "src/flochat/youtube.py",
    "src/flochat/database.py",
    "scripts/check_repository.py",
)

REQUIRED_README_SECTIONS = (
    "Project Identity",
    "Purpose",
    "Supported Platforms",
    "Architecture",
    "Technology",
    "Component Responsibilities",
    "Platform Adapter Responsibilities",
    "Lifecycle",
    "Security",
    "Privacy",
    "Submission Safety",
    "Design System",
    "Development Standards",
    "Installation",
    "Verification",
    "Completion Report",
    "Known Limitations",
    "Pending Work",
)


@dataclass
class Result:
    violations: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    secret_scan_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": self.checks,
            "violations": self.violations,
            "secret_scan_files": self.secret_scan_files,
        }


def _tracked_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(root).parts
        and ".venv" not in path.parts
    )


def _check_top_level(root: Path, result: Result) -> None:
    entries = {entry.name for entry in root.iterdir() if entry.name not in IGNORED_DIRS}
    unexpected = sorted(entries - ALLOWED_TOP_LEVEL)
    forbidden = sorted(entries & FORBIDDEN_TOP_LEVEL)
    for name in forbidden:
        result.violations.append(f"Forbidden top-level folder or file: {name}")
    for name in unexpected:
        result.violations.append(
            f"Unexpected top-level entry: {name} (update the allow-list if intended)"
        )
    result.checks.append(f"top-level entries inspected: {len(entries)}")


def _check_placeholders(root: Path, result: Result) -> None:
    """Reject generated folders, stray Markdown, placeholder files, and empty folders."""
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.is_dir() and path.name in FORBIDDEN_ANYWHERE:
            result.violations.append(f"Generated or clutter folder present: {relative}")
            continue
        if path.is_file():
            if path.suffix == ".md" and relative.as_posix() != "README.md":
                result.violations.append(f"Extra Markdown file: {relative}")
            if path.name == ".gitkeep" or path.name.lower().startswith(("placeholder", "todo.")):
                result.violations.append(f"Placeholder file: {relative}")
    for directory in _walk(root):
        if directory.is_dir() and not any(directory.iterdir()):
            result.violations.append(f"Empty folder: {directory.relative_to(root)}")
    result.checks.append("placeholder, generated folder, and empty folder scan completed")


def _check_required_files(root: Path, result: Result) -> None:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            result.violations.append(f"Missing required file: {relative}")
    result.checks.append(f"required files checked: {len(REQUIRED_FILES)}")


def _check_secrets(root: Path, result: Result) -> None:
    scanned = 0
    for path in _tracked_files(root):
        if path.suffix in {".sqlite3", ".db", ".png", ".jpg", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            result.violations.append(
                f"Unreadable file during secret scan: {path.relative_to(root)}"
            )
            continue
        scanned += 1
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                result.violations.append(
                    f"Possible credential in {path.relative_to(root)}: matches {pattern.pattern!r}"
                )
    result.secret_scan_files = scanned
    result.checks.append(f"secret patterns scanned in {scanned} files")


def _check_readme(root: Path, result: Result) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        result.violations.append("README.md is missing")
        return
    text = readme.read_text(encoding="utf-8")
    missing = [
        section for section in REQUIRED_README_SECTIONS if section.lower() not in text.lower()
    ]
    for section in missing:
        result.violations.append(f"README.md is missing the {section!r} section")
    if len(text.splitlines()) < 100:
        result.violations.append("README.md is too short to be the central Phase 01 record")
    result.checks.append(f"README sections checked: {len(REQUIRED_README_SECTIONS)}")


def _check_dead_code(root: Path, result: Result) -> None:
    """Fail on definitions nothing references.

    Phase 01 rules forbid placeholder code written only to represent a planned
    feature. A name referenced exactly once (its own definition) is dead code.
    """
    import ast

    files = [p for p in _tracked_files(root) if p.suffix == ".py"]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    defined: dict[str, Path] = {}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.setdefault(node.name, path)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined.setdefault(node.target.id, path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(
                        item, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and not item.name.startswith("__"):
                        defined.setdefault(item.name, path)
    #: Entry points are invoked by the interpreter or console script, not by our code.
    exempt = {"main", "run", "build_parser"}
    for name, path in sorted(defined.items()):
        if name in exempt or name.startswith("_"):
            continue
        if len(re.findall(rf"\b{re.escape(name)}\b", combined)) <= 1:
            result.violations.append(
                f"Dead code: {name} in {path.relative_to(root)} is never referenced"
            )
    result.checks.append(f"dead code scan completed over {len(defined)} definitions")


def _check_python_syntax(root: Path, result: Result) -> None:
    import ast

    for path in sorted((root / "src").rglob("*.py")) + sorted((root / "scripts").rglob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            result.violations.append(f"Syntax error in {path.relative_to(root)}: {exc}")
    result.checks.append("Python syntax parsed for src and scripts")


def check(root: Path = ROOT) -> Result:
    result = Result()
    _check_top_level(root, result)
    _check_placeholders(root, result)
    _check_required_files(root, result)
    _check_secrets(root, result)
    _check_dead_code(root, result)
    _check_readme(root, result)
    _check_python_syntax(root, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the FloChat repository structure.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--root", default=str(ROOT), help="Repository root (default: parent of scripts)."
    )
    args = parser.parse_args(argv)

    result = check(Path(args.root).resolve())
    if args.json:
        json.dump(result.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for check_name in result.checks:
            print(f"ok  {check_name}")
        for violation in result.violations:
            print(f"FAIL {violation}")
        print("clean" if result.ok else f"{len(result.violations)} violation(s)")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
