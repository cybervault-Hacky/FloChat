#!/usr/bin/env bash
# FloChat installer for Android (Termux), Linux, and macOS.
#
# Conservative by design:
#   * never runs as root and never uses sudo
#   * never modifies system Python or system packages
#   * never deletes your files; the only directory it creates is ./.venv
#   * never reports success it has not verified by running the CLI
#
# Windows uses install.ps1 instead.
#
# Exit codes: 0 installed, 1 installation failed, 2 unusable usage/environment,
#             3 unsupported platform.

set -u

FLOCHAT_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 2

# shellcheck source=scripts/install_lib.sh
. "$FLOCHAT_SCRIPT_DIR/scripts/install_lib.sh" || {
    printf 'FAILED could not load scripts/install_lib.sh\n' >&2
    printf '  Next: clone the whole repository, not only install.sh\n' >&2
    exit 2
}

flochat_step "FloChat installer"

# --- 1. platform ------------------------------------------------------------
_uname_s=$(uname -s 2>/dev/null || printf unknown)
_platform=""
if flochat_is_termux; then
    _platform="android"
elif [ "$_uname_s" = "Linux" ]; then
    _platform="linux"
elif [ "$_uname_s" = "Darwin" ]; then
    _platform="macos"
else
    flochat_fail "This operating system is not supported by install.sh: $_uname_s" \
        "FloChat supports Android/Termux, Linux, and macOS terminals." \
        "On Windows use install.ps1 in PowerShell instead."
    exit "$FLOCHAT_EXIT_UNSUPPORTED"
fi

case "$_platform" in
    android) flochat_ok "Platform: Android (Termux) on $(uname -m 2>/dev/null)" ;;
    linux)   flochat_ok "Platform: Linux ($(flochat_linux_distro)) on $(uname -m 2>/dev/null)" ;;
    macos)   flochat_ok "Platform: macOS $(sw_vers -productVersion 2>/dev/null) on $(uname -m 2>/dev/null)" ;;
esac

# --- 2. refuse root ---------------------------------------------------------
if [ "$(id -u 2>/dev/null || printf 1)" = "0" ]; then
    flochat_fail "Refusing to install as root." \
        "A root-owned .venv would break normal use and risks system changes." \
        "Run this installer as your normal user, without sudo."
    exit "$FLOCHAT_EXIT_USAGE"
fi

# --- 3. project directory ---------------------------------------------------
if [ ! -f "$FLOCHAT_SCRIPT_DIR/pyproject.toml" ] || [ ! -d "$FLOCHAT_SCRIPT_DIR/src/flochat" ]; then
    flochat_fail "This does not look like the FloChat repository: $FLOCHAT_SCRIPT_DIR" \
        "pyproject.toml or src/flochat is missing; the clone may be incomplete." \
        "Clone the full repository again and run ./install.sh from its root."
    exit "$FLOCHAT_EXIT_USAGE"
fi
flochat_ok "Project directory: $FLOCHAT_SCRIPT_DIR"

# --- 4. git (only needed to clone; report rather than install) --------------
if flochat_check_git; then
    flochat_ok "Git: $(git --version 2>/dev/null)"
else
    flochat_warn "Git is not installed. FloChat will work, but updates need it."
    flochat_note "Install it with: sudo $(flochat_package_hint) install git"
fi

# --- 5. python --------------------------------------------------------------
flochat_step "Checking Python"
if ! _python=$(flochat_find_python); then
    flochat_fail "No Python 3.10 or newer was found." \
        "Python is missing, or only an older version is on PATH." \
        "Install Python 3.10+ (Termux: pkg install python; Debian/Ubuntu: sudo apt-get install python3) and run this installer again."
    exit "$FLOCHAT_EXIT_USAGE"
fi
flochat_ok "Python $(flochat_python_version "$_python") ($(command -v "$_python"))"

if ! flochat_check_venv_support "$_python"; then
    flochat_fail "This Python cannot create virtual environments with pip." \
        "The venv module or ensurepip is missing from this Python installation." \
        "Run: $(flochat_venv_support_hint), then run this installer again."
    exit "$FLOCHAT_EXIT_USAGE"
fi
flochat_ok "Virtual environments with pip are available"

# --- 6. network reachability (informational, no download performed) --------
if flochat_check_curl; then
    flochat_note "curl is available; pip will download dependencies if needed."
else
    flochat_warn "curl is not installed. pip may still work; run 'flochat doctor' afterwards."
fi

# --- 7. install -------------------------------------------------------------
flochat_step "Preparing the environment"
_venv="$FLOCHAT_SCRIPT_DIR/.venv"
flochat_ensure_venv "$_python" "$_venv" || exit "$FLOCHAT_EXIT_FAILED"
flochat_install_project "$_venv" "$FLOCHAT_SCRIPT_DIR" || exit "$FLOCHAT_EXIT_FAILED"

flochat_step "Verifying the installation"
flochat_verify_install "$_venv" || exit "$FLOCHAT_EXIT_FAILED"

# --- 8. honest platform limits ---------------------------------------------
if [ "$_platform" = "android" ]; then
    flochat_note "Termux provides a terminal only: no floating overlay and no background service."
    flochat_note "Android overlays require a companion app (Phase 06) and are not installed here."
fi

flochat_summary "$FLOCHAT_SCRIPT_DIR"
exit 0
