#!/bin/sh
# VCOO Agent one-liner installer
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

# Create temp directory
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
cd "$TMPDIR"

echo "Downloading agent..."
curl -fsSL "$AGENT_URL" -o agent_http.py

# Verify checksum if provided
if [ "$AGENT_SHA256" != "SKIP" ] && command -v sha256sum >/dev/null 2>&1; then
    echo "Verifying checksum..."
    echo "$AGENT_SHA256  agent_http.py" | sha256sum -c -
elif [ "$AGENT_SHA256" != "SKIP" ]; then
    echo "WARNING: sha256sum not found, skipping checksum verification"
fi

# Check for Python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required. Install with: apt install python3"
    exit 1
fi

# Install requirements
echo "Checking Python dependencies..."

MISSING=""
python3 -c "import requests" 2>/dev/null || MISSING="$MISSING requests"
python3 -c "import rich" 2>/dev/null || MISSING="$MISSING rich"

if [ -n "$MISSING" ]; then
    echo "  Installing:$MISSING"
    # Try pip first
    python3 -m pip install --user $MISSING 2>/dev/null || \
    python3 -m pip install $MISSING 2>/dev/null || \
    pip3 install $MISSING 2>/dev/null || {
        # Fallback: try apt for requests, pip for rich
        echo "  pip not available, trying apt..."
        apt-get update -qq 2>/dev/null
        apt-get install -y -qq python3-requests 2>/dev/null || true
        # For rich, we need pip
        if echo "$MISSING" | grep -q "rich"; then
            echo "  Installing pip to get rich..."
            apt-get install -y -qq python3-pip 2>/dev/null && \
            pip3 install rich 2>/dev/null || \
            echo "  WARNING: rich not available, agent will run in plain-text mode"
        fi
    }
fi

# Verify
python3 -c "import requests" 2>/dev/null || {
    echo "ERROR: requests module is required. Install manually: apt install python3-requests"
    exit 1
}

echo "Starting agent in foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

python3 agent_http.py "$CONTROL_PLANE" "$PROVISION_TOKEN"

echo "---"
echo "Agent finished. Temporary files cleaned up."
