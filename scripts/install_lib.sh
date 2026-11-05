# FloChat installer helpers, sourced by install.sh. Not executable on its own.
#
# Every function here is conservative by design: nothing deletes user files,
# nothing runs as root, nothing touches system Python, and nothing reports success
# it has not observed. Messages always say what failed, why it may have failed,
# and what the user can safely do next.

FLOCHAT_MIN_PYTHON_MAJOR=3
FLOCHAT_MIN_PYTHON_MINOR=10
FLOCHAT_EXIT_UNSUPPORTED=3
FLOCHAT_EXIT_FAILED=1
FLOCHAT_EXIT_USAGE=2

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    FLOCHAT_BOLD=$(printf '\033[1m')
    FLOCHAT_DIM=$(printf '\033[2m')
    FLOCHAT_GREEN=$(printf '\033[32m')
    FLOCHAT_YELLOW=$(printf '\033[33m')
    FLOCHAT_RED=$(printf '\033[31m')
    FLOCHAT_RESET=$(printf '\033[0m')
else
    FLOCHAT_BOLD=""
    FLOCHAT_DIM=""
    FLOCHAT_GREEN=""
    FLOCHAT_YELLOW=""
    FLOCHAT_RED=""
    FLOCHAT_RESET=""
fi

flochat_say() { printf '%s\n' "$*"; }
flochat_step() { printf '\n%s==>%s %s\n' "$FLOCHAT_BOLD" "$FLOCHAT_RESET" "$*"; }
flochat_ok() { printf '%s  ok%s %s\n' "$FLOCHAT_GREEN" "$FLOCHAT_RESET" "$*"; }
flochat_note() { printf '%s  --%s %s\n' "$FLOCHAT_DIM" "$FLOCHAT_RESET" "$*"; }
flochat_warn() { printf '%s warn%s %s\n' "$FLOCHAT_YELLOW" "$FLOCHAT_RESET" "$*"; }

# flochat_fail <what failed> <why it may have failed> <what to do next>
flochat_fail() {
    printf '\n%sFAILED%s %s\n' "$FLOCHAT_RED" "$FLOCHAT_RESET" "$1" >&2
    if [ -n "${2:-}" ]; then printf '  Why:    %s\n' "$2" >&2; fi
    if [ -n "${3:-}" ]; then printf '  Next:   %s\n' "$3" >&2; fi
}

flochat_is_termux() {
    [ -n "${TERMUX_VERSION:-}" ] && return 0
    case "${PREFIX:-}" in
        *com.termux*) return 0 ;;
    esac
    return 1
}

flochat_install_dir() {
    # The directory holding install.sh, resolved without requiring GNU readlink.
    _flochat_src="${BASH_SOURCE[0]:-$0}"
    _flochat_dir=$(CDPATH= cd -- "$(dirname -- "$_flochat_src")" && pwd -P)
    printf '%s' "$_flochat_dir"
}

# Pick an interpreter that satisfies the minimum version; never assume `python3`.
flochat_find_python() {
    for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

flochat_python_version() {
    "$1" -c 'import platform; print(platform.python_version())' 2>/dev/null
}

flochat_check_venv_support() {
    # A missing venv/ensurepip module is the most common install failure.
    "$1" -c 'import venv' >/dev/null 2>&1 && "$1" -m ensurepip --version >/dev/null 2>&1
}

flochat_venv_support_hint() {
    if flochat_is_termux; then
        printf 'pkg install python'
    elif [ "$(uname -s)" = "Darwin" ]; then
        printf 'reinstall Python 3 from python.org (it includes venv)'
    else
        printf 'install the python3-venv package for your distribution'
    fi
}

flochat_check_git() {
    command -v git >/dev/null 2>&1
}

flochat_check_curl() {
    command -v curl >/dev/null 2>&1
}

# Describe the Linux distribution, using whichever release file exists.
flochat_linux_distro() {
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        printf '%s' "${PRETTY_NAME:-${ID:-unknown}}"
    elif [ -r /etc/lsb-release ]; then
        printf '%s' "$(sed -n 's/^DISTRIB_DESCRIPTION="\(.*\)"$/\1/p' /etc/lsb-release)"
    else
        printf 'unknown'
    fi
}

flochat_package_hint() {
    if command -v pkg >/dev/null 2>&1; then
        printf 'pkg'
    elif command -v apt-get >/dev/null 2>&1; then
        printf 'apt-get'
    elif command -v dnf >/dev/null 2>&1; then
        printf 'dnf'
    elif command -v pacman >/dev/null 2>&1; then
        printf 'pacman'
    elif command -v zypper >/dev/null 2>&1; then
        printf 'zypper'
    else
        printf 'your package manager'
    fi
}

# Create or reuse .venv. Reuse is only accepted when it is this project's venv and
# its interpreter is usable; a broken environment is reported, not silently reused.
flochat_ensure_venv() {
    _python="$1"
    _venv="$2"
    if [ -d "$_venv" ]; then
        if [ ! -x "$_venv/bin/python" ]; then
            flochat_fail "The existing environment at $_venv is incomplete." \
                "It has no working bin/python; the previous install may have been interrupted." \
                "Remove it with: rm -rf '$_venv'  then run this installer again."
            return 1
        fi
        if "$_venv/bin/python" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
            flochat_ok "Reusing the existing environment at $_venv"
            return 0
        fi
        flochat_fail "The existing environment at $_venv uses an old Python." \
            "It was created with a version older than 3.10." \
            "Remove it with: rm -rf '$_venv'  then run this installer again."
        return 1
    fi
    flochat_note "Creating an isolated environment at $_venv"
    if ! "$_python" -m venv "$_venv"; then
        flochat_fail "Could not create the Python environment." \
            "The venv module or ensurepip is unavailable for $_python." \
            "Run: $(flochat_venv_support_hint), then run this installer again."
        return 1
    fi
    flochat_ok "Environment created"
}

# Upgrade pip, then install the project. Both steps must be observed to succeed.
flochat_install_project() {
    _venv="$1"
    _root="$2"
    if ! "$_venv/bin/python" -m pip --version >/dev/null 2>&1; then
        flochat_fail "pip is not available in the environment." \
            "ensurepip may be missing or disabled." \
            "Run: $(flochat_venv_support_hint), remove $_venv, and try again."
        return 1
    fi
    flochat_step "Installing FloChat and its dependencies"
    if ! "$_venv/bin/python" -m pip install --quiet --upgrade 'pip>=26.2' >/dev/null 2>&1; then
        flochat_fail "Could not install the required packaging tool (pip >=26.2)." \
            "Older bundled versions have published security advisories." \
            "Check network/proxy or use a trusted compatible wheel; do not bypass this check."
        return 1
    fi
    if ! "$_venv/bin/python" -m pip install --quiet -e "$_root"; then
        flochat_fail "Installing FloChat failed." \
            "pip could not resolve or download the declared dependencies, or there is no network access." \
            "Check your connection and proxy settings, then run this installer again."
        return 1
    fi
    flochat_ok "FloChat installed into the environment"
}

# Prove the install works by running it, rather than trusting pip's exit status.
# The reason is captured from the real failure rather than guessed.
flochat_verify_install() {
    _venv="$1"
    if ! _version=$("$_venv/bin/python" -m flochat.cli --version 2>&1); then
        _reason=$(printf '%s\n' "$_version" | grep -v '^[[:space:]]*$' | tail -3)
        flochat_fail "FloChat installed but does not run." \
            "The CLI exited with an error; last output: ${_reason:-no output}" \
            "Run: '$_venv/bin/python -m flochat.cli doctor' for details, or '$_venv/bin/python -m flochat.cli --help'."
        return 1
    fi
    flochat_ok "Verified: $_version"
    if ! "$_venv/bin/python" -m flochat.cli doctor >/dev/null 2>&1; then
        flochat_warn "Installation works, but 'doctor' reported problems."
        flochat_note "Run: '$_venv/bin/python -m flochat.cli doctor' to see them."
    fi
    return 0
}

flochat_summary() {
    _install_dir="$1"
    _quoted_dir=$(printf '%s' "$_install_dir" | sed "s/'/'\\\\''/g")
    flochat_step "Done"
    flochat_say "Start FloChat from this directory with:"
    flochat_say "  cd '$_quoted_dir' && ./start.sh"
    flochat_say ""
    flochat_say "Or activate the environment yourself:"
    flochat_say "  . '$_quoted_dir/.venv/bin/activate' && flochat doctor"
    flochat_say ""
    flochat_note "Installs the terminal CLI, including the local Comment Manager."
    flochat_note "YouTube needs OAuth setup and individual approval. Floating UI is optional: see Phase 06 setup in README.md. No automatic startup or posting."
}
