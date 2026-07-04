#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VCOO Virtual — Asistente de configuración OAuth
# ═══════════════════════════════════════════════════════════════
# Guía al cliente para conectar sus cuentas (Google, Trello, etc.)
#
# Uso: bash provision/configure-oauth.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[OAUTH]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }

HERMES_HOME="${HOME}/.hermes"
SCRIPTS_DIR="${HERMES_HOME}/scripts/vcoo"
VCOO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Configuración de Integraciones VCOO    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Google Workspace ────────────────────────────────────────
echo -e "${YELLOW}═══ Google Workspace (Drive, Docs, Gmail) ═══${NC}"
echo ""
echo "   Para conectar Google necesitas:"
echo "   1. Ir a https://console.cloud.google.com/"
echo "   2. Crear un proyecto → Habilitar APIs (Drive, Docs, Sheets, Gmail)"
echo "   3. Crear credenciales OAuth 2.0 → Descargar JSON"
echo "   4. Colocar el JSON en: ${HERMES_HOME}/google_client_secret.json"
echo "   5. Ejecutar el siguiente comando para iniciar sesión:"
echo ""
echo "      python3 ${SCRIPTS_DIR}/vcoo-google.py drive list"
echo ""
echo "   (Se abrirá un navegador para autorizar el acceso)"
echo ""
read -p "   ¿Has configurado Google OAuth? (s/N): " google_ok
if [[ "$google_ok" =~ ^[sS] ]]; then
    ok "Google Workspace marcado como configurado"
else
    warn "Puedes configurarlo más tarde"
fi

# ── 2. Trello ──────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}═══ Trello (Backlog y Tareas) ═══${NC}"
echo ""
echo "   Para conectar Trello necesitas:"
echo "   1. Ir a https://trello.com/power-ups/admin"
echo "   2. Crear un Power-Up → Obtener API Key"
echo "   3. Generar un Token en:"
echo "      https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=VCOO&key=TU_API_KEY"
echo ""
echo "   Crea el archivo: ${VCOO_DIR}/.env.trello"
echo "   con el siguiente contenido:"
echo ""
echo "      TRELLO_API_KEY=\"tu-api-key\""
echo "      TRELLO_TOKEN=\"tu-token\""
echo ""
read -p "   ¿Has configurado Trello? (s/N): " trello_ok
if [[ "$trello_ok" =~ ^[sS] ]]; then
    ok "Trello marcado como configurado"
else
    warn "Puedes configurarlo más tarde"
fi

# ── 3. Discord ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}═══ Discord (Canal de comunicación) ═══${NC}"
echo ""
echo "   Asegúrate de que el archivo .env tenga:"
echo "   DISCORD_BOT_TOKEN=tu-bot-token"
echo ""
echo "   El bot necesita los siguientes intents:"
echo "   - Message Content Intent"
echo "   - Server Members Intent"
echo ""
read -p "   ¿Has configurado Discord? (s/N): " discord_ok
if [[ "$discord_ok" =~ ^[sS] ]]; then
    ok "Discord marcado como configurado"
else
    warn "Puedes configurarlo más tarde"
fi

# ── 4. Prueba de integraciones ─────────────────────────────────
echo ""
echo -e "${YELLOW}═══ Verificación ═══${NC}"
echo ""

if [ -f "${SCRIPTS_DIR}/vcoo-trello.py" ] && [ -f "${VCOO_DIR}/.env.trello" ]; then
    echo "   Probando Trello..."
    python3 "${SCRIPTS_DIR}/vcoo-trello.py" boards 2>&1 | head -5
fi

if [ -f "${HOME}/.hermes/google_token.json" ]; then
    echo "   Probando Google Drive..."
    python3 "${SCRIPTS_DIR}/vcoo-google.py" drive list 2>&1 | head -5
fi

echo ""
ok "Configuración completada"
echo ""
echo "   Ahora puedes arrancar MAGI:"
echo "   hermes gateway run"
echo ""
