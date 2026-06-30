#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------
# 1. Detectar el usuario que ejecuta el script
# -------------------------------------------------
if [ -n "${SUDO_USER:-}" ]; then
    # El script se lanzó con sudo; el usuario original está en SUDO_USER
    INSTALL_USER="$SUDO_USER"
else
    INSTALL_USER="$USER"
fi
HOME_DIR=$(getent passwd "$INSTALL_USER" | cut -d: -f6)
[ -z "$HOME_DIR" ] && HOME_DIR="/home/$INSTALL_USER"

echo "=== Instalando versusd para el usuario: $INSTALL_USER (home: $HOME_DIR) ==="

INSTALL_DIR="/opt/vsd"
LOG_DIR="/var/log"
TOKENS_DIR="/etc/versusd/tokens"

# -------------------------------------------------
# 2. Crear directorios base
# -------------------------------------------------
mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$TOKENS_DIR"

# -------------------------------------------------
# 3. Copiar los archivos desde el directorio donde se descomprimió el release
#    (el one‑liner ya habrá extraído el tarball en $INSTALL_DIR)
# -------------------------------------------------
chown -R "$INSTALL_USER":"$INSTALL_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/versusd.sh"
chmod +x "$INSTALL_DIR/vsctl"
chmod +x "$INSTALL_DIR/install_vsd.sh"

# -------------------------------------------------
# 4. Instalar unidades systemd (sustituir %i por el usuario real)
# -------------------------------------------------
for unit in versusd.service versusd-update.service versusd-update.timer; do
    sed "s/%i/$INSTALL_USER/g" "$INSTALL_DIR/$unit" > "/etc/systemd/system/$unit"
    chmod 644 "/etc/systemd/system/$unit"
done

# -------------------------------------------------
# 5. Instalar Hermes Agent (gateway) como usuario no root
# -------------------------------------------------
echo "Instalando Hermes Agent (como usuario $INSTALL_USER)…"
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sudo -u "$INSTALL_USER" bash

# Instalar el servicio de gateway de Hermes (systemd de usuario)
sudo -u "$INSTALL_USER" /home/$INSTALL_USER/.local/bin/hermes gateway install --system --run-as-user "$INSTALL_USER" <<< $'Y\nY'

# -------------------------------------------------
# 6. Habilitar y arrancar nuestros servicios
# -------------------------------------------------
systemctl daemon-reload
systemctl enable --now versusd.service
systemctl enable --now versusd-update.timer

# -------------------------------------------------
# 7. Preparar logs y dar propiedad al usuario
# -------------------------------------------------
touch "$LOG_DIR/versusd.log" "$LOG_DIR/hermes-gateway.log"
chown "$INSTALL_USER:$INSTALL_USER" "$LOG_DIR/versusd.log" "$LOG_DIR/hermes-gateway.log"

# -------------------------------------------------
# 8. Almacenar el token de provisión (uno por producto)
# -------------------------------------------------
if [ -n "${PROVISION_TOKEN:-}" ] && [ -n "${PROVISION_ID:-}" ]; then
    TOKEN_FILE="$TOKENS_DIR/$PROVISION_ID.token"
    echo "Guardando token de provisión para el producto '$PROVISION_ID'…"
    echo "$PROVISION_TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    chown root:root "$TOKEN_FILE"
    echo "Token guardado en $TOKEN_FILE"
else
    echo "Advertencia: no se recibió PROVISION_TOKEN y/o PROVISION_ID; el registro del producto quedará pendiente."
fi

# -------------------------------------------------
# 9. Ejecutar una actualización inicial
# -------------------------------------------------
echo "Ejecutando actualización inicial de Hermes y plantilla VCOO…"
sudo -u "$INSTALL_USER" "$INSTALL_DIR/vsctl" update

echo "=== Instalación completada ==="
echo "Servicios activos:"
echo "  hermes-gateway.service      (gateway de Hermes, monitorizado por versusd)"
echo "  versusd.service            (watchdog que reinicia hermes‑gateway si cae)"
echo "  versusd-update.timer       (timer diario que ejecuta 'vsctl update')"
echo ""
echo "Puedes usar el comando 'vsctl' para interactuar:"
echo "  vsctl status   → estado de hermes‑gateway y versusd"
echo "  vsctl update   → actualiza Hermes y la plantilla VCOO"
echo "  vsctl logs     → sigue el log de versusd"
echo "  vsctl hermes-logs → sigue el log de hermes‑gateway"
echo ""
echo "Los tokens de provisión se encuentran en:"
echo "  $TOKENS_DIR/<PROVISION_ID>.token"
