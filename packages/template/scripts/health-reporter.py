#!/usr/bin/env python3
"""
VCOO Health Reporter v1.0
==========================
Ligero, corre en background con nohup (sin dependencia de systemd).
Reporta salud del VPS al control plane de VERSUS cada N segundos.

Solo reporta — NO verifica licencias, NO bloquea nada.
Si el cliente no paga mantenimiento, VERSUS deja de mirar.

Uso:
    export AGENT_ID=... AGENT_TOKEN=... CONTROL_PLANE=https://...
    nohup python3 health-reporter.py > /tmp/vcoo-health.log 2>&1 &

Variables de entorno:
    AGENT_ID        (requerido) — ID del agente registrado
    AGENT_TOKEN     (requerido) — Token JWT del agente
    CONTROL_PLANE   (opcional)  — URL del control plane, default: https://vcoo-onboarding.vercel.app
    HEALTH_INTERVAL (opcional)  — Segundos entre pings, default: 300 (5 min)
"""

import os
import sys
import json
import time
import socket
import signal
import subprocess
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────
CONTROL_PLANE = os.environ.get(
    "CONTROL_PLANE",
    "https://vcoo-onboarding.vercel.app"
)
AGENT_ID = os.environ.get("AGENT_ID", "")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
POLL_INTERVAL = int(os.environ.get("HEALTH_INTERVAL", "300"))  # 5 min

STATE_DIR = os.path.expanduser("~/.vcoo-agent")
STATUS_FILE = os.path.join(STATE_DIR, "health-status.json")
LOG_FILE = os.path.join(STATE_DIR, "health-reporter.log")
LOCK_FILE = os.path.join(STATE_DIR, "health-reporter.lock")

os.makedirs(STATE_DIR, exist_ok=True)


# ── Helpers ─────────────────────────────────────────────────

def log(msg: str):
    """Append timestamped message to log file."""
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n")


def get_system_info() -> dict:
    """Collect minimal system health data."""
    info = {
        "hostname": socket.gethostname(),
        "timestamp": time.time(),
    }

    # System uptime
    try:
        with open("/proc/uptime") as f:
            uptime_secs = float(f.read().split()[0])
            info["uptime_seconds"] = int(uptime_secs)
    except Exception:
        info["uptime_seconds"] = 0

    # Hermes gateway running?
    try:
        result = subprocess.run(
            ["pgrep", "-f", "hermes.*gateway"],
            capture_output=True, text=True, timeout=5
        )
        info["hermes_running"] = result.returncode == 0
    except Exception:
        info["hermes_running"] = False

    # Disk usage
    try:
        stat = os.statvfs(os.path.expanduser("~"))
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bfree
        info["disk_total_gb"] = round(total / (1024 ** 3), 1)
        info["disk_free_gb"] = round(free / (1024 ** 3), 1)
        info["disk_used_pct"] = round((1 - free / total) * 100, 1)
    except Exception:
        pass

    return info


def send_health() -> bool:
    """Send health ping to control plane. Returns True on success."""
    if not AGENT_ID:
        log("AGENT_ID not set — skipping health ping")
        return False

    info = get_system_info()
    data = json.dumps(info).encode()

    headers = {
        "Content-Type": "application/json",
    }
    if AGENT_TOKEN:
        headers["Authorization"] = f"Bearer {AGENT_TOKEN}"
    req = urllib.request.Request(
        f"{CONTROL_PLANE}/agent/{AGENT_ID}/health",
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        # Save last health status for local reference
        with open(STATUS_FILE, "w") as f:
            json.dump({**info, "last_response": result}, f, indent=2)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log(f"Health ping HTTP {e.code}: {body[:200]}")
        return False
    except Exception as e:
        log(f"Health ping failed: {e}")
        return False


# ── Main loop ───────────────────────────────────────────────

def main():
    log("╔══════════════════════════════════════════╗")
    log("║     VCOO Health Reporter iniciado        ║")
    log("╚══════════════════════════════════════════╝")
    log(f"  Control plane: {CONTROL_PLANE}")
    log(f"  Agent ID:      {AGENT_ID}")
    log(f"  Interval:      {POLL_INTERVAL}s")
    log(f"  Log file:      {LOG_FILE}")

    tick = 0
    while True:
        tick += 1
        ok = send_health()
        status = "✓" if ok else "✗"
        log(f"[{tick}] Health ping {status}")

        time.sleep(POLL_INTERVAL)


# ── Entry point ─────────────────────────────────────────────

if __name__ == "__main__":
    # Single-instance check
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = f.read().strip()
            if pid and os.path.exists(f"/proc/{pid}"):
                print(f"Health reporter ya está en ejecución (PID {pid})", file=sys.stderr)
                sys.exit(0)
        except (ValueError, OSError):
            pass  # Stale lock file — remove and continue

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Clean up lock file on SIGTERM (kill) and SIGINT (Ctrl+C)
    def _cleanup(*_args):
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        main()
    except KeyboardInterrupt:
        log("Health reporter detenido por el usuario")
    except Exception as e:
        log(f"Error fatal: {e}")
        raise
    finally:
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
