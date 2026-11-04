"""FloChat command line interface.

Phase 01 deliberately uses :mod:`argparse` from the standard library. Typer is
the approved direction for Phase 02 (CLI & Installation); adopting it now would
add a dependency before the CLI surface exists. The command names, exit codes,
and JSON envelope below are the contract Phase 02 will keep.

Exit codes: 0 success, 1 failure, 2 invalid usage or configuration,
3 unsupported platform.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from flochat import __version__
from flochat.config import configure_logging
from flochat.controller import Controller
from flochat.errors import ConfigurationError, FloChatError, PlatformError
from flochat.state import AppState, StatusReport

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3

_STATE_EXIT = {
    AppState.SUCCESS: EXIT_OK,
    AppState.UNSUPPORTED_PLATFORM: EXIT_UNSUPPORTED,
    AppState.FAILURE: EXIT_FAILURE,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flochat",
        description="FloChat - Your Live Chat, Always Within Reach.",
        epilog=(
            "Phase 01 provides status and lifecycle boundaries only. "
            "OAuth, live chat discovery, and comment submission are not implemented."
        ),
    )
    parser.add_argument("--version", action="version", version=f"FloChat {__version__}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

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

    config = subparsers.add_parser("config", help="Inspect or validate configuration.")
    config_sub = config.add_subparsers(dest="config_command", metavar="action")
    config_sub.add_parser("show", help="Show effective and persisted configuration.")
    config_sub.add_parser("validate", help="Validate configuration and report problems.")

    return parser


def _render_item(item: object, *, indent: int) -> str:
    """Render a list entry: scalars inline, mappings as indented key/value lines."""
    if not isinstance(item, dict):
        return str(item)
    pad = " " * indent
    rendered = "\n".join(
        f"{pad}{key}: {_render_item(value, indent=indent + 2)}" for key, value in item.items()
    )
    return rendered.lstrip()


def _emit(payload: object, *, as_json: bool, stream=sys.stdout) -> None:
    if as_json:
        json.dump(payload, stream, indent=2, default=str)
        stream.write("\n")
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                print(f"{key}:", file=stream)
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {sub_value}", file=stream)
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
    if report.state is AppState.PENDING:
        return EXIT_FAILURE
    if report.state is AppState.PERMISSION_REQUIRED:
        return EXIT_UNSUPPORTED
    return _STATE_EXIT.get(report.state, EXIT_FAILURE)


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_USAGE

    try:
        controller = Controller.create()
    except ConfigurationError as exc:
        _emit(
            {"state": AppState.FAILURE.value, "error": str(exc)},
            as_json=args.json,
            stream=sys.stderr,
        )
        return EXIT_USAGE

    configure_logging(controller.config.log_level)

    try:
        if args.command == "version":
            _emit(controller.version_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "status":
            _emit(controller.status_report(), as_json=args.json)
            return EXIT_OK
        if args.command == "platform":
            _emit(controller.platform_report(), as_json=args.json)
            return EXIT_OK
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
    except PlatformError as exc:
        _emit(
            {"state": exc.state.value, "error": str(exc)},
            as_json=args.json,
            stream=sys.stderr,
        )
        return EXIT_UNSUPPORTED
    except FloChatError as exc:
        _emit({"state": exc.state.value, "error": str(exc)}, as_json=args.json, stream=sys.stderr)
        return EXIT_FAILURE

    parser.error(f"unknown command: {args.command}")
    return EXIT_USAGE  # pragma: no cover - argparse exits first


def main() -> None:
    """Console script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
