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

# ── Detección de instalación previa ─────────────────────────
VCOO_SUPERVISOR_DIR="/opt/vcoo-supervisor"
PREVIOUS_INSTALL=false
if [ -d "$VCOO_SUPERVISOR_DIR" ] || systemctl list-unit-files 2>/dev/null | grep -q 'vcoo-'; then
    PREVIOUS_INSTALL=true
    echo ""
    echo -e "${YELLOW}⚠ Se detectó una instalación previa de VCOO.${NC}"
    echo -n -e "${YELLOW}¿Deseas reinstalar los servicios VCOO? (se conservarán las dependencias del sistema) [s/N]: ${NC}"
    REINSTALL=""
    if [ -t 0 ]; then
        read -r REINSTALL
    elif [ -e /dev/tty ]; then
        read -r REINSTALL < /dev/tty
    fi
    if [ "$REINSTALL" != "s" ] && [ "$REINSTALL" != "S" ]; then
        echo ""
        info "Reinstalación cancelada por el usuario."
        exit 0
    fi
    info "Limpiando servicios VCOO anteriores..."
    for svc in vcoo-health-reporter vcoo-hermes-gateway vcoo-supervisor; do
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo rm -f "/etc/systemd/system/${svc}.service" 2>/dev/null || true
    done
    sudo systemctl daemon-reload
    sudo rm -rf "$VCOO_SUPERVISOR_DIR" 2>/dev/null || true
    ok "Limpieza completada"
fi

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
ok "curl disponiblee"

# Git
if ! command -v git &>/dev/null; then
    warn "git no encontrado. Instalando..."
    apt-get update -qq && apt-get install -y -qq git
fi
ok "git disponiblee"

# XZ (needed for tar .xz)
if ! command -v xz &>/dev/null; then
    info "XZ no encontrado. Instalando..."
    apt-get update -qq && apt-get install -y -qq xz-utils
fi
ok "xz disponible"

# gettext (provides envsubst)
if ! command -v gettext &>/dev/null; then
    info "gettext no encontrado. Instalando..."
    apt-get update -qq && apt-get install -y -qq gettext
fi
ok "gettext disponiblee"

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
    
    # Crear VCOO venv con dependencias de Python (google-api, etc.)
    mkdir -p "${HERMES_SCRIPTS}"
    if [ ! -d "${HERMES_SCRIPTS}/.venv" ]; then
        uv venv --python ${PYTHON} "${HERMES_SCRIPTS}/.venv"
    fi
    
    # Instalar dependencias de VCOO en el venv (NO Hermes Agent)
    uv pip install --python "${HERMES_SCRIPTS}/.venv/bin/python" \
        google-api-python-client google-auth-httplib2 google-auth-oauthlib \
        reportlab weasyprint httpx pyyaml 2>&1 | tail -1
    
    # Instalar Hermes Agent (método oficial: installer de Nous Research)
    # Documentación: https://hermes-agent.nousresearch.com/docs/installation
    if ! command -v hermes &>/dev/null; then
        info "Instalando Hermes Agent (método oficial)..."
        if curl -fsSL --connect-timeout 10 --max-time 300 https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup --skip-browser --non-interactive; then
            export PATH="$HOME/.local/bin:$PATH"
            hash -r
            ok "Hermes Agent $(hermes --version 2>/dev/null || echo 'instalado')"
        else
            warn "No se pudo descargar/instalar Hermes Agent automáticamente."
            warn "  Si hay conexión a Internet, instálalo manualmente:"
            warn "    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
        fi
    else
        ok "Hermes Agent $(hermes --version 2>/dev/null || echo 'presente')"
    fi
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

# ── 5. Instalar skills VCOO (solo módulos contratados) ──────────
# Skill → módulo que la requiere
skill_requires_module() {
    case "$1" in
        vcoo-core)              echo "core" ;;
        vcoo-google-workspace)  echo "office" ;;
        vcoo-email)             echo "mail" ;;
        vcoo-trello)            echo "planner" ;;
        vcoo-pdf|vcoo-testing|vcoo-behavioral-testing) echo "" ;;  # siempre
        *) echo "" ;;
    esac
}

if [ -d "${VCOO_DIR}/skills" ]; then
    info "Instalando skills VCOO..."
    mkdir -p "${HERMES_SKILLS}/versus-multiagent-orchestration"
    for skill_dir in "${VCOO_DIR}/skills/"*/; do
        skill_name="$(basename "$skill_dir")"
        req_mod=$(skill_requires_module "$skill_name")
        if [ -n "$req_mod" ]; then
            # Solo instalar si el módulo está contratado
            echo "${MODULES:-}" | grep -qw "$req_mod" || continue
        fi
        target="${HERMES_SKILLS}/versus-multiagent-orchestration/${skill_name}"
        if [ -d "$skill_dir" ]; then
            mkdir -p "$target"
            cp -r "$skill_dir"/* "$target/" 2>/dev/null || true
            ok "  Skill: ${skill_name}"
        fi
    done
fi

# ─── 6. Descargar scripts VCOO (autenticado con PROVISION_TOKEN) ──
info "Descargando scripts de integración..."
mkdir -p "${HERMES_SCRIPTS}"
VCOO_ID="${VCOO_ID:-$(grep -oP 'VCOO_ID=\K.*' "${HERMES_HOME}/.env" 2>/dev/null || echo '')}"
PROV_TOKEN="${PROVISION_TOKEN:-$(grep -oP 'PROVISION_TOKEN=\K.*' "${HERMES_HOME}/.env" 2>/dev/null || echo '')}"
CONTROL="${CONTROL_PLANE:-${CONTROL_PLANE_URL:-}}"

# Obtener módulos del VCOO desde el control plane
MODULES=""
if [ -n "$VCOO_ID" ] && [ -n "$PROV_TOKEN" ] && [ -n "$CONTROL" ]; then
    MODULES=$(curl -sSf "${CONTROL}/setup/${VCOO_ID}" -H "Authorization: Bearer ${PROV_TOKEN}" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(' '.join(d.get('modules',[])))" 2>/dev/null || echo "")
fi

fetch_script() {
    local name="$1"
    local dest="${HERMES_SCRIPTS}/${name}"
    if [ -f "$dest" ]; then
        return 0
    fi
    if curl -sSf -o "$dest" "${CONTROL}/setup/${VCOO_ID}/playbooks/${name}" \
        -H "Authorization: Bearer ${PROV_TOKEN}" 2>/dev/null; then
        sed -i "1s|^#!/usr/bin/env python3|#!${HERMES_SCRIPTS}/.venv/bin/python3|" "$dest" 2>/dev/null || true
        chmod +x "$dest"
        ok "$name"
        return 0
    fi
}

# Solo descargar scripts de los módulos contratados
for mod in $MODULES; do
    case "$mod" in
        core)     fetch_script "vcoo-bootstrap.py" && fetch_script "venv-setup.sh" ;;
        office)   fetch_script "vcoo-google.py" ;;
        mail)     fetch_script "vcoo-email.py" ;;
        planner)  fetch_script "vcoo-trello.py" ;;
    esac
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
# Si AGENT_ID ya está exportado (ej: instalación vía unified installer),
# saltamos el registro API y configuramos directamente.
REGISTERED=false
if [ -n "${AGENT_ID:-}" ]; then
    info "Agente ya registrado (ID: ${AGENT_ID}) — omitiendo registro..."
    REGISTERED=true
elif [ -n "${PROVISION_TOKEN:-}" ] && [ -n "${CONTROL_PLANE_URL:-}" ]; then
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
        REGISTERED=true
        ok "Agente registrado en control plane (ID: $AGENT_ID)"
    else
        warn "No se pudo registrar el agente (HTTP $HTTP_CODE). Se puede registrar manualmente desde el panel."
    fi
fi

# ── 9b. Configurar .env y servicios systemd si tenemos agente ──
if $REGISTERED && [ -n "${AGENT_ID:-}" ]; then
    # Guardar/actualizar .env de Hermes
    {
        echo ""
        echo "# VCOO Control Plane (añadido por instalador)"
        echo "VCOO_ID=${VCOO_ID:-}"
        echo "AGENT_ID=${AGENT_ID}"
        echo "AGENT_TOKEN=${AGENT_TOKEN:-}"
        echo "CONTROL_PLANE=${CONTROL_PLANE:-${CONTROL_PLANE_URL:-}}"
    } >> "${HERMES_HOME}/.env"

    # Detectar paths para systemd
    HERMES_PYTHON="${HERMES_PYTHON:-$(which python3 2>/dev/null || echo /usr/bin/python3)}"
    HERMES_BIN="${HERMES_BIN:-$(which hermes 2>/dev/null || echo /usr/local/bin/hermes)}"
    export HERMES_PYTHON HERMES_BIN HERMES_SCRIPTS HERMES_HOME HOME USER

    # Copiar supervisor VCOO
    SUPERVISOR_SRC="${VCOO_DIR}/vcoo-supervisor"
    if [ -d "$SUPERVISOR_SRC" ]; then
        info "Instalando vcoo-supervisor..."
        sudo mkdir -p "$VCOO_SUPERVISOR_DIR/plugins"
        sudo cp "$SUPERVISOR_SRC/supervisor.py" "$VCOO_SUPERVISOR_DIR/"
        sudo cp "$SUPERVISOR_SRC/config.json" "$VCOO_SUPERVISOR_DIR/"
        sudo cp "$SUPERVISOR_SRC/plugins/"*.py "$VCOO_SUPERVISOR_DIR/plugins/"
        # Escribir AGENT_ID y CONTROL_PLANE en config
        sudo python3 -c "
import json
with open('$VCOO_SUPERVISOR_DIR/config.json') as f:
    cfg = json.load(f)
tk = cfg.setdefault('plugins', {}).setdefault('tick', {})
tk['agent_id'] = '$AGENT_ID'
tk['agent_token'] = '$AGENT_TOKEN'
tk['control_plane'] = '${CONTROL_PLANE:-${CONTROL_PLANE_URL:-}}'
with open('$VCOO_SUPERVISOR_DIR/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"
        ok "vcoo-supervisor instalado en $VCOO_SUPERVISOR_DIR"
    else
        warn "Origen del supervisor no encontrado en $SUPERVISOR_SRC — saltando"
    fi

    # Configurar servicios systemd
    info "Configurando servicios systemd..."
    
    SERVICE_TEMP_DIR="$(mktemp -d)"
    cp "${VCOO_DIR}/files/systemd/vcoo-supervisor.service" "${SERVICE_TEMP_DIR}/" 2>/dev/null || true
    cp "${VCOO_DIR}/files/systemd/vcoo-hermes-gateway.service" "${SERVICE_TEMP_DIR}/" 2>/dev/null || true
    
    for service_template in "${SERVICE_TEMP_DIR}"/*.service; do
        [ -f "$service_template" ] || continue
        service_name="$(basename "$service_template")"
        
        envsubst < "$service_template" | sudo tee "/etc/systemd/system/$service_name" > /dev/null || {
            sed -e "s|\$HERMES_SCRIPTS|${HERMES_SCRIPTS}|g" \
                -e "s|\$HERMES_HOME|${HERMES_HOME}|g" \
                -e "s|\$HERMES_PYTHON|${HERMES_PYTHON:-/usr/bin/python3}|g" \
                -e "s|\$HERMES_BIN|${HERMES_BIN:-/usr/local/bin/hermes}|g" \
                -e "s|\$HOME|${HOME}|g" \
                -e "s|\$USER|$(whoami)|g" \
                "$service_template" | sudo tee "/etc/systemd/system/$service_name" > /dev/null
        }
        
        ok "Service copiado: $service_name"
    done
    
    sudo systemctl daemon-reload && ok "Systemd daemon recargado"
    
    sudo systemctl enable --now vcoo-supervisor.service && \
    ok "Supervisor habilitado e iniciado" || \
    warn "Failed to enable/start supervisor"
    
    sudo systemctl enable --now vcoo-hermes-gateway.service && \
    ok "Hermes gateway habilitado e iniciado" || \
    warn "Failed to enable/start Hermes gateway"
    
    rm -rf "$SERVICE_TEMP_DIR"
    
    info "Servicios systemd configurados. Puede verificar con:"
    info "  systemctl status vcoo-supervisor"
    info "  systemctl status vcoo-hermes-gateway"
fi

# ── 10. Resumen final ──────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Instalación completada                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "   Próximos pasos:"
echo ""
echo "   1. Verifica el estado de los servicios:"
echo "      systemctl status vcoo-supervisor"
echo "      systemctl status vcoo-hermes-gateway"
echo ""
echo "   2. Edita tu configuración:"
echo "      hermes config edit"
echo ""
echo "   3. Configura las integraciones:"
echo "      bash provision/configure-oauth.sh"
echo ""
echo "   4. Envía un mensaje a MAGI desde Discord o Telegram"
echo ""
