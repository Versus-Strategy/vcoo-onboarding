#!/bin/sh
# VCOO Agent one-liner installer
# Usage: curl -fsSL <url>/install.sh | PROVISION_TOKEN=<token> bash
# Or:    PROVISION_TOKEN=<token> bash install.sh
set -e

CONTROL_PLANE="${CONTROL_PLANE:-https://control-plane.vcoo.dev}"
AGENT_URL="${AGENT_URL:-https://cdn.vcoo.dev/agent_http.py}"

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

# Check for Python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required. Install with: apt install python3"
    exit 1
fi

echo "Starting agent in foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

python3 agent_http.py "$CONTROL_PLANE" "$PROVISION_TOKEN"

echo "---"
echo "Agent finished. Temporary files cleaned up."
