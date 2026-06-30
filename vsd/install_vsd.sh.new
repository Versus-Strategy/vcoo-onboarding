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

echo "=== Instalando versusd para el usuario: $INSTALL_USER (home: $HOME_DIR) ==="

INSTALL_DIR="/opt/vsd"
LOG_DIR="/var/log"
VERSUS="versusd"
TOKENS="tokens"
TOKENS_DIR="/etc/$VERSUS/$TOKENS"
PROVISION_ID_FILE="/etc/$VERSUS/provision_id"

# -------------------------------------------------
# 2. Crear directorios base
# -------------------------------------------------
mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$TOKENS_DIR"

# -------------------------------------------------
# 3. Copiar los archivos desde el directorio donde se descomprimió el release
#    (el one‑liner ya habrá extraído el tarball en $INSTALL_DIR)
# -------------------------------------------------
chown -R "$INSTALL_USER":"$INSTALL_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/versusd.sh"
chmod +x "$INSTALL_DIR/vsctl"
chmod +x "$INSTALL_DIR/install_vsd.sh"
# onboard.sh will be created later; ensure it's executable if exists
if [ -f "$INSTALL_DIR/onboard.sh" ]; then
    chmod +x "$INSTALL_DIR/onboard.sh"
fi

# -------------------------------------------------
# 4. Instalar unidades systemd (sustituir %i por el usuario real)
# -------------------------------------------------
for unit in versusd.service versusd-update.service versusd-update.timer versusd-onboarding.service; do
    sed "s|%i|$INSTALL_USER|g" "$INSTALL_DIR/$unit" > "/etc/systemd/system/$unit"
    chmod 644 "/etc/systemd/system/$unit"
done

# -------------------------------------------------
# 5. Preparar logs y dar propiedad al usuario
# -------------------------------------------------
touch "$LOG_DIR/versusd.log" "$LOG_DIR/hermes-gateway.log"
chown "$INSTALL_USER:$INSTALL_USER" "$LOG_DIR/versusd.log" "$LOG_DIR/hermes-gateway.log"

# -------------------------------------------------
# 6. Almacenar el token de provisión (uno por producto)
# -------------------------------------------------
if [ -n "${PROVISION_TOKEN:-}" ] && [ -n "${PROVISION_ID:-}" ]; then
    TOKEN_FILE="$TOKENS_DIR/$PROVISION_ID.token"
    echo "Guardando token de provisión para el producto '$PROVISION_ID'…"
    echo "$PROVISION_TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    chown root:root "$TOKEN_FILE"

    # Guardar también el ID para que el service de onboarding lo lea
    echo "$PROVISION_ID" > "$PROVISION_ID_FILE"
    chmod 644 "$PROVISION_ID_FILE"
    chown root:root "$PROVISION_ID_FILE"

    echo "Token y ID guardados en $TOKENS_DIR y $PROVISION_ID_FILE"
else
    echo "Advertencia: no se recibió PROVISION_TOKEN y/o PROVISION_ID; el registro del producto quedará pendiente."
fi

# -------------------------------------------------
# 7. Habilitar y arrancar nuestros servicios
# -------------------------------------------------
systemctl daemon-reload
systemctl enable --now versusd.service
systemctl enable --now versusd-update.timer
systemctl enable --now versusd-onboarding.service   # se ejecutará tras versusd.service

# -------------------------------------------------
# 8. Mensaje final
# -------------------------------------------------
echo "=== Instalación completada ==="
echo "Servicios activos:"
echo "  hermes-gateway.service      (gateway de Hermes, monitorizado por versusd)"
echo "  versusd.service            (watchdog que reinicia hermes‑gateway si cae)"
echo "  versusd-update.timer       (timer diario que ejecuta 'vsctl update')"
echo "  versusd-onboarding.service (oneshot que obtiene e instala VCOO desde el backend)"
echo ""
echo "Puedes usar el comando 'vsctl' para interactuar:"
echo "  vsctl status   → estado de hermes‑gateway y versusd"
echo "  vsctl update   → actualiza Hermes y la plantilla VCOO"
echo "  vsctl logs     → sigue el log de versusd"
echo "  vsctl hermes-logs → sigue el log de hermes‑gateway"
echo ""
echo "Los tokens de provisión se encuentran en:"
echo "  $TOKENS_DIR/<PROVISION_ID>.token"
echo "  y el ID en $PROVISION_ID_FILE"
