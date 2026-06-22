#!/usr/bin/env python3
"""
VCOO Agent v2 — Polling client with COMMAND_MAP, ACK, heartbeat, finalize.

Usage: python3 agent_http.py <control_plane_url> <provision_token>
   or: PROVISION_TOKEN=*** python3 agent_http.py <control_plane_url>

Only executes commands defined in COMMAND_MAP.
Reports results with ACK and retry (5s/15s/30s backoff).
Sends heartbeat every 60s.
Cleans up and self-deletes on finalize.
"""

import sys, os, time, json, subprocess, random
import requests

# ── Config ──
BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CONTROL_PLANE", "http://localhost:8000")
PROV = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROVISION_TOKEN", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
CMD_TIMEOUT = int(os.environ.get("CMD_TIMEOUT", "60"))
STORAGE_DIR = os.path.expanduser("~/.vcoo-agent")

# ── COMMAND_MAP ──
COMMAND_MAP = {
    "verify-bootstrap": ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-bootstrap.py")],
    "verify-google":    ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-google.py"), "drive", "list"],
    "verify-trello":    ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-trello.py"), "boards"],
    "verify-email":     ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-email.py"), "list", "3"],
    "verify-github":    ["gh", "repo", "list", "--limit", "3"],
    "verify-vercel":    ["vercel", "projects", "ls", "--limit", "3"],
    "verify-supabase":  ["supabase", "status"],
    "save-creds":       None,
    "finalize":         None,
}

session = requests.Session()


# ── Helpers ──

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def jitter():
    return random.uniform(0, POLL_INTERVAL * 0.3)


# ── Persistencia ──

def save_agent(agent_id, agent_token, vcoo_id):
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(os.path.join(STORAGE_DIR, "agent.json"), "w") as f:
        json.dump({"agent_id": agent_id, "agent_token": agent_token, "vcoo_id": vcoo_id}, f)
    log("Agente guardado en " + STORAGE_DIR)


def load_agent():
    path = os.path.join(STORAGE_DIR, "agent.json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return None


# ── Registro ──

def register():
    try:
        resp = session.post(
            BASE + "/register",
            json={"token": PROV, "info": {"hostname": os.uname().nodename}},
            timeout=10
        )
    except Exception as e:
        log("Error de registro: " + str(e))
        return None
    if resp.status_code != 200:
        log("Registro fallido: HTTP " + str(resp.status_code) + " " + resp.text[:200])
        return None
    j = resp.json()
    log("Registrado como agente " + j.get("agent_id", "?")[:20])
    return j


# ── Ejecucion ──

def execute_command(cmd):
    """Ejecuta un comando del COMMAND_MAP y devuelve resultado."""
    command = cmd.get("command", "")
    step = cmd.get("step", "")
    cmd_id = cmd.get("cmd_id", "")

    args = COMMAND_MAP.get(command)
    if args is None:
        log("Ignorado: " + command + " (no esta en COMMAND_MAP)")
        return {"exit_code": -1, "output": "Comando no soportado: " + command, "step": step, "cmd_id": cmd_id}

    log("Ejecutando: " + command + " -> " + " ".join(args))
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=CMD_TIMEOUT)
        output = (proc.stdout + proc.stderr).strip() or "(sin salida)"
        return {"exit_code": proc.returncode, "output": output, "step": step, "cmd_id": cmd_id}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": "TIMEOUT (" + str(CMD_TIMEOUT) + "s)", "step": step, "cmd_id": cmd_id}
    except FileNotFoundError:
        return {"exit_code": -1, "output": "Ejecutable no encontrado: " + args[0], "step": step, "cmd_id": cmd_id}
    except Exception as e:
        return {"exit_code": -1, "output": "Error: " + str(e), "step": step, "cmd_id": cmd_id}


# ── Reporte con ACK ──

def report_with_retry(agent_id, agent_token, result, max_retries=3):
    """Reporta resultado con backoff 5s/15s/30s hasta recibir ACK."""
    payload = {
        "cmd_id": result["cmd_id"],
        "step": result.get("step", ""),
        "status": "ok" if result["exit_code"] == 0 else "error",
        "output": result["output"][:5000]
    }
    headers = {"Authorization": "Bearer " + agent_token}

    for attempt, delay in enumerate([5, 15, 30]):
        try:
            resp = session.post(
                BASE + "/agent/" + agent_id + "/result",
                json=payload, headers=headers, timeout=10
            )
            if resp.status_code in (200, 201, 409):
                log("ACK recibido para " + result["cmd_id"][:12])
                return True
            if resp.status_code == 404:
                log("Comando " + result["cmd_id"][:12] + " no encontrado, descartando")
                return True
            log("Reintento " + str(attempt+1) + "/" + str(max_retries) + ": HTTP " + str(resp.status_code))
        except Exception as e:
            log("Reintento " + str(attempt+1) + "/" + str(max_retries) + ": " + str(e))
        if attempt < max_retries - 1:
            time.sleep(delay)
    log("FALLO: No se pudo reportar " + result["cmd_id"][:12] + " tras " + str(max_retries) + " intentos")
    return False


# ── Heartbeat ──

def heartbeat(agent_id, vcoo_id, agent_token):
    try:
        session.post(
            BASE + "/agent/heartbeat",
            json={"agent_id": agent_id, "vcoo_id": vcoo_id},
            headers={"Authorization": "Bearer " + agent_token},
            timeout=5
        )
    except:
        pass  # heartbeat failures are silent


# ── Finalize ──

def finalize(vcoo_id):
    """Cleanup post-onboarding y autoborrado."""
    log("Finalizando onboarding...")

    # 1. Arrancar Hermes gateway
    try:
        subprocess.run(["systemctl", "--user", "start", "hermes-gateway"], capture_output=True, timeout=30)
        log("Hermes gateway iniciado via systemctl")
    except:
        try:
            subprocess.Popen(["hermes", "gateway", "run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("Hermes gateway iniciado via CLI")
        except Exception as e:
            log("ADVERTENCIA: No se pudo iniciar Hermes gateway: " + str(e))

    # 2. Limpiar credenciales
    if os.path.isdir(STORAGE_DIR):
        for f in os.listdir(STORAGE_DIR):
            fp = os.path.join(STORAGE_DIR, f)
            try:
                os.remove(fp)
            except OSError:
                pass
        try:
            os.rmdir(STORAGE_DIR)
        except OSError:
            pass
        log("Credenciales de provision eliminadas")

    # 3. Autoborrado
    script_path = os.path.abspath(__file__)
    log("Eliminando " + script_path)
    try:
        os.remove(script_path)
        log("agent_http.py eliminado. Onboarding completado.")
    except OSError as e:
        log("No se pudo autoborrar: " + str(e))


# ── Bucle principal ──

def poll_loop(agent_id, agent_token, vcoo_id):
    headers = {"Authorization": "Bearer " + agent_token}
    last_heartbeat = 0
    log("Polling cada " + str(POLL_INTERVAL) + "s (+jitter) en " + BASE)

    while True:
        now = time.time()
        if now - last_heartbeat >= 60:
            heartbeat(agent_id, vcoo_id, agent_token)
            last_heartbeat = now

        try:
            r = session.get(BASE + "/agent/" + agent_id + "/poll", headers=headers, timeout=10)
        except Exception as e:
            log("Error de poll: " + str(e))
            time.sleep(POLL_INTERVAL + jitter())
            continue

        if r.status_code == 200:
            cmds = r.json().get("commands", [])
            for cmd in cmds:
                command = cmd.get("command", "")

                # Manejar comandos especiales
                if command == "finalize":
                    log("Recibido comando finalize")
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": "finalize",
                        "exit_code": 0,
                        "output": "Onboarding completado"
                    })
                    finalize(vcoo_id)
                    sys.exit(0)

                if command == "save-creds":
                    log("save-creds manejado por el frontend, ignorando")
                    continue

                # Ejecutar y reportar
                result = execute_command(cmd)
                report_with_retry(agent_id, agent_token, result)

        elif r.status_code == 401:
            log("Token expirado, saliendo")
            break

        time.sleep(POLL_INTERVAL + jitter())


# ── Entry point ──

def main():
    if not PROV:
        print("PROVISION_TOKEN requerido", file=sys.stderr)
        print("Uso: python3 agent_http.py <url> <token>", file=sys.stderr)
        sys.exit(2)

    log("VCOO Agent v2 iniciando...")

    # Cargar estado persistente
    loaded = load_agent()

    # Si hay token nuevo, siempre intenta registrar (prioridad sobre estado guardado)
    if PROV:
        meta = register()
        if meta:
            agent_id = meta["agent_id"]
            agent_token = meta["agent_token"]
            vcoo_id = meta["vcoo_id"]
            # Si el estado guardado es de otro VCOO, sobrescribir
            if loaded and loaded.get("vcoo_id") != vcoo_id:
                log("Token nuevo detectado (VCOO " + vcoo_id[:12] + "), sobrescribiendo estado anterior (" + loaded.get("vcoo_id", "?")[:12] + ")")
            save_agent(agent_id, agent_token, vcoo_id)
        elif loaded:
            # Registro falló (token expirado?), usar estado guardado
            log("Registro fallido, restaurando estado guardado")
            agent_id = loaded["agent_id"]
            agent_token = loaded["agent_token"]
            vcoo_id = loaded["vcoo_id"]
        else:
            log("FATAL: No se pudo registrar y no hay estado guardado")
            sys.exit(1)
    elif loaded:
        agent_id = loaded["agent_id"]
        agent_token = loaded["agent_token"]
        vcoo_id = loaded["vcoo_id"]
        log("Estado restaurado: agente " + agent_id[:20])
    else:
        log("FATAL: Sin PROVISION_TOKEN y sin estado guardado")
        sys.exit(1)

    try:
        poll_loop(agent_id, agent_token, vcoo_id)
    except KeyboardInterrupt:
        log("Interrumpido por el usuario")
        sys.exit(0)


if __name__ == "__main__":
    main()
