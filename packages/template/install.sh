#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VCOO Virtual — Instalador completo
# ═══════════════════════════════════════════════════════════════
# Uso:
#   bash install.sh
# o
#   curl -fsSL https://install.vcoo.dev | bash
#
# Este script:
#   1. Verifica requisitos del sistema
#   2. Instala dependencias (Python, uv, node, etc.)
#   3. Configura Hermes Agent
#   4. Copia skills y scripts VCOO
#   5. Configura integraciones
#   6. Arranca el gateway
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colores ─────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[VCOO]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# ── Configuración ──────────────────────────────────────────────
VCOO_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HOME}/.hermes"
HERMES_SKILLS="${HERMES_HOME}/skills"
HERMES_SCRIPTS="${HERMES_HOME}/scripts/vcoo"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     VCOO Virtual — Instalador            ║${NC}"
echo -e "${BLUE}║     by VERSUS Strategy SL                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Requisitos ──────────────────────────────────────────────
info "Verificando requisitos del sistema..."

OS="$(uname -s)"
ARCH="$(uname -m)"
info "  Sistema: ${OS} ${ARCH}"

# Python
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    err "Python3 no encontrado. Instálalo con: apt install python3"
    exit 1
fi
PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python ${PYVER} encontrado"

# curl
if ! command -v curl &>/dev/null; then
    warn "curl no encontrado. Instalando..."
    apt-get update -qq && apt-get install -y -qq curl
fi
ok "curl disponible"

# Git
if ! command -v git &>/dev/null; then
    warn "git no encontrado. Instalando..."
    apt-get update -qq && apt-get install -y -qq git
fi
ok "git disponible"

# ── 2. uv (gestor de paquetes Python rápido) ───────────────────
if ! command -v uv &>/dev/null; then
    info "Instalando uv..."
    curl -fsSL https://astral.sh/uv/install.sh | bash
    export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version 2>/dev/null || echo 'instalado')"

# ── 3. Instalar Hermes Agent + VCOO venv ────────────────────────
if ! command -v hermes &>/dev/null; then
    info "Instalando Hermes Agent..."
    
    # Crear VCOO venv con todas las dependencias (incluyendo Hermes Agent)
    mkdir -p "${HERMES_SCRIPTS}"
    if [ ! -d "${HERMES_SCRIPTS}/.venv" ]; then
        uv venv --python ${PYTHON} "${HERMES_SCRIPTS}/.venv"
    fi
    
    uv pip install --python "${HERMES_SCRIPTS}/.venv/bin/python" \
        hermes-agent \
        google-api-python-client google-auth-httplib2 google-auth-oauthlib \
        reportlab weasyprint httpx pyyaml 2>&1 | tail -1
    
    # Crear symlink para el comando hermes
    ln -sf "${HERMES_SCRIPTS}/.venv/bin/hermes" "${HOME}/.local/bin/hermes" 2>/dev/null || \
        warn "Crea un alias manual: alias hermes='${HERMES_SCRIPTS}/.venv/bin/hermes'"
    
    # Asegurar que ~/.local/bin está en PATH
    case ":${PATH}:" in
        *:"${HOME}/.local/bin":*) ;;
        *) export PATH="${HOME}/.local/bin:${PATH}"
           echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.bashrc" ;;
    esac
    
    ok "Hermes Agent instalado (vía pip en VCOO venv)"
else
    ok "Hermes Agent $(hermes --version 2>/dev/null || echo 'presente')"
fi

# ── 4. Configurar Hermes Agent (primera vez) ────────────────────
if [ ! -f "${HERMES_HOME}/config.yaml" ]; then
    info "Configurando Hermes Agent por primera vez..."
    mkdir -p "${HERMES_HOME}"
    
    # Copiar configuración base
    if [ -f "${VCOO_DIR}/config.yaml" ]; then
        cp "${VCOO_DIR}/config.yaml" "${HERMES_HOME}/config.yaml"
        ok "Configuración base copiada"
    fi
    
    # Copiar .env si existe
    if [ -f "${VCOO_DIR}/.env" ]; then
        cp "${VCOO_DIR}/.env" "${HERMES_HOME}/.env"
        chmod 600 "${HERMES_HOME}/.env"
        ok "Variables de entorno copiadas"
    fi
    
    # Copiar SOUL.md
    if [ -f "${VCOO_DIR}/SOUL.md" ]; then
        cp "${VCOO_DIR}/SOUL.md" "${HERMES_HOME}/SOUL.md"
        ok "Personalidad VCOO copiada"
    fi
    
    # Advertir si falta DISCORD_HOME_CHANNEL
    if [ -f "${HERMES_HOME}/.env" ] && ! grep -q '^DISCORD_HOME_CHANNEL=' "${HERMES_HOME}/.env" 2>/dev/null; then
        warn "DISCORD_HOME_CHANNEL no definido en .env — usa el ID del canal de Discord"
        warn "  Ejemplo: DISCORD_HOME_CHANNEL=1519113868411146391"
    fi
else
    info "Hermes Agent ya configurado. Saltando..."
fi

# ── 5. Copiar skills VCOO ──────────────────────────────────────
if [ -d "${VCOO_DIR}/skills" ]; then
    info "Instalando skills VCOO..."
    mkdir -p "${HERMES_SKILLS}/versus-multiagent-orchestration"
    for skill_dir in "${VCOO_DIR}/skills/"*/; do
        skill_name="$(basename "$skill_dir")"
        target="${HERMES_SKILLS}/versus-multiagent-orchestration/${skill_name}"
        if [ -d "$skill_dir" ]; then
            mkdir -p "$target"
            cp -r "$skill_dir"/* "$target/" 2>/dev/null || true
            ok "  Skill: ${skill_name}"
        fi
    done
fi

# ─── 6. Copiar scripts VCOO ─────────────────────────────────────
if [ -d "${VCOO_DIR}/scripts" ]; then
    info "Instalando scripts de integración..."
    mkdir -p "${HERMES_SCRIPTS}"
    for script in "${VCOO_DIR}/scripts/"*.py; do
        if [ -f "$script" ]; then
            # Skip vcoo-tester.py (it already has a portable shebang)
            if [[ "$(basename "$script")" == "vcoo-tester.py" ]]; then
                cp "$script" "${HERMES_SCRIPTS}/"
            else
                # Rewrite shebang to point to VCOO venv
                sed "1s|^#!/usr/bin/env python3|#!${HERMES_SCRIPTS}/.venv/bin/python3|" "$script" > "${HERMES_SCRIPTS}/$(basename "$script")"
            fi
            chmod +x "${HERMES_SCRIPTS}/$(basename "$script")"
        fi
    done
    for script in "${VCOO_DIR}/scripts/"*.sh; do
        if [ -f "$script" ]; then
            cp "$script" "${HERMES_SCRIPTS}/"
            chmod +x "${HERMES_SCRIPTS}/$(basename "$script")"
        fi
    done
    
    # Crear VCOO venv si no existe
    if [ ! -d "${HERMES_SCRIPTS}/.venv" ]; then
        info "Creando entorno virtual VCOO..."
        uv venv "${HERMES_SCRIPTS}/.venv"
        uv pip install --python "${HERMES_SCRIPTS}/.venv/bin/python" \
            google-api-python-client google-auth-httplib2 google-auth-oauthlib \
            reportlab weasyprint httpx pyyaml 2>&1 | tail -1
        ok "Entorno virtual VCOO creado"
    fi
    
    ok "Scripts de integración instalados"
fi

# ── 7. Ejecutar provisionamiento del servidor ──────────────────
if [ -f "${VCOO_DIR}/provision/setup-server.sh" ]; then
    info "Ejecutando provisionamiento del servidor..."
    bash "${VCOO_DIR}/provision/setup-server.sh" || warn "Provisionamiento parcial"
fi

# ── 8. Instalar y activar cron jobs ──────────────────────────────
if command -v hermes &>/dev/null; then
    if [ -d "${VCOO_DIR}/cron-jobs" ]; then
        info "Instalando y activando cron jobs automáticos..."
        mkdir -p "${HERMES_HOME}/cron/job-definitions"
        cp "${VCOO_DIR}/cron-jobs/"*.json "${HERMES_HOME}/cron/job-definitions/" 2>/dev/null || true
        
        # Activar cada cron job a partir de su JSON de definición
        for cronfile in "${HERMES_HOME}/cron/job-definitions/"*.json; do
            [ -f "$cronfile" ] || continue
            name=$(python3 -c "import json; print(json.load(open('$cronfile'))['name'])" 2>/dev/null)
            schedule=$(python3 -c "import json; print(json.load(open('$cronfile'))['schedule'])" 2>/dev/null)
            prompt=$(python3 -c "import json; print(json.load(open('$cronfile'))['prompt'])" 2>/dev/null)
            deliver=$(python3 -c "import json; print(json.load(open('$cronfile')).get('deliver',''))" 2>/dev/null)
            
            if [ -n "$name" ] && [ -n "$schedule" ]; then
                CMD="hermes cron create \"$schedule\" \"$prompt\" --name \"$name\""
                [ -n "$deliver" ] && CMD="$CMD --deliver $deliver"
                
                # No fallar si el cron ya existe (idempotente)
                eval "$CMD" 2>/dev/null && ok "  Cron activado: ${name} (${schedule})" || \
                    warn "  Cron ya existe o no se pudo activar: ${name}"
            fi
        done
        
        ok "Cron jobs configurados y activados"
    fi
fi

# ── 9. Registrar en control plane (si hay PROVISION_TOKEN) ──
if [ -n "${PROVISION_TOKEN:-}" ] && [ -n "${CONTROL_PLANE_URL:-}" ]; then
    info "Registrando agente en control plane..."
    RESP=$(curl -sS -w "\n%{http_code}" "${CONTROL_PLANE_URL}/register" \
      -H "Content-Type: application/json" \
      -d "{\"token\": \"$PROVISION_TOKEN\", \"info\": {\"hostname\": \"$(hostname)\", \"installer\": \"template-v2\"}}")
    HTTP_CODE=$(echo "$RESP" | tail -1)
    BODY=$(echo "$RESP" | sed '$d')

    if [ "$HTTP_CODE" = "200" ]; then
        AGENT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['agent_id'])" 2>/dev/null || echo "")
        VCOO_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['vcoo_id'])" 2>/dev/null || echo "")
        AGENT_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['agent_token'])" 2>/dev/null || echo "")

        # Guardar en .env de Hermes
        {
            echo ""
            echo "# VCOO Control Plane (añadido por instalador)"
            echo "VCOO_ID=${VCOO_ID}"
            echo "AGENT_ID=${AGENT_ID}"
            echo "AGENT_TOKEN=${AGENT_TOKEN}"
        } >> "${HERMES_HOME}/.env"

        ok "Agente registrado en control plane (ID: $AGENT_ID)"

        # Arrancar health reporter
        if [ -f "${HERMES_SCRIPTS}/vcoo/health-reporter.py" ]; then
            export AGENT_ID VCOO_ID AGENT_TOKEN CONTROL_PLANE="${CONTROL_PLANE_URL}"
            nohup python3 "${HERMES_SCRIPTS}/vcoo/health-reporter.py" > /tmp/vcoo-health.log 2>&1 &
            HPID=$!
            mkdir -p "$HOME/.vcoo-agent"
            echo "$HPID" > "$HOME/.vcoo-agent/health-reporter.pid"
            ok "Health reporter iniciado (PID $HPID)"
        fi
    else
        warn "No se pudo registrar el agente (HTTP $HTTP_CODE). Se puede registrar manualmente desde el panel."
    fi
fi

# ── 10. Resumen final ──────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Instalación completada                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "   Próximos pasos:"
echo ""
echo "   1. Configura las integraciones:"
echo "      bash provision/configure-oauth.sh"
echo ""
echo "   2. Edita tu configuración:"
echo "      hermes config edit"
echo ""
echo "   3. Arranca MAGI:"
echo "      hermes gateway run"
echo ""
echo "   4. Envíale un mensaje a MAGI desde Discord o Telegram"
echo ""
