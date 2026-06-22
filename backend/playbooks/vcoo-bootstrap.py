#!/usr/bin/env python3
"""vcoo-bootstrap: verifica que el entorno base del VCOO está correcto."""
import sys, os, subprocess, json

results = {"ok": [], "fail": [], "exit_code": 0}

# ── 1. Python version ──
py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
if sys.version_info >= (3, 10):
    results["ok"].append(f"Python {py_ver}")
else:
    results["fail"].append(f"Python {py_ver} — se requiere 3.10+")
    results["exit_code"] = 1

# ── 2. Hermes binary ──
try:
    r = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
    out = r.stdout.strip() or r.stderr.strip()
    results["ok"].append(f"Hermes Agent: {out}")
except FileNotFoundError:
    results["fail"].append("Hermes Agent no encontrado — ¿se ejecutó install.sh?")
    results["exit_code"] = 1
except Exception as e:
    results["fail"].append(f"Hermes Agent error: {e}")
    results["exit_code"] = 1

# ── 3. Python requests module ──
try:
    import requests  # noqa: F401
    results["ok"].append("Módulo requests instalado")
except ImportError:
    results["fail"].append("Módulo requests no instalado — ejecuta: pip install requests")
    results["exit_code"] = 1

# ── 4. Scripts VCOO presentes ──
vcoo_dir = os.path.expanduser("~/.hermes/scripts/vcoo")
expected = ["vcoo-google.py", "vcoo-trello.py", "vcoo-email.py"]
for script in expected:
    path = os.path.join(vcoo_dir, script)
    if os.path.isfile(path):
        results["ok"].append(f"Script {script} presente")
    else:
        results["fail"].append(f"Script {script} no encontrado en {vcoo_dir}")
        results["exit_code"] = 1

# ── 5. Directorio .hermes ──
hermes_dir = os.path.expanduser("~/.hermes")
if os.path.isdir(hermes_dir):
    results["ok"].append("Directorio ~/.hermes/ existe")
else:
    results["fail"].append("Directorio ~/.hermes/ no existe")
    results["exit_code"] = 1

print(json.dumps(results, indent=2, ensure_ascii=False))
sys.exit(results["exit_code"])
