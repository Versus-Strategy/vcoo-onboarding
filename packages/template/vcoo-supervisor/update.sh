#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# VCOO — Auto-update del supervisor (supervisor.py + plugins)
# Descarga la template desde el control plane y redeploya /opt/vcoo-supervisor.
# Preserva config.json (contiene agent_id / agent_token / encryption_key).
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

VCOO_SUPERVISOR_DIR="${VCOO_SUPERVISOR_DIR:-/opt/vcoo-supervisor}"

# Control plane: ~/.hermes/.env > config.json del supervisor > default prod
CONTROL_PLANE="$(grep -E '^CONTROL_PLANE=' "${HOME}/.hermes/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' || true)"
if [ -z "${CONTROL_PLANE}" ] && [ -f "${VCOO_SUPERVISOR_DIR}/config.json" ]; then
    CONTROL_PLANE="$(python3 -c "import json; print(json.load(open('${VCOO_SUPERVISOR_DIR}/config.json')).get('plugins',{}).get('tick',{}).get('control_plane',''))" 2>/dev/null || true)"
fi
CONTROL_PLANE="${CONTROL_PLANE:-https://vcoo-onboarding.vercel.app}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

echo "[vcoo-update] Descargando template desde ${CONTROL_PLANE}..."
if ! curl -fsSL --max-time 120 "${CONTROL_PLANE}/template.tar.gz" -o "${TMPDIR}/template.tar.gz"; then
    echo "[vcoo-update] ERROR: no se pudo descargar template.tar.gz" >&2
    exit 1
fi

tar -xzf "${TMPDIR}/template.tar.gz" -C "${TMPDIR}"
if [ ! -f "${TMPDIR}/vcoo-supervisor/supervisor.py" ]; then
    echo "[vcoo-update] ERROR: template inválida (sin vcoo-supervisor/supervisor.py)" >&2
    exit 1
fi

mkdir -p "${VCOO_SUPERVISOR_DIR}/plugins"
install -m 0644 "${TMPDIR}/vcoo-supervisor/supervisor.py" "${VCOO_SUPERVISOR_DIR}/supervisor.py"
install -m 0644 "${TMPDIR}/vcoo-supervisor/plugins/"*.py "${VCOO_SUPERVISOR_DIR}/plugins/"

echo "[vcoo-update] Supervisor + plugins actualizados en ${VCOO_SUPERVISOR_DIR}"
