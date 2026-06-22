#!/bin/sh
# Playbook: install-docker
# Installs Docker CE on Ubuntu/Debian using the official convenience script
set -e
echo "Installing Docker..."
if command -v docker >/dev/null 2>&1; then
    echo "Docker already installed: $(docker --version)"
    exit 0
fi
curl -fsSL https://get.docker.com | sh
echo "Docker installed successfully."
docker --version
