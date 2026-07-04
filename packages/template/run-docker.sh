#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# VCOO Virtual — Lanzador Docker
# ═══════════════════════════════════════════════════════════════════
# Construye y ejecuta la imagen de test con todos los mounts necesarios
# para preservar pairing, home channel, Google OAuth y tokens.
#
# Uso:
#   ./run-docker.sh              → build (si no existe) + run interactivo (home: #🤖・testing)
#   ./run-docker.sh --rebuild    → rebuild completo + run interactivo
#   ./run-docker.sh --test       → build (si no existe) + test suite
#   ./run-docker.sh --behavior   → build + behavioral tests
#   ./run-docker.sh --help       → esta ayuda
#
# Variables de entorno:
#   VCOO_HOME_CHANNEL=id   → canal alternativo para el agente (default: 1519113868411146391)
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="vcoo-test"
TIMESTAMP="$(date +%s)"

# ── Colores ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[VCOO]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# ── Parse args ───────────────────────────────────────────────────
REBUILD="auto"   # auto = build solo si no existe
MODE="interactive"
for arg in "$@"; do
    case "$arg" in
        --rebuild) REBUILD="force" ;;
        --test) MODE="test" ;;
        --behavior|--behavioral) MODE="behavioral" ;;
        --help) head -35 "$0"; exit 0 ;;
    esac
done

# ── 1. Build imagen Docker ───────────────────────────────────────
NEEDS_BUILD=false
if [ "$REBUILD" = "force" ]; then
    NEEDS_BUILD=true
    info "Rebuild forzado (--rebuild)..."
elif ! docker image inspect "$IMAGE" &>/dev/null; then
    NEEDS_BUILD=true
    info "Imagen no encontrada. Construyendo..."
fi

if [ "$NEEDS_BUILD" = true ]; then
    info "docker build -f Dockerfile.test -t $IMAGE ."
    echo "   (puede tardar 2-5 min la primera vez)"
    if docker build -f "$DIR/Dockerfile.test" -t "$IMAGE" "$DIR"; then
        ok "Imagen $IMAGE construida"
    else
        err "Falló el build. Revisa Dockerfile.test"
        exit 1
    fi
else
    info "Usando imagen existente ($IMAGE). Usa --rebuild para forzar rebuild."
fi

# ── 2. Verificar archivos necesarios ─────────────────────────────
MOUNTS=()

# ── Home channel para el agente VCOO ─────────────────────────────
# Por defecto, canal 🤖・testing. Se puede sobreescribir con:
#   VCOO_HOME_CHANNEL=otro_id ./run-docker.sh
HOME_CHANNEL="${VCOO_HOME_CHANNEL:-1519113868411146391}"

if [ ! -f "$HOME/.env.test" ]; then
    warn "$HOME/.env.test no existe — los secrets no estarán disponibles"
else
    MOUNTS+=(-v "$HOME/.env.test:/root/.hermes/.env")
fi

if [ -f "$HOME/.hermes/google_token.json" ]; then
    MOUNTS+=(-v "$HOME/.hermes/google_token.json:/root/.hermes/google_token.json")
else
    warn "google_token.json no encontrado — Gmail/Drive no disponibles"
fi

if [ -f "$HOME/.hermes/google_client_secret.json" ]; then
    MOUNTS+=(-v "$HOME/.hermes/google_client_secret.json:/root/.hermes/google_client_secret.json")
fi
if [ -f "$HOME/.hermes/auth.json" ]; then
    MOUNTS+=(-v "$HOME/.hermes/auth.json:/root/.hermes/auth.json")
fi
if [ -f "$HOME/.hermes/channel_directory.json" ]; then
    MOUNTS+=(-v "$HOME/.hermes/channel_directory.json:/root/.hermes/channel_directory.json")
fi

# ── 3. Ejecutar ──────────────────────────────────────────────────
if [ "$MODE" = "test" ]; then
    info "Ejecutando test suite..."
    echo ""
    # shellcheck disable=SC2068
    docker run --rm "${MOUNTS[@]}" "$IMAGE" \
        python3 /opt/vcoo-template/scripts/vcoo-tester.py

elif [ "$MODE" = "behavioral" ]; then
    info "Ejecutando tests de comportamiento del agente..."
    echo ""
    echo -e "  ${YELLOW}Los behavioral tests enviarán prompts en lenguaje natural al agente VCOO${NC}"
    echo -e "  ${YELLOW}y evaluarán sus respuestas mediante LLM Judge.{NC}"
    echo ""
    # shellcheck disable=SC2068
    docker run --rm "${MOUNTS[@]}" "$IMAGE" \
        python3 /opt/vcoo-template/scripts/vcoo-behavior-tester.py

elif [ "$MODE" = "interactive" ]; then
    info "Arrancando agente VCOO en canal 🤖・testing..."
    echo ""
    echo -e "  ${YELLOW}El agente responderá en #🤖・testing (home: $HOME_CHANNEL)${NC}"
    echo -e "  ${YELLOW}Prueba:${NC}"
    echo -e "  ${YELLOW}  ejecuta el test de la plantilla${NC}"
    echo -e "  ${YELLOW}  genera una factura de ejemplo${NC}"
    echo -e "  ${YELLOW}  ejecuta los tests de comportamiento${NC}"
    echo ""
    # shellcheck disable=SC2068
    docker run -it --rm --name "vcoo-test-agent-${TIMESTAMP}" \
        -e DISCORD_HOME_CHANNEL="$HOME_CHANNEL" \
        "${MOUNTS[@]}" "$IMAGE" \
        bash -l -c 'cd /opt/vcoo-template && hermes gateway run > /tmp/gw.log 2>&1 & disown && sleep 3 && hermes'
fi
