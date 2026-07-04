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

import sys, os, time, json, subprocess, random, select, threading
import base64
import hashlib

try:
    import requests
except ImportError:
    # fallback handled later
    pass

# ── Remote config crypto (inline, no external module needed) ──
# Decrypts API keys encrypted by the backend with Fernet-like AES.
# Uses hashlib.pbkdf2_hmac for key derivation + XOR stream cipher
# so the agent needs NO extra Python packages beyond stdlib.

_CRYPTO_ITERS = 100000

def _crypto_derive_key(encryption_key: str, agent_id: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from encryption_key + agent_id + salt."""
    seed = (encryption_key + ":" + agent_id).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", seed, salt, _CRYPTO_ITERS, dklen=32)

def _crypto_decrypt(token_b64: str, encryption_key: str, agent_id: str) -> str:
    """Decrypt a Fernet-compatible token using PBKDF2 + AES-CTR-like XOR.

    Token format (urlsafe-base64):
      base64_urlsafe(salt(16) || iv(16) || ciphertext || hmac(32))
    """
    try:
        raw = base64.urlsafe_b64decode(_crypto_pad(token_b64))
    except Exception:
        raise ValueError("token inválido")

    if len(raw) < 48:
        raise ValueError("token demasiado corto")

    salt = raw[:16]
    iv = raw[16:32]
    ciphertext = raw[32:-32]
    expected_hmac = raw[-32:]

    key = _crypto_derive_key(encryption_key, agent_id, salt)

    # Verify HMAC
    h = hashlib.sha256(key + iv + ciphertext).digest()
    if not _crypto_constant_time_compare(h, expected_hmac):
        raise ValueError("HMAC inválido — clave incorrecta o token corrupto")

    # Decrypt: XOR ciphertext with keystream = SHA-256(key + iv + counter)
    plain = bytearray()
    counter = 0
    for offset in range(0, len(ciphertext), 32):
        keystream = hashlib.sha256(key + iv + bytes([counter])).digest()
        chunk = ciphertext[offset:offset + 32]
        for i in range(len(chunk)):
            plain.append(chunk[i] ^ keystream[i])
        counter += 1

    return bytes(plain).decode("utf-8")

def _crypto_pad(s: str) -> str:
    """Add base64 padding."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return s

def _crypto_constant_time_compare(a: bytes, b: bytes) -> bool:
    """Compare two bytes in constant time."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0

# ── End crypto ──

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
    "step_label": "",
    "step_instructions": [],
    "auth_url": "",
    "progress_done": 0,
    "progress_total": 0,
    "last_heartbeat": "",
    "last_poll": "",
    "log": [],
    "debug": os.environ.get("VCOO_DEBUG", "") == "1",
}

# ── Step labels & instructions ──
STEP_INFO = {
    "bootstrap":      ("Instalación base",        ["Ejecuta el one-liner en tu VPS", "El agente verificará la instalación"]),
    "google-oauth":   ("Google Workspace",         ["Abre el enlace de autorización", "Inicia sesión y concede permisos"]),
    "gmail-setup":    ("Gmail",                    ["Incluido en la autorización de Google", "Se completa automáticamente"]),
    "trello-setup":   ("Trello",                   ["Abre el enlace de autorización de Trello", "Concede permisos de lectura/escritura"]),
    "github-setup":   ("GitHub",                   ["Ejecuta: gh auth login", "El agente verificará la conexión"]),
    "vercel-setup":   ("Vercel",                   ["Ejecuta: vercel login", "El agente verificará la conexión"]),
    "supabase-setup": ("Supabase",                 ["Ejecuta: supabase login", "El agente verificará la conexión"]),
    "finalize":       ("Finalizar",                ["Todos los pasos completados", "El agente limpiará y MAGI estará lista"]),
    "done":           ("Completado",               ["¡MAGI está lista!", "Pulsa Ctrl+C para salir"]),
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


def save_credentials(service, data):
    """Guarda credenciales OAuth/API en ~/.hermes/"""
    hermes_dir = os.path.expanduser("~/.hermes")
    os.makedirs(hermes_dir, exist_ok=True)

    if service == "google":
        token_path = os.path.join(hermes_dir, "google_token.json")
        # Use real tokens from backend exchange (preferred) or fall back to raw code
        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        code = data.get("code", "")
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "code": code if not access_token else "",  # keep code only if exchange failed
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.readonly",
        }
        with open(token_path, "w") as f:
            json.dump(token_data, f)
        if access_token:
            log("Token Google guardado (access_token + refresh_token)")
        else:
            log("Token Google guardado (solo code — el agente debera intercambiarlo)")

    elif service == "trello":
        env_path = os.path.join(hermes_dir, ".env")
        api_key = data.get("api_key", data.get("access_token", ""))
        api_token = data.get("api_token", data.get("code", ""))
        with open(env_path, "a") as f:
            f.write(f"\nTRELLO_API_KEY={api_key}\nTRELLO_API_TOKEN={api_token}\n")
        log("Token Trello guardado en .env")

    else:
        # Generic: save to .env
        env_path = os.path.join(hermes_dir, ".env")
        with open(env_path, "a") as f:
            for k, v in data.items():
                if k not in ("service",):
                    f.write(f"\n{k.upper()}={v}\n")
        log("Credenciales guardadas en .env para " + service)


# ── Rich TUI rendering ──

def generate_tui(debug=None):
    """Genera el layout Rich. Simple por defecto, debug con VCOO_DEBUG=1."""
    if debug is None:
        debug = TUI.get("debug", False)
    layout = Layout()

    done = TUI["progress_done"]
    total = TUI["progress_total"]
    step = TUI["step"] or "Conectando..."
    label, instructions = STEP_INFO.get(step, (step.replace("-", " ").title(), []))
    TUI["step_label"] = label
    TUI["step_instructions"] = instructions

    if debug:
        # Vista debug: full info + logs
        header = Panel(
            f"[bold white]Control Plane:[/] [cyan]{TUI['base']}[/]\n"
            f"[bold white]Agent:[/] [dim]{TUI['agent_id'][:24]}...[/]  "
            f"[bold white]VCOO:[/] [dim]{TUI['vcoo_id'][:12]}...[/]\n"
            f"[bold white]Estado:[/] [green]{TUI['status']}[/]  "
            f"[bold white]Paso:[/] [yellow]{step}[/]",
            title="[bold cyan]VCOO Agent v3 — DEBUG[/]", border_style="cyan"
        )
        log_lines = TUI["log"][-30:]
        if not log_lines:
            log_lines = ["[dim](sin eventos)[/]"]
        log_panel = Panel("\n".join(log_lines), title="[bold]Logs (últimos 30)[/]", border_style="green")
        layout.split_column(Layout(header, size=6), Layout(log_panel))
    else:
        # Vista cliente: progreso + instrucciones del paso actual
        if total > 0:
            bar_w = 40
            pct = done / total if total > 0 else 0
            filled = int(bar_w * pct)
            bar = "█" * filled + "░" * (bar_w - filled)
            prog_line = f"[cyan]{bar}[/] [bold white]{done}/{total}[/] [dim]({int(pct*100)}%)[/]"
        else:
            prog_line = "[dim]Preparando...[/]"

        status_color = "green" if TUI["status"] == "Online" else "yellow"

        # Build instructions text
        instr_text = ""
        for i, instr in enumerate(instructions[:3]):
            instr_text += f"  [dim]{i+1}.[/] {instr}\n"
        if not instr_text:
            instr_text = "  [dim]Esperando comandos...[/]\n"

        # Auth URL hint for OAuth steps
        auth_hint = ""
        if step in ("google-oauth", "trello-setup"):
            setup_url = f"{TUI['base'].replace('vcoo-onboarding.vercel.app', 'frontend-ivory-seven-d0aw1wzkae.vercel.app')}/setup/{TUI.get('vcoo_id','')}"
            auth_hint = f"\n[bold yellow]⚠[/] [cyan]Abre el wizard para autorizar:[/]\n[dim]{setup_url}[/]\n"

        body = (
            f"[bold]Paso {done+1}/{total}: [yellow]{label}[/yellow][/]\n\n"
            f"{prog_line}\n\n"
            f"[bold]Instrucciones:[/]\n{instr_text}\n"
            f"{auth_hint}"
            f"[dim]♥ {TUI['last_heartbeat'] or '—'}  |  Poll {TUI['last_poll'] or '—'}  |  "
            f"{'[red]DEBUG[/]' if debug else '[dim]D=debug[/]'}"
            f"[/]\n"
            f"[dim]Ctrl+C para cancelar[/]"
        )
        panel = Panel(body, title="[bold cyan]⚡ VCOO Agent[/]", border_style="cyan")
        layout.split_column(Layout(panel))

    return layout


# ── Persistencia ──

def save_agent(agent_id, agent_token, vcoo_id, encryption_key=None):
    os.makedirs(STORAGE_DIR, exist_ok=True)
    path = os.path.join(STORAGE_DIR, "agent.json")
    data = {"agent_id": agent_id, "agent_token": agent_token, "vcoo_id": vcoo_id}
    if encryption_key:
        data["encryption_key"] = encryption_key
    with open(path, "w") as f:
        json.dump(data, f)


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
            # Accept any 2xx status (200, 201, 202, etc.) and 409 (already reported)
            if 200 <= resp.status_code < 300 or resp.status_code == 409:
                log("ACK para " + result["cmd_id"][:12])
                try:
                    data = resp.json() if resp.text else {}
                except Exception:
                    data = {}
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


# ── Keyboard listener thread (bypasses Rich screen mode) ──

_keyboard_toggle = threading.Event()

def _keyboard_listener():
    """Lee stdin sin raw mode — compatible con Rich Live (screen=False)."""
    try:
        while True:
            # Non-blocking check every 200ms
            import select as _sel
            r, _, _ = _sel.select([sys.stdin], [], [], 0.2)
            if r:
                ch = os.read(sys.stdin.fileno(), 1)
                if ch == b'd' or ch == b'D':
                    _keyboard_toggle.set()
                    # Drain queued bytes
                    while _sel.select([sys.stdin], [], [], 0.05)[0]:
                        os.read(sys.stdin.fileno(), 1)
    except (OSError, Exception):
        pass


# ── Reporte de capacidades (proveedores/modelos) ──

def discover_capabilities():
    """Discover available providers and models from the Hermes installation.
    Returns a dict: {hermes_version, providers: [{id, name, description, models}]}
    """
    result = {
        "hermes_version": "unknown",
        "providers": []
    }

    try:
        # Use subprocess to get providers from Hermes' Python (works from any venv)
        import subprocess as _sp
        import json as _json
        _script = """
import sys, json
sys.path.insert(0, '/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages')
try:
    from hermes_cli.models import CANONICAL_PROVIDERS, _PROVIDER_MODELS
except ImportError:
    # Try different Python paths
    for p in [
        '/usr/local/lib/hermes-agent/venv/lib/python3.12/site-packages',
        '/usr/lib/python3/dist-packages',
        '/usr/local/lib/python3.11/dist-packages',
    ]:
        sys.path.insert(0, p)
    from hermes_cli.models import CANONICAL_PROVIDERS, _PROVIDER_MODELS
providers = []
for entry in CANONICAL_PROVIDERS:
    slug = entry.slug
    models = list(_PROVIDER_MODELS.get(slug, []))
    providers.append({
        "id": slug,
        "name": getattr(entry, "label", slug),
        "description": getattr(entry, "tui_desc", ""),
        "models": models
    })
print(json.dumps({"providers": providers, "hermes_version": "v0.17"}))
"""
        for _python in ["python3", "/usr/local/lib/hermes-agent/venv/bin/python3", "python3.11", "python3.12"]:
            try:
                _result = _sp.run([_python, "-c", _script], capture_output=True, text=True, timeout=10)
                if _result.returncode == 0 and _result.stdout.strip():
                    _caps = _json.loads(_result.stdout.strip())
                    if "providers" in _caps and len(_caps["providers"]) > 0:
                        result["providers"] = _caps["providers"]
                        log("capabilities: " + str(len(result["providers"])) + " proveedores via " + _python)
                        break
            except Exception:
                continue
        else:
            # Fallback: try direct import (inside Hermes venv)
            try:
                from hermes_cli.models import CANONICAL_PROVIDERS, _PROVIDER_MODELS
                for entry in CANONICAL_PROVIDERS:
                    slug = entry.slug
                    provider_info = {
                        "id": slug,
                        "name": getattr(entry, "label", slug),
                        "description": getattr(entry, "tui_desc", ""),
                        "models": list(_PROVIDER_MODELS.get(slug, []))
                    }
                    result["providers"].append(provider_info)
                log("capabilities: " + str(len(result["providers"])) + " proveedores via direct import")
            except ImportError:
                log("capabilities: hermes_cli no disponible, reportando vacio")
    except Exception as e:
        log("capabilities: error descubriendo proveedores: " + str(e))

    return result


def report_capabilities(agent_id, agent_token):
    """Discover capabilities and report them to the backend."""
    log("Reportando capacidades del agente...")
    caps = discover_capabilities()
    log("  Proveedores descubiertos: " + str(len(caps.get("providers", []))))

    try:
        import requests as _req
        r = _req.post(
            BASE + "/agent/" + agent_id + "/capabilities",
            json=caps,
            headers={"Authorization": "Bearer " + agent_token},
            timeout=10
        )
        if r.status_code == 200:
            log("  Capacidades reportadas correctamente")
        else:
            log("  Error reportando capacidades: HTTP " + str(r.status_code))
    except Exception as e:
        log("  Error reportando capacidades: " + str(e))


# ── Bucle principal ──

def main_loop(agent_id, agent_token, vcoo_id):
    """Bucle principal de polling y ejecución."""
    last_heartbeat = 0
    log("Polling cada " + str(POLL_INTERVAL) + "s (+jitter) en " + BASE)
    TUI["status"] = "Online"

    while True:
        now = time.time()

        # Check for keyboard toggle (thread-driven, works with Rich screen=True)
        if _keyboard_toggle.is_set():
            _keyboard_toggle.clear()
            TUI["debug"] = not TUI.get("debug", False)
            log("Debug: " + ("ON" if TUI["debug"] else "OFF"))
            if LIVE:
                LIVE.update(generate_tui(debug=TUI["debug"]))

        if now - last_heartbeat >= 60:
            heartbeat(agent_id, vcoo_id, agent_token)
            last_heartbeat = now

        cmds, expired = poll_commands(agent_id, agent_token, vcoo_id)
        if expired:
            break

        for cmd in cmds:
            command = cmd.get("command", "")
            cmd_id = cmd.get("cmd_id", "")

            # Defense in depth: filter invalid commands client-side too
            if command not in COMMAND_MAP:
                log("Ignorado: " + command + " (no esta en COMMAND_MAP)")
                report_with_retry(agent_id, agent_token, {
                    "cmd_id": cmd_id,
                    "step": cmd.get("step", ""),
                    "exit_code": -1,
                    "output": "Comando no soportado: " + command
                })
                continue

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
                # Guardar credenciales en ~/.hermes/
                payload_data = cmd.get("payload", {})
                step = cmd.get("step", "save-creds")  # Usar el step real (ej: google-oauth)
                if payload_data:
                    service = payload_data.get("service", "unknown")
                    log("save-creds: guardando credenciales para " + service)
                    save_credentials(service, payload_data)
                    ok, next_step = report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": 0,
                        "output": "Credenciales guardadas para " + service
                    })
                else:
                    log("save-creds: sin payload, ignorando")
                    ok, next_step = report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": 0,
                        "output": "Sin credenciales que guardar"
                    })
                # Update TUI with next step from server
                if ok and next_step:
                    TUI["step"] = next_step
                    if LIVE:
                        LIVE.update(generate_tui())
                continue

            if command == "set-provider":
                payload_data = cmd.get("payload", {})
                step = cmd.get("step", "set-provider")
                encrypted = payload_data.get("encrypted", "")
                provider = payload_data.get("provider", "")
                model = payload_data.get("model", "")

                if not encrypted or not provider:
                    log("set-provider: payload incompleto, ignorando")
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "Payload incompleto"
                    })
                    continue

                # Load encryption key
                agent_data = load_agent()
                enc_key = agent_data.get("encryption_key", "") if agent_data else ""
                if not enc_key:
                    log("set-provider: NO encryption_key disponible, abortando")
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "Encryption key no disponible"
                    })
                    continue

                # Decrypt the API key
                try:
                    api_key = _crypto_decrypt(encrypted, enc_key, agent_id)
                except Exception as e:
                    log("set-provider: error al descifrar: " + str(e))
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "Error al descifrar API key: " + str(e)
                    })
                    continue

                # Execute hermes auth add
                log("set-provider: configurando proveedor " + provider + " modelo " + model)
                try:
                    import subprocess
                    # Add API key to credential pool (non-interactive)
                    r1 = subprocess.run(
                        ["hermes", "auth", "add", provider, "api-key", "--key", api_key],
                        capture_output=True, text=True, timeout=30
                    )
                    if r1.returncode != 0:
                        err = (r1.stderr or r1.stdout or "error desconocido")[:200]
                        log("set-provider: hermes auth add falló: " + err)
                        report_with_retry(agent_id, agent_token, {
                            "cmd_id": cmd.get("cmd_id", ""),
                            "step": step,
                            "exit_code": r1.returncode,
                            "output": "Error auth add: " + err
                        })
                        continue
                    log("set-provider: API key añadida correctamente")

                    # Set default model
                    if model:
                        r2 = subprocess.run(
                            ["hermes", "config", "set", "model.default", model],
                            capture_output=True, text=True, timeout=15
                        )
                        if r2.returncode != 0:
                            log("set-provider: config set aviso: " + (r2.stderr or "")[:200])
                        log("set-provider: modelo default configurado: " + model)

                    output = f"Proveedor {provider} configurado"
                    if model:
                        output += f" con modelo {model}"
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": 0,
                        "output": output
                    })
                    log("set-provider: " + output)
                except subprocess.TimeoutExpired:
                    log("set-provider: timeout ejecutando hermes auth")
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "Timeout ejecutando hermes auth"
                    })
                except FileNotFoundError as e:
                    log("set-provider: hermes no encontrado: " + str(e))
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "hermes CLI no encontrado. ¿Está instalado?"
                    })
                except Exception as e:
                    log("set-provider: error inesperado: " + str(e))
                    report_with_retry(agent_id, agent_token, {
                        "cmd_id": cmd.get("cmd_id", ""),
                        "step": step,
                        "exit_code": -1,
                        "output": "Error: " + str(e)
                    })
                continue

            result = execute_command(cmd, agent_id, agent_token)
            ok, next_step = report_with_retry(agent_id, agent_token, result)
            # Update TUI with next step from server
            if ok and next_step:
                TUI["step"] = next_step
            if LIVE:
                LIVE.update(generate_tui())

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

    # Si hay PROVISION_TOKEN, SIEMPRE intentamos registrar (sobrescribe estado anterior)
    if PROV:
        meta = register_agent()
        if meta:
            agent_id = meta["agent_id"]
            agent_token = meta["agent_token"]
            vcoo_id = meta["vcoo_id"]
            TUI["agent_id"] = agent_id
            TUI["vcoo_id"] = vcoo_id
            if loaded:
                old_vcoo = loaded.get("vcoo_id", "")
                if old_vcoo != vcoo_id:
                    log("Token nuevo (VCOO " + vcoo_id[:12] + "), sobrescribiendo anterior (" + old_vcoo[:12] + ")")
                else:
                    log("Re-registrado: agente " + agent_id[:20])
            else:
                log("Registrado: agente " + agent_id[:20])
            save_agent(agent_id, agent_token, vcoo_id, meta.get("encryption_key"))
            # Report capabilities (async — don't block startup)
            try:
                _cap_thread = threading.Thread(
                    target=report_capabilities, args=(agent_id, agent_token),
                    daemon=True
                )
                _cap_thread.start()
            except Exception:
                pass
        elif loaded:
            log("Registro fallido (token expirado/invalido), restaurando estado guardado")
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

    # Start keyboard listener thread for debug toggle (works even with Rich screen=True)
    kb_thread = threading.Thread(target=_keyboard_listener, daemon=True)
    kb_thread.start()

    if use_tui:
        console = Console()
        LIVE = RichLive(generate_tui(), console=console, refresh_per_second=4, screen=False)
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
