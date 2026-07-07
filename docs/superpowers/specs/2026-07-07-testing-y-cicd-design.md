# Diseño: Testing + CI/CD para vcoo-onboarding

**Fecha:** 2026-07-07
**Estado:** Aprobado

## Objetivo

Añadir una suite de tests completa (backend + frontend + E2E) y un pipeline de
CI/CD en GitHub Actions que la ejecute automáticamente en cada `push` y
`pull_request`.

## Estado actual

- **Monorepo**: FastAPI backend (`apps/backend`) + React/Vite frontend (`apps/frontend`).
- **Backend**: `tests/test_auth.py` con 21 tests pytest que pasan (auth, tokens,
  agentes, rate limiting, audit). Además ~5 scripts ad-hoc con `print`
  (`test_onboarding.py`, `test_onboarding2.py`, `test_final.py`,
  `check_onboard.py`, `final_check.py`, `playwright_check.py`) que **no** son
  tests pytest. Sin `pytest.ini`, sin dependencias de test fijadas.
- **Frontend**: `package.json` referencia `vitest` en el script `test` pero no
  está instalado; 0 archivos de test. 31 ficheros TS/TSX.
- **CI/CD**: no existe. Remoto en GitHub (`Versus-Strategy/vcoo-onboarding`).

## Enfoque elegido

Un único workflow de GitHub Actions con 3 jobs paralelos (backend, frontend-unit,
frontend-e2e). Los E2E solo corren si el build del frontend pasa.

## Arquitectura

### Sección A — Backend testing (pytest)

- `apps/backend/pytest.ini`: `testpaths=tests`, filtro de `DeprecationWarning`,
  marcadores.
- `apps/backend/tests/conftest.py`: setup centralizado de env vars + fixtures
  `client`, `db_session`, `reset_db` (autouse), helpers `auth_token`,
  `create_vcoo`, `active_provision_token`.
- Nuevos tests pytest (patrón de `test_auth.py`):
  - `test_vcoos.py`: crear/listar/borrar VCOO, `/vcoo/{id}/state`,
    provision-token, regenerate, complete/reactivate.
  - `test_onboarding.py`: `/setup/{id}` read-only (requires_registration),
    `/setup/{id}/verify` (auto_completed en modo demo), auth-url, retry/skip.
  - `test_agents.py`: register, poll, result (ACK), heartbeat, health, capabilities.
  - `test_utils.py`: `/healthz`, `/playbooks`, `/install.sh`.
- `apps/backend/requirements-dev.txt`: `pytest`, `pytest-cov`, `httpx`.

**Contratos verificados** (leídos de `main.py`):
- `/setup/{identifier}` usa **UUID del VCOO** (no el token); sin auth →
  `{requires_registration: True, token_valid: True, vcoo_name}`.
- `/setup/{identifier}/verify` sin agente → `{status: "auto_completed", ...}`.
- `/register` → `{agent_id, vcoo_id, agent_token, encryption_key}`.
- `/agent/{id}/result` → ACK, requiere `cmd_id` válido; 409 si ya reportado.
- `/healthz` → `{status: "ok", version: "v2", python: ...}`.
- `/agent/heartbeat` → requiere `agent_id` en body → `{ack: True}`.

### Sección B — Frontend testing (vitest + RTL)

- Instalar: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`,
  `@testing-library/user-event`, `jsdom`.
- Config `test` en `vite.config.ts` (`environment: jsdom`, `setupFiles`, `globals`).
- `src/test/setup.ts`: importa `@testing-library/jest-dom`.
- Tests:
  - `components/StatusBadge.test.tsx`, `StepIndicator.test.tsx`,
    `Button.test.tsx`, `DataTable.test.tsx` (componentes puros).
  - `api/apiClient.test.ts`: interceptor de auth (Bearer desde localStorage),
    refresh en 401, cola de refresh concurrente, 429 sin reintento.
  - `store/*.test.ts`: estado zustand.

### Sección C — E2E (Playwright)

- Instalar `@playwright/test`.
- `playwright.config.ts` con `webServer` que arranca `vite preview` (build
  previo). Tests de smoke: carga de `/login`, navegación básica.
- Scripts: `test:e2e`.

### Sección D — Limpieza

- Mover scripts ad-hoc a `apps/backend/scripts/manual/` para que pytest no los
  recoja. Se conservan como referencia manual.

### Sección E — CI/CD (GitHub Actions)

`.github/workflows/ci.yml`, triggers `push` + `pull_request` sobre `main`:

- **job `backend-tests`**: Python 3.11, instala `requirements.txt` +
  `requirements-dev.txt`, corre `pytest` con env vars de test (SQLite).
- **job `frontend-unit`**: Node 20, `npm ci`, `npm run lint`, `npm run test`
  (vitest en modo run), `npm run build`.
- **job `frontend-e2e`**: `needs: frontend-unit`, instala navegadores de
  Playwright, corre `npm run test:e2e`.

## Testing de la solución

- Backend: `python3 -m pytest` en `apps/backend` → todos verdes.
- Frontend: `npm run test -- --run` en `apps/frontend` → todos verdes.
- CI: el workflow se valida por sintaxis y se confía en su ejecución en GitHub.

## Fuera de alcance (YAGNI)

- Cobertura mínima obligatoria (coverage gate) — se reporta pero no bloquea.
- Tests de los módulos WebSocket (`ws_*`) — no críticos, entorno local.
- Deploy automático a Vercel desde CI (Vercel ya lo hace vía integración Git).

## Desviaciones / hallazgos durante la implementación

- **Bug encontrado y corregido**: `crud.delete_vcoo` bindeaba el id como objeto
  `uuid.UUID`, lo que rompía en SQLite (`type 'UUID' is not supported`) y hacía
  que `DELETE /vcoo/{id}` devolviera 500. Los modelos usan `String(36)`. Fix:
  bindear el id como `str` (compatible con SQLite y Postgres). El test
  `test_delete_vcoo` ahora verifica el 200 correcto.
- **ESLint sin configuración**: el `package.json` tenía script `lint` y plugins,
  pero no existía config. Se añadió `.eslintrc.cjs` (ESLint 8) para que
  `npm run lint` funcione en CI (solo warnings, 0 errores).
- **Resultado de verificación**: backend 62 tests (67% cobertura), frontend 29
  tests unitarios + 3 E2E, lint y build en verde.

