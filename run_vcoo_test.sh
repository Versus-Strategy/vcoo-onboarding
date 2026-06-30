#!/usr/bin/env bash
set -euo pipefail

VM="vcoo-test"
SNAP="clean-base"

echo "🔄 Deteniendo VM..."
multipass stop "$VM"

echo "🔄 Restaurando snapshot limpio..."
multipass restore --destructive "$VM.$SNAP"

echo "🚪 Iniciando VM..."
multipass start "$VM"

echo "🚪 Ejecutando instalación en la VM..."
multipass exec "$VM" -- bash -c "
  set -euo pipefail
  echo \"▶️  Iniciando instalación de VCOO...\"
  # Pre-install python3.11 and set up symlink to avoid permission issues in the one-liner
  if ! command -v python3.11 &>/dev/null; then
      sudo apt-get update -qq && sudo apt-get install -y -qq python3.11 python3.11-venv
  fi
  # Create symlink if it doesn't exist or is broken
  if [ ! -L /usr/local/bin/python3 ] || [ ! -e /usr/local/bin/python3 ]; then
      sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3
  fi
  # Now run the one-liner as the ubuntu user (no sudo)
  export HOME=/home/ubuntu
  echo \"▶️  Ejecutando one-liner...\"
  curl -fsSL https://vcoo-onboarding.vercel.app/install.sh | bash -s
  echo \"\"
  echo \"✅ Instalación finalizada. Verificando servicios críticos...\"
  echo \"\"
  # Verificar que Hermes esté instalado y en el PATH
  which hermes || echo \"❌ Hermes no encontrado en PATH\"
  hermes --version 2>/dev/null || echo \"❌ No se pudo obtener versión de Hermes\"
  echo \"\"
  # Verificar estado de los servicios systemd
  echo \"🔍 Estado de vcoo-health-reporter:\"
  systemctl is-active vcoo-health-reporter && echo \"  → active (running)\" || echo \"  → inactive/failed\"
  systemctl status vcoo-health-reporter --no-pager | head -5
  echo \"\"
  echo \"🔍 Estado de vcoo-hermes-gateway:\"
  systemctl is-active vcoo-hermes-gateway && echo \"  → active (running)\" || echo \"  → inactive/failed\"
  systemctl status vcoo-hermes-gateway --no-pager | head -5
  echo \"\"
  # Probar manejo de token caducado (debe devolver JSON 400 estructurado)
  echo \"🔍 Probando respuesta de token inválido (debe ser HTTP 400 + JSON):\"
  curl -sS -w \"\\nHTTP STATUS: %{http_code}\\n\" \"https://vcoo-onboarding.vercel.app/setup/token-inválido-o-expirado\" | head -2
  echo \"\"
  echo \"🎉 Prueba completada. Para repetir, ejecuta nuevamente este script.\"
"
