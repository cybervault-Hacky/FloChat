#!/usr/bin/env bash
# Launch FloChat using the project's own virtual environment.
#
# This script never installs anything and never modifies the environment. If the
# environment is missing or broken it says so and points at install.sh.

set -u

FLOCHAT_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
FLOCHAT_VENV="$FLOCHAT_SCRIPT_DIR/.venv"
FLOCHAT_PY="$FLOCHAT_VENV/bin/python"

if [ ! -d "$FLOCHAT_VENV" ]; then
    printf 'FloChat is not installed in this directory.\n' >&2
    printf '  Next:  cd %s && ./install.sh\n' "$FLOCHAT_SCRIPT_DIR" >&2
    exit 2
fi

if [ ! -x "$FLOCHAT_PY" ]; then
    printf 'The environment at %s is incomplete (no bin/python).\n' "$FLOCHAT_VENV" >&2
    printf '  Why:   a previous install was interrupted or the folder was moved.\n' >&2
    printf '  Next:  rm -rf %s && ./install.sh\n' "$FLOCHAT_VENV" >&2
    exit 2
fi

if ! "$FLOCHAT_PY" -c 'import flochat.cli' >/dev/null 2>&1; then
    printf 'FloChat is installed but cannot be imported in %s.\n' "$FLOCHAT_VENV" >&2
    printf '  Next:  ./install.sh   (it will repair the environment)\n' >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    exec "$FLOCHAT_PY" -m flochat.cli --help
fi

exec "$FLOCHAT_PY" -m flochat.cli "$@"
