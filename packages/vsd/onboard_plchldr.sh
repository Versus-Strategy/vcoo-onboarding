#!/usr/bin/env bash
set -euo pipefail

VERSUS="versusd"
TOKENS=***KENS"
PROVISION_ID_FILE="/etc/__D__VERSUS/provision_id"

echo "=== Iniciando onboarding automatico de VCOO ==="

# Leer ID de provision
if [[ ! -f "__D__PROVISION_ID_FILE" ]]; then
    echo "Error: no se encontro el fichero de provision ID en __D__PROVISION_ID_FILE" >&2
    exit 1
fi
PROVISION_ID=$(cat "__D__PROVISION_ID_FILE")
echo "ID de provision leido: __D__PROVISION_ID"

# Leer token de provision
TOKEN_FILE="__D__TOKENS_DIR/__D__PROVISION_ID.token"
if [[ ! -f "__D__TOKEN_FILE" ]]; then
    echo "Error: no se encontro el token de provision en __D__TOKEN_FILE" >&2
    exit 1
fi
PROVISION_TOKEN=$(cat "__D__TOKEN_FILE")
echo "Token de provision leido (longitud: __D__{__D__#PROVISION_TOKEN})"

# Determinar el usuario que instalo versusd
if [[ -f "/opt/vsd/versusd.sh" ]]; then
    INSTALL_USER=$(stat -c '%U' "/opt/vsd/versusd.sh")
    HOME_DIR=$(getent passwd "__D__INSTALL_USER" | cut -d: -f6)
else
    INSTALL_USER="__D__USER"
    HOME_DIR="__D__HOME"
fi
echo "Usuario de instalacion: __D__INSTALL_USER (home: __D__HOME_DIR)"

# Backend de control
CONTROL_PLANE="https://vcoo-onboarding.vercel.app"

echo "Descargando e instalando componentes VCOO desde __D__CONTROL_PLANE ..."

# Ejecutar el installer unificado como el usuario de instalacion
sudo -u "__D__INSTALL_USER" \
    PROVISION_TOKEN="__D__PROVISION_TOKEN" \
    CONTROL_PLANE="__D__CONTROL_PLANE" \
    VCOO_HOME="__D__HOME_DIR/.vcoo" \
    HERMES_HOME="__D__HOME_DIR/.hermes" \
    bash -c "$(curl -fsSL "__D__CONTROL_PLANE/install.sh")"

echo "=== Onboarding completado ==="
