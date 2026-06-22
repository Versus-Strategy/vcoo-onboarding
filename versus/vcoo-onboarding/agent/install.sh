# Instalador de vcoo-agent (POC)

set -e
ROOT="/opt/vcoo-agent"
VENV="$ROOT/venv"
PYTHON="python3"

if [ "$1" = "--dry-run" ]; then
  echo "Dry run: se crearán las siguientes acciones:\n - crear $ROOT\n - crear venv en $VENV\n - instalar dependencias\n - copiar agent.py\n - crear /etc/vcoo-agent/master.key (si no existe)\n - crear unit file (template en agent/vcoo-agent.service)"
  exit 0
fi

if [ `id -u` -ne 0 ]; then
  echo "Por favor ejecuta como root para instalar el servicio: sudo ./install.sh"
  exit 1
fi

mkdir -p "$ROOT"
$PYTHON -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$(dirname "$0")/agent/requirements.txt"
cp "$(dirname "$0")/agent/agent.py" "$ROOT/agent.py"
chown -R root:root "$ROOT"

# MASTER_KEY
if [ ! -f /etc/vcoo-agent/master.key ]; then
  echo "Generando MASTER_KEY..."
  "${VENV}/bin/python" - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
  mkdir -p /etc/vcoo-agent
  "${VENV}/bin/python" - <<'PY' > /etc/vcoo-agent/master.key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
  chmod 600 /etc/vcoo-agent/master.key
fi

echo "Instalación completada. Revisa agent/vcoo-agent.service y luego habilítalo con systemctl --user or systemctl.
"
