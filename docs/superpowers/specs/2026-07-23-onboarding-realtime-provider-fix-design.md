# Onboarding: Realtime Updates + Provider → Model Flow Fix

## Problem

Two bugs discovered during manual onboarding testing (LXC vcoo-test):

1. **Page doesn't auto-update** after agent connects. 15s polling interval + browser tab throttling + dead WebSocket code means the user often needs to manually reload to see onboarding progress.

2. **Provider config doesn't advance to model selection.** After configuring `opencode-go` via the wizard, the agent stores the API key correctly (`hermes auth add` succeeds) but the frontend never shows the model selector. Reloading doesn't help.

## Root Causes

### Bug 1: Stale UI
- `RealtimeManager.ts`: `canUseWebSocket()` hardcodes `return false`; `initPollingFallback()` is a deliberate no-op
- `SetupWizard.tsx` relies solely on a 15-second `setInterval` that browsers throttle heavily when the tab is in background
- No `visibilitychange` listener to refresh when the user returns to the tab
- No immediate fetch after key actions (copying the one-liner)

### Bug 2: Provider → Model Blocked
- Agent's `_handle_set_provider` adds the API key (`hermes auth add`) but never updates `model.provider`
- Agent's `_detect_hermes_config()` returns `"auto"` (the pre-existing `model.provider` value)
- Agent's `_report_capabilities()` reports `models` under the `"auto"` key
- Frontend `enviarApiKey()` looks for `models["opencode-go"]` → undefined → model list stays empty → `setModoSelectorModelo(true)` never called
- User is stuck: even reloading doesn't skip the API-key step because `modoSelectorModelo` resets to `false`

## Design

### Section 1: Agent — set model.provider on api_key config

**File:** `packages/template/vcoo-supervisor/plugins/tick.py` (+ `packages/vcoo-supervisor/plugins/tick.py`)

In `_handle_set_provider`, when `api_key` is provided (first call, no model yet), run:
```python
subprocess.run([hermes_bin, "config", "set", "model.provider", provider],
               capture_output=True, text=True, timeout=15)
```

This makes `_detect_hermes_config()` return the correct provider, `_report_capabilities()` reports models under `provider` key, and the frontend's polling finds them.

### Section 2: Frontend — defensive model search + skip API key if already configured

**File:** `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx`

**2a.** In `enviarApiKey`, iterate ALL keys in `models` dict instead of only `[providerId, "opencode-go"]`.

**2b.** In `renderPasoProveedor`, if `onboarding.checks.provider === "ok"` on initial render (after reload), skip the API-key form and directly show the model selector. This handles recovery after page reload when provider is already configured.

### Section 3: Frontend — faster and smarter polling

**File:** `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx`

- Reduce main polling from 15s → 5s during active onboarding (`wizard_step < 3`)
- Add `document.addEventListener("visibilitychange", ...)` to re-fetch when tab becomes visible
- Call `fetchOnboarding()` immediately after the user clicks "Copiar" for the one-liner

### Section 4: Agent — add logging

**File:** `packages/template/vcoo-supervisor/supervisor.py` (+ `packages/vcoo-supervisor/supervisor.py`)

- Configure Python logging to write to `/opt/vcoo-supervisor/supervisor.log`
- Log: tick cycles, commands received, commands executed (result), health check results
- Simple rotation: 5 files × 1MB

### Section 5: Backend — debug endpoint

**File:** `apps/backend/main.py`

New admin endpoint `GET /admin/vcoo/{vcoo_id}/debug` (operator-only JWT):
- Returns raw `OnboardingState` row
- Returns raw `Agent` row (capabilities, last_seen, encryption_key presence)
- Returns pending/unacked commands for that agent
- Useful field: `command_queue_length`, `last_seen_seconds_ago`, `capabilities_summary`

## Not in Scope

- WebSocket re-enable (too risky, requires full E2E testing)
- Supervisor auto-update of tick.py (assumes next template deploy)
- UI for the debug endpoint (JSON is sufficient for operator debugging)
