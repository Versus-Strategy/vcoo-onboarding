#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# E2E Test: Full integration — Backend + LXC + Oneliner
# ═══════════════════════════════════════════════════════════════
# Valida el flujo completo:
#   1. Backend real con SQLite
#   2. Creación de VCOO + token
#   3. Oneliner ejecutado en contenedor LXC Ubuntu 22.04
#   4. Filtrado correcto de skills según módulos contratados
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

export LC_ALL=C.UTF-8
HOST_IP="10.38.132.1"
BACKEND_PORT="8000"
BACKEND_URL="http://${HOST_IP}:${BACKEND_PORT}"
CONTAINER_NAME="vcoo-e2e-$(date +%s)"
# Sube 4 niveles desde lxc/ hasta la raíz del repo
PROJECT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"
BACKEND_DIR="${PROJECT_DIR}/apps/backend"
MODULES_TEST="core planner"  # módulos para el test
PASS=0
FAIL=0
PID_BACKEND=""

cleanup() {
    echo ""
    echo "🧹 Limpiando..."
    [ -n "$PID_BACKEND" ] && kill "$PID_BACKEND" 2>/dev/null && echo "  Backend detenido (PID $PID_BACKEND)" || true
    lxc delete --force "$CONTAINER_NAME" 2>/dev/null && echo "  Contenedor $CONTAINER_NAME eliminado" || true
    rm -f /tmp/vcoo-e2e-db.sqlite3 /tmp/vcoo-e2e-backend.log
    return 0
}
trap cleanup EXIT

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  VCOO E2E — Test de integración completo         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Preparar template.tar.gz ──
echo "📦 Preparando template.tar.gz..."
cd "$PROJECT_DIR"
tar czf /tmp/template-e2e.tar.gz -C packages/template \
    --exclude=.gitignore --exclude=.dockerignore --exclude=VERSION \
    --exclude=PLAN.md --exclude=README.md --exclude=TESTING.md \
    --exclude=.vercel --exclude=.vcoo-root .
cp /tmp/template-e2e.tar.gz "${BACKEND_DIR}/template.tar.gz"
echo "  template.tar.gz: $(ls -lh ${BACKEND_DIR}/template.tar.gz | awk '{print $5}')"

# ── 2. Iniciar backend ──
echo ""
echo "🚀 Iniciando backend (puerto ${BACKEND_PORT}, SQLite)..."
export POSTGRES_URL="sqlite:////tmp/vcoo-e2e-db.sqlite3"
export MASTER_KEY="e2e-test-master-key-$(date +%s)"
export SECRET_KEY="e2e-test-secret-key"
export FIRST_OPERATOR_EMAIL="admin@e2e-test.io"
export FIRST_OPERATOR_PASSWORD="TestPass123"
export FIRST_OPERATOR_NAME="E2E Admin"
export DASHBOARD_PASSWORD="test"
export DASHBOARD_URL="http://localhost:3000"
export CONTROL_PLANE="${BACKEND_URL}"
export FRONTEND_URL="http://localhost:3000"
export PYTHONUNBUFFERED=1

cd "$BACKEND_DIR"
python3 -m uvicorn main:application \
    --host 0.0.0.0 --port "$BACKEND_PORT" \
    --log-level warning 2>/tmp/vcoo-e2e-backend.log &
PID_BACKEND=$!

# Esperar a que el backend esté listo
echo "⏳ Esperando backend..."
for i in $(seq 1 30); do
    if curl -sS "${BACKEND_URL}/healthz" >/dev/null 2>&1; then
        echo "  Backend listo tras ${i}s (PID $PID_BACKEND)"
        break
    fi
    if ! kill -0 "$PID_BACKEND" 2>/dev/null; then
        echo "❌ El backend se detuvo inesperadamente"
        cat /tmp/vcoo-e2e-backend.log
        exit 1
    fi
    sleep 1
done

# ── 3. Login como operador ──
echo ""
echo "🔑 Login como operador..."
OPERATOR_TOKEN=$(curl -sS "${BACKEND_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@e2e-test.io","password":"TestPass123"}' | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")
if [ -z "$OPERATOR_TOKEN" ]; then
    echo "❌ No se pudo obtener token de operador"
    cat /tmp/vcoo-e2e-backend.log
    exit 1
fi
echo "  Token obtenido (${#OPERATOR_TOKEN} chars)"

# ── 4. Crear VCOO ──
echo ""
echo "📋 Creando VCOO con módulos: ${MODULES_TEST}..."
JSON_BODY=$(python3 -c "import json; modules='${MODULES_TEST}'.split(); print(json.dumps({'name':'E2E Test VCOO','modules':modules}))")
VCOO_RESP=$(curl -sS "${BACKEND_URL}/vcoo" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${OPERATOR_TOKEN}" \
    -d "$JSON_BODY")
VCOO_ID=$(echo "$VCOO_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
if [ -z "$VCOO_ID" ]; then
    echo "❌ No se pudo crear VCOO"
    echo "  Response: $VCOO_RESP"
    exit 1
fi
echo "  VCOO ID: $VCOO_ID"

# ── 5. Obtener token de provisión ──
echo ""
echo "🔑 Obteniendo token de provisión..."
TOKEN_RESP=$(curl -sS "${BACKEND_URL}/vcoo/${VCOO_ID}/provision-token" \
    -H "Authorization: Bearer ${OPERATOR_TOKEN}")
PROV_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")
if [ -z "$PROV_TOKEN" ]; then
    echo "❌ No se pudo obtener token de provisión"
    echo "  Response: $TOKEN_RESP"
    exit 1
fi
INSTALL_CMD=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('install_command',''))" 2>/dev/null || echo "")
echo "  Token: ${PROV_TOKEN:0:16}..."
echo "  CMD:   ${INSTALL_CMD:0:60}..."

# ── 6. Lanzar LXC ──
echo ""
echo "🐳 Lanzando contenedor LXC Ubuntu 22.04..."
if ! lxc launch ubuntu:22.04 "$CONTAINER_NAME" 2>&1 | tail -1; then
    echo "❌ No se pudo crear el contenedor"
    exit 1
fi
echo "⏳ Esperando conectividad..."
for i in $(seq 1 30); do
    if lxc exec "$CONTAINER_NAME" -- true 2>/dev/null; then
        echo "  Listo tras ${i}s"
        sleep 3
        break
    fi
    sleep 1
done

# ── 7. Instalar dependencias mínimas en contenedor ──
echo ""
echo "📦 Instalando dependencias en contenedor..."
lxc exec "$CONTAINER_NAME" -- bash -c "
    apt-get update -qq && apt-get install -y -qq curl ca-certificates 2>&1 | tail -2
" 2>&1

# ── 8. Ejecutar oneliner ──
echo ""
echo "⚡ Ejecutando oneliner en contenedor..."
echo "  Comando: $INSTALL_CMD"
echo ""
echo "⏳ Esto puede tomar varios minutos (instala Hermes Agent)..."
echo "──────────────────────────────────────────────"
set +e
lxc exec "$CONTAINER_NAME" \
    --env=CONTROL_PLANE="${BACKEND_URL}" \
    --env=PROVISION_TOKEN="${PROV_TOKEN}" \
    --env=MODULES="${MODULES_TEST}" \
    --env=DEBIAN_FRONTEND=noninteractive \
    -- bash -c "curl -sSL ${BACKEND_URL}/install.sh | bash" 2>&1
E2E_EXIT=$?
set -e
echo "──────────────────────────────────────────────"
echo "  Oneliner exit code: $E2E_EXIT"

# ── 9. Verificar skills instalados ──
echo ""
echo "🔍 Verificando skills instalados en contenedor..."
INSTALLED_SKILLS=$(lxc exec "$CONTAINER_NAME" -- bash -c "
    if [ -d ~/.hermes/skills/versus-multiagent-orchestration ]; then
        ls ~/.hermes/skills/versus-multiagent-orchestration/
    else
        echo 'NO_SKILLS_DIR'
    fi
" 2>&1)

echo ""
echo "  Skills instalados:"
echo "$INSTALLED_SKILLS" | sed 's/^/    /'

# ── 10. Validar ──
echo ""
echo "🧪 Validando resultados..."

# Skills que deberían estar presentes (always + core + trello)
ALWAYS=("vcoo-behavioral-testing" "vcoo-pdf" "vcoo-testing")
EXPECTED=("vcoo-core" "vcoo-trello" "${ALWAYS[@]}")

# Skills que NO deberían estar (no contratados)
NOT_EXPECTED=("vcoo-google-workspace" "vcoo-email")

ALL_OK=true
for skill in "${EXPECTED[@]}"; do
    if echo "$INSTALLED_SKILLS" | grep -qw "$skill"; then
        echo "  ✓ $skill presente"
    else
        echo "  ✗ $skill ausente (DEBERÍA estar)"
        ALL_OK=false
        FAIL=1
    fi
done

for skill in "${NOT_EXPECTED[@]}"; do
    if echo "$INSTALLED_SKILLS" | grep -qw "$skill"; then
        echo "  ✗ $skill presente (NO DEBERÍA)"
        ALL_OK=false
        FAIL=1
    else
        echo "  ✓ $skill ausente (correcto)"
    fi
done

echo ""
if $ALL_OK && [ "$E2E_EXIT" -eq 0 ]; then
    echo "✅ TEST E2E COMPLETADO — TODAS LAS VALIDACIONES PASARON"
    PASS=1
else
    echo "❌ ERRORES ENCONTRADOS"
    [ "$E2E_EXIT" -ne 0 ] && echo "  - Oneliner exit code: $E2E_EXIT (esperado: 0)"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Resultado E2E                              ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Backend PID:  $PID_BACKEND"
echo "  Contenedor:   $CONTAINER_NAME"
echo "  VCOO ID:      $VCOO_ID"
echo "  Módulos:      ${MODULES_TEST}"
echo ""

[ "$PASS" -eq 1 ]
