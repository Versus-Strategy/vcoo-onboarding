#!/bin/sh
# VCOO Agent one-liner installer (self-healing, transparent)
# Usage:
#   curl -fsSL <url>/install.sh | PROVISION_TOKEN=*** bash
#   PROVISION_TOKEN=*** bash install.sh

CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"
AGENT_URL="${AGENT_URL:-https://vcoo-onboarding.vercel.app/agent_http.py}"
AGENT_SHA256="${AGENT_SHA256:-SKIP}"

echo "=== VCOO Agent Installer ==="
echo "Control plane: $CONTROL_PLANE"

if [ -z "$PROVISION_TOKEN" ]; then
    echo "ERROR: PROVISION_TOKEN env var is required"
    echo "Usage: curl -sSL $CONTROL_PLANE/install.sh | PROVISION_TOKEN=*** bash"
    exit 1
fi

# ── Helpers ────────────────────────────────────────────────

IS_ROOT=false
[ "$(id -u)" = "0" ] && IS_ROOT=true

SUDO=""
if ! $IS_ROOT && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

# Detect package manager
pkg_install() {
    if command -v apt-get >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "$@"
    elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y -q "$@"
    elif command -v yum >/dev/null 2>&1; then
        $SUDO yum install -y -q "$@"
    elif command -v apk >/dev/null 2>&1; then
        $SUDO apk add --no-cache "$@"
    else
        return 1
    fi
}

# ── Python3 (auto-install if missing) ─────────────────────

if ! command -v python3 >/dev/null 2>&1; then
    echo "Installing python3..."
    if ! pkg_install python3; then
        echo "ERROR: Could not install python3 automatically"
        echo "Install python3 manually and retry: https://www.python.org/downloads/"
        exit 1
    fi
fi

echo "Python: $(python3 --version 2>&1)"

# ── Virtual environment (auto-healing) ────────────────────

AGENT_HOME="${AGENT_HOME:-$HOME/.vcoo-agent}"
VENV_DIR="$AGENT_HOME/venv"
USE_VENV=true

ensure_venv() {
    # Returns 0 if venv is ready, non-zero if we should fall back to --user
    if [ -f "$VENV_DIR/bin/python" ]; then
        return 0
    fi

    echo "Creating virtual environment..."

    # Attempt 1: standard venv
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "Virtual environment created."
        return 0
    fi

    # Attempt 2: install python3-venv and retry
    echo "Installing python3-venv..."
    PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    pkg_install python3-venv 2>/dev/null || \
    pkg_install "python${PYVER}-venv" 2>/dev/null || true

    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "Virtual environment created."
        return 0
    fi

    # Attempt 3: venv without pip (ensurepip not bundled in some minimal images)
    echo "Trying venv --without-pip..."
    if python3 -m venv --without-pip "$VENV_DIR" 2>/dev/null; then
        echo "Bootstrapping pip..."
        "$VENV_DIR/bin/python" -m ensurepip --default-pip 2>/dev/null || \
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$VENV_DIR/bin/python" 2>/dev/null || true
        if [ -f "$VENV_DIR/bin/pip" ] || "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
            echo "Pip bootstrapped."
            return 0
        fi
    fi

    echo "WARNING: venv creation failed, falling back to --user install"
    USE_VENV=false
    return 1
}

ensure_venv

# ── Dependencies ───────────────────────────────────────────

if $USE_VENV; then
    PIP="$VENV_DIR/bin/pip"
    PYTHON="$VENV_DIR/bin/python"
else
    PIP="python3 -m pip"
    PYTHON="python3"
fi

# Ensure pip is available
if ! $PYTHON -m pip --version >/dev/null 2>&1; then
    echo "Bootstrapping pip..."
    $PYTHON -m ensurepip --default-pip 2>/dev/null || \
    curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON 2>/dev/null || \
    pkg_install python3-pip 2>/dev/null || true
fi

echo "Installing dependencies..."
# requests is the only hard requirement
$PIP install --quiet requests 2>/dev/null || \
$PYTHON -m pip install --quiet --user requests 2>/dev/null || {
    echo "ERROR: Failed to install 'requests'"
    echo "Try manually: $PIP install requests"
    exit 1
}

# rich is cosmetic — its absence is not fatal
$PIP install --quiet rich 2>/dev/null || true

# Verify
if ! $PYTHON -c "import requests" 2>/dev/null; then
    echo "ERROR: requests module still not importable after install"
    exit 1
fi

echo "Dependencies ready."

# ── Run agent ───────────────────────────────────────────────

echo "Starting agent in foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
cd "$TMPDIR"

echo "Downloading agent..."
if ! curl -fsSL "$AGENT_URL" -o agent_http.py; then
    echo "ERROR: Could not download agent from $AGENT_URL"
    exit 1
fi

if [ "$AGENT_SHA256" != "SKIP" ] && command -v sha256sum >/dev/null 2>&1; then
    echo "Verifying checksum..."
    echo "$AGENT_SHA256  agent_http.py" | sha256sum -c - || {
        echo "WARNING: Checksum mismatch, continuing anyway..."
    }
fi

"$PYTHON" agent_http.py "$CONTROL_PLANE" "$PROVISION_TOKEN"

echo "---"
echo "Agent finished. Temporary files cleaned up."
