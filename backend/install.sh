#!/usr/bin/env bash
set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# ── VCOO Agent Installer v2.3 ──
# One-liner: curl -sSL <url>/install.sh | PROVISION_TOKEN=*** bash -
#
# Features:
#   • Venv auto-reparador (3-tier fallback)
#   • Descarga scripts VCOO del control plane
#   • Auto-deteccion de sudo
#   • Feedback claro si algo falla
#   • Ejecuta el agente en foreground

CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"
AGENT_URL="${AGENT_URL:-${CONTROL_PLANE}/agent_http.py}"
AGENT_HOME="${AGENT_HOME:-$HOME/.vcoo-agent}"
VENV_DIR="$AGENT_HOME/venv"
HERMES_DIR="${HERMES_DIR:-$HOME/.hermes}"
VCOO_DIR="$HERMES_DIR/scripts/vcoo"
USE_VENV=true
HAD_ERRORS=false

echo ""
echo "=== VCOO Agent Installer ==="
echo "Control plane: $CONTROL_PLANE"
echo ""

# ── Root detection ──
IS_ROOT=false
[ "$(id -u)" = "0" ] && IS_ROOT=true

SUDO=""
if ! $IS_ROOT && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

# ── Package manager helper ──
pkg_install() {
    local ok=true
    if command -v apt-get >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "$@" 2>&1 | tail -1 || ok=false
    elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y -q "$@" 2>&1 | tail -1 || ok=false
    elif command -v yum >/dev/null 2>&1; then
        $SUDO yum install -y -q "$@" 2>&1 | tail -1 || ok=false
    elif command -v apk >/dev/null 2>&1; then
        $SUDO apk add --no-cache "$@" 2>&1 | tail -1 || ok=false
    else
        echo "  [!] No se encontro package manager (apt/dnf/yum/apk)"
        ok=false
    fi
    if ! $ok; then
        if [ -n "$SUDO" ]; then
            echo "  [!] El comando sudo fallo. ¿Tienes permisos de administrador?"
            echo "      Prueba: sudo -v (para verificar tu acceso sudo)"
        fi
        HAD_ERRORS=true
    fi
    $ok
}

# ── Asegurar python3 ──
if ! command -v python3 >/dev/null 2>&1; then
    echo "Instalando python3..."
    pkg_install python3 || { echo "ERROR: No se pudo instalar python3."; exit 1; }
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

# ── Venv con 3-tier fallback ──
ensure_venv() {
    if [ -f "$VENV_DIR/bin/python" ]; then return 0; fi
    echo "Creando entorno virtual..."

    # Attempt 1: standard
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "  [OK] venv creado"
        return 0
    fi

    # Attempt 2: install python3-venv
    echo "  Instalando python${PYVER}-venv..."
    pkg_install "python${PYVER}-venv" 2>/dev/null || pkg_install python3-venv 2>/dev/null || true
    if python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "  [OK] venv creado (tras instalar python3-venv)"
        return 0
    fi

    # Attempt 3: --without-pip + bootstrap
    echo "  Intentando venv --without-pip..."
    if python3 -m venv --without-pip "$VENV_DIR" 2>/dev/null; then
        if curl -sSL https://bootstrap.pypa.io/get-pip.py | "$VENV_DIR/bin/python" 2>/dev/null; then
            echo "  [OK] venv creado con pip bootstrap"
            return 0
        fi
    fi

    echo "  [!] No se pudo crear venv. Usando pip --user como fallback."
    USE_VENV=false
    return 1
}

ensure_venv || true

# ── Instalar dependencias Python ──
if $USE_VENV; then
    PIP="$VENV_DIR/bin/pip"
    PYTHON="$VENV_DIR/bin/python"
    if [ ! -f "$PIP" ]; then
        "$PYTHON" -m ensurepip --default-pip 2>/dev/null || \
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PYTHON" 2>/dev/null || true
    fi
    echo "Instalando dependencias (venv)..."
    "$PIP" install -q requests rich 2>&1 | tail -1 && echo "  [OK] requests, rich instalados" || echo "  [!] Fallo al instalar dependencias"
else
    PIP="pip3"
    PYTHON="python3"
    echo "Instalando dependencias (--user)..."
    $PIP install --user -q requests 2>&1 | tail -1 && echo "  [OK] requests instalado" || echo "  [!] pip --user fallo"
    # Rich es opcional
    $PIP install --user -q rich 2>&1 | tail -1 && echo "  [OK] rich instalado" || echo "  [i] Rich no disponible (modo texto)"
fi

# ── Descargar scripts VCOO ──
echo ""
echo "Descargando scripts VCOO..."
mkdir -p "$VCOO_DIR"

VCOO_SCRIPTS="vcoo-bootstrap.py vcoo-google.py vcoo-trello.py vcoo-email.py"
for script in $VCOO_SCRIPTS; do
    dest="$VCOO_DIR/$script"
    if [ -f "$dest" ]; then
        echo "  [OK] $script (ya existe)"
    elif curl -sSf -o "$dest" "$CONTROL_PLANE/playbooks/$script/raw" 2>/dev/null; then
        chmod 700 "$dest"
        echo "  [OK] $script descargado"
    else
        echo "  [!] No se pudo descargar $script"
        HAD_ERRORS=true
    fi
done

# ── Descargar el agente ──
echo ""
echo "Descargando agente..."
AGENT_PATH="$AGENT_HOME/agent_http.py"
mkdir -p "$AGENT_HOME"

if curl -sSf -o "$AGENT_PATH" "$AGENT_URL" 2>/dev/null; then
    echo "  [OK] agent_http.py descargado"
else
    echo "ERROR: No se pudo descargar el agente desde $AGENT_URL"
    exit 1
fi

# ── Arrancar agente ──
echo ""
if $HAD_ERRORS; then
    echo "[!] Algunos componentes opcionales no se pudieron instalar."
    echo "    El agente arrancara igualmente y los verificara."
fi
echo "Iniciando agente en foreground..."
echo "Press Ctrl+C to abort at any time."
echo "---"

exec "$PYTHON" "$AGENT_PATH" "$CONTROL_PLANE" "$PROVISION_TOKEN"
