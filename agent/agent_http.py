#!/usr/bin/env python3
"""
VCOO Agent v3 — Polling client with Rich TUI, COMMAND_MAP, ACK, heartbeat, finalize, log streaming.

Usage: python3 agent_http.py <control_plane_url> <provision_token>
   or: PROVISION_TOKEN=*** python3 agent_http.py <control_plane_url>

- Only executes commands defined in COMMAND_MAP.
- Reports results with ACK + retry (5s/15s/30s backoff).
- Streams command output to backend in real time (POST /agent/{id}/logs).
- Sends heartbeat every 60s.
- Rich TUI if library is installed and stdout is a TTY, plain text otherwise.
- Cleans up and self-deletes on finalize.
"""

import sys, os, time, json, subprocess, random, select

try:
    import requests
except ImportError:
    print("[FATAL] requests no instalado. Ejecuta: pip install requests", file=sys.stderr)
    sys.exit(3)

# ── Rich TUI (optional) ──
RICH_OK = False
LIVE = None  # Rich Live instance (set if TUI active)

try:
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live as RichLive
    from rich.console import Console
    RICH_OK = True
except ImportError:
    pass

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

# ── TUI State ──
TUI = {
    "base": BASE,
    "agent_id": "",
    "vcoo_id": "",
    "status": "Conectando...",
    "step": "",
    "progress_done": 0,
    "progress_total": 0,
    "last_heartbeat": "",
    "last_poll": "",
    "log": [],
}


def tui_log(msg):
    """Añade entrada al buffer de logs de la TUI."""
    ts = time.strftime("%H:%M:%S")
    TUI["log"].append(f"[{ts}] {msg}")
    if len(TUI["log"]) > 100:
        TUI["log"] = TUI["log"][-100:]
    if LIVE:
        try:
            LIVE.update(generate_tui())
        except Exception:
            pass


def log(msg):
    """Log a TUI (si activa) o a stdout (modo texto)."""
    ts = time.strftime("%H:%M:%S")
    if LIVE is None:
        print(f"[{ts}] {msg}", flush=True)
    else:
        TUI["log"].append(f"[{ts}] {msg}")
        if len(TUI["log"]) > 100:
            TUI["log"] = TUI["log"][-100:]
        try:
            LIVE.update(generate_tui())
        except Exception:
            pass


def jitter():
    return random.uniform(0, POLL_INTERVAL * 0.3)


# ── Rich TUI rendering ──

def generate_tui():
    """Genera el layout Rich para Live display."""
    layout = Layout()

    header = Panel(
        f"[bold white]Control Plane:[/] [cyan]{TUI['base']}[/]\n"
        f"[bold white]Agent:[/] [dim]{TUI['agent_id'][:24]}...[/]  "
        f"[bold white]VCOO:[/] [dim]{TUI['vcoo_id'][:12]}...[/]\n"
        f"[bold white]Estado:[/] [green]{TUI['status']}[/]",
        title="[bold cyan]⚡ VCOO Agent v3[/]",
        border_style="cyan"
    )

    done = TUI["progress_done"]
    total = TUI["progress_total"]
    if total > 0:
        bar_w = 36
        pct = done / total if total > 0 else 0
        filled = int(bar_w * pct)
        bar = "█" * filled + "░" * (bar_w - filled)
        prog = f"Progreso: [{done}/{total}] [cyan]{bar}[/] [dim]{int(pct*100)}%[/]"
    else:
        prog = "[dim]Esperando comandos...[/]"

    info = Panel(
        f"{prog}\n"
        f"[bold]Paso actual:[/] [yellow]{TUI['step'] or '—'}[/]  "
        f"[bold]♥:[/] [dim]{TUI['last_heartbeat'] or '—'}[/]  "
        f"[bold]Poll:[/] [dim]{TUI['last_poll'] or '—'}[/]",
        title="[bold]Onboarding[/]",
        border_style="blue"
    )

    log_lines = TUI["log"][-18:]
    if not log_lines:
        log_lines = ["[dim](sin eventos aún)[/]"]
    log_panel = Panel(
        "\n".join(log_lines),
        title="[bold]Eventos[/]",
        border_style="green"
    )

    layout.split_column(
        Layout(header, size=8),
        Layout(info, size=5),
        Layout(log_panel),
    )
    return layout


# ── Persistencia ──

def save_agent(agent_id, agent_token, vcoo_id):
    os.makedirs(STORAGE_DIR, exist_ok=True)
    path = os.path.join(STORAGE_DIR, "agent.json")
    with open(path, "w") as f:
        json.dump({"agent_id": agent_id, "agent_token": agent_token, "vcoo_id": vcoo_id}, f)


def load_agent():
    path = os.path.join(STORAGE_DIR, "agent.json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return None


# ── Registro ──

def register_agent():
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
        log("Registro fallido: HTTP " + str(resp.status_code))
        return None
    return resp.json()


# ── Ejecucion con log streaming ──

def send_log_chunk(agent_id, agent_token, cmd_id, chunk, stream_name="stdout"):
    """Envía un chunk de log al backend (silent on failure)."""
    try:
        session.post(
            BASE + f"/agent/{agent_id}/logs",
            json={"cmd_id": cmd_id, "chunk": chunk, "stream": stream_name},
            headers={"Authorization": "Bearer " + agent_token},
            timeout=5
        )
    except Exception:
        pass


def execute_command(cmd, agent_id=None, agent_token=None):
    """Ejecuta un comando con streaming de logs al backend (Popen + select)."""
    command = cmd.get("command", "")
    step = cmd.get("step", "")
    cmd_id = cmd.get("cmd_id", "")

    args = COMMAND_MAP.get(command)
    if args is None:
        log("Ignorado: " + command + " (no esta en COMMAND_MAP)")
        return {"exit_code": -1, "output": "Comando no soportado: " + command, "step": step, "cmd_id": cmd_id}

    display = " ".join(args)
    log("Ejecutando: " + command + " -> " + display)
    TUI["step"] = step or command

    try:
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        stdout_chunks = []
        stderr_chunks = []

        while True:
            readable = []
            if proc.stdout:
                readable.append(proc.stdout)
            if proc.stderr:
                readable.append(proc.stderr)

            if readable:
                rlist, _, _ = select.select(readable, [], [], 0.5)
                for pipe in rlist:
                    line = pipe.readline()
                    if not line:
                        continue
                    if pipe is proc.stdout:
                        stdout_chunks.append(line)
                        if agent_id and agent_token:
                            send_log_chunk(agent_id, agent_token, cmd_id, line, "stdout")
                    else:
                        stderr_chunks.append(line)
                        if agent_id and agent_token:
                            send_log_chunk(agent_id, agent_token, cmd_id, line, "stderr")

            if proc.poll() is not None:
                # Drain remaining
                if proc.stdout:
                    for line in proc.stdout:
                        stdout_chunks.append(line)
                if proc.stderr:
                    for line in proc.stderr:
                        stderr_chunks.append(line)
                break

        output = "".join(stdout_chunks + stderr_chunks).strip() or "(sin salida)"
        log("Resultado: exit=" + str(proc.returncode))
        return {"exit_code": proc.returncode, "output": output, "step": step, "cmd_id": cmd_id}

    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        log("TIMEOUT (" + str(CMD_TIMEOUT) + "s)")
        return {"exit_code": -1, "output": "TIMEOUT (" + str(CMD_TIMEOUT) + "s)", "step": step, "cmd_id": cmd_id}
    except FileNotFoundError:
        log("Ejecutable no encontrado: " + args[0])
        return {"exit_code": -1, "output": "Ejecutable no encontrado: " + args[0], "step": step, "cmd_id": cmd_id}
    except Exception as e:
        log("Error: " + str(e))
        return {"exit_code": -1, "output": "Error: " + str(e), "step": step, "cmd_id": cmd_id}


# ── Reporte con ACK ──

def report_with_retry(agent_id, agent_token, result, max_retries=3):
    """Reporta resultado con backoff 5s/15s/30s hasta recibir ACK."""
    output_text = (result.get("output") or "")[:5000]
    payload = {
        "cmd_id": result["cmd_id"],
        "step": result.get("step", ""),
        "status": "ok" if result["exit_code"] == 0 else "error",
        "output": output_text
    }
    headers = {"Authorization": "Bearer " + agent_token}

    for attempt, delay in enumerate([5, 15, 30]):
        try:
            resp = session.post(
                BASE + "/agent/" + agent_id + "/result",
                json=payload, headers=headers, timeout=10
            )
            if resp.status_code in (200, 201, 409):
                log("ACK para " + result["cmd_id"][:12])
                data = resp.json() if resp.text else {}
                return True, data.get("next_step")
            if resp.status_code == 404:
                log("Cmd " + result["cmd_id"][:12] + " no encontrado, descartando")
                return True, None
            log("Reintento " + str(attempt+1) + "/" + str(max_retries) + ": HTTP " + str(resp.status_code))
        except Exception as e:
            log("Reintento " + str(attempt+1) + "/" + str(max_retries) + ": " + str(e))
        if attempt < max_retries - 1:
            time.sleep(delay)

    log("FALLO: No se pudo reportar " + result["cmd_id"][:12] + " tras " + str(max_retries) + " intentos")
    return False, None


# ── Heartbeat ──

def heartbeat(agent_id, vcoo_id, agent_token):
    try:
        session.post(
            BASE + "/agent/heartbeat",
            json={"agent_id": agent_id, "vcoo_id": vcoo_id},
            headers={"Authorization": "Bearer " + agent_token},
            timeout=5
        )
    except Exception:
        pass
    TUI["last_heartbeat"] = time.strftime("%H:%M:%S")


# ── Finalize ──

def finalize(vcoo_id):
    """Cleanup post-onboarding y autoborrado."""
    log("Finalizando onboarding...")

    try:
        subprocess.run(["systemctl", "--user", "start", "hermes-gateway"],
                       capture_output=True, timeout=30)
        log("Hermes gateway iniciado via systemctl")
    except Exception:
        try:
            subprocess.Popen(["hermes", "gateway", "run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("Hermes gateway iniciado via CLI")
        except Exception as e:
            log("ADVERTENCIA: No se pudo iniciar Hermes: " + str(e))

    if os.path.isdir(STORAGE_DIR):
        import shutil
        shutil.rmtree(STORAGE_DIR, ignore_errors=True)
        log("Credenciales de provision eliminadas")

    script_path = os.path.abspath(__file__)
    try:
        os.remove(script_path)
        log("agent_http.py eliminado. Onboarding completado.")
    except OSError as e:
        log("No se pudo autoborrar: " + str(e))


# ── Poll ──

def poll_commands(agent_id, agent_token, vcoo_id):
    """Polls for pending commands. Returns (commands, error)."""
    headers = {"Authorization": "Bearer " + agent_token}
    try:
        r = session.get(BASE + "/agent/" + agent_id + "/poll", headers=headers, timeout=10)
    except Exception as e:
        log("Error de poll: " + str(e))
        return [], None

    if r.status_code == 200:
        data = r.json()
        TUI["last_poll"] = time.strftime("%H:%M:%S")
        if data.get("progress"):
            TUI["progress_done"] = data["progress"].get("done", 0)
            TUI["progress_total"] = data["progress"].get("total", 0)
        if data.get("step"):
            TUI["step"] = data["step"]
        return data.get("commands", []), None
    elif r.status_code == 401:
        log("Token expirado, saliendo")
        return [], "expired"

    return [], None


# ── Bucle principal ──

def main_loop(agent_id, agent_token, vcoo_id):
    """Bucle principal de polling y ejecución."""
    last_heartbeat = 0
    log("Polling cada " + str(POLL_INTERVAL) + "s (+jitter) en " + BASE)
    TUI["status"] = "Online"

    while True:
        now = time.time()

        if now - last_heartbeat >= 60:
            heartbeat(agent_id, vcoo_id, agent_token)
            last_heartbeat = now

        cmds, expired = poll_commands(agent_id, agent_token, vcoo_id)
        if expired:
            break

        for cmd in cmds:
            command = cmd.get("command", "")

            if command == "finalize":
                log("Recibido comando finalize")
                report_with_retry(agent_id, agent_token, {
                    "cmd_id": cmd.get("cmd_id", ""),
                    "step": "finalize",
                    "exit_code": 0,
                    "output": "Onboarding completado"
                })
                finalize(vcoo_id)
                TUI["status"] = "Completado"
                if LIVE:
                    LIVE.update(generate_tui())
                time.sleep(3)
                return

            if command == "save-creds":
                log("save-creds manejado por el frontend, ignorando")
                continue

            result = execute_command(cmd, agent_id, agent_token)
            ok, next_step = report_with_retry(agent_id, agent_token, result)

        time.sleep(POLL_INTERVAL + jitter())


# ── Entry point ──

def main():
    global LIVE

    if not PROV:
        print("PROVISION_TOKEN requerido", file=sys.stderr)
        print("Uso: python3 agent_http.py <url> <token>", file=sys.stderr)
        sys.exit(2)

    log("VCOO Agent v3 iniciando...")
    log("Control plane: " + BASE)

    loaded = load_agent()

    if PROV:
        meta = register_agent()
        if meta:
            agent_id = meta["agent_id"]
            agent_token = meta["agent_token"]
            vcoo_id = meta["vcoo_id"]
            TUI["agent_id"] = agent_id
            TUI["vcoo_id"] = vcoo_id
            if loaded and loaded.get("vcoo_id") != vcoo_id:
                log("Token nuevo (VCOO " + vcoo_id[:12] + "), sobrescribiendo anterior")
            save_agent(agent_id, agent_token, vcoo_id)
            log("Registrado: agente " + agent_id[:20])
        elif loaded:
            log("Registro fallido, restaurando estado guardado")
            agent_id = loaded["agent_id"]
            agent_token = loaded["agent_token"]
            vcoo_id = loaded["vcoo_id"]
            TUI["agent_id"] = agent_id
            TUI["vcoo_id"] = vcoo_id
            log("Estado restaurado: agente " + agent_id[:20])
        else:
            log("FATAL: No se pudo registrar y no hay estado guardado")
            sys.exit(1)
    elif loaded:
        agent_id = loaded["agent_id"]
        agent_token = loaded["agent_token"]
        vcoo_id = loaded["vcoo_id"]
        TUI["agent_id"] = agent_id
        TUI["vcoo_id"] = vcoo_id
        log("Estado restaurado: agente " + agent_id[:20])
    else:
        log("FATAL: Sin PROVISION_TOKEN y sin estado guardado")
        sys.exit(1)

    # ── Iniciar TUI (si Rich + TTY) o modo texto ──
    use_tui = RICH_OK and sys.stdout.isatty()

    if use_tui:
        console = Console()
        LIVE = RichLive(generate_tui(), console=console, refresh_per_second=4, screen=True)
        try:
            with LIVE:
                main_loop(agent_id, agent_token, vcoo_id)
        except KeyboardInterrupt:
            log("Interrumpido por el usuario")
            time.sleep(0.5)
    else:
        if not RICH_OK:
            log("(Rich no instalado — modo texto)")
        try:
            main_loop(agent_id, agent_token, vcoo_id)
        except KeyboardInterrupt:
            log("Interrumpido por el usuario")


if __name__ == "__main__":
    main()
