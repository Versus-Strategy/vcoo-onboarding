# Onboarding Realtime + Provider Flow Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two onboarding bugs: page not auto-updating after agent connects, and provider config not advancing to model selection.

**Architecture:** Fix at three layers: (1) agent's `_handle_set_provider` sets `model.provider` so capabilities are reported under the correct key, (2) frontend defensively searches all model keys and skips API key step when already configured, (3) polling improvements for realtime feel.

**Tech Stack:** Python (supervisor), TypeScript/React (frontend), FastAPI (backend)

## Global Constraints

- All Spanish UI strings, comments, and identifiers must remain in Spanish
- Backend: follow flat import style (`import auth, crud, models, db`)
- Supervisor files: edit both `packages/template/vcoo-supervisor/` and `packages/vcoo-supervisor/` mirrors
- Run backend commands from inside `apps/backend/`
- Frontend: npm run dev = port 3000, vite preview = port 4173

---

### Task 1: Agent — set model.provider in _handle_set_provider

**Files:**
- Modify: `packages/template/vcoo-supervisor/plugins/tick.py:120-132`
- Modify: `packages/vcoo-supervisor/plugins/tick.py:120-132`

**Interfaces:**
- Consumes: `_handle_set_provider(payload)` — dict with keys `provider`, `api_key`, `model` (optional)
- Produces: After api_key is configured, `model.provider` is set to the configured provider so `_detect_hermes_config()` returns the correct provider

**Problem:** When `api_key` is sent (no `model` yet), `_handle_set_provider` runs `hermes auth add` but never updates `model.provider`. Since `model.provider` stays at `"auto"`, `_detect_hermes_config()` returns `"auto"`, and models are reported under the `"auto"` key. Frontend looks for `models["opencode-go"]` and finds nothing.

- [ ] **Step 1: Add model.provider set after successful auth add**

After line 119 (`if r.returncode != 0: return error`), add the model.provider set:

```python
            if api_key:
                r = subprocess.run(
                    [hermes_bin, "auth", "add", provider, "--type", "api-key", "--api-key", api_key],
                    capture_output=True, text=True, timeout=30
                )
                if r.returncode != 0:
                    return {"status": "error", "output": r.stderr.strip() or f"hermes auth add exit={r.returncode}"}
                # Set model.provider so health checks detect it and models are reported under this key
                subprocess.run(
                    [hermes_bin, "config", "set", "model.provider", provider],
                    capture_output=True, text=True, timeout=15
                )
```

Apply same change to both files: `packages/template/vcoo-supervisor/plugins/tick.py` and `packages/vcoo-supervisor/plugins/tick.py`.

- [ ] **Step 2: Verify edit correctness**

Read the edited files to confirm the diff looks right. Re-run `pytest` from `apps/backend/` to ensure no backend tests broken (unrelated, but good practice).

- [ ] **Step 3: Deploy to LXC vcoo-test and verify**

```bash
lxc exec vcoo-test -- bash -c '
# Copy updated tick.py to supervisor
cat > /tmp/new_tick.py << '"'"'PYEOF'"'"'
# ... content of updated tick.py ...
PYEOF
cp /tmp/new_tick.py /opt/vcoo-supervisor/plugins/tick.py
chmod 644 /opt/vcoo-supervisor/plugins/tick.py
# Restart supervisor
sudo systemctl restart vcoo-supervisor
'
```

Verify: `hermes config show` should show `model.provider` set to `opencode-go`.

---

### Task 2: Frontend — defensive model search in enviarApiKey

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:496-514`

**Interfaces:**
- Consumes: `onboarding.models` from `GET /setup/{token}` response — dict keyed by provider id
- Produces: models found regardless of which provider key they're under

**Problem:** The model-search loop only checks `[providerId, 'opencode-go']`. If models are under a different key (e.g., `"auto"` or the actual provider id), they're missed.

- [ ] **Step 1: Read current code**

Read lines 490-530 of SetupWizard.tsx to see the exact model search code.

- [ ] **Step 2: Replace model search to iterate all keys**

Change from:
```typescript
let modelList: unknown[] = [];
for (let i = 0; i < 6; i++) {
  const { data: fresh } = await apiClient.get(`/setup/${token}`);
  const modelSources = [providerId, 'opencode-go'];
  let provModels: unknown = undefined;
  for (const src of modelSources) {
    const m = ((fresh as any).models || {})[src];
    if (m) { provModels = m; break; }
  }
  const extractList = (pm: unknown): unknown[] => {
    if (Array.isArray(pm)) return pm;
    if (pm && typeof pm === 'object') {
      const o = pm as Record<string, unknown>;
      return (o.list || o.models || []) as unknown[];
    }
    return [];
  };
  modelList = extractList(provModels);
  if (modelList.length > 0) break;
  await new Promise(r => setTimeout(r, 5000));
}
```

To:
```typescript
let modelList: unknown[] = [];
for (let i = 0; i < 6; i++) {
  const { data: fresh } = await apiClient.get(`/setup/${token}`);
  const allModels = (fresh as any).models || {};
  let provModels: unknown = undefined;
  // Search ALL model keys, not just the selected provider
  for (const key of Object.keys(allModels)) {
    const m = allModels[key];
    if (m) { provModels = m; break; }
  }
  const extractList = (pm: unknown): unknown[] => {
    if (Array.isArray(pm)) return pm;
    if (pm && typeof pm === 'object') {
      const o = pm as Record<string, unknown>;
      return (o.list || o.models || []) as unknown[];
    }
    return [];
  };
  modelList = extractList(provModels);
  if (modelList.length > 0) break;
  await new Promise(r => setTimeout(r, 5000));
}
```

- [ ] **Step 3: Build frontend to verify**

```bash
cd apps/frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds without TypeScript errors.

---

### Task 3: Frontend — skip API key form if provider already configured

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:666-680`

**Interfaces:**
- Consumes: `onboarding.checks.provider` from the onboarding state
- Produces: If `checks.provider === "ok"` on initial render, automatically advance to model selector

**Problem:** After a page reload when the provider is already configured (`checks.provider === "ok"`), the user still sees the API key form. They have to re-enter the key, which is confusing and wasteful.

- [ ] **Step 1: Read the beginning of renderPasoProveedor**

Read lines 666-720 of SetupWizard.tsx.

- [ ] **Step 2: Add guard to skip to model selector when already configured**

At the beginning of `renderPasoProveedor`, after the existing guard (line 675-677), add:

```typescript
const renderPasoProveedor = () => {
  if (modoSelectorModelo && !proveedorSeleccionado) {
    setModoSelectorModelo(false);
  }
  // If provider already configured (after reload), find it and show model selector
  if (!proveedorSeleccionado && !modoSelectorModelo && onboarding?.checks?.provider === 'ok') {
    const providers = onboarding.providers || [];
    const configured = providers.find(p => p.id === 'opencode-go') || providers[0];
    if (configured) {
      setProveedorSeleccionado(configured);
      setModoSelectorModelo(true);
    }
  }
  const prov = proveedorSeleccionado;
```

- [ ] **Step 3: Build frontend to verify**

```bash
cd apps/frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

---

### Task 4: Frontend — faster polling and visibility listener

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx:332-336`

- [ ] **Step 1: Change polling interval from 15s to 5s**

Change:
```typescript
useEffect(() => {
  if (!mostrarWizard) return;
  const interval = setInterval(fetchOnboarding, 15000);
  return () => clearInterval(interval);
}, [mostrarWizard, fetchOnboarding]);
```

To:
```typescript
useEffect(() => {
  if (!mostrarWizard) return;
  const interval = setInterval(fetchOnboarding, 5000);
  return () => clearInterval(interval);
}, [mostrarWizard, fetchOnboarding]);
```

- [ ] **Step 2: Add visibilitychange listener**

Add a new useEffect after the polling one (around line 337):

```typescript
// Refresh when user returns to tab (browsers throttle setInterval in background)
useEffect(() => {
  if (!mostrarWizard) return;
  const onVisible = () => { if (document.visibilityState === 'visible') fetchOnboarding(); };
  document.addEventListener('visibilitychange', onVisible);
  return () => document.removeEventListener('visibilitychange', onVisible);
}, [mostrarWizard, fetchOnboarding]);
```

- [ ] **Step 3: Add immediate refresh after copying one-liner**

Find the copy button at lines 645-653 and change the onClick:

```typescript
onClick={() => {
  navigator.clipboard.writeText(cmdText);
  fetchOnboarding(); // Refresh after copying — agent may have just registered
}}
```

- [ ] **Step 4: Build frontend to verify**

```bash
cd apps/frontend && npm run build 2>&1 | tail -20
```

---

### Task 5: Agent — add file logging to supervisor

**Files:**
- Modify: `packages/template/vcoo-supervisor/supervisor.py:61-62`
- Modify: `packages/vcoo-supervisor/supervisor.py:61-62`

- [ ] **Step 1: Add logging configuration**

Replace the basic logging config with file + rotation:

```python
import logging.handlers

if __name__ == "__main__":
    log_dir = Path("/opt/vcoo-supervisor")
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(log_dir / "supervisor.log"), maxBytes=1024*1024, backupCount=5
    )
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(handler)
    # Also log to stderr for container/journald visibility
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
```

Apply same change to both: `packages/template/vcoo-supervisor/supervisor.py` and `packages/vcoo-supervisor/supervisor.py`.

Also update the Supervisor.run() to log tick cycles:

```python
def run(self):
    self.load_plugins()
    while self.running:
        now = time.time()
        for plugin in self.plugins:
            if now - self.last_tick[plugin.name] >= plugin.interval:
                try:
                    plugin.tick()
                    logging.info(f"[{plugin.name}] tick ok")
                except Exception as e:
                    logging.error(f"[{plugin.name}] Error: {e}")
                self.last_tick[plugin.name] = now
        time.sleep(1)
```

- [ ] **Step 2: Deploy to LXC and verify logs appear**

```bash
lxc exec vcoo-test -- bash -c '
cat > /opt/vcoo-supervisor/supervisor.py < /tmp/new_supervisor.py
'
lxc exec vcoo-test -- systemctl restart vcoo-supervisor
sleep 5
lxc exec vcoo-test -- ls -la /opt/vcoo-supervisor/supervisor.log
lxc exec vcoo-test -- tail -20 /opt/vcoo-supervisor/supervisor.log
```

---

### Task 6: Backend — debug endpoint for operators

**Files:**
- Modify: `apps/backend/main.py` (around line 1700, before the app startup block)

- [ ] **Step 1: Add the debug endpoint**

```python
@application.get("/admin/vcoo/{vcoo_id}/debug")
def admin_vcoo_debug(vcoo_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Operator-only: raw VCOO state for debugging onboarding issues."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="auth required")
    token_payload = auth.verify_operator_token(authorization.split(None, 1)[1])
    if not token_payload:
        raise HTTPException(status_code=401, detail="invalid token")
    
    v = crud.get_vcoo(db, vcoo_id)
    if not v:
        raise HTTPException(status_code=404, detail="vcoo not found")
    
    state = crud.get_onboarding_state(db, str(v.id))
    agent = crud.get_agent_by_vcoo(db, str(v.id))
    
    result: dict[str, Any] = {
        "vcoo_id": str(v.id),
        "vcoo_name": v.name,
        "vcoo_modules": list(v.modules or []),
        "created_at": str(v.created_at) if v.created_at else None,
    }
    
    if state:
        result["onboarding"] = {
            "step": state.step,
            "status": state.status,
            "completed": state.completed or [],
            "errors": state.errors or {},
            "retry_count": state.retry_count or {},
        }
    
    if agent:
        caps = {}
        if agent.capabilities:
            try:
                caps = json.loads(agent.capabilities)
            except Exception:
                caps = {"parse_error": True}
        
        last_seen_ago = None
        if agent.last_seen:
            import datetime as dt
            last_seen_ago = (dt.datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
        
        # Get pending commands
        pending_cmds = []
        try:
            pending_cmds = [
                {"id": str(c.id), "command": c.command, "created_at": str(c.created_at)}
                for c in db.query(models.Command)
                    .filter(models.Command.agent_id == agent.id, models.Command.status == "pending")
                    .all()
            ]
        except Exception:
            pass
        
        result["agent"] = {
            "id": str(agent.id),
            "online": last_seen_ago is not None and last_seen_ago < 120,
            "last_seen_seconds_ago": last_seen_ago,
            "has_encryption_key": bool(agent.encryption_key),
            "capabilities_summary": {
                "providers_count": len(caps.get("providers", [])),
                "models_keys": list(caps.get("models", {}).keys()),
                "checks": caps.get("checks", {}),
                "current_provider": caps.get("current_provider"),
            },
            "pending_commands": pending_cmds,
        }
    
    return result
```

Add `from typing import Any` at the top of main.py if not already there.

- [ ] **Step 2: Run backend tests**

```bash
cd apps/backend && python3 -m pytest tests/ -x -q 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 3: Verify endpoint works**

```bash
# First get an operator token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.io","password":"AdminPass1"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Then call debug endpoint
curl -s http://localhost:8000/admin/vcoo/some-vcoo-id/debug \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

### Task 7: E2E — test the full flow

- [ ] **Step 1: Reset and trigger a fresh onboarding via the LXC**

```bash
# Reset LXC to clean state (if snapshot exists)
lxc snapshot vcoo-test pre-fix 2>/dev/null || true
```

- [ ] **Step 2: Walk through the full onboarding flow**

Follow the full flow from frontend: create VCOO → get one-liner → run on LXC → verify page auto-updates → configure provider → verify model selector appears → select model → verify advance works.

- [ ] **Step 3: Debug any failures using the new debug endpoint and supervisor logs**
