"""FloChat command line interface.

This build deliberately uses :mod:`argparse` from the standard library. Typer was
listed as a possible direction, but adopting it would add a runtime dependency and
rewrite a verified surface; see the Phase 02 report in README.md. The command
names, exit codes, and JSON envelope below are the stable contract.

Exit codes: 0 success, 1 failure, 2 invalid usage or configuration,
3 unsupported platform.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from flochat import __version__
from flochat.dependencies import install_hint
from flochat.dependencies import missing_runtime_dependencies as _missing_dependencies
from flochat.errors import ConfigurationError, FloChatError, PlatformError
from flochat.state import AppState, StatusReport

#: Imported only after the dependency check, so a missing package produces an
#: explanation instead of an ImportError traceback.
_MISSING = _missing_dependencies()
if not _MISSING:
    from flochat.config import configure_logging
    from flochat.controller import Controller
    from flochat.doctor import diagnose as run_diagnosis
    from flochat.doctor import exit_code as diagnosis_exit_code
    from flochat.doctor import render as render_diagnosis
    from flochat.settings import describe_settings

EXIT_ENVIRONMENT = 4

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3

#: Single source of truth for how a state maps to a process exit code.
_STATE_EXIT = {
    AppState.SUCCESS: EXIT_OK,
    AppState.PENDING: EXIT_FAILURE,
    AppState.PERMISSION_REQUIRED: EXIT_UNSUPPORTED,
    AppState.UNSUPPORTED_PLATFORM: EXIT_UNSUPPORTED,
    AppState.FAILURE: EXIT_FAILURE,
}


def phase_tag() -> str:
    """Phase label usable before the rest of the package is imported."""
    if _MISSING:
        return "environment incomplete"
    from flochat.roadmap import phase_label as _label

    return _label()


def dependency_failure(as_json: bool) -> int:
    """Explain a missing or outdated dependency instead of raising ImportError."""
    names = ", ".join(sorted(_MISSING))
    message = (
        "FloChat cannot start because required Python packages are missing or out of date: "
        f"{names}."
    )
    if as_json:
        _emit(
            {
                "state": AppState.FAILURE.value,
                "error": message,
                "dependencies": _MISSING,
                "fix": install_hint(),
            },
            as_json=True,
            stream=sys.stderr,
        )
    else:
        print(message, file=sys.stderr)
        for name, status in sorted(_MISSING.items()):
            detail = status.get("error") or (
                f"found {status.get('present')}, needs {status.get('required')}"
            )
            print(f"  {name}: {detail}", file=sys.stderr)
        print(f"  Next:  {install_hint()}", file=sys.stderr)
        print("  Or re-run the installer for this platform.", file=sys.stderr)
    return EXIT_ENVIRONMENT


def state_exit_code(state: AppState) -> int:
    """Exit code for a state. States not listed here fail closed."""
    return _STATE_EXIT.get(state, EXIT_FAILURE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flochat",
        description="FloChat - Your Live Chat, Always Within Reach.",
        epilog=(
            f"{phase_tag()}. OAuth setup is required for YouTube. "
            "Individual posting requires the interactive safety console. "
            "Optional floating controls use the same safety owner; "
            "native behavior is platform-dependent. "
            "Run 'flochat doctor' if something is wrong with your installation."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"FloChat {__version__} ({phase_tag()})"
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    panel = subparsers.add_parser("panel", help="Explicit floating UI/background owner.")
    panels = panel.add_subparsers(dest="panel_action", required=True)
    for action in ("start", "serve"):
        command = panels.add_parser(action)
        command.add_argument("--mode", choices=("manual", "persistent"), default=None)
        if action == "start":
            command.add_argument("--core-only", action="store_true")
    for action in ("view", "stop", "status", "pair"):
        panels.add_parser(action)
    session = subparsers.add_parser("session", help="Control the live shared safety session.")
    session.add_argument(
        "session_action", choices=("start", "pause", "resume", "stop", "status", "recover")
    )
    mode = subparsers.add_parser("mode", help="Change running owner mode; invalidate approval.")
    mode.add_argument("value", choices=("manual", "persistent"))
    start = subparsers.add_parser("start", help="Start a session in the configured mode.")
    start.add_argument(
        "--mode",
        choices=("manual", "persistent"),
        default=None,
        help="Override the configured mode for this run.",
    )

    subparsers.add_parser("version", help="Print the FloChat version and phase.")
    subparsers.add_parser("stop", help="Stop the current session cleanly.")
    subparsers.add_parser("status", help="Report the real state of every boundary.")
    subparsers.add_parser("platform", help="Show detected platform and adapter state.")
    subparsers.add_parser("state", help="List the application states and their exit codes.")
    subparsers.add_parser(
        "settings", help="Show effective settings and where each value came from."
    )
    subparsers.add_parser("doctor", help="Diagnose this installation and report what to do next.")

    config = subparsers.add_parser("config", help="Inspect or validate configuration.")
    config_sub = config.add_subparsers(dest="config_command", metavar="action")
    config_sub.add_parser("show", help="Show effective and persisted configuration.")
    config_sub.add_parser("validate", help="Validate configuration and report problems.")

    youtube = subparsers.add_parser(
        "youtube", help="Explicit OAuth and official read-only YouTube operations."
    )
    actions = youtube.add_subparsers(dest="youtube_action", required=True)
    actions.add_parser(
        "status", help="Local authorization, selected chat and request counts; no network."
    )
    connect = actions.add_parser(
        "connect",
        help="Authorize readonly access; optional explicit posting grant in your local browser.",
    )
    connect.add_argument(
        "--local-browser",
        action="store_true",
        help="Confirm browser and CLI run on the same desktop (not Termux/remote preview).",
    )
    connect.add_argument(
        "--allow-posting",
        action="store_true",
        help="Explicitly request youtube.force-ssl for guarded individual "
        "writes; requires new consent.",
    )
    disconnect = actions.add_parser(
        "disconnect", help="Remove local authorization; optional Google revocation."
    )
    disconnect.add_argument(
        "--yes", action="store_true", help="Confirm credential removal and clear selection."
    )
    disconnect.add_argument(
        "--revoke",
        action="store_true",
        help="Also attempt Google revocation, reporting actual result.",
    )
    actions.add_parser("account", help="Verify account through channels.list (network required).")
    streams = actions.add_parser(
        "streams", help="List one page of owned broadcasts; no automatic selection."
    )
    streams.add_argument("--page-token", help="Explicitly retrieve the next page shown by streams.")
    for action in ("inspect", "select"):
        selection = actions.add_parser(
            action, help=f"{action.capitalize()} a video's current live chat (network required)."
        )
        selection.add_argument(
            "video_id", help="Explicit video ID, not a URL or fabricated chat ID."
        )

    subparsers.add_parser(
        "safety",
        help="Foreground safety console: explicit start, review and one-time confirmation.",
    )
    _add_comment_commands(subparsers)
    return parser


def _add_comment_commands(subparsers) -> None:
    """Register the local manager without duplicating existing commands."""
    username = subparsers.add_parser("username", help="Manage one local, unverified username.")
    actions = username.add_subparsers(dest="local_action", required=True)
    actions.add_parser("show", help="Show the saved local profile.")
    setting = actions.add_parser("set", help="Create or update the saved username.")
    setting.add_argument("value", help="Ordinary username or handle (not verified).")
    deleting = actions.add_parser("delete", help="Delete only the saved profile.")
    deleting.add_argument("--yes", action="store_true", help="Confirm profile deletion.")

    comment = subparsers.add_parser("comment", help="Persistent local text editor and preview.")
    actions = comment.add_subparsers(dest="local_action", required=True)
    actions.add_parser("show", help="Show editor text, count and saved status.")
    actions.add_parser("preview", help="Preview exact text; never submits.")
    for action in ("new", "edit"):
        editing = actions.add_parser(action, help=f"{action.capitalize()} editor text.")
        source = editing.add_mutually_exclusive_group(required=True)
        source.add_argument("--text", help="Comment text; quote it for your shell.")
        source.add_argument(
            "--stdin", action="store_true", help="Read UTF-8 text from standard input."
        )
        if action == "new":
            editing.add_argument(
                "--replace", action="store_true", help="Explicitly replace existing editor content."
            )
    generate = actions.add_parser(
        "generate", help="Explicitly prepare text using the saved username."
    )
    generate.add_argument("--template", choices=("intro", "hello", "entry"), default="intro")
    generate.add_argument(
        "--replace", action="store_true", help="Explicitly replace editor content."
    )
    clear = actions.add_parser("clear", help="Clear only the editor, not saved drafts.")
    clear.add_argument("--yes", action="store_true", help="Confirm clearing editor content.")

    drafts = subparsers.add_parser("drafts", help="Save and organize local drafts.")
    actions = drafts.add_subparsers(dest="local_action", required=True)
    actions.add_parser("list", help="List draft IDs, titles, counts and timestamps.")
    save = actions.add_parser("save", help="Save the editor; update its open draft or create one.")
    save.add_argument("--title", help="Draft title; default: Untitled draft.")
    for action in ("open", "rename", "delete"):
        draft = actions.add_parser(
            action, help=f"{action.capitalize()} a saved draft by its full ID."
        )
        draft.add_argument("draft_id")
        if action == "open":
            draft.add_argument(
                "--replace", action="store_true", help="Explicitly replace editor content."
            )
        elif action == "rename":
            draft.add_argument("title")
        else:
            draft.add_argument("--yes", action="store_true", help="Confirm deletion of this draft.")

    history = subparsers.add_parser(
        "history", help="Local metadata history, not submission history."
    )
    actions = history.add_subparsers(dest="local_action", required=True)
    listing = actions.add_parser("list", help="List newest events first (no text snapshots).")
    listing.add_argument("--limit", type=int, default=50, help="1-1000 events; default 50.")
    clear = actions.add_parser(
        "clear", help="Delete history only, leaving drafts and editor intact."
    )
    clear.add_argument("--yes", action="store_true", help="Confirm history deletion.")


def _local_options(args) -> dict:
    options = vars(args).copy()
    for key in ("command", "local_action", "json"):
        options.pop(key, None)
    from_stdin = options.pop("stdin", False)
    if from_stdin:
        try:
            # Read bytes for consistent UTF-8 across Windows and Unix locales.
            options["text"] = sys.stdin.buffer.read().decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise FloChatError("Could not read UTF-8 comment text from stdin.") from exc
    return options


def _render_item(item: object, *, indent: int) -> str:
    """Render a list entry: scalars inline, mappings as indented key/value lines."""
    if not isinstance(item, dict):
        return str(item)
    pad = " " * indent
    rendered = "\n".join(
        f"{pad}{key}: {_render_item(value, indent=indent + 2)}" for key, value in item.items()
    )
    return rendered.lstrip()


def _emit(payload: object, *, as_json: bool, stream=None) -> None:
    if stream is None:
        stream = sys.stdout
    if as_json:
        json.dump(payload, stream, indent=2, default=str)
        stream.write("\n")
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                print(f"{key}:", file=stream)
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {_render_item(sub_value, indent=4)}", file=stream)
            elif isinstance(value, list):
                print(f"{key}:", file=stream)
                for item in value:
                    print(f"  - {_render_item(item, indent=4)}", file=stream)
            else:
                print(f"{key}: {value}", file=stream)
    else:
        print(payload, file=stream)


def _render_report(report: StatusReport, *, as_json: bool) -> None:
    if as_json:
        _emit(report.to_dict(), as_json=True)
        return
    print(f"state: {report.state.value}")
    print(f"message: {report.state.message}")
    if report.detail:
        print(f"detail: {report.detail}")
    print(f"confirmed: {'yes' if report.confirmed else 'no'}")
    for note in report.notes:
        print(f"note: {note}")


def _exit_code(report: StatusReport) -> int:
    return state_exit_code(report.state)


def _state_table() -> dict[str, object]:
    """The full state vocabulary with its user-facing meaning and exit code."""
    return {
        "states": [
            {
                "state": state.value,
                "message": state.message,
                "exit_code": state_exit_code(state),
                "confirmed_when_success": state is AppState.SUCCESS,
            }
            for state in AppState
        ],
        "note": "Success requires confirmation. Failures are never silent.",
    }


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_USAGE

    if _MISSING:
        return dependency_failure(args.json)

    config_error: ConfigurationError | None = None
    try:
        controller = Controller.create()
    except ConfigurationError as exc:
        # `doctor` exists to diagnose a broken setup, so it must still run and
        # report the configuration failure rather than abort before checking.
        if args.command != "doctor":
            _emit(
                {"state": AppState.FAILURE.value, "error": str(exc)},
                as_json=args.json,
                stream=sys.stderr,
            )
            return EXIT_USAGE
        config_error = exc
        controller = Controller.degraded()

    configure_logging(controller.config.log_level)

    try:
        if args.command in ("panel", "session", "mode"):
            from flochat.ipc import Client, read_endpoint
            from flochat.runtime import launch, owner_status, serve

            config = controller.config
            if args.command == "panel" and getattr(args, "mode", None):
                config = config.model_copy(update={"mode": args.mode})
            if args.command == "session":
                payload = Client(config).call(args.session_action)
            elif args.command == "mode":
                payload = Client(config).call("mode", value=args.value)
            elif args.panel_action == "serve":
                return serve(config)
            elif args.panel_action == "view":
                from flochat.panel import show_panel

                return show_panel(config)
            elif args.panel_action == "start":
                if args.mode and owner_status(config)["availability"] == "RUNNING":
                    Client(config).call("mode", value=args.mode)
                payload = launch(config, core_only=args.core_only)
            elif args.panel_action == "stop":
                payload = Client(config).call("shutdown")
            elif args.panel_action == "status":
                payload = owner_status(config)
            else:
                metadata, key = read_endpoint(config)
                if metadata["family"] != "loopback" or not sys.stdout.isatty() or args.json:
                    raise FloChatError(
                        "Pairing is Android-only and requires a private local terminal."
                    )
                payload = {
                    "pairing_code": (
                        f"fc1:{metadata['endpoint']}:{metadata['instance']}:{key.hex()}"
                    ),
                    "warning": "Sensitive local IPC capability. Enter only in your "
                    "companion. Rotates on core restart.",
                }
            _emit(payload, as_json=args.json)
            return EXIT_OK
        if args.command == "safety":
            if args.json or not sys.stdin.isatty() or not sys.stdout.isatty():
                raise FloChatError(
                    "Safety console requires an interactive terminal. No piped "
                    "approval or --json posting."
                )
            return controller.safety_console()
        if args.command == "youtube":
            options = vars(args).copy()
            for key in ("command", "youtube_action", "json"):
                options.pop(key, None)
            payload = controller.manage_youtube(args.youtube_action, **options)
            _emit(payload, as_json=args.json)
            return EXIT_OK if payload.get("operation_ok", True) else EXIT_FAILURE
        if args.command in ("username", "comment", "drafts", "history"):
            payload = controller.manage_comments(
                args.command, args.local_action, **_local_options(args)
            )
            _emit(payload, as_json=args.json)
            return (
                EXIT_FAILURE if args.local_action == "preview" and not payload["valid"] else EXIT_OK
            )
        if args.command == "version":
            _emit(controller.version_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "status":
            _emit(controller.status_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "platform":
            _emit(controller.platform_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "state":
            _emit(_state_table(), as_json=args.json)
            return EXIT_OK
        if args.command == "settings":
            _emit(
                describe_settings(controller.config, platform=controller.platform),
                as_json=args.json,
            )
            return EXIT_OK
        if args.command == "doctor":
            if config_error is not None:
                print(
                    f"Configuration could not be loaded, so defaults were used: {config_error}",
                    file=sys.stderr,
                )
            diagnosis = run_diagnosis(
                controller.config,
                platform_info=controller.platform,
                configuration_error=str(config_error) if config_error else None,
            )
            if args.json:
                _emit(diagnosis.to_dict(), as_json=True)
            else:
                print(render_diagnosis(diagnosis))
            return diagnosis_exit_code(diagnosis)
        if args.command == "config":
            if args.config_command == "validate":
                _emit(
                    {
                        "state": AppState.SUCCESS.value,
                        "detail": "Configuration is valid.",
                        "effective": controller.config.to_public_dict(platform=controller.platform),
                    },
                    as_json=args.json,
                )
                return EXIT_OK
            _emit(controller.config_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "start":
            if args.mode:
                controller.override_mode(args.mode)
            report = controller.start()
            _render_report(report, as_json=args.json)
            return _exit_code(report)
        if args.command == "stop":
            report = controller.stop()
            _render_report(report, as_json=args.json)
            return _exit_code(report)
    except KeyboardInterrupt:
        _emit(
            {"state": AppState.PENDING.value, "error": "Operation cancelled."},
            as_json=args.json,
            stream=sys.stderr,
        )
        return EXIT_FAILURE
    except PlatformError as exc:
        _emit(
            {"state": exc.state.value, "error": str(exc)},
            as_json=args.json,
            stream=sys.stderr,
        )
        return EXIT_UNSUPPORTED
    except FloChatError as exc:
        payload = {"state": exc.state.value, "error": str(exc)}
        if hasattr(exc, "code"):
            payload.update(code=exc.code, temporary=exc.temporary)
        _emit(payload, as_json=args.json, stream=sys.stderr)
        return state_exit_code(exc.state)

    parser.error(f"unknown command: {args.command}")
    return EXIT_USAGE  # pragma: no cover - argparse exits first


def main() -> None:
    """Console script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
