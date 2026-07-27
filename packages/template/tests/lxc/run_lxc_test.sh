#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# LXC runner: ejecuta test_module_filter.sh dentro de un
# contenedor LXC Ubuntu 22.04 temporal.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

CONTAINER_NAME="vcoo-test-$(date +%s)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cleanup() {
    echo ""
    echo "🧹 Limpiando contenedor $CONTAINER_NAME..."
    lxc delete --force "$CONTAINER_NAME" 2>/dev/null || true
    return 0
}
trap cleanup EXIT

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  LXC: Test de filtrado de módulos VCOO      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Lanzar contenedor ──
echo "🚀 Creando contenedor $CONTAINER_NAME..."
if ! lxc launch ubuntu:22.04 "$CONTAINER_NAME" 2>&1 | tail -1; then
    echo "❌ Error al crear contenedor"
    exit 1
fi

echo "⏳ Esperando conectividad..."
for i in $(seq 1 30); do
    if lxc exec "$CONTAINER_NAME" -- true 2>/dev/null; then
        echo "   Listo tras ${i}s"
        sleep 3
        break
    fi
    sleep 1
done

# ── 2. Crear directorios ──
echo "📦 Preparando archivos..."
lxc exec "$CONTAINER_NAME" -- mkdir -p /tmp/vcoo/skills

# ── 3. Copiar skills (tarball con nombre fijo) ──
cd "$TEMPLATE_DIR/skills"
tar czf /tmp/vcoo-skills.tar.gz .
lxc file push /tmp/vcoo-skills.tar.gz "$CONTAINER_NAME/tmp/vcoo-skills.tar.gz"
lxc exec "$CONTAINER_NAME" -- tar xzf /tmp/vcoo-skills.tar.gz -C /tmp/vcoo/skills/
rm -f /tmp/vcoo-skills.tar.gz

# ── 4. Copiar test script (directorio padre: test_module_filter.sh está en tests/, no en tests/lxc/) ──
tar czf /tmp/vcoo-test-script.tar.gz -C "$SCRIPT_DIR/.." test_module_filter.sh
lxc file push /tmp/vcoo-test-script.tar.gz "$CONTAINER_NAME/tmp/vcoo-test-script.tar.gz"
lxc exec "$CONTAINER_NAME" -- tar xzf /tmp/vcoo-test-script.tar.gz -C /tmp/vcoo/
lxc exec "$CONTAINER_NAME" -- chmod +x /tmp/vcoo/test_module_filter.sh
rm -f /tmp/vcoo-test-script.tar.gz

# ── 5. Verificar estructura ──
echo "🔍 Verificando estructura..."
lxc exec "$CONTAINER_NAME" -- ls /tmp/vcoo/skills/

# ── 6. Ejecutar test dentro del contenedor ──
echo ""
echo "🧪 Ejecutando test en LXC..."
echo "──────────────────────────────────────────────"
set +e
output=$(lxc exec "$CONTAINER_NAME" -- env SKILLS_DIR=/tmp/vcoo/skills bash /tmp/vcoo/test_module_filter.sh 2>&1)
EXIT_CODE=$?
echo "$output"
set -e

# Verificar por el resultado impreso (más confiable que exit code de lxc exec)
if echo "$output" | grep -q "0 failed"; then
    echo "✅ TODOS LOS TESTS PASARON"
    PASS=1
else
    echo "❌ HUBO FALLOS (exit code: $EXIT_CODE)"
    FAIL=1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Resultado LXC                              ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Contenedor: $CONTAINER_NAME"
echo ""

if [ "$PASS" -eq 1 ]; then
    exit 0
fi
exit 1
