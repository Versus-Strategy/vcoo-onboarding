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
#   1. Verifica/instala dependencias (curl, python3, git)
#   2. Valida PROVISION_TOKEN contra el control plane
#   3. Descarga la template
#   4. Configura .env con secrets del control plane
#   5. Ejecuta install.sh de la template (Hermes + skills + cron)
#   6. Arranca health reporter en background
#   7. Muestra resumen final
#
# Sin PROVISION_TOKEN → instalación manual (solo template)
# ═══════════════════════════════════════════════════════════════

# Asegurar HOME (systemd no lo exporta por defecto cuando corre como root)
export HOME="${HOME:-/root}"

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

# ── 0. Dependencias ─────────────────────────────────────────
info "Verificando dependencias del sistema..."

# Detectar gestor de paquetes
PKG_MANAGER=""
INSTALL_CMD=""
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt-get"
    INSTALL_CMD="apt-get install -y"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
    INSTALL_CMD="yum install -y"
elif command -v apk &>/dev/null; then
    PKG_MANAGER="apk"
    INSTALL_CMD="apk add"
fi

# Detectar si podemos instalar paquetes
CAN_INSTALL=false
if [ "$(id -u)" = "0" ] && [ -n "$PKG_MANAGER" ]; then
    CAN_INSTALL=true
elif command -v sudo &>/dev/null && [ -n "$PKG_MANAGER" ]; then
    CAN_INSTALL=true
    INSTALL_CMD="sudo $INSTALL_CMD"
fi

# Función para instalar o avisar
ensure_cmd() {
    local cmd="$1"
    local pkg="${2:-$1}"
    if ! command -v "$cmd" &>/dev/null; then
        if $CAN_INSTALL; then
            info "Instalando $pkg..."
            $INSTALL_CMD "$pkg" || warn "No se pudo instalar $pkg automáticamente"
        fi
        if ! command -v "$cmd" &>/dev/null; then
            warn "Falta $cmd. Instálalo manualmente:"
            if [ -n "$PKG_MANAGER" ]; then
                echo "  $INSTALL_CMD $pkg"
            else
                echo "  $pkg (usa el gestor de paquetes de tu distro)"
            fi
        fi
    fi
}

ensure_cmd curl curl
ensure_cmd python3 python3
ensure_cmd git git
ensure_cmd xz xz-utils

# Verificar que tenemos lo mínimo indispensable
if ! command -v curl &>/dev/null; then
    err "curl es necesario. Instálalo y vuelve a ejecutar."
fi

# Verificar que python3 >= 3.11 (hermes-agent lo requiere)
PYTHON_OK=false
if command -v python3 &>/dev/null; then
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -gt 3 ] || { [ "$PY_MAJOR" = "3" ] && [ "$PY_MINOR" -ge 11 ]; }; then
        PYTHON_OK=true
    fi
fi

if ! $PYTHON_OK; then
    warn "Se necesita Python >= 3.11 (actual: $(python3 --version 2>/dev/null || echo 'no encontrado'))"
    if $CAN_INSTALL && [ "$PKG_MANAGER" = "apt-get" ]; then
        info "Instalando Python 3.11..."
        $INSTALL_CMD python3.11 python3.11-venv 2>/dev/null || true
        if command -v python3.11 &>/dev/null; then
            # Hacer que python3 apunte a 3.11 (para que el template lo use)
            ln -sf /usr/bin/python3.11 /usr/local/bin/python3
            hash -r
            PYTHON_OK=true
        fi
    fi
    if ! $PYTHON_OK; then
        echo ""
        warn "Instala Python 3.11 manualmente:"
        echo "  sudo apt-get install python3.11 python3.11-venv"
        err "Python >= 3.11 es necesario. Vuelve a ejecutar tras instalarlo."
    fi
fi

if ! command -v python3 &>/dev/null; then
    err "python3 es necesario. Instálalo y vuelve a ejecutar."
fi

ok "Dependencias listas"

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
info "Descargando template VCOO..."
mkdir -p "$VCOO_HOME"

# Opción 1: descarga directa desde el control plane
info "  Descargando ${CONTROL_PLANE}/template.tar.gz ..."
curl -fsSL "${CONTROL_PLANE}/template.tar.gz" -o /tmp/vcoo-template.tar.gz || {
        # Opción 2: git clone como fallback
        if command -v git &>/dev/null; then
            warn "Descarga directa falló, intentando git clone..."
            git clone --depth 1 "https://github.com/Versus-Strategy/vcoo-template.git" "$TEMPLATE_DIR" 2>/dev/null || \
            err "No se pudo descargar la template. Verifica conexión a Internet."
        else
            err "No se pudo descargar la template. Verifica conexión a Internet."
        fi
    }

    # Si descargamos el tar.gz, extraerlo
    if [ -f /tmp/vcoo-template.tar.gz ]; then
        mkdir -p "$TEMPLATE_DIR"
        tar -xzf /tmp/vcoo-template.tar.gz -C "$TEMPLATE_DIR" || \
        err "Error al extraer la template (descarga corrupta)."
    fi

    # Verificar que se descargó correctamente
    if [ -f "$TEMPLATE_DIR/install.sh" ]; then
        ok "Template descargada en $TEMPLATE_DIR"
    else
        err "La template descargada no contiene install.sh — descarga corrupta."
    fi

# ── 3. Configurar .env ──
if [ -n "$VCOO_ID" ]; then
    if [ ! -f "$TEMPLATE_DIR/.env" ]; then
        info "Configurando .env con secrets del control plane..."
        ENV_RESP=$(curl -sS "${CONTROL_PLANE}/vcoo/${VCOO_ID}/secrets" 2>/dev/null || echo "{}")

        OPENROUTER_KEY=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('OPENROUTER_API_KEY',''))" 2>/dev/null || echo "")
        DISCORD_TOKEN=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('DISCORD_BOT_TOKEN',''))" 2>/dev/null || echo "")
        TELEGRAM_TOKEN=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('TELEGRAM_BOT_TOKEN',''))" 2>/dev/null || echo "")
        HOME_CHANNEL=$(echo "$ENV_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('DISCORD_HOME_CHANNEL',''))" 2>/dev/null || echo "")

        > "$TEMPLATE_DIR/.env"
        echo "# VCOO — Generado por instalador unificado v1.0" >> "$TEMPLATE_DIR/.env"
        echo "OPENROUTER_API_KEY=${OPENROUTER_KEY}" >> "$TEMPLATE_DIR/.env"
        echo "DISCORD_BOT_TOKEN=${DISCORD_TOKEN}" >> "$TEMPLATE_DIR/.env"
        echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}" >> "$TEMPLATE_DIR/.env"
        echo "DISCORD_HOME_CHANNEL=${HOME_CHANNEL}" >> "$TEMPLATE_DIR/.env"
        echo "VCOO_ID=${VCOO_ID}" >> "$TEMPLATE_DIR/.env"
        echo "AGENT_ID=${AGENT_ID}" >> "$TEMPLATE_DIR/.env"
        echo "AGENT_TOKEN=${AGENT_TOKEN}" >> "$TEMPLATE_DIR/.env"
        echo "CONTROL_PLANE_URL=${CONTROL_PLANE}" >> "$TEMPLATE_DIR/.env"
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
fi
echo ""
echo "  Próximos pasos:"
echo "  1. Configura los módulos contratados:"
echo "     - Google OAuth:  ${CONTROL_PLANE}/setup/${PROVISION_TOKEN}"
echo "     - Trello:        Configurar API key en el panel"
echo "     - GitHub:        gh auth login"
echo ""
echo "  2. Verifica el estado de los servicios:"
echo "     systemctl status vcoo-health-reporter"
echo "     systemctl status vcoo-hermes-gateway"
echo ""
echo "  3. Edita tu configuración:"
echo "      hermes config edit"
echo ""
echo "  4. Envía un mensaje a MAGI desde Discord o Telegram"
echo ""
echo -e "${CYAN}¿Necesitas ayuda? contact@versusstrategy.com${NC}"
echo ""
