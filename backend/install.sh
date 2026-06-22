#!/bin/sh
# VCOO Agent one-liner installer (venv-based)
# Usage:
#   curl -fsSL <url>/install.sh | PROVISION_TOKEN=*** bash
#   PROVISION_TOKEN=*** bash install.sh
set -e

CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"
AGENT_URL="${AGENT_URL:-https://vcoo-onboarding.vercel.app/agent_http.py}"
AGENT_SHA256="${AGENT_SHA256:-SKIP}"

echo "=== VCOO Agent Installer ==="
echo "Control plane: $CONTROL_PLANE"

if [ -z "$PROVISION_TOKEN" ]; then
    echo "ERROR: PROVISION_TOKEN env var is required"
    exit 1
fi

# Check for Python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required. Install with: apt install python3 python3-venv"
    exit 1
fi

# Create venv if missing
AGENT_HOME="${AGENT_HOME:-$HOME/.vcoo-agent}"
VENV_DIR="$AGENT_HOME/venv"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" || {
        echo "ERROR: python3-venv not available. Install with: apt install python3-venv"
        exit 1
    }
fi

# Activate and install dependencies
echo "Checking Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet requests rich 2>/dev/null

# Verify
if ! "$VENV_DIR/bin/python" -c "import requests" 2>/dev/null; then
    echo "ERROR: requests module failed to install"
    exit 1
fi

echo "Starting agent in foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

# Download agent to temp location and run from venv
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
cd "$TMPDIR"

echo "Downloading agent..."
curl -fsSL "$AGENT_URL" -o agent_http.py

if [ "$AGENT_SHA256" != "SKIP" ] && command -v sha256sum >/dev/null 2>&1; then
    echo "Verifying checksum..."
    echo "$AGENT_SHA256  agent_http.py" | sha256sum -c -
elif [ "$AGENT_SHA256" != "SKIP" ]; then
    echo "WARNING: sha256sum not found, skipping checksum verification"
fi

"$VENV_DIR/bin/python" agent_http.py "$CONTROL_PLANE" "$PROVISION_TOKEN"

echo "---"
echo "Agent finished. Temporary files cleaned up."
