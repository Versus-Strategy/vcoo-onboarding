# AGENTS.md

Guidance for agents working in this repo. `README.md` is thorough but has a few
stale claims (called out below). Prefer this file and the executable config when
they conflict with prose.

## What this is

Monorepo for the **VCOO Onboarding** control plane.

- `apps/backend/` — FastAPI + SQLAlchemy 2.0 API (Python 3.11). Deployed to Vercel as serverless functions.
- `apps/frontend/` — React 18 + Vite 4 SPA (`vcoo-dashboard`), TypeScript. Separate Vercel project.
- `packages/` — client-VPS artifacts (agent, supervisor, watchdog, product template). **Not imported by the backend**; delivered/installed on customer VPSs. Editing them does not affect backend runtime.
- `api/` — Vercel entrypoint. `docs/` — plans/specs. `infra/` — Docker + `Dockerfile.backend`. `supabase/` — CLI project (migrations, `config.toml`).

Each `apps/*` deploys as its own Vercel project (different Root Directory). UI strings, comments, and many identifiers are in **Spanish** — match that when editing.

## Gotchas (things that will bite you)

- **The FastAPI app object is `application`, not `app`.** Only `main:application` works. `main:app` is broken/stale in `infra/Dockerfile.backend`, `README.md`, and the `scripts/manual/*` files — do not copy those. Tests and `playwright.config.ts` correctly use `main:application`.
- **The active Vercel entrypoint is `api/index.py`** (`vercel.json` rewrites everything to `/api/index`). `api/[...slug].py` is `.vercelignore`d and unused despite the README naming it the entrypoint.
- **Backend imports are flat/top-level** (`import db, crud, auth, models`), not package-qualified. Everything runs with `apps/backend/` on `sys.path` (handled by `conftest.py`, `main.py`, and the Vercel shim). Run backend commands from inside `apps/backend/`.
- **Passwords use bcrypt** (`auth.py`), not hashlib (README says hashlib — wrong).
- **Schema is created at app startup**, not via the Supabase migrations. `main.py` startup runs `Base.metadata.create_all()` plus hand-written `ALTER TABLE` blocks for new columns. If you add a column to `models.py`, add a matching idempotent `ALTER TABLE ... ADD COLUMN` in the startup migration block (Postgres won't get it from `create_all` on existing tables). `supabase/migrations/*.sql` is a separate, parallel schema source.
- **WebSocket routes only register off-Vercel** (`register_ws_routes` runs only when `VERCEL_ENV` is unset). Prod is polling-only; the frontend `RealtimeManager` hardcodes `canUseWebSocket() -> false` and always polls.
- **`MASTER_KEY` is required.** `auth.py` raises `RuntimeError('MASTER_KEY not set')` when signing tokens. It's the HMAC secret for all JWTs (provision tokens, operator/client/agent tokens) and derives Fernet keys for agent config.
- **Login is rate-limited** (5 attempts / 300s per IP, in-memory). Multiple logins in a test/script will 429. Override with `LOGIN_RATE_MAX_ATTEMPTS` / `LOGIN_RATE_WINDOW_SECONDS` (E2E sets it high).
- Frontend `apps/frontend/.env` points `VITE_API_URL` at a LAN IP (`http://10.0.0.1:8000`); it overrides the `http://localhost:8000` default. There is no frontend `.env.example` despite README references.
- Frontend ports differ by mode: `npm run dev` = **3000**, `vite preview` (E2E) = **4173**. README's 5173 is wrong. Fast Refresh is intentionally disabled in `vite.config.ts` (custom plugin strips the preamble) — don't re-enable it blindly.

## Commands

Backend (run from `apps/backend/`):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                    # whole suite; SQLite in /tmp, no env setup needed (conftest sets defaults)
pytest tests/test_auth.py::test_name   # single test
pytest --cov=. --cov-report=term-missing
python3 -m uvicorn main:application --reload --port 8000 --host 0.0.0.0   # local server
```

Frontend (run from `apps/frontend/`):

```bash
npm ci
npm run lint              # eslint src (ESLint 8, strictness relaxed; no-explicit-any off)
npm run test              # vitest run (unit; *.test.tsx co-located in src/)
npm run build
npm run test:e2e          # builds with VITE_API_URL=localhost:8000, then Playwright; auto-starts a real uvicorn backend + vite preview. Needs Python available.
```

CI (`.github/workflows/ci.yml`, on push/PR to `main`): `backend-tests` (pytest, Py 3.11) and `frontend-unit` (lint+vitest+build, Node 22) run in parallel; `frontend-e2e` (Playwright) needs `frontend-unit`. Match those versions.

Docker (from `infra/`): `docker compose up -d --build backend` (Postgres + backend on :8000). Note the Dockerfile's `main:app` CMD is broken — see gotchas.

## Testing notes

- Backend tests use SQLite and seed a `FIRST_OPERATOR_*` admin; `conftest.py` fixtures give `client`, `operator_token`, `make_vcoo`, `provision_token`. `reset_db` (autouse) wipes tables and resets the rate limiter between tests.
- `apps/backend/scripts/manual/*` are ad-hoc `print`-based scripts, NOT part of the pytest suite (and use the stale `from main import app`).

## Where things live (backend)

`main.py` (~1600 lines) holds all routes. `crud.py` = DB ops, `models.py` = SQLAlchemy tables, `schemas.py` = Pydantic, `auth.py` = JWT + bcrypt, `crypto.py` = Fernet agent-config encryption, `onboarding.py` = the step/module state machine and step→command map, `ratelimit.py` = login limiter, `ws_*.py` = local-only WebSockets.

Provision-token semantics matter and don't fully match the README. The `/setup/{identifier}` wizard endpoints accept a **VCOO UUID** (preferred) and read state read-only via `crud.get_vcoo` — they no longer consume a JWT token. Registration (`/register`, `/auth/client/register`) calls `crud.validate_provision_token()`, which consumes (`used=True`). There is no `lookup_provision_token()` in the code despite the README mentioning it. See `DESIGN_DECISIONS.md` for the onboarding/token rationale.
