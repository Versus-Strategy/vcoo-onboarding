#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------
# 1. Detectar el usuario que ejecuta el script
# -------------------------------------------------
if [ -n "${SUDO_USER:-}" ]; then
    INSTALL_USER="$SUDO_USER"
else
    INSTALL_USER="$USER"
fi
HOME_DIR=$(getent passwd "$INSTALL_USER" | cut -d: -f6)
[ -z "$HOME_DIR" ] && HOME_DIR="/home/$INSTALL_USER"

echo "=== Instalando componentes protegidos de VCOO para el usuario: $INSTALL_USER ==="

INSTALL_DIR="/opt/vsd"
LOG_DIR="/var/log"
TOKENS_DIR="/etc/vsd/tokens"
# -------------------------------------------------
# 2. Instalar Hermes Agent (gateway) como usuario no root
# -------------------------------------------------
echo "Instalando Hermes Agent (como usuario $INSTALL_USER)…"
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sudo -u "$INSTALL_USER" bash

# Instalar el servicio de gateway de Hermes (systemd de usuario)
sudo -u "$INSTALL_USER" /home/$INSTALL_USER/.local/bin/hermes gateway install --system --run-as-user "$INSTALL_USER" <<< $'Y\nY'

# -------------------------------------------------
# 3. Instalar plantillas de VCOO (ejemplo: copiar desde un directorio protegido)
#    En un escenario real, el backend podría proporcionar un tarball con las plantillas.
#    Aquí asumimos que las plantillas ya están disponibles en /opt/vsd/templates/
#    o que se descargan desde el backend usando el token.
# -------------------------------------------------
if [ -d "$INSTALL_DIR/templates" ]; then
    echo "Copiando plantillas de VCOO a /usr/local/share/vcoo/…"
    mkdir -p /usr/local/share/vcoo
    cp -r "$INSTALL_DIR/templates"/* /usr/local/share/vcoo/
    chown -R "$INSTALL_USER":"$INSTALL_USER" /usr/local/share/vcoo
else
    echo "Advertencia: no se encontró directorio de plantillas en $INSTALL_DIR/templates"
fi

# -------------------------------------------------
# 4. Registrar el servicio en versusd (opcional: asegurar que el token esté almacenado)
#    El script público ya guardó el token en /etc/versusd/tokens/<PROVISION_ID>.token
#    Aquí podemos verificar su existencia y, si falta, solicitarlo.
# -------------------------------------------------
if [ -n "${PROVISION_TOKEN:-}" ] && [ -n "${PROVISION_ID:-}" ]; then
    TOKEN_FILE="$TOKENS_DIR/$PROVISION_ID.token"
    if [ ! -f "$TOKEN_FILE" ]; then
        echo "Guardando token de provisión para el producto '$PROVISION_ID'…"
        echo "$PROVISION_TOKEN" > "$TOKEN_FILE"
        chmod 600 "$TOKEN_FILE"
        chown root:root "$TOKEN_FILE"
    fi
    echo "Token de producto '$PROVISION_ID' confirmado en $TOKEN_FILE"
else
    echo "Advertencia: no se proporcionaron PROVISION_TOKEN y PROVISION_ID; el registro de producto se omite."
fi

# -------------------------------------------------
# 5. Actualizar Hermes y plantillas (opcional)
# -------------------------------------------------
echo "Actualizando Hermes y plantillas VCOO…"
sudo -u "$INSTALL_USER" "$INSTALL_DIR/vsctl" update

echo "=== Instalación completada ==="
echo "Componentes instalados:"
echo "  Hermes Agent (gateway) y su servicio de systemd de usuario"
echo "  Plantillas de VCOO en /usr/local/share/vcoo (si estaban disponibles)"
echo "  Token de producto almacenado en $TOKENS_DIR/<PROVISION_ID>.token"
echo ""
echo "Versusd ya está activo y monitorizando hermes‑gateway.service"
