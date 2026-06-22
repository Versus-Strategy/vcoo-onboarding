#!/bin/sh
# VCOO Agent one-liner installer
# Usage:
#   curl -fsSL <url>/install.sh | PROVISION_TOKEN=*** bash
#   PROVISION_TOKEN=*** bash install.sh
set -e

CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"
AGENT_URL="${AGENT_URL:-https://frontend-ivory-seven-d0aw1wzkae.vercel.app/agent_http.py}"
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

# Install requests if not available
python3 -c "import requests" 2>/dev/null || {
    echo "Installing requests module..."
    python3 -m pip install --user requests 2>/dev/null || {
        echo "WARNING: Could not install requests, agent may fail"
    }
}

echo "Starting agent in foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

python3 agent_http.py "$CONTROL_PLANE" "$PROVISION_TOKEN"

echo "---"
echo "Agent finished. Temporary files cleaned up."
