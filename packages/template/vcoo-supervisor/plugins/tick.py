import os, json, socket, subprocess, time, urllib.request, base64, hashlib

COMMAND_MAP = {
    "verify-bootstrap": ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-bootstrap.py")],
    "verify-google":    ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-google.py"), "drive", "list"],
    "verify-trello":    ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-trello.py"), "boards"],
    "verify-email":     ["python3", os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-email.py"), "list", "3"],
    "verify-github":    ["gh", "repo", "list", "--limit", "3"],
    "verify-vercel":    ["vercel", "projects", "ls", "--limit", "3"],
    "verify-supabase":  ["supabase", "status"],
    "verify-whatsapp":  ["hermes", "whatsapp", "--check"],
    "pair-whatsapp":    None,
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
        self.encryption_key = os.environ.get("ENCRYPTION_KEY", config.get("encryption_key", ""))
        self.last_command_id = None
        cfg_interval = config.get("interval")
        if cfg_interval and isinstance(cfg_interval, (int, float)) and cfg_interval > 0:
            self.interval = int(cfg_interval)
            self.tick_interval = self.interval
        else:
            self.tick_interval = self.interval
        self._tick_count = 1
        self._checks: dict[str, str] = {}
        if self.agent_id:
            self._run_health_checks()
            if cfg_interval and isinstance(cfg_interval, (int, float)) and cfg_interval > 0:
                self.interval = int(cfg_interval)
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

    @staticmethod
    def _crypto_decrypt(token_b64: str, encryption_key: str, agent_id: str) -> str:
        """Decrypt an API key token (compatible with backend's encrypt_api_key)."""
        padding = 4 - len(token_b64) % 4
        if padding != 4:
            token_b64 += "=" * padding
        raw = base64.urlsafe_b64decode(token_b64)
        if len(raw) < 48:
            raise ValueError("token too short")
        salt = raw[:16]
        iv = raw[16:32]
        ciphertext = raw[32:-32]
        expected_hmac = raw[-32:]
        seed = (encryption_key + ":" + agent_id).encode("utf-8")
        key = hashlib.pbkdf2_hmac("sha256", seed, salt, 100000, dklen=32)
        h = hashlib.sha256(key + iv + ciphertext).digest()
        # constant-time compare
        if len(h) != len(expected_hmac):
            raise ValueError("HMAC mismatch")
        result = 0
        for x, y in zip(h, expected_hmac):
            result |= x ^ y
        if result:
            raise ValueError("HMAC mismatch")
        plain = bytearray()
        for offset in range(0, len(ciphertext), 32):
            keystream = hashlib.sha256(key + iv + bytes([offset // 32])).digest()
            chunk = ciphertext[offset:offset + 32]
            for i in range(len(chunk)):
                plain.append(chunk[i] ^ keystream[i])
        return bytes(plain).decode("utf-8")

    def _handle_set_provider(self, payload: dict) -> dict:
        provider = payload.get("provider", "")
        raw_key = payload.get("api_key") or payload.get("encrypted", "")
        api_key = raw_key
        if payload.get("encrypted") and not payload.get("api_key"):
            enc_key = getattr(self, 'encryption_key', '')
            if enc_key:
                try:
                    api_key = self._crypto_decrypt(raw_key, enc_key, self.agent_id)
                except Exception as e:
                    return {"status": "error", "output": f"decryption failed: {e}"}
        model = payload.get("model", "")
        if not provider:
            return {"status": "error", "output": "missing provider"}
        hermes_bin = os.path.expanduser("~/.local/bin/hermes")
        if not os.path.isfile(hermes_bin):
            hermes_bin = "hermes"
        try:
            # Only run auth add if api_key provided (model-only calls skip this)
            if api_key:
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
                # Extract provider from model name (e.g. opencode-go/gpt-5.4-mini)
                if "/" in model:
                    prov_from_model = model.split("/")[0]
                    subprocess.run(
                        [hermes_bin, "config", "set", "model.provider", prov_from_model],
                        capture_output=True, text=True, timeout=15
                    )
            self._run_health_checks()
            self._report_capabilities()
            return {"status": "ok", "output": f"Provider {provider} configurado"}
        except FileNotFoundError:
            return {"status": "error", "output": "hermes command not found"}
        except Exception as e:
            return {"status": "error", "output": str(e)}

    def _handle_save_creds(self, cmd: dict) -> dict:
        import json, os
        try:
            payload = cmd.get("payload", {})
            service = payload.get("service", "google")
            token_path = os.path.expanduser("~/.hermes/google_token.json")
            cred_data = {
                "token": payload.get("access_token", ""),
                "refresh_token": payload.get("refresh_token", ""),
                "token_uri": payload.get("token_uri", "https://oauth2.googleapis.com/token"),
                "client_id": payload.get("client_id", ""),
                "client_secret": payload.get("client_secret", ""),
                "scopes": payload.get("scopes", []),
            }
            with open(token_path, "w") as f:
                json.dump(cred_data, f, indent=2)
            client_id = payload.get("client_id", "")
            if client_id:
                subprocess.run(
                    ["hermes", "config", "set", "google.client_id", client_id],
                    capture_output=True, timeout=15
                )
            self._run_health_checks()
            return {"status": "ok", "output": f"Credenciales {service} guardadas en {token_path}"}
        except Exception as e:
            return {"status": "error", "output": f"Error guardando credenciales: {e}"}

    def _handle_pair_whatsapp(self, cmd):
        """Run WhatsApp bridge in pair-only mode and return QR or pairing code."""
        script = os.path.expanduser("~/.hermes/scripts/vcoo/vcoo-whatsapp-pair.py")
        if not os.path.isfile(script):
            return {"status": "error", "output": "vcoo-whatsapp-pair.py not found"}
        try:
            payload = cmd.get("payload", {})
            if isinstance(payload, str):
                import json as _json
                try:
                    payload = _json.loads(payload)
                except Exception:
                    payload = {}
            phone = payload.get("phone", "") if isinstance(payload, dict) else ""
            args = ["python3", script]
            if phone:
                args.append(phone)
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            stdout, stderr = proc.communicate(timeout=120)
            output = (stdout + stderr).strip()
            lines = [l for l in output.split("\n") if l.strip()]
            if lines:
                import json as _json
                try:
                    parsed = _json.loads(lines[0])
                    qr = parsed.get("qr", "")
                    code = parsed.get("pairing_code", "")
                    if qr:
                        return {"status": "ok", "output": qr, "mode": "qr"}
                    if code:
                        return {"status": "ok", "output": code, "mode": "pairing_code"}
                except Exception:
                    pass
            return {"status": "error", "output": output[:2000]}
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"status": "error", "output": "TIMEOUT"}
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
        if command == "save-creds":
            result = self._handle_save_creds(cmd)
            result["cmd_id"] = cmd_id
            result["step"] = step
            return result
        if command == "pair-whatsapp":
            result = self._handle_pair_whatsapp(cmd)
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

    @staticmethod
    def _pick_fastest_model(models: list[str]) -> str:
        """Score models: flash keywords +1, premium keywords -1, pick highest score, first in list wins ties."""
        flash_kw = ("flash", "haiku", "mini", "nano", "small", "fast", "light", "turbo")
        premium_kw = ("max", "plus", "pro", "ultra", "premium", "advanced", "super")
        best = models[0] if models else ""
        best_score = -999
        for m in models:
            name = m.split("/")[-1].lower()
            score = sum(1 for kw in flash_kw if kw in name) - sum(1 for kw in premium_kw if kw in name)
            if score > best_score:
                best = m
                best_score = score
        return best

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
            # First try model.provider
            m = _re.search(r"provider:\s*['\"]?(\w[\w./-]*)", content)
            if m:
                provider = m.group(1)
            else:
                # Fallback: parse from default model
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
        result["bootstrap"] = "ok" if os.path.isdir(os.path.expanduser("~/.hermes/scripts/vcoo")) else "missing"
        result["provider"] = "ok" if has_provider else "missing"
        # Check model.default is configured
        import re as _re2
        dm = _re2.search(r"'default':\s*'([^']+)'", config_text)
        result["model"] = "ok" if (dm and dm.group(1) and "/" in dm.group(1)) else "missing"
        # Check Google OAuth (office/mail modules) via token file
        google_token_path = os.path.expanduser("~/.hermes/google_token.json")
        if os.path.isfile(google_token_path):
            try:
                with open(google_token_path) as f:
                    tok = json.load(f)
                result["google"] = "ok" if tok.get("token") else "error"
            except Exception:
                result["google"] = "error"
        else:
            result["google"] = "missing"
        # Check Trello (planner module)
        result["trello"] = "ok" if "trello" in auth_text or "trello.api_key" in config_text else "missing"
        # Check GitHub (developer module)
        result["github"] = "ok" if "github" in auth_text or "github.token" in config_text else "missing"
        # Check Vercel (developer module)
        result["vercel"] = "ok" if "vercel.token" in config_text else "missing"
        # Check Supabase (developer module)
        result["supabase"] = "ok" if "supabase.access_token" in config_text else "missing"
        # Check WhatsApp (communication channel)
        gateway_state = os.path.expanduser("~/.hermes/gateway_state.json")
        wa_ok = False
        if os.path.isfile(gateway_state):
            try:
                with open(gateway_state) as f:
                    gs = json.load(f)
                platforms = gs.get("platforms", {})
                wa_ok = "whatsapp" in platforms
            except Exception:
                pass
        result["whatsapp"] = "ok" if wa_ok else "missing"
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
            models = self._discover_models(current_provider)
            recommended = self._pick_fastest_model(models)
            caps["models"] = {current_provider: {"list": models, "recommended": recommended}}
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
