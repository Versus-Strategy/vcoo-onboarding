# OFFICE Module — Google OAuth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual Google Cloud Console setup with one-click "Conectar con Google" OAuth button for the OFFICE module, using VERSUS's own Google OAuth client, with agent-side token storage and health checks.

**Architecture:** Backend serves OAuth URLs for `google-drive` (office) and `gmail` (mail) services with separate scopes. OAuth callback exchanges code for tokens and sends them to the agent via `save-creds` command. Agent saves tokens to `~/.hermes/google_token.json` and registers with Hermes auth. `_run_health_checks()` detects the token file and reports `checks.google`. Frontend uses `checks.google` to show OAuth button or success state.

**Tech Stack:** FastAPI (backend), React/TypeScript (frontend), Python agent (tick.py), Google OAuth 2.0

---

### File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `apps/backend/main.py:478-629` | OAuth auth-url + callback endpoints | Add `google-drive`/`gmail` service support, separate step mapping |
| `packages/vcoo-supervisor/plugins/tick.py:99-131` | Agent command execution | Add `save-creds` handler |
| `packages/vcoo-supervisor/plugins/tick.py:319-360` | Agent health checks | Improve google check to detect token file |
| `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:450-477` | Module detail view | Replace manual instructions with OAuth button |
| `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:774-891` | Module step renderer | Wire `checks.google` for visual state |

---

### Task 1: Backend — Add google-drive and gmail OAuth services

**Files:**
- Modify: `apps/backend/main.py:478-629`

- [ ] **Step 1: Update auth-url endpoint to accept google-drive and gmail services**

Replace the `if service == "google":` block (lines 493-500) with a scope map that supports multiple Google services:

```python
SCOPES_MAP: dict[str, str] = {
    "google-drive": "https://www.googleapis.com/auth/drive.file+https://www.googleapis.com/auth/documents+https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/presentations",
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
    "google": "https://www.googleapis.com/auth/drive.file+https://www.googleapis.com/auth/documents+https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/presentations",
}

SERVICE_LABELS: dict[str, str] = {
    "google-drive": "Google Drive",
    "gmail": "Gmail",
    "google": "Google",
}
```

Change the google service block to:

```python
if service in SCOPES_MAP:
    client_id = _os.getenv("GOOGLE_CLIENT_ID", "")
    redirect = _os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    state = f"{vcoo_id}:{service}"
    if not client_id:
        raise HTTPException(status_code=400, detail="GOOGLE_CLIENT_ID no configurado. Contacta al administrador.")
    scopes = SCOPES_MAP[service]
    url = ("https://accounts.google.com/o/oauth2/v2/auth"
           f"?client_id={client_id}&redirect_uri={redirect}"
           f"&response_type=code&scope={scopes}"
           "&access_type=offline&prompt=consent"
           f"&state={state}")
    return {"url": url, "service": service}
```

- [ ] **Step 2: Update callback step_map to handle the new services**

In `oauth_callback` (line 590), change:

```python
step_map = {"google": "google-oauth", "trello": "trello-setup"}
mapped_step = step_map.get(service, "save-creds")
```

To:

```python
step_map: dict[str, str] = {
    "google": "google-oauth",
    "google-drive": "google-oauth",
    "gmail": "gmail-setup",
    "trello": "trello-setup",
}
mapped_step = step_map.get(service, "save-creds")
```

- [ ] **Step 3: Remove auto-advance of gmail-setup when google-oauth completes**

Remove lines 597-601 (the `if service == "google":` block that auto-advances `gmail-setup`). The modules are now independent — office does not auto-configure mail.

```python
# Remove this entire block (lines ~597-601):
# Google OAuth includes gmail scope — also complete gmail-setup if mail module is active
if service == "google":
    st = crud.get_onboarding_state(db, vcoo_id)
    if st and "mail" in (st.modules or []) and "gmail-setup" not in (st.completed or []):
        crud.advance_onboarding_step(db, vcoo_id, "gmail-setup")
```

- [ ] **Step 4: Include client_id and client_secret in save-creds payload**

The save-creds payload needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET so the agent can write the proper format that `google.oauth2.credentials.Credentials.from_authorized_user_info()` expects. Update the creds_data dict (lines 613-617):

```python
creds_data = {
    "service": service,
    "code": code,
    "access_token": access_token,
    "refresh_token": refresh_token,
    "client_id": _os.getenv("GOOGLE_CLIENT_ID", ""),
    "client_secret": _os.getenv("GOOGLE_CLIENT_SECRET", ""),
    "token_uri": "https://oauth2.googleapis.com/token",
    "scopes": SCOPES_MAP.get(service, "").split("+"),
}
```

- [ ] **Step 5: Verify the changes compile**

Run: `cd /home/ubuntu/versus/vcoo-onboarding/apps/backend && python -c "from main import app; print('OK')"`

Expected output: `OK`

---

### Task 2: Agent — Implement save-creds handler

**Files:**
- Modify: `packages/vcoo-supervisor/plugins/tick.py:99-131`

The current `save-creds` command returns `"ignored"` because `COMMAND_MAP["save-creds"]` is `None`. Add a real handler.

- [ ] **Step 1: Add save-creds handler method**

Add to the `Plugin` class in `tick.py`:

```python
def _handle_save_creds(self, cmd: dict) -> dict:
    import json, os
    try:
        payload = cmd.get("payload", {})
        service = payload.get("service", "google")
        token_path = os.path.expanduser("~/.hermes/google_token.json")

        # Normalize token format for google.oauth2.credentials.Credentials
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

        # Register with Hermes auth
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
```

- [ ] **Step 2: Wire save-creds into _execute_command**

In `_execute_command` method (around line 99-131), BEFORE the `args = COMMAND_MAP.get(command)` line, add the dispatch:

```python
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

    # NEW: save-creds handler
    if command == "save-creds":
        result = self._handle_save_creds(cmd)
        result["cmd_id"] = cmd_id
        result["step"] = step
        return result

    args = COMMAND_MAP.get(command)
    ...
```

- [ ] **Step 3: Verify syntax**

Run: `cd /home/ubuntu/versus/vcoo-onboarding/packages/vcoo-supervisor && python -c "from plugins.tick import Plugin; print('OK')"`

Expected output: `OK`

---

### Task 3: Agent — Improve google health check

**Files:**
- Modify: `packages/vcoo-supervisor/plugins/tick.py:319-360`

- [ ] **Step 1: Replace the google check with token file detection**

In `_run_health_checks`, replace the current google check at line 350-351:

```python
# Current (line ~350-351):
# Check Google OAuth (office/mail modules)
result["google"] = "ok" if ("google" in auth_text or "google.client_id" in config_text) else "missing"
```

With:

```python
# Check Google OAuth (office/mail modules) via token file
google_token_path = os.path.expanduser("~/.hermes/google_token.json")
if os.path.isfile(google_token_path):
    try:
        with open(google_token_path) as f:
            tok = json.load(f)
        if tok.get("token"):
            result["google"] = "ok"
        else:
            result["google"] = "error"
    except Exception:
        result["google"] = "error"
else:
    result["google"] = "missing"
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/ubuntu/versus/vcoo-onboarding/packages/vcoo-supervisor && python -c "from plugins.tick import Plugin; print('OK')"`

Expected output: `OK`

---

### Task 4: Frontend — OAuth button for module configuration

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:450-477,774-891`

- [ ] **Step 1: Replace MODULE_INSTRUCTIONS.office with OAuth config**

Replace the `MODULE_INSTRUCTIONS` dict (lines 450-473). Keep `planner` and `developer`, replace `office` and `mail` with OAuth service references:

```typescript
const MODULE_OAUTH: Record<string, { service: string; scopes: string }> = {
  office: { service: 'google-drive', scopes: 'Drive, Docs, Sheets y Slides' },
  mail: { service: 'gmail', scopes: 'Gmail' },
};
```

Remove `MODULE_INSTRUCTIONS` entirely (or keep `planner` and `developer` entries only).

- [ ] **Step 2: Add OAuth popup function**

Add this function after `manejarConectarModulo`:

```typescript
const conectarOAuth = async (service: string) => {
  if (!token) return;
  try {
    const { data } = await apiClient.get(`/setup/${token}/auth-url?service=${service}`);
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const popup = window.open(
      data.url,
      'google-oauth',
      `width=${width},height=${height},left=${left},top=${top}`
    );
    if (!popup) {
      setError('El navegador bloqueó la ventana emergente. Permite popups para este sitio.');
      return;
    }
    setConectando(service);
    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        setConectando(null);
        fetchOnboarding();
      }
    }, 500);
  } catch {
    setError('Error al iniciar la conexión con Google');
    setConectando(null);
  }
};
```

- [ ] **Step 3: Update renderPasoModulos detail view**

In `renderPasoModulos`, when `moduloSeleccionado` is set, change the detail view to show an OAuth button instead of manual instructions:

Replace `MODULE_INSTRUCTIONS[moduloSeleccionado]` usage with OAuth check. In the detail area (around line 803-832), replace:

```typescript
if (moduloSeleccionado) {
  const info = modulosInfo[moduloSeleccionado];
  const instr = MODULE_INSTRUCTIONS[moduloSeleccionado];
  return (
    <div className="space-y-6 max-w-2xl">
      ...
      {instr ? (
        <div className="space-y-3">
          <p className="text-sm font-medium text-gray-700">Pasos para conectar:</p>
          {instr.pasos.map((paso, i) => (
            <div key={i} className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 border border-gray-100">{paso}</div>
          ))}
        </div>
      ) : (...)}
    </div>
  );
}
```

With:

```typescript
if (moduloSeleccionado) {
  const info = modulosInfo[moduloSeleccionado];
  const oauthConfig = MODULE_OAUTH[moduloSeleccionado];
  const googleCheck = (checks as Record<string, string>).google;
  const googleOk = googleCheck === 'ok';
  const googleError = googleCheck === 'error';
  return (
    <div className="space-y-6 max-w-2xl">
      <button onClick={() => setModuloSeleccionado(null)}
        className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Volver a módulos
      </button>
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <h3 className="text-lg font-bold text-gray-900 mb-2">{info?.nombre || moduloSeleccionado}</h3>
        <p className="text-sm text-gray-500 mb-4">{info?.descripcion}</p>
        {oauthConfig ? (
          <div className="text-center py-6">
            {googleOk ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-green-700 font-medium">Conectado a {info?.nombre}</p>
                <p className="text-xs text-gray-400">Acceso a {oauthConfig.scopes}</p>
              </div>
            ) : googleError ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center">
                  <svg className="w-7 h-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01" />
                  </svg>
                </div>
                <p className="text-red-700 font-medium">Conexión expirada o inválida</p>
                <Button variant="primary" size="lg" onClick={() => conectarOAuth(oauthConfig.service)}
                  loading={conectando === oauthConfig.service}>
                  Reconectar con Google
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <p className="text-sm text-gray-600 mb-2">
                  Autoriza a VCOO a acceder a tus documentos de Google:
                </p>
                <p className="text-xs text-gray-400 mb-4">
                  {oauthConfig.scopes}
                </p>
                <Button variant="primary" size="lg" onClick={() => conectarOAuth(oauthConfig.service)}
                  loading={conectando === oauthConfig.service}>
                  {conectando === oauthConfig.service ? 'Conectando...' : 'Conectar con Google'}
                </Button>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-yellow-700 bg-yellow-50 rounded-lg p-4">
            Configura este módulo directamente desde la terminal de tu VPS.
          </p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add conectando state variable**

Ensure `conectando` is already declared at the top of SetupWizard. It is (line 225): `const [conectando, setConectando] = useState<string | null>(null);`

No change needed.

---

### Task 5: Frontend — Wire checks.google for module card state

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:774-891`

- [ ] **Step 1: Show connection status on module cards**

In `renderPasoModulos`, inside the module card grid (around line 860-887), add a status indicator based on `checks`:

Replace the card content (lines 873-884) from:

```typescript
<div className="flex flex-col items-center text-center">
  <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mb-3 text-2xl">
    {info.icono}
  </div>
  <h3 className="font-semibold text-gray-900 mb-1">
    {info.nombre}
  </h3>
  <p className="text-sm text-gray-500">
    {info.descripcion}
  </p>
</div>
```

To:

```typescript
<div className="flex flex-col items-center text-center">
  <div className={`w-14 h-14 rounded-full flex items-center justify-center mb-3 text-2xl ${
    modulo === 'office' && (checks as Record<string, string>).google === 'ok' ? 'bg-green-100' :
    modulo === 'mail' && (checks as Record<string, string>).gmail === 'ok' ? 'bg-green-100' :
    'bg-gray-100'
  }`}>
    {modulo === 'office' && (checks as Record<string, string>).google === 'ok' ? '✅' : info.icono}
  </div>
  <h3 className="font-semibold text-gray-900 mb-1">
    {info.nombre}
  </h3>
  <p className="text-sm text-gray-500">
    {modulo === 'office' && (checks as Record<string, string>).google === 'ok' ? 'Conectado' :
     modulo === 'mail' && (checks as Record<string, string>).gmail === 'ok' ? 'Conectado' :
     info.descripcion}
  </p>
</div>
```

---

### Task 6: Google Cloud — Configure project (manual)

**No code changes — manual configuration in Google Cloud Console.**

- [ ] **Step 1: Create Google Cloud Project**
  - Name: "VCOO" (or as decided by VERSUS)
  - Note the project ID

- [ ] **Step 2: Enable required APIs**
  - Google Drive API
  - Google Docs API
  - Google Sheets API
  - Google Slides API
  - Gmail API

- [ ] **Step 3: Configure OAuth consent screen**
  - User Type: External
  - App name: "VCOO"
  - Support email: VERSUS team email
  - Scopes: `drive.file`, `documents`, `spreadsheets`, `presentations`, `gmail.readonly`
  - Test users: add initial client accounts
  - Status: Testing (up to 100 users)

- [ ] **Step 4: Create OAuth 2.0 Web Client credentials**
  - Application type: Web application
  - Name: "VCOO Onboarding"
  - Authorized redirect URIs:
    - `https://vcoo-onboarding.vercel.app/auth/callback` (production)
    - `http://localhost:8000/auth/callback` (development)
  - Copy the Client ID and Client Secret

- [ ] **Step 5: Set environment variables**
  In `.env` (root) and `.env.production`:
  ```
  GOOGLE_CLIENT_ID=<client-id>
  GOOGLE_CLIENT_SECRET=<client-secret>
  GOOGLE_REDIRECT_URI=https://vcoo-onboarding.vercel.app/auth/callback
  ```
