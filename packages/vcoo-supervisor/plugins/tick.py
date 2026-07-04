import os, json, socket, subprocess, time, urllib.request

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

    def _handle_set_provider(self, payload: dict) -> dict:
        provider = payload.get("provider", "")
        encrypted = payload.get("encrypted", "")
        if not provider or not encrypted:
            return {"status": "error", "output": "missing provider or key"}
        auth = self._parse_auth_from_config().get(provider, {})
        if auth.get("type") == "oauth":
            return {"status": "ok", "output": f"OAuth para {provider} pendiente"}
        # Decrypt if needed
        api_key = encrypted
        if payload.get("has_encryption"):
            try:
                from crypto import decrypt_api_key
                api_key = decrypt_api_key(encrypted)
            except Exception as e:
                return {"status": "error", "output": f"decrypt failed: {e}"}
        # Run hermes auth add
        try:
            r = subprocess.run(
                ["hermes", "auth", "add", provider, "--type", "api-key", "--api-key", api_key],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return {"status": "ok", "output": r.stdout.strip() or f"Provider {provider} configurado"}
            return {"status": "error", "output": r.stderr.strip() or f"hermes auth add exit={r.returncode}"}
        except FileNotFoundError:
            return {"status": "error", "output": "hermes command not found"}
        except Exception as e:
            return {"status": "error", "output": str(e)}

    def _execute_command(self, cmd):
        command = cmd.get("command", "")
        step = cmd.get("step", "")
        cmd_id = cmd.get("cmd_id", "")
        # set-provider uses payload, not subprocess
        if command == "set-provider":
            result = self._handle_set_provider(cmd.get("payload", {}))
            result["cmd_id"] = cmd_id
            result["step"] = step
            return result
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

    def _parse_auth_from_config(self) -> dict[str, dict]:
        """Parse auth metadata dynamically from Hermes config.yaml comments.
        Lines like: #   "anthropic" - Direct Anthropic API (requires: ANTHROPIC_API_KEY)
        Providers not in config.yaml get inferred defaults.
        """
        import re as _re
        config_path = os.path.expanduser("~/.hermes/config.yaml")
        auth_map: dict[str, dict] = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path) as f:
                    content = f.read()
                for m in _re.finditer(r'#\s+"(\w[\w-]+)"\s+-\s+(.+)', content):
                    pid = m.group(1)
                    desc = m.group(2)
                    auth: dict = {"hint": desc.strip()}
                    req_match = _re.search(r"requires:\s*\$?(\w[\w-]*)", desc)
                    if req_match:
                        req = req_match.group(1)
                        if req.startswith("hermes") or req in ("",):
                            auth["type"] = "oauth"
                        else:
                            auth["type"] = "api_key"
                            auth["credential"] = req
                    else:
                        auth["type"] = "manual"
                    auth_map[pid] = auth
            except Exception:
                pass
        # Infer type for providers not in config.yaml
        for pid, atype, cred, hint in [
            ("opencode-go",  "api_key", "OPENCODE_API_KEY", "API key de OpenCode Go"),
            ("opencode-zen", "api_key", "OPENCODE_API_KEY", "API key de OpenCode Zen"),
            ("openai-api",   "api_key", "OPENAI_API_KEY",   "API key de OpenAI (https://platform.openai.com)"),
            ("bedrock",      "manual",  "",                 "Configura AWS credentials (aws configure)"),
            ("custom",       "manual",  "",                 "Configura OPENAI_BASE_URL y OPENAI_API_KEY"),
            ("lmstudio",     "manual",  "",                 "LM Studio corre localmente, no requiere API key"),
            ("moa",          "manual",  "",                 "Mixture of Agents requiere múltiples providers"),
            ("vertex",       "manual",  "",                 "Configura Google Vertex AI (gcloud auth)"),
        ]:
            if pid not in auth_map:
                entry = {"type": atype, "hint": hint}
                if cred:
                    entry["credential"] = cred
                auth_map[pid] = entry
        return auth_map

    def _discover_providers(self):
        """Read providers dynamically from Hermes' CANONICAL_PROVIDERS."""
        hermes_dir = os.path.expanduser("~/.hermes/hermes-agent")
        models_path = os.path.join(hermes_dir, "hermes_cli", "models.py")
        if not os.path.isfile(models_path):
            return []
        try:
            import importlib.util as _iu
            import sys as _sys
            _sys.path.insert(0, hermes_dir)
            spec = _iu.spec_from_file_location("hermes_cli.models", models_path)
            if not spec or not spec.loader:
                return []
            mod = _iu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            entries = getattr(mod, "CANONICAL_PROVIDERS", [])
            auth_map = self._parse_auth_from_config()
            result = []
            for e in entries:
                if e.slug.startswith("_"):
                    continue
                provider = {"id": e.slug, "nombre": e.label, "descripcion": e.tui_desc}
                auth = auth_map.get(e.slug)
                if auth:
                    provider["auth"] = auth
                result.append(provider)
            return result
        except Exception:
            return []

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
            import re as _re
            m = _re.search(r"default:\s*['\"](\w[\w./-]*)", content)
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
        providers = self._discover_providers()
        caps = {"providers": providers}
        if version:
            caps["hermes_version"] = version
        if current_provider:
            caps["current_provider"] = current_provider
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
