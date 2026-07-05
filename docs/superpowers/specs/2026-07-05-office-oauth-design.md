# OFFICE Module — Google OAuth Design

## Overview

Replace the current manual Google Cloud Console setup instructions (client creates own OAuth client) with a one-click "Conectar con Google" OAuth flow using VERSUS's own Google Cloud Project. The OFFICE module covers Google Drive, Docs, Sheets, and Slides with read/write access.

## Architecture

### Service Identifiers

| Module | Service ID | Scopes |
|--------|-----------|--------|
| OFFICE | `google-drive` | `https://www.googleapis.com/auth/drive.file` + `https://www.googleapis.com/auth/documents` + `https://www.googleapis.com/auth/spreadsheets` + `https://www.googleapis.com/auth/presentations` |
| MAIL | `gmail` | `https://www.googleapis.com/auth/gmail.readonly` |

Each service is separate. A single OAuth authorization covers only one module.

### OAuth Flow

```
Browser                  Backend                    Google               Agent VPS
  │                        │                         │                     │
  │  GET /auth-url         │                         │                     │
  │  ?service=google-drive │                         │                     │
  │───────────────────────>│                         │                     │
  │  { url }               │                         │                     │
  │<───────────────────────│                         │                     │
  │                        │                         │                     │
  │  Open popup →          │  redirect to Google      │                     │
  │──────────────────────────────────────────────────>│                     │
  │                        │                         │  User consents      │
  │                        │                         │  (drive.file,       │
  │                        │                         │   documents,        │
  │                        │                         │   spreadsheets,     │
  │                        │                         │   presentations)    │
  │                        │                         │                     │
  │                        │  redirect /auth/callback│                     │
  │                        │  ?code=...&state=...    │                     │
  │                        │<─────────────────────────│                     │
  │                        │                         │                     │
  │                        │  Exchange code for      │                     │
  │                        │  access+refresh tokens  │                     │
  │                        │─────────────────────────>│                     │
  │                        │  tokens                 │                     │
  │                        │<─────────────────────────│                     │
  │                        │                         │                     │
  │                        │  Create "save-creds" cmd│                     │
  │                        │  Advance google-oauth   │                     │
  │                        │  step                   │                     │
  │                        │                         │                     │
  │  HTML "success, close" │                         │                     │
  │<───────────────────────│                         │                     │
  │                        │                         │                     │
  │  Popup closes          │                         │                     │
  │                        │                         │                     │
  │                        │  Tick → fetch commands  │                     │
  │                        │──────────────────────────────────────────────>│
  │                        │                         │                     │
  │                        │  save-creds command     │                     │
  │                        │<──────────────────────────────────────────────│
  │                        │                         │                     │
  │                        │                         │  Save tokens to     │
  │                        │                         │  google_token.json  │
  │                        │                         │  hermes auth add    │
  │                        │                         │                     │
  │                        │  command result (ok)    │                     │
  │                        │<──────────────────────────────────────────────│
  │                        │                         │                     │
  │                        │  (auto) queue           │                     │
  │                        │  verify-google command  │                     │
  │                        │                         │                     │
  │                        │  Tick → fetch commands  │                     │
  │                        │──────────────────────────────────────────────>│
  │                        │                         │  Run vcoo-google.py │
  │                        │                         │  drive list         │
  │                        │                         │                     │
  │                        │  verify result (ok)     │                     │
  │                        │<──────────────────────────────────────────────│
```

### Backend Changes

#### Auth URL endpoint (`GET /setup/{identifier}/auth-url`)

Accept `service=google-drive` and `service=gmail` in addition to `google`.

```python
SCOPES_MAP = {
    "google-drive": (
        "https://www.googleapis.com/auth/drive.file"
        "+https://www.googleapis.com/auth/documents"
        "+https://www.googleapis.com/auth/spreadsheets"
        "+https://www.googleapis.com/auth/presentations"
    ),
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
}
```

State format remains `{vcoo_id}:{service}`.

#### OAuth callback (`GET /auth/callback`)

```python
STEP_MAP = {
    "google-drive": "google-oauth",
    "gmail": "gmail-setup",
}
```

Remove the auto-advance of `gmail-setup` when `google-oauth` completes (modules are now separate).

#### save-creds command

The backend stores the tokens in the command's `result` column and the tick endpoint sends them to the agent as `payload`. The callback already creates this command with `command="save-creds"` and the tokens serialized in `result`.

### Agent Changes (tick.py)

#### save-creds handler (NEW)

Currently `save-creds` is a no-op (returns "ignored"). Implement:

1. Parse `result` JSON from the command payload
2. Extract `access_token`, `refresh_token`, `service`
3. Save tokens to `~/.hermes/google_token.json`
4. Run `hermes auth add google` to register in Hermes auth system
5. Re-run health checks immediately
6. Return `{"status": "ok"}`

```python
_command_handlers = {
    "save-creds": _handle_save_creds,
}

def _handle_save_creds(self, cmd: dict) -> dict:
    import json, os
    try:
        payload = cmd.get("payload", {})
        service = payload.get("service", "google")
        token_path = os.path.expanduser("~/.hermes/google_token.json")
        with open(token_path, "w") as f:
            json.dump(payload, f, indent=2)
        # Register in Hermes auth
        access_token = payload.get("access_token", "")
        if access_token:
            subprocess.run(
                ["hermes", "auth", "add", "google", "--oauth-token", access_token],
                capture_output=True, timeout=15
            )
        self._run_health_checks()
        return {"status": "ok", "output": f"Credenciales {service} guardadas"}
    except Exception as e:
        return {"status": "error", "output": str(e)}
```

#### Improved health check for google (`_run_health_checks`)

Replace the string-matching check with a token file check:

```python
google_token_path = os.path.expanduser("~/.hermes/google_token.json")
if os.path.isfile(google_token_path):
    try:
        with open(google_token_path) as f:
            tok = json.load(f)
        if tok.get("access_token"):
            result["google"] = "ok"
        else:
            result["google"] = "error"
    except:
        result["google"] = "error"
else:
    result["google"] = "missing"
```

Optionally verify the token works by running `vcoo-google.py drive list` (more robust but slower).

#### Verify-google command update

The existing `verify-google` command maps to:
```python
"verify-google": ["python3", "~/.hermes/scripts/vcoo/vcoo-google.py", "drive", "list"],
```

This already works — it reads from `~/.hermes/google_token.json` and makes a Drive API call. No changes needed.

### Frontend Changes (SetupWizard.tsx)

#### Module instructions → OAuth button

Replace `MODULE_INSTRUCTIONS.office` (manual Google Cloud steps) with an OAuth button:

```typescript
const MODULE_OAUTH: Record<string, { service: string; scopes: string }> = {
  office: { service: 'google-drive', scopes: 'Drive, Docs, Sheets, Slides' },
  mail: { service: 'gmail', scopes: 'Gmail' },
};
```

When user clicks a module card and `checks.google === "ok"` → show ✅ "Conectado".
When `checks.google !== "ok"` → show "Conectar con Google" button.

#### OAuth popup flow

```typescript
const conectarOAuth = async (service: string) => {
  const { data } = await apiClient.get(`/setup/${token}/auth-url?service=${service}`);
  const width = 600, height = 700;
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;
  const popup = window.open(
    data.url, 'google-oauth',
    `width=${width},height=${height},left=${left},top=${top}`
  );
  // Poll until popup closes
  const checkClosed = setInterval(() => {
    if (popup?.closed) {
      clearInterval(checkClosed);
      fetchOnboarding();  // refresh state
    }
  }, 500);
};
```

#### Use checks.google for visual state

```typescript
const googleCheck = checks.google;
// "ok" → mostrar "Conectado" con checkmark
// "missing" → mostrar botón "Conectar con Google"
// "error" → mostrar "Reconectar" con advertencia
// undefined → mostrar botón "Conectar con Google"
```

#### Remove manual instructions

Delete `MODULE_INSTRUCTIONS.office` entry. The mail module also gets its own OAuth button (separate from office).

### Google Cloud Project Setup

| Item | Value |
|------|-------|
| Project | VCOO (VERSUS-owned) |
| APIs enabled | Drive API, Docs API, Sheets API, Slides API, Gmail API |
| OAuth type | Web application |
| Redirect URIs | `https://vcoo-onboarding.vercel.app/auth/callback` (prod), `http://localhost:8000/auth/callback` (dev) |
| Scopes | `drive.file`, `documents`, `spreadsheets`, `presentations`, `gmail.readonly` |
| Consent screen | External (any Google account) |
| Status | Testing initially (up to 100 users), plan verification for production |

### Security

- Same `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` used for all clients
- Each user gets their own access+refresh tokens scoped to their Google account
- Tokens stored per-VPS at `~/.hermes/google_token.json`
- No cross-account access possible — tokens are tied to individual user consent
- Token revocation: user can revoke via Google Account settings, or agent can delete token file

### Error Handling

| Scenario | Behavior |
|----------|----------|
| User denies consent | Google returns `?error=access_denied` → callback shows "Autorización denegada" page |
| Token exchange fails | Backend still stores the `code` as fallback, shows success page |
| Token expired | Agent's health check detects → `checks.google = "error"` → frontend shows "Reconectar" |
| Network error saving creds | Agent returns error → backend marks command as failed → retry on next tick |
| Agent offline when OAuth completes | Command queued in DB → agent picks it up when it comes back online |
