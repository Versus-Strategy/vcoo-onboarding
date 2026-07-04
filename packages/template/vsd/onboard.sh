#!/usr/bin/env bash
set -euo pipefail

VERSUS="versusd"
TOKENS="tokens"
TONES_DIR="/etc/$VERSUS/$TOKENS"
PROVISION_ID_FILE="/etc/$VERSUS/provision_id"

echo "=== Iniciando onboarding automático de VCOO ==="

# Leer ID
if [[ ! -f "$PROVISION_ID_FILE" ]]; then
    echo "Error: no se encontró el fichero de provision ID en $PROVISION_ID_FILE" >&2
    exit 1
fi
PROVISION_ID=$(cat "$PROVISION_ID_FILE")
echo "ID de provisión leído: $PROVISION_ID"

# Leer token
TOKEN_FILE="$TONES_DIR/$PROVISION_ID.token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: no se encontró el token de provisión en $TOKEN_FILE" >&2
    exit 1
fi
PROVISION_TOKEN=$(cat "$TOKEN_FILE")
echo "Token de provisión leído (longitud: ${#PROVISION_TOKEN})"

# Determinar el usuario que instaló versusd (dueño de /opt/vsd/versusd.sh)
if [[ -f "/opt/vsd/versusd.sh" ]]; then
    INSTALL_USER=$(stat -c '%U' "/opt/vsd/versusd.sh")
else
    # Fallback: use the user invoking the service (should be root, but we need non-root for user files)
    INSTALL_USER="$USER"
    [[ -z "$INSTALL_USER" ]] && INSTALL_USER=$(whoami)
fi
echo "Usuario de instalación determinado: $INSTALL_USER"

# Llamar al backend protegido para obtener el script de instalación de VCOO
# En un entorno real, el endpoint devolvería un script que instala Hermes y plantillas.
# Aquí simulamos la descarga y ejecución.
BACKEND_URL="https://api.example.com/vsd/vcoo-install.sh"

echo "Descargando script de instalación desde $BACKEND_URL ..."
# Simulamos la descarga (en realidad usaríamos curl con el token)
# curl -fsSL -H "Authorization: Bearer $PROVISION_TOKEN" "$BACKEND_URL" | bash
# Para la demo, simplemente creamos un marcador de instalación.
echo "Simulando instalación de componentes VCOO (Hermes, plantillas)..."
mkdir -p /opt/vsd/vcoo
echo "VCOO installed at $(date)" > /opt/vsd/vcoo/installed.txt
chown -R "$INSTALL_USER":"$INSTALL_USER" /opt/vsd/vcoo 2>/dev/null || true

echo "=== Onboarding completado ==="