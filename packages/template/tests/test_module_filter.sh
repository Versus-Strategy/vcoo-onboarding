#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Test de integración: filtrado de skills por módulos contratados
# ═══════════════════════════════════════════════════════════════
# Ejecuta la misma lógica de skill_requires_module + filtro del
# install.sh de la template, verificando que solo se instalen
# los skills correspondientes a los módulos activados.
#
# Uso:
#   bash tests/test_module_filter.sh              # test local
#   bash tests/test_module_filter.sh --lxc        # test en contenedor LXC
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SRC="${SKILLS_DIR:-${TEMPLATE_DIR}/skills}"
PASS=0
FAIL=0
TMPDIR=""

cleanup() {
    [ -n "$TMPDIR" ] && rm -rf "$TMPDIR"
    return 0  # no sobrescribir el exit code del script
}
trap cleanup EXIT

# ── Misma lógica que install.sh ─────────────────────────────────
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

filter_skill() {
    local skill_dir="$1"
    local MODULES="$2"
    local skill_name
    skill_name=$(basename "$skill_dir")
    local req_mod
    req_mod=$(skill_requires_module "$skill_name")
    if [ -n "$req_mod" ]; then
        # Solo instalar si el módulo está contratado
        echo "$MODULES" | grep -qw "$req_mod" || return 1
    fi
    return 0
}

# ── Test runner ──────────────────────────────────────────────────
test_combination() {
    local desc="$1"
    local modules="$2"
    shift 2
    local expected_installed=("$@")

    TMPDIR=$(mktemp -d)
    local target="${TMPDIR}/skills"
    mkdir -p "$target"

    # Copiar skills fuente
    cp -r "$SKILLS_SRC"/* "$target/"

    # Aplicar filtrado (misma lógica que install.sh línea 229-242)
    for skill_dir in "$target"/*/; do
        [ -d "$skill_dir" ] || continue
        if ! filter_skill "$skill_dir" "$modules"; then
            rm -rf "$skill_dir"
        fi
    done

    # Verificar skills instalados
    local actual_installed
    actual_installed=$(ls "$target" 2>/dev/null | sort | tr '\n' ' ')
    actual_installed="${actual_installed%" "}"
    local expected_sorted
    expected_sorted=$(printf '%s\n' "${expected_installed[@]}" | sort | tr '\n' ' ')
    expected_sorted="${expected_sorted%" "}"

    if [ "$actual_installed" = "$expected_sorted" ]; then
        echo "  ✓ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $desc"
        echo "    Módulos:  '$modules'"
        echo "    Esperado: $expected_sorted"
        echo "    Obtenido: $actual_installed"
        FAIL=$((FAIL + 1))
    fi

    rm -rf "$TMPDIR"
    TMPDIR=""
}

# ── Tests ──────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Test: Filtrado de skills por módulos        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Skills "always" que se instalan siempre (sin requisito de módulo)
ALWAYS=("vcoo-behavioral-testing" "vcoo-pdf" "vcoo-testing")

echo "── 1. Solo core ──"
test_combination "core activado → core + always" "core" \
    "vcoo-core" "${ALWAYS[@]}"

echo "── 2. Core + office ──"
test_combination "office activado → +google-workspace" "core office" \
    "vcoo-core" "vcoo-google-workspace" "${ALWAYS[@]}"

echo "── 3. Core + mail ──"
test_combination "mail activado → +email" "core mail" \
    "vcoo-core" "vcoo-email" "${ALWAYS[@]}"

echo "── 4. Core + planner ──"
test_combination "planner activado → +trello" "core planner" \
    "vcoo-core" "vcoo-trello" "${ALWAYS[@]}"

echo "── 5. Todos los módulos ──"
test_combination "todos activados → todos los skills" "core office mail planner" \
    "vcoo-core" "vcoo-google-workspace" "vcoo-email" "vcoo-trello" "${ALWAYS[@]}"

echo "── 6. Sin módulos ──"
test_combination "sin módulos → solo always" "" \
    "${ALWAYS[@]}"

echo "── 7. Módulo no existente ──"
test_combination "módulo 'foo' no afecta" "core foo" \
    "vcoo-core" "${ALWAYS[@]}"

echo "── 8. Solo office (sin core) ──"
test_combination "solo office sin core → solo office + always" "office" \
    "vcoo-google-workspace" "${ALWAYS[@]}"

# ── Resultado ──
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Resultado: $PASS passed, $FAIL failed               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

if [ "$FAIL" -eq 0 ]; then
    exit 0
fi
exit 1
