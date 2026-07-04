#!/bin/sh
# Playbook: system-info
# Safe read-only diagnostic script for VPS onboarding
echo "=== System Information ==="
echo "Hostname: $(hostname)"
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo "Uptime: $(uptime -p)"
echo ""
echo "=== Disk Usage ==="
df -h /
echo ""
echo "=== Memory ==="
free -h
echo ""
echo "=== OS Release ==="
cat /etc/os-release 2>/dev/null | head -5 || true
echo ""
echo "=== Python ==="
python3 --version 2>/dev/null || echo "Python3 not found"
echo "Done."
