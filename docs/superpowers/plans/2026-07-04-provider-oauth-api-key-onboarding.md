# Provider OAuth / API Key Onboarding Plan

> **For agentic workers:** Use subagent-driven development to implement task-by-task.

**Goal:** Allow users to configure AI providers (API key or OAuth) entirely from the onboarding wizard, without SSH access to the VPS.

**Architecture:** The tick plugin reports provider metadata (auth type, credential fields, OAuth URLs) alongside the provider list. The frontend shows the appropriate form (API key input or OAuth button) based on the metadata. The backend encrypts and sends credentials to the agent via `set-provider` command.

**Tech Stack:** Hermes CANONICAL_PROVIDERS + config.yaml, FastAPI, React, tick.py

---

## Provider Auth Metadata

Each provider will report:

```json
{
  "id": "anthropic",
  "nombre": "Anthropic",
  "descripcion": "Anthropic (Claude models via API key or Claude Code)",
  "auth": {
    "type": "api_key",
    "credential": "ANTHROPIC_API_KEY",
    "instructions": "Obtén tu API key en https://console.anthropic.com"
  }
}
```

For OAuth providers:
```json
{
  "id": "opencode-go",
  "nombre": "OpenCode Go",
  "descripcion": "OpenCode Go (Open models subscription)",
  "auth": {
    "type": "oauth",
    "oauth_url": "https://..."
  }
}
```

For providers that support both:
```json
{
  "id": "openai-codex",
  "nombre": "OpenAI Codex",
  "auth": {
    "type": "both",
    "oauth_url": "...",
    "credential": "OPENAI_API_KEY"
  }
}
```

Where does this metadata come from? Two sources:
1. **Hermes config.yaml comments** — each provider documents required env vars
2. **Hardcoded mapping in tick.py** — for fields not in config.yaml (OAuth URLs, display names)

### Files to modify

| File | Change |
|------|--------|
| `packages/vcoo-supervisor/plugins/tick.py` | Add `_discover_provider_auth()` that reads config.yaml, returns auth metadata |
| `apps/backend/onboarding.py` | Optional: fallback auth metadata if agent hasn't reported |
| `apps/backend/main.py` | Add `POST /setup/{id}/set-provider` endpoint for onboarding |
| `apps/backend/crud.py` | Add `create_provider_command()` similar to operator's set-provider |
| `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx` | Replace instruction view with API key form or OAuth button |

---

### Task 1: Tick plugin reports auth metadata

**Files:**
- Modify: `packages/vcoo-supervisor/plugins/tick.py`

The `_discover_providers()` method currently returns `{id, nombre, descripcion}`. Extend it to include `auth` metadata.

Parse Hermes config.yaml comments to extract credential requirements:

```python
# Per-provider auth metadata (hardcoded mapping based on Hermes config.yaml)
PROVIDER_AUTH: dict[str, dict] = {
    "anthropic":     {"type": "api_key", "credential": "ANTHROPIC_API_KEY", "instructions": "Consigue tu API key en https://console.anthropic.com"},
    "openai-api":    {"type": "api_key", "credential": "OPENAI_API_KEY",   "instructions": "Consigue tu API key en https://platform.openai.com"},
    "openai-codex":  {"type": "oauth",   "instructions": "Ejecuta: hermes auth add openai"},
    "copilot":       {"type": "api_key", "credential": "GITHUB_TOKEN",     "instructions": "Genera un token en https://github.com/settings/tokens"},
    "gemini":        {"type": "api_key", "credential": "GOOGLE_API_KEY",   "instructions": "Consigue tu API key en https://aistudio.google.com"},
    "openrouter":    {"type": "api_key", "credential": "OPENROUTER_API_KEY","instructions": "Consigue tu API key en https://openrouter.ai/keys"},
    "opencode-zen":  {"type": "oauth",   "instructions": "Autentícate con OpenCode para empezar"},
    "opencode-go":   {"type": "oauth",   "instructions": "Autentícate con OpenCode Go"},
    "nous":          {"type": "oauth",   "instructions": "Autentícate con Nous Portal"},
    "anthropic":     {"type": "api_key", "credential": "ANTHROPIC_API_KEY","instructions": "Consigue tu API key en https://console.anthropic.com"},
    # ... repeat for all 38 providers
}
```

In `_discover_providers()`, attach `auth` to each provider:

```python
entries = getattr(mod, "CANONICAL_PROVIDERS", [])
result = []
for e in entries:
    if e.slug.startswith("_"):
        continue
    provider = {"id": e.slug, "nombre": e.label, "descripcion": e.tui_desc}
    auth = PROVIDER_AUTH.get(e.slug)
    if auth:
        provider["auth"] = auth
    result.append(provider)
return result
```

- [ ] **Step 1**: Add PROVIDER_AUTH dict with auth metadata for each provider
- [ ] **Step 2**: Update _discover_providers to attach auth to each provider
- [ ] **Step 3**: Commit

### Task 2: Backend endpoint for onboarding set-provider

**Files:**
- Modify: `apps/backend/main.py`
- Modify: `apps/backend/crud.py`

Create a public endpoint for the onboarding flow to send provider credentials to the agent:

```python
@app.post("/setup/{identifier}/set-provider")
def setup_set_provider(identifier: str, payload: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Client sets provider credentials from onboarding wizard."""
    # 1. Validate client auth
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    # 2. Find VCOO
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="invalid identifier")
    vcoo_id = str(v.id)
    # 3. Verify client owns this VCOO
    bearer = authorization.split(None, 1)[1]
    client_payload = auth.verify_client_token(bearer)
    if not client_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    client_email = client_payload.get("email", "")
    client_obj = crud.get_client_by_email(db, client_email)
    owns = client_obj and client_obj.vcoo_id and str(client_obj.vcoo_id) == vcoo_id
    if not owns:
        raise HTTPException(status_code=403, detail="not your VCOO")
    # 4. Get agent
    agent = crud.get_agent_by_vcoo(db, vcoo_id)
    if not agent:
        raise HTTPException(status_code=400, detail="agent not installed yet")
    # 5. Encrypt and send command
    provider = payload.get("provider", "").strip()
    api_key = payload.get("api_key", "").strip()
    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider and api_key required")
    import auth as _auth
    encrypted = _auth.encrypt_for_agent(api_key, agent.id)
    command_payload = json.dumps({"provider": provider, "api_key_encrypted": encrypted})
    cmd = crud.create_command(db, agent_id=str(agent.id), command="set-provider", result=command_payload)
    return {"status": "command_sent", "cmd_id": str(cmd.id), "provider": provider}
```

- [ ] **Step 1**: Add `setup_set_provider` endpoint in main.py
- [ ] **Step 2**: Commit

### Task 3: Frontend provider config forms

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx`

Replace the instruction view with an interactive form:

For `auth.type === "api_key"`:
```tsx
<div>
  <p className="text-sm text-gray-600 mb-4">{proveedor.auth.instructions}</p>
  <input
    type="password"
    placeholder={`API Key (${proveedor.auth.credential})`}
    value={apiKeyValue}
    onChange={e => setApiKeyValue(e.target.value)}
    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-gray-900 mb-3"
  />
  <Button onClick={() => enviarApiKey(proveedor.id, apiKeyValue)}
    disabled={!apiKeyValue.trim() || enviando}
    variant="primary" size="lg" className="w-full"
  >
    {enviando ? 'Conectando...' : 'Conectar'}
  </Button>
</div>
```

For `auth.type === "oauth"`:
```tsx
<Button onClick={() => iniciarOAuth(proveedor.id)}
  variant="primary" size="lg" className="w-full"
>
  Conectar con {proveedor.nombre}
</Button>
```

- [ ] **Step 1**: Add apiKeyValue and enviando state at top level
- [ ] **Step 2**: Update proveedor detail view to render form based on auth.type
- [ ] **Step 3**: Add enviarApiKey() function that POSTs to /setup/{token}/set-provider
- [ ] **Step 4**: Add iniciarOAuth() function that redirects to OAuth URL
- [ ] **Step 5**: Commit

### Task 4: Agent-side set-provider handler

**Files:**
- Modify: `packages/vcoo-supervisor/plugins/tick.py`

The existing `set-provider` command in COMMAND_MAP is `None` (no handler). Add a handler that decrypts and runs the Hermes config commands:

```python
def _handle_set_provider(self, cmd):
    payload = cmd.get("payload", {})
    provider = payload.get("provider", "")
    api_key_encrypted = payload.get("api_key_encrypted", "")
    if not provider or not api_key_encrypted:
        return {"status": "error", "output": "missing provider or key"}
    # Decrypt
    try:
        import json
        # The key was encrypted for this agent by the backend
        # For now, pass through as-is since the backend's encrypt/decrypt
        # is handled via auth module
        api_key = api_key_encrypted  # TODO: proper decryption
    except Exception as e:
        return {"status": "error", "output": f"decrypt failed: {e}"}
    # Run Hermes commands
    cmds = [
        ["hermes", "config", "set", "model.provider", provider],
        ["hermes", "config", "set", "model.default", f"{provider}/default"],
    ]
    results = []
    for args in cmds:
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=30)
            results.append(f"{' '.join(args)}: exit={r.returncode}")
        except Exception as e:
            results.append(f"{' '.join(args)}: error={e}")
    return {"status": "ok", "output": "; ".join(results)}
```

- [ ] **Step 1**: Add `_handle_set_provider` method to Plugin class
- [ ] **Step 2**: Update `_execute_command` to call `_handle_set_provider` for "set-provider" command
- [ ] **Step 3**: Update template/supervisor files, rebuild archive, commit

### Task 5: OAuth callback endpoint

**Files:**
- Create or modify: `apps/backend/main.py`

For providers with OAuth support, add a callback endpoint:

```python
@app.get("/setup/{identifier}/oauth-callback")
def setup_oauth_callback(identifier: str, service: str, code: str = None, db: Session = Depends(get_db)):
    """OAuth callback for provider auth in onboarding flow."""
    # Exchange code for token, send to agent via set-provider command
    ...
```

This requires per-provider OAuth client configuration (client_id, client_secret, redirect_uri). For a simpler first pass, redirect users to the provider's own auth page and have them paste the token.

- [ ] **Step 1**: Add OAuth callback endpoint
- [ ] **Step 2**: Commit

---

## Summary of what gets reported

The tick plugin will report per provider:

```json
{
  "id": "anthropic",
  "nombre": "Anthropic",
  "descripcion": "Anthropic (Claude models via API key or Claude Code)",
  "auth": {
    "type": "api_key",
    "credential": "ANTHROPIC_API_KEY",
    "instructions": "Consigue tu API key en https://console.anthropic.com"
  }
}
```

The frontend uses:
- `auth.type === "api_key"` → show password input + Connect button
- `auth.type === "oauth"` → show OAuth connect button
- `auth.type === "both"` → show both options
- No `auth` field → show generic instruction view (fallback)

## API flow

```
Frontend                          Backend                         Agent
   |                                |                               |
   |-- POST /setup/{id}/set-provider -->|                           |
   |   {provider:"anthropic",        |                               |
   |    api_key:"sk-ant-..."}       |                               |
   |                                |-- encrypt api_key             |
   |                                |-- create Command              |
   |                                |   (set-provider, payload)     |
   |<-- {status:"command_sent"}     |                               |
   |                                |                               |
   |                                |          tick poll            |
   |                                |<------------------------------|
   |                                |-- return commands             |
   |                                |------------------------------>|
   |                                |          run hermes config    |
   |                                |<-- result --------------------|
   |                                |                               |
```

Onboarding wizard shows "Conectado" confirmation after agent reports success.
