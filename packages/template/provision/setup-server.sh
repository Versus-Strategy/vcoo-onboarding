#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VCOO Virtual — Provisionamiento del servidor
# ═══════════════════════════════════════════════════════════════
# Configura el servidor Linux para VCOO: hardening, dependencias,
# y optimizaciones de rendimiento.
#
# Uso: bash provision/setup-server.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[SETUP]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }

# ── Verificar que somos root o tenemos sudo ─────────────────────
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo &>/dev/null; then
        SUDO="sudo"
    else
        warn "No se ejecuta como root ni sudo está disponible."
        warn "Algunas operaciones pueden fallar."
    fi
fi

# ── Detectar gestor de paquetes ────────────────────────────────
if command -v apt-get &>/dev/null; then
    PKG="apt-get"
    INSTALL="${SUDO} apt-get install -y -qq"
    UPDATE="${SUDO} apt-get update -qq"
elif command -v yum &>/dev/null; then
    PKG="yum"
    INSTALL="${SUDO} yum install -y -q"
    UPDATE=""
else
    err "Gestor de paquetes no soportado (usa apt o yum)"
    exit 1
fi

echo ""
info "Provisionando servidor para VCOO Virtual..."
echo ""

# ── 1. Dependencias base ───────────────────────────────────────
info "Instalando dependencias del sistema..."
$UPDATE 2>/dev/null || true
$INSTALL curl wget git python3 python3-pip python3-venv \
    build-essential libssl-dev 2>&1 | tail -1
ok "Dependencias base instaladas"

# ── 2. Node.js (para Maton CLI) ────────────────────────────────
if ! command -v node &>/dev/null; then
    info "Instalando Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | ${SUDO} bash -
    $INSTALL nodejs 2>&1 | tail -1
fi
ok "Node.js $(node --version 2>/dev/null || echo 'ok')"

# ── 3. Maton CLI (opcional, para integraciones adicionales) ────
if ! command -v maton &>/dev/null; then
    info "Instalando Maton CLI..."
    npm install -g @maton/cli 2>&1 | tail -1
fi
ok "Maton CLI $(maton --version 2>/dev/null || echo 'instalado')"

# ── 4. Optimizaciones del sistema ──────────────────────────────
info "Aplicando optimizaciones..."

# Aumentar límite de archivos abiertos para procesos largos
if [ -f /etc/security/limits.conf ]; then
    if ! grep -q "nofile" /etc/security/limits.conf 2>/dev/null; then
        echo "* soft nofile 65536" | ${SUDO} tee -a /etc/security/limits.conf >/dev/null
        echo "* hard nofile 65536" | ${SUDO} tee -a /etc/security/limits.conf >/dev/null
        ok "Límite de archivos abiertos aumentado"
    fi
fi

# Asegurar que systemd user mode está disponible (para gateway)
if command -v loginctl &>/dev/null; then
    ${SUDO} loginctl enable-linger "$(whoami)" 2>/dev/null || true
    ok "Linger habilitado para sesiones de usuario"
fi

# ── 5. Firewall (opcional, solo si ufw está disponible) ────────
if command -v ufw &>/dev/null; then
    info "Verificando firewall..."
    ${SUDO} ufw status | grep -q "active" || {
        warn "Firewall no activo. Considera: sudo ufw enable"
    }
fi

# ── 6. Verificación final ──────────────────────────────────────
echo ""
ok "Provisionamiento completado"
echo ""
echo "   Resumen:"
echo "   - SO:       $(uname -a)"
echo "   - Python:   $(python3 --version 2>/dev/null)"
echo "   - Node:     $(node --version 2>/dev/null)"
echo "   - Espacio:  $(df -h / | awk 'NR==2 {print $4}') libres"
echo ""
