#!/usr/bin/env bash
set -euo pipefail
# ═══════════════════════════════════════════════════════════════
# VCOO Virtual — Unified One-Line Installer v1.0
# ═══════════════════════════════════════════════════════════════
# by VERSUS Strategy SL
#
# Uso:
#   curl -fsSL https://vcoo.dev/install | PROVISION_TOKEN=*** bash
#
# Este script despliega la template VCOO completa:
#   1. Valida PROVISION_TOKEN contra el control plane
#   2. Descarga la template (git clone → fallback ZIP)
#   3. Configura .env con secrets del control plane
#   4. Ejecuta install.sh de la template (Hermes + skills + cron)
#   5. Arranca health reporter en background
#   6. Muestra resumen final
#
# Sin PROVISION_TOKEN → fallback a instalación manual (solo template)
# ═══════════════════════════════════════════════════════════════

CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"
VCOO_HOME="${VCOO_HOME:-$HOME/.vcoo}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

# ── Colores ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[VCOO]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     VCOO Virtual — Instalador            ║${NC}"
echo -e "${BLUE}║     by VERSUS Strategy SL                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Validar PROVISION_TOKEN (opcional) ──
PROVISION_TOKEN="${PROVISION_TOKEN:-}"
AGENT_ID=""
VCOO_ID=""
AGENT_TOKEN=""

if [ -n "$PROVISION_TOKEN" ]; then
    info "Validando provision token..."
    RESP=$(curl -sS -w "\n%{http_code}" "${CONTROL_PLANE}/register" \
      -H "Content-Type: application/json" \
      -d "{\"token\": \"$PROVISION_TOKEN\", \"info\": {\"hostname\": \"$(hostname)\", \"platform\": \"linux\", \"installer\": \"unified-v1\"}}")
    HTTP_CODE=$(echo "$RESP" | tail -1)
    BODY=$(echo "$RESP" | sed '$d')

    if [ "$HTTP_CODE" != "200" ]; then
        err "Token inválido o expirado (HTTP $HTTP_CODE).\n  Verifica tu token en el panel de control (${CONTROL_PLANE})."
    fi

    AGENT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['agent_id'])" 2>/dev/null || echo "")
    VCOO_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['vcoo_id'])" 2>/dev/null || echo "")
    AGENT_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['agent_token'])" 2>/dev/null || echo "")
    ok "Token válido. Agente registrado (ID: ${AGENT_ID})"
else
    warn "No se proporcionó PROVISION_TOKEN — instalación manual."
    warn "El agente no se registrará automáticamente en el control plane."
    echo ""
fi

# ── 2. Descargar template VCOO ──
TEMPLATE_DIR="${VCOO_HOME}/template"
if [ -d "$TEMPLATE_DIR" ] && [ -f "$TEMPLATE_DIR/install.sh" ]; then
    info "Template ya existe en $TEMPLATE_DIR (se omite descarga)"
else
    info "Descargando template VCOO..."
    mkdir -p "$VCOO_HOME"

    if command -v git &>/dev/null; then
        GIT_REPO="${VCOO_GIT_REPO:-https://github.com/Versus-Strategy/vcoo-template.git}"
        git clone --depth 1 "$GIT_REPO" "$TEMPLATE_DIR" 2>/dev/null || {
            warn "Git clone falló, intentando descarga directa..."
            curl -sSL "${CONTROL_PLANE}/template.tar.gz" -o /tmp/vcoo-template.tar.gz 2>/dev/null || \
            curl -sSL "https://github.com/Versus-Strategy/vcoo-template/archive/main.tar.gz" -o /tmp/vcoo-template.tar.gz
            mkdir -p "$TEMPLATE_DIR"
            tar -xzf /tmp/vcoo-template.tar.gz --strip-components=1 -C "$TEMPLATE_DIR" 2>/dev/null || \
            err "No se pudo descargar la template. Verifica conexión a GitHub."
        }
    else
        warn "git no disponible — usando descarga directa..."
        curl -sSL "https://github.com/Versus-Strategy/vcoo-template/archive/main.tar.gz" -o /tmp/vcoo-template.tar.gz
        mkdir -p "$TEMPLATE_DIR"
        tar -xzf /tmp/vcoo-template.tar.gz --strip-components=1 -C "$TEMPLATE_DIR" || \
        err "No se pudo descargar la template."
    fi
    ok "Template descargada en $TEMPLATE_DIR"
fi

if [ ! -f "$TEMPLATE_DIR/install.sh" ]; then
    err "La template descargada no contiene install.sh — descarga corrupta."
fi

# ── 3. Configurar .env ──
if [ -n "$VCOO_ID" ]; then
    if [ ! -f "$TEMPLATE_DIR/.env" ]; then
        info "Configurando .env con secrets del control plane..."
        # Intentar obtener secrets — fallback silencioso a vacío
        ENV_RESP=$(curl -sS "${CONTROL_PLANE}/vcoo/${VCOO_ID}/secrets" 2>/dev/null || echo "{}")

        # Extraer secrets con python3
        OPENROUTER_KEY=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('OPENROUTER_API_KEY',''))" 2>/dev/null || echo "")
        DISCORD_TOKEN=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('DISCORD_BOT_TOKEN',''))" 2>/dev/null || echo "")
        TELEGRAM_TOKEN=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null || echo "")
        HOME_CHANNEL=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('DISCORD_HOME_CHANNEL',''))" 2>/dev/null || echo "")

        cat > "$TEMPLATE_DIR/.env" << EOF
# VCOO — Generado por instalador unificado v1.0
OPENROUTER_API_KEY=${OPENROUTER_KEY}
DISCORD_BOT_TOKEN=${DISCORD_TOKEN}
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}
DISCORD_HOME_CHANNEL=${HOME_CHANNEL}
VCOO_ID=${VCOO_ID}
AGENT_ID=${AGENT_ID}
AGENT_TOKEN=${AGENT_TOKEN}
CONTROL_PLANE_URL=${CONTROL_PLANE}
EOF
        chmod 600 "$TEMPLATE_DIR/.env"
        ok ".env configurado en $TEMPLATE_DIR/.env"
    else
        info ".env ya existe — se mantiene el existente"
    fi
fi

# ── 4. Ejecutar instalador de la template ──
export PROVISION_TOKEN="${PROVISION_TOKEN:-}"
export VCOO_ID="${VCOO_ID:-}"
export AGENT_ID="${AGENT_ID:-}"
export AGENT_TOKEN="${AGENT_TOKEN:-}"
export CONTROL_PLANE_URL="${CONTROL_PLANE}"

info "Ejecutando instalador de la template..."
bash "$TEMPLATE_DIR/install.sh"
ok "Template instalada correctamente"

# ── 5. Arrancar health reporter (si hay agente registrado) ──
if [ -n "$AGENT_ID" ] && [ -f "$TEMPLATE_DIR/scripts/health-reporter.py" ]; then
    HEALTH_SCRIPT="${HERMES_HOME}/scripts/vcoo/health-reporter.py"
    mkdir -p "$(dirname "$HEALTH_SCRIPT")"
    cp "$TEMPLATE_DIR/scripts/health-reporter.py" "$HEALTH_SCRIPT"

    info "Arrancando health reporter..."
    export AGENT_ID VCOO_ID AGENT_TOKEN CONTROL_PLANE
    nohup python3 "$HEALTH_SCRIPT" > /tmp/vcoo-health.log 2>&1 &
    HPID=$!
    mkdir -p "$HOME/.vcoo-agent"
    echo "$HPID" > "$HOME/.vcoo-agent/health-reporter.pid"
    ok "Health reporter iniciado (PID $HPID)"
    info "  Logs: /tmp/vcoo-health.log"
    info "  PIDs: $HOME/.vcoo-agent/health-reporter.pid"
fi

# ── 6. Resumen final ──
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Instalación completada               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Template:   $TEMPLATE_DIR"
echo "  Hermes:     $HERMES_HOME"
if [ -n "$VCOO_ID" ]; then
    echo "  VCOO ID:    $VCOO_ID"
fi
if [ -n "$AGENT_ID" ]; then
    echo "  Agent ID:   $AGENT_ID"
    echo "  Health PID: $(cat $HOME/.vcoo-agent/health-reporter.pid 2>/dev/null || echo 'N/A')"
fi
echo ""
echo "  Próximos pasos:"
echo "  1. Configura los módulos contratados:"
echo "     - Google OAuth:  ${CONTROL_PLANE}/setup/${PROVISION_TOKEN}"
echo "     - Trello:        Configurar API key en el panel"
echo "     - GitHub:        gh auth login"
echo "  2. Inicia Hermes:   cd ~/.hermes && hermes gateway run"
echo "  3. Envía un mensaje desde Discord al bot para probar"
echo ""
echo -e "${CYAN}¿Necesitas ayuda? contact@versusstrategy.com${NC}"
echo ""
