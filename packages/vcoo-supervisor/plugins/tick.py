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
        self._tick_count = 1
        self._checks: dict[str, str] = {}
        if self.agent_id:
            self._run_health_checks()
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
        api_key = payload.get("api_key") or payload.get("encrypted", "")
        model = payload.get("model", "")
        if not provider or not api_key:
            return {"status": "error", "output": "missing provider or key"}
        # Check if already configured for this provider
        try:
            existing = subprocess.run([hermes_bin, "auth", "list"], capture_output=True, text=True, timeout=15)
            if provider in existing.stdout:
                self._run_health_checks()
                self._report_capabilities()
                return {"status": "ok", "output": f"Provider {provider} ya configurado"}
        except Exception:
            pass
        # Run hermes auth add + set as default provider
        hermes_bin = os.path.expanduser("~/.local/bin/hermes")
        if not os.path.isfile(hermes_bin):
            hermes_bin = "hermes"
        try:
            r = subprocess.run(
                [hermes_bin, "auth", "add", provider, "--type", "api-key", "--api-key", api_key],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return {"status": "error", "output": r.stderr.strip() or f"hermes auth add exit={r.returncode}"}
            subprocess.run(
                [hermes_bin, "config", "set", "model.provider", provider],
                capture_output=True, text=True, timeout=15
            )
            if model:
                subprocess.run(
                    [hermes_bin, "config", "set", "model.default", model],
                    capture_output=True, text=True, timeout=15
                )
            self._run_health_checks()
            self._report_capabilities()
            return {"status": "ok", "output": f"Provider {provider} configurado"}
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

    def _report_result(self, result, retries=3):
        data = json.dumps(result).encode()
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    f"{self.control_plane}/agent/{self.agent_id}/result",
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.agent_token}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15):
                    return
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    return  # already acked, stop retrying
                time.sleep(2 ** attempt)  # backoff: 1s, 2s, 4s

    def _parse_auth_from_registry(self) -> dict[str, dict]:
        """Parse auth metadata from Hermes' PROVIDER_REGISTRY via text scan."""
        import re as _re
        hermes_dir = os.path.expanduser("~/.hermes/hermes-agent")
        auth_path = os.path.join(hermes_dir, "hermes_cli", "auth.py")
        auth_map: dict[str, dict] = {}
        if not os.path.isfile(auth_path):
            return auth_map
        try:
            text = open(auth_path).read()
            idx = text.find("PROVIDER_REGISTRY")
            if idx < 0:
                return auth_map
            block = text[idx:]
            # Extract each ProviderConfig block by counting parens
            pos = 0
            while True:
                em = _re.search(r'"(\w[\w-]+)"\s*:\s*ProviderConfig\(', block[pos:])
                if not em:
                    break
                pid = em.group(1)
                start = pos + em.end()
                depth = 1
                i = start
                while i < len(block) and depth > 0:
                    if block[i] == '(':
                        depth += 1
                    elif block[i] == ')':
                        depth -= 1
                    i += 1
                body = block[start:i-1]  # content inside ProviderConfig( ... )
                # Extract fields from body
                name = pid
                auth_type = "manual"
                env_vars: list[str] = []
                for f in _re.finditer(r'(\w+)\s*=\s*"([^"]*)"', body):
                    k, v = f.group(1), f.group(2)
                    if k == "name":
                        name = v
                    elif k == "auth_type":
                        if v.startswith("oauth") or v == "external_process":
                            auth_type = "oauth"
                        elif v == "api_key":
                            auth_type = "api_key"
                ev = _re.search(r'api_key_env_vars\s*=\s*\(([^)]*)\)', body)
                if ev:
                    env_vars = [v.strip().strip('"\'') for v in ev.group(1).split(",") if v.strip()]
                entry: dict = {"type": auth_type}
                if env_vars:
                    entry["credential"] = env_vars[0]
                if auth_type == "oauth":
                    entry["hint"] = f"Autentícate con {name}"
                elif auth_type == "api_key":
                    var = env_vars[0] if env_vars else "API_KEY"
                    entry["hint"] = f"Introduce tu API key ({var})"
                else:
                    entry["hint"] = f"Configura {name} manualmente"
                auth_map[pid] = entry
                pos = start + (i - start)
        except Exception:
            pass
        return auth_map

    def _discover_models(self, provider_id: str) -> list[str]:
        """Read available models for a provider from Hermes' OPENROUTER_MODELS and OpenCode lists."""
        import re as _re
        hermes_dir = os.path.expanduser("~/.hermes/hermes-agent")
        models_path = os.path.join(hermes_dir, "hermes_cli", "models.py")
        if not os.path.isfile(models_path):
            return []
        text = open(models_path).read()
        models: list[str] = []
        # Check OpenCode model lists
        for pid in (provider_id,):
            m = _re.search(r'"' + pid + r'"\s*:\s*\[(.*?)\]', text, _re.DOTALL)
            if m:
                models = [v.strip().strip('"\'') for v in m.group(1).split(",") if v.strip()]
                break
        if models:
            return [f"{provider_id}/{m}" for m in models]
        # Check OPENROUTER_MODELS for provider prefix
        for m in _re.finditer(r'\("(\w[\w./-]+)"', text):
            full = m.group(1)
            if full.startswith(provider_id + "/") or full.startswith(provider_id.replace("-", "-") + "/"):
                models.append(full)
        return models

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
            auth_map = self._parse_auth_from_registry()
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

    def _run_health_checks(self):
        """Every 10 ticks, verify provider and modules are still configured."""
        result: dict[str, str] = {}
        hermes_bin = os.path.expanduser("~/.local/bin/hermes")
        if not os.path.isfile(hermes_bin):
            hermes_bin = "hermes"
        config_text = ""
        auth_text = ""
        try:
            cr = subprocess.run([hermes_bin, "config", "show"], capture_output=True, text=True, timeout=15)
            config_text = cr.stdout
        except Exception:
            pass
        try:
            ar = subprocess.run([hermes_bin, "auth", "list"], capture_output=True, text=True, timeout=15)
            auth_text = ar.stdout + ar.stderr
        except Exception:
            pass
        # Check provider: look for any provider name in auth list output
        has_provider = False
        for line in auth_text.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("(") and not line.startswith("Credential"):
                has_provider = True
                break
        result["provider"] = "ok" if has_provider else "missing"
        # Check Google OAuth (office/mail modules)
        result["google"] = "ok" if ("google" in auth_text or "google.client_id" in config_text) else "missing"
        # Check Trello (planner module)
        result["trello"] = "ok" if "trello" in auth_text or "trello.api_key" in config_text else "missing"
        # Check GitHub (developer module)
        result["github"] = "ok" if "github" in auth_text or "github.token" in config_text else "missing"
        # Check Vercel (developer module)
        result["vercel"] = "ok" if "vercel.token" in config_text else "missing"
        # Check Supabase (developer module)
        result["supabase"] = "ok" if "supabase.access_token" in config_text else "missing"
        self._checks = result

    def _report_capabilities(self):
        last = getattr(self, "_caps_reported_at", 0)
        # Re-report if 6h passed OR checks changed
        checks_changed = getattr(self, "_last_reported_checks", None) != self._checks
        if last and time.time() - last < 21600 and not checks_changed:
            return
        version, current_provider = self._detect_hermes_config()
        providers = self._discover_providers()
        caps = {"providers": providers, "checks": self._checks}
        if current_provider:
            caps["models"] = {current_provider: self._discover_models(current_provider)}
        self._last_reported_checks = dict(self._checks)
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
            self._caps_reported_at = time.time()
        except Exception:
            pass

    def tick(self):
        if not self.agent_id:
            return
        self._tick_count += 1
        if self._tick_count % 10 == 0:
            self._run_health_checks()
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
