#!/usr/bin/env python3
"""
vcoo-bootstrap: verifica y repara el entorno base del VCOO.

Auto-reparador:
- Crea ~/.hermes/scripts/vcoo/ si no existe
- Descarga los scripts VCOO del control plane si faltan
- Verifica Python, requests, Hermes (solo warning)
- Siempre intenta completar con exito
"""

import sys, os, subprocess, json

results = {"ok": [], "fail": [], "warning": [], "exit_code": 0}

# ── Control plane URL ──
BASE = os.environ.get("CONTROL_PLANE", "https://vcoo-onboarding.vercel.app")

# ── Directorios ──
HERMES_DIR = os.path.expanduser("~/.hermes")
VCOO_DIR = os.path.join(HERMES_DIR, "scripts", "vcoo")

# ── 1. Python version ──
py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
if sys.version_info >= (3, 10):
    results["ok"].append(f"Python {py_ver}")
else:
    results["fail"].append(f"Python {py_ver} — se requiere 3.10+")
    results["exit_code"] = 1

# ── 2. Python requests module ──
try:
    import requests  # noqa: F401
    results["ok"].append("Modulo requests instalado")
except ImportError:
    # El agente corre desde venv con requests, bootstrap usa system python
    results["warning"].append("Modulo requests no encontrado en system python (el agente usa venv)")
    # No modificar exit_code — no es critico para bootstrap

# ── 3. Crear directorio .hermes/ ──
if not os.path.isdir(HERMES_DIR):
    try:
        os.makedirs(HERMES_DIR, exist_ok=True)
        results["ok"].append("Directorio ~/.hermes/ creado")
    except Exception as e:
        results["fail"].append(f"No se pudo crear ~/.hermes/: {e}")
        results["exit_code"] = 1
else:
    results["ok"].append("Directorio ~/.hermes/ existe")

# ── 4. Crear y poblar VCOO scripts ──
REQUIRED_SCRIPTS = [
    "vcoo-bootstrap.py",
    "vcoo-google.py",
    "vcoo-trello.py",
    "vcoo-email.py",
]

os.makedirs(VCOO_DIR, exist_ok=True)

for script in REQUIRED_SCRIPTS:
    path = os.path.join(VCOO_DIR, script)
    if os.path.isfile(path):
        results["ok"].append(f"Script {script} presente")
        continue

    # Intentar descargar del control plane
    try:
        import urllib.request
        url = f"{BASE}/playbooks/{script}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                content = data.get("script", "")
                if content:
                    with open(path, "w") as f:
                        f.write(content)
                    os.chmod(path, 0o700)
                    results["ok"].append(f"Script {script} descargado del control plane")
                else:
                    results["fail"].append(f"Script {script} vacio en respuesta")
                    results["exit_code"] = 1
            else:
                results["fail"].append(f"Script {script} no disponible (HTTP {resp.status})")
                results["exit_code"] = 1
    except Exception as e:
        results["fail"].append(f"Script {script} no se pudo descargar: {e}")
        results["exit_code"] = 1

# ── 5. Hermes binary (solo warning, no bloquea) ──
try:
    r = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
    out = r.stdout.strip() or r.stderr.strip()
    results["ok"].append(f"Hermes Agent: {out}")
except FileNotFoundError:
    results["warning"].append("Hermes Agent no encontrado — se instalara mas tarde")
except Exception as e:
    results["warning"].append(f"Hermes Agent error: {e}")

print(json.dumps(results, indent=2, ensure_ascii=False))
sys.exit(results["exit_code"])
