import os, json, socket, subprocess, time, urllib.request
import re as _re

# Proveedores que Hermes soporta, extraídos de su config.yaml
HERMES_PROVIDERS = [
    {"id": "anthropic",    "nombre": "Anthropic",   "descripcion": "Claude — modelos de última generación"},
    {"id": "openai",       "nombre": "OpenAI",      "descripcion": "GPT-4, GPT-4o y más"},
    {"id": "google",       "nombre": "Google IA",   "descripcion": "Gemini y modelos de Google"},
    {"id": "mistral",      "nombre": "Mistral AI",  "descripcion": "Modelos abiertos y eficientes"},
    {"id": "xai",          "nombre": "xAI",         "descripcion": "Grok y modelos de xAI"},
    {"id": "cohere",       "nombre": "Cohere",      "descripcion": "Modelos empresariales"},
    {"id": "openrouter",   "nombre": "OpenRouter",  "descripcion": "Múltiples modelos en un solo API"},
    {"id": "copilot",      "nombre": "GitHub Copilot", "descripcion": "Modelos de GitHub y socios"},
    {"id": "gemini",       "nombre": "Google Gemini","descripcion": "Modelos Gemini de Google"},
    {"id": "huggingface",  "nombre": "Hugging Face", "descripcion": "Modelos open source"},
    {"id": "nvidia",       "nombre": "NVIDIA NIM",  "descripcion": "Modelos acelerados por NVIDIA"},
    {"id": "ollama-cloud", "nombre": "Ollama Cloud","descripcion": "Modelos locales en la nube"},
    {"id": "azure-foundry","nombre": "Azure Foundry","descripcion": "Microsoft Azure OpenAI"},
    {"id": "lmstudio",     "nombre": "LM Studio",   "descripcion": "Servidor local OpenAI-compatible"},
    {"id": "custom",       "nombre": "Custom API",  "descripcion": "Cualquier endpoint OpenAI-compatible"},
]

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

class Plugin:
    name = "tick"
    interval = 60

    def start(self, config):
        self.agent_id = os.environ.get("AGENT_ID", config.get("agent_id", ""))
        self.agent_token = os.environ.get("AGENT_TOKEN", config.get("agent_token", ""))
        self.control_plane = os.environ.get("CONTROL_PLANE", config.get("control_plane", "http://localhost:8000"))
        self.last_command_id = None
        self.tick_interval = self.interval
        if self.agent_id:
            self.tick()

    def stop(self):
        pass

    def _get_health_payload(self):
        try:
            with open("/proc/uptime") as f:
                uptime = float(f.read().split()[0])
        except:
            uptime = 0
        try:
            s = os.statvfs("/")
            total = s.f_frsize * s.f_blocks
            free = s.f_frsize * s.f_bfree
            disk_pct = round((1 - free / total) * 100, 1)
        except:
            total = free = disk_pct = 0
        try:
            r = subprocess.run(["pgrep", "-f", "hermes.*gateway"], capture_output=True, timeout=5)
            hermes = r.returncode == 0
        except:
            hermes = False
        return {
            "hostname": socket.gethostname(),
            "cpu_pct": None,
            "memory_pct": None,
            "disk_pct": disk_pct,
            "hermes_running": hermes,
            "template_version": os.environ.get("TEMPLATE_VERSION", ""),
        }

    def _execute_command(self, cmd):
        command = cmd.get("command", "")
        step = cmd.get("step", "")
        cmd_id = cmd.get("cmd_id", "")
        args = COMMAND_MAP.get(command)
        if args is None:
            return {"cmd_id": cmd_id, "step": step, "status": "ignored", "output": "no handler"}
        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1
            )
            stdout, stderr = proc.communicate(timeout=60)
            output = (stdout + stderr).strip() or "(sin salida)"
            return {
                "cmd_id": cmd_id,
                "step": step,
                "status": "ok" if proc.returncode == 0 else "error",
                "output": output[:5000],
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"cmd_id": cmd_id, "step": step, "status": "error", "output": "TIMEOUT"}
        except FileNotFoundError:
            return {"cmd_id": cmd_id, "step": step, "status": "error", "output": "binary not found: " + args[0]}
        except Exception as e:
            return {"cmd_id": cmd_id, "step": step, "status": "error", "output": str(e)}

    def _report_result(self, result):
        data = json.dumps(result).encode()
        req = urllib.request.Request(
            f"{self.control_plane}/agent/{self.agent_id}/result",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agent_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception:
            pass

    def _detect_hermes_config(self):
        """Returns (hermes_version, current_provider) or (None, None)."""
        config_path = os.path.expanduser("~/.hermes/config.yaml")
        if not os.path.isfile(config_path):
            return None, None
        version = None
        provider = None
        try:
            r = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                version = r.stdout.strip().split("\n")[0]
        except Exception:
            pass
        try:
            with open(config_path) as f:
                content = f.read()
            m = _re.search(r"default:\s*['\"]?(\w[\w./-]*)", content)
            if m:
                full = m.group(1)
                if "/" in full:
                    provider, _ = full.split("/", 1)
                else:
                    provider = full
        except Exception:
            pass
        return version, provider

    def _report_capabilities(self):
        if getattr(self, "_caps_reported", False):
            return
        version, current_provider = self._detect_hermes_config()
        if version is None and current_provider is None:
            caps = {"providers": HERMES_PROVIDERS}
        else:
            caps = {
                "hermes_version": version,
                "providers": HERMES_PROVIDERS,
                "current_provider": current_provider,
            }
        data = json.dumps(caps).encode()
        req = urllib.request.Request(
            f"{self.control_plane}/agent/{self.agent_id}/capabilities",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agent_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
            self._caps_reported = True
        except Exception:
            pass

    def tick(self):
        if not self.agent_id:
            return
        self._report_capabilities()
        payload = self._get_health_payload()
        body = json.dumps({"health": payload, "last_command_id": self.last_command_id}).encode()
        req = urllib.request.Request(
            f"{self.control_plane}/agent/{self.agent_id}/tick",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.agent_token}",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
        except Exception:
            return

        for cmd in data.get("commands", []):
            result = self._execute_command(cmd)
            self._report_result(result)
            if cmd.get("cmd_id"):
                self.last_command_id = cmd["cmd_id"]

        ti = data.get("tick_interval")
        if ti and isinstance(ti, (int, float)):
            self.tick_interval = ti
            self.interval = ti
