#!/usr/bin/env bash
set -euo pipefail

VERSUS="versusd"
TOKENS="tokens"
TOKENS_DIR="/etc/$VERSUS/$TOKENS"
PROVISION_ID_FILE="/etc/$VERSUS/provision_id"

echo "=== Iniciando onboarding autmatico de VCOO ==="

# Leer ID
if [[ ! -f "$PROVISION_ID_FILE" ]]; then
    echo "Error: no se encontro el fichero de provision ID en $PROVISION_ID_FILE" >&2
    exit 1
fi
PROVISION_ID=$(cat "$PROVISION_ID_FILE")
echo "ID de provision leido: $PROVISION_ID"

# Leer token
TOKEN_FILE="$TOKENS_DIR/$PROVISION_ID.token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: no se encontro el token de provision en $TOKEN_FILE" >&2
    exit 1
fi
PROVISION_TOKEN=$(cat "$TOKEN_FILE")
echo "Token de provision leido (longitud: ${#PROVISION_TOKEN})"

# Determinar el usuario que instalo versusd (dueno de /opt/vsd/versusd.sh)
if [[ -f "/opt/vsd/versusd.sh" ]]; then
    INSTALL_USER=$(stat -c '%U' "/opt/vsd/versusd.sh")
else
    # Fallback: use the user invoking the service (should be root, but we need non-root for user files)
    INSTALL_USER="$USER"
    [[ -z "$INSTALL_USER" ]] && INSTALL_USER=$(whoami)
fi
echo "Usuario de instalacion determinado: $INSTALL_USER"

# Llamar al backend protegido para obtener el script de instalacion de VCOO
BACKEND_URL="https://vcoo-onboarding.vercel.app/install.sh"

echo "Descargando script de instalacion desde $BACKEND_URL ..."
sudo -u "$INSTALL_USER" PROVISION_TOKEN=*** bash -c "( curl -fsSL "$BACKEND_URL" )"

echo "=== Onboarding completado ==="
