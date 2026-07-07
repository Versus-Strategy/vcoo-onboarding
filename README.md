# VCOO Onboarding API

[![CI](https://github.com/Versus-Strategy/vcoo-onboarding/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Versus-Strategy/vcoo-onboarding/actions/workflows/ci.yml)

API REST que orquesta el ciclo de vida completo de las instancias **VCOO** (Virtual Cognitive Orchestration Operator): provisionamiento, autenticación, onboarding de clientes, registro de agentes y ejecución de comandos de verificación.

## Stack Tecnológico

| Capa              | Tecnología                                     |
|-------------------|------------------------------------------------|
| Framework web     | FastAPI (Python 3.11+)                         |
| ORM               | SQLAlchemy 2.0                                 |
| Base de datos     | PostgreSQL (Supabase)                          |
| Autenticación     | JWT (PyJWT) + hashlib (password hashing)       |
| Despliegue        | Vercel (serverless functions via `api/[...slug].py`) |
| Agente VPS        | vcoo-supervisor (Python, modular, systemd)     |
| Frontend          | React SPA (vcoo-dashboard)                     |
| WebSockets        | FastAPI WebSocket + bridge (entorno local)     |
| Testing           | pytest (backend), Vitest + Testing Library + Playwright (frontend) |
| CI/CD             | GitHub Actions                                |

## Arquitectura

```
┌──────────────┐     HTTP/JSON      ┌──────────────────────┐
│  vcoo-dashboard├──────────────────→│  VCOO Onboarding API  │
│  (React SPA)  │←──────────────────│  (FastAPI Serverless)  │
│  Vercel       │                   │  Vercel                │
└──────────────┘                    └───────────┬──────────┘
                                                 │ SQLAlchemy
                                                 ↓
                                         ┌──────────────┐
                                         │  Supabase     │
                                         │  PostgreSQL   │
                                         └──────────────┘

┌──────────────────────┐  POST /agent/{id}/health  ┌──────────────────────┐
│  vcoo-supervisor      │ ────────────────────────→│  VCOO Onboarding API  │
│  (VPS del cliente)    │ (métricas, versión,       │                       │
│  systemd + plugins)   │  heartbeat)               │                       │
└──────────────────────┘                           └──────────────────────┘
```

La aplicación se despliega como **funciones serverless** en Vercel. `api/[...slug].py` es el punto de entrada para Vercel. En entorno local, los WebSockets están disponibles para comunicación en tiempo real agente-UI.

Este repositorio es un **monorepo** con la siguiente estructura:

```
apps/           → Aplicaciones desplegables independientemente
  backend/      → FastAPI (Python)
    tests/      → Suite pytest (test_*.py + conftest.py)
    pytest.ini  → Configuración de pytest
  frontend/     → React SPA (TypeScript)
    src/**/*.test.tsx → Tests unitarios (Vitest + Testing Library)
    e2e/        → Tests end-to-end (Playwright)
packages/       → Código compartido (no se despliega solo)
  agent/        → Scripts del agente VCOO
  vsd/          → Watchdog systemd
  template/     → Plantillas de provisioning
infra/          → Configuración de infraestructura
  docker-compose.yml
  Dockerfile.backend
  supabase/
api/            → Entrypoint serverless Vercel
docs/           → Documentación y planos
.github/workflows/ci.yml → Pipeline de CI (GitHub Actions)
```

## Endpoints de la API

### Autenticación

| Método | Ruta                    | Descripción                                                    |
|--------|-------------------------|----------------------------------------------------------------|
| POST   | `/auth/login`           | Login de operador (email + password). Devuelve JWT.            |
| POST   | `/auth/verify`          | Verifica si una contraseña de operador es correcta.            |
| POST   | `/auth/client/register` | Registro de cliente vinculado a un VCOO mediante token.        |
| POST   | `/auth/client/login`    | Login de cliente existente (email + password).                 |
| GET    | `/auth/client/me`       | Obtiene información del cliente autenticado + datos del VCOO.  |
| GET    | `/auth/callback`        | Callback OAuth de Google (intercambia code por tokens).        |

### VCOOs

| Método | Ruta                       | Descripción                                      |
|--------|----------------------------|--------------------------------------------------|
| GET    | `/vcoos`                   | Lista todos los VCOOs con estado del agente.     |
| POST   | `/vcoo`                    | Crea un nuevo VCOO con onboarding state + token. |
| GET    | `/vcoo/{id}/state`         | Obtiene el estado completo de un VCOO.           |
| DELETE | `/vcoo/{id}`               | Elimina un VCOO y todos sus registros asociados. |

### Tokens de Provision

| Método | Ruta                               | Descripción                                                |
|--------|------------------------------------|------------------------------------------------------------|
| GET    | `/vcoo/{id}/provision-token`       | Obtiene el token activo de un VCOO.                        |
| POST   | `/vcoo/{id}/regenerate-token`      | Revoca el token actual y genera uno nuevo.                 |

### Wizard de Onboarding

| Método | Ruta                      | Descripción                                                |
|--------|---------------------------|------------------------------------------------------------|
| GET    | `/setup/{token}`          | Obtiene datos de onboarding (read-only, no consume token). |
| POST   | `/setup/{token}/verify`   | Encola comando de verificación o avanza paso en modo demo. |
| GET    | `/setup/{token}/auth-url` | Genera URL de autorización OAuth para el servicio indicado.|

### Agente

| Método | Ruta                        | Descripción                                                |
|--------|-----------------------------|------------------------------------------------------------|
| POST   | `/register`                 | Registra un agente usando un token de provision.           |
| GET    | `/agent/{id}/poll`          | Polling de comandos pendientes para un agente.             |
| POST   | `/agent/{id}/result`        | Reporta el resultado de un comando con semántica ACK.      |
| POST   | `/agent/{id}/logs`          | Stream de logs en tiempo real desde el agente.             |
| POST   | `/agent/heartbeat`          | Heartbeat del agente (actualiza `last_seen` y `status`).   |

### Utilidad

| Método | Ruta                         | Descripción                                         |
|--------|------------------------------|-----------------------------------------------------|
| GET    | `/healthz`                   | Healthcheck con información de conexión a BD.       |
| GET    | `/install.sh`                | Script de instalación del agente (one-liner).       |
| GET    | `/template.tar.gz`           | Template VCOO para provisioning del VPS.            |
| GET    | `/playbooks`                 | Lista playbooks disponibles.                        |

## Esquema de Base de Datos

La base de datos se ejecuta en **Supabase (PostgreSQL)**. Las tablas principales son:

| Tabla              | Descripción                                                    |
|--------------------|----------------------------------------------------------------|
| `vcoos`            | Instancias VCOO (id, name, status, created_at).                |
| `provision_tokens` | Tokens de provision para vincular clientes (token, vcoo_id, expires_at, used). |
| `clients`          | Clientes registrados (email, password_hash, name, vcoo_id).    |
| `agents`           | Agentes VCOO registrados (vcoo_id, info, status, last_seen, health_payload, template_version, supervisor_version). |
| `commands`         | Comandos encolados para los agentes (command, status, step, result, ttl). |
| `command_logs`     | Logs chunked de ejecución de comandos (command_id, stream, chunk). |
| `onboarding_state` | Estado del wizard de onboarding por VCOO (step, status, modules, completed, errors, retry_count). |
| `audit_log`        | Registro de auditoría de acciones del operador (action, actor_email, vcoo_id, log_metadata). |

## vcoo-supervisor (agente en VPS)

El supervisor es un proceso Python modular que corre como servicio systemd en cada VPS del cliente. Reemplaza los antiguos `versusd`, `health-reporter.py` y el heartbeat del agente.

```
vcoo-supervisor/
├── supervisor.py          ← Core: ciclo, scheduler, logging
├── config.json            ← Configuración de plugins
├── plugins/
│   ├── health_reporter.py ← Métricas VPS cada 60s → POST /agent/{id}/health
│   ├── watchdog.py        ← pgrep Hermes cada 30s, restart si caído
│   └── updater.py         ← hermes update cada 7 días
└── vcoo-supervisor.service ← systemd unit
```

Cada plugin implementa la interfaz:
```python
class Plugin:
    name: str
    interval: int
    def start(self, config): ...
    def stop(self): ...
    def tick(): ...
```

### Métricas reportadas

```json
{
  "hostname": "vcoo-test",
  "uptime_seconds": 3600,
  "hermes_running": true,
  "disk_used_pct": 21.8,
  "template_version": "1.2.0",
  "supervisor_version": "0.1.0"
}
```

## Auditoría

Cada acción crítica del operador registra un evento en la tabla `audit_log`:

| Acción | Endpoint |
|--------|----------|
| `vcoo.created` | `POST /vcoo` |
| `vcoo.deleted` | `DELETE /vcoo/{id}` |
| `token.regenerated` | `POST /vcoo/{id}/regenerate-token` |

Los eventos se muestran como timeline en la página de detalle del cliente (`/operador/clientes/{id}`).

Las tablas se crean automáticamente al iniciar la aplicación mediante `Base.metadata.create_all()`.

## Flujo de Registro de Cliente

1. El **operador** crea un VCOO (`POST /vcoo`) y obtiene una URL de onboarding que contiene un token JWT firmado.
2. El operador envía la URL al cliente (por email, enlace, etc.).
3. El cliente abre la URL → el frontend carga `GET /setup/{token}` (read-only, no consume).
4. El cliente se **registra** (`POST /auth/client/register`) con nombre, email, contraseña + el token.
5. El backend valida el token, lo consume (`used = True`), crea el cliente y lo enlaza al `vcoo_id`.
6. El cliente recibe un JWT y queda autenticado para continuar el wizard.

## Mecanismo de Tokens de Provision

- Son **JWT firmados** con `MASTER_KEY` (algoritmo HS256), con expiración por defecto de 60 minutos (7 días si se generan desde `create_provision_for_vcoo`).
- Se almacenan también en la tabla `provision_tokens` para persistencia y trazabilidad.
- **`lookup_provision_token()`** — validación **read-only**, no marca el token como usado. Se usa en el wizard público.
- **`validate_provision_token()`** — validación **con consumo**: marca `used = True` si es válido. Se usa en el registro de cliente y agente.
- Si un token expira, el operador puede regenerarlo (`POST /vcoo/{id}/regenerate-token`).

## Sistema Watchdog: vsd/

El directorio `vsd/` contiene el sistema **versusd** — un watchdog que se ejecuta en el VPS del cliente y gestiona el agente VCOO como un servicio systemd. Incluye:

- **Servicios systemd** para el agente VCOO y Hermes Gateway.
- **`vsctl`** — CLI para controlar el watchdog (start, stop, status, logs, provision).
- **`onboard.sh`** — Script de instalación one-liner que configura systemd, instala dependencias y arranca el agente.

Este sistema está separado de Hermes Agent por diseño: el watchdog no debe depender de Hermes ni viceversa. Es un servicio independiente de monitorización y ciclo de vida.

## Variables de Entorno

| Variable              | Local (apps/backend/.env) | Producción (Vercel)                             | Descripción                                                     |
|-----------------------|---------------------------|-------------------------------------------------|-----------------------------------------------------------------|
| `POSTGRES_URL`        | `sqlite:///./test.db`     | PostgreSQL URL (Supabase)                       | URL de conexión a base de datos.                                |
| `MASTER_KEY`          | `vcoo-test-master-key-…`  | Secreto seguro (64+ chars)                      | Clave HMAC para firmar/verificar todos los JWT.                 |
| `DASHBOARD_PASSWORD`  | `versus`                  | Contraseña del dashboard de operador            | Login del operador en `/auth/verify`.                           |
| `DASHBOARD_URL`       | `http://10.0.0.1:3000`    | `https://vcoo-dashboard.vercel.app`             | URL del frontend SPA (dashboard + wizard).                      |
| `CONTROL_PLANE`       | `http://10.0.0.1:8000`    | `https://vcoo-onboarding.vercel.app`            | URL de esta API (para el agente y scripts).                     |
| `FRONTEND_URL`        | — (usa DASHBOARD_URL)     | — (usa DASHBOARD_URL)                           | Deprecated — mantiene compatibilidad. Usar `DASHBOARD_URL`.     |
| `OP_TOKEN`            | `op-test-token`           | Token para WebSocket operator                   | Autenticación del operador en WebSockets (local only).          |
| `SECRET_KEY`          | `vcoo-test-secret-key-…`  | Secreto secundario                              | Comodín para futuros usos.                                      |
| `GOOGLE_CLIENT_ID`    | —                         | Google OAuth Client ID                          | Para autenticación OAuth con Google Workspace.                  |
| `GOOGLE_CLIENT_SECRET`| —                         | Google OAuth Client Secret                      | Para autenticación OAuth con Google Workspace.                  |
| `GOOGLE_REDIRECT_URI` | —                         | `https://vcoo-onboarding.vercel.app/auth/callback` | URI de redirect OAuth.                                          |
| `TRELLO_API_KEY`      | —                         | Trello API Key                                  | Para integración con Trello.                                    |

> **Importante:** En producción, las URLs `DASHBOARD_URL` y `CONTROL_PLANE` deben referenciarse mutuamente:
> - `DASHBOARD_URL` → apunta al frontend SPA (p.ej. `https://vcoo-dashboard.vercel.app`)
> - `CONTROL_PLANE` → apunta a esta API (p.ej. `https://vcoo-onboarding.vercel.app`)
> - El frontend a su vez apunta al backend mediante `VITE_API_URL` (configurado en Vercel)

## Desarrollo Local

### Backend (Docker — recomendado)

```bash
# Reconstruir e iniciar backend + base de datos
cd infra
docker compose up -d --build backend

# La API está en http://10.0.0.1:8000
# Documentación interactiva: http://10.0.0.1:8000/docs
```

### Backend (Python directo)

```bash
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

### Frontend

```bash
cd apps/frontend
npm install
npm run dev
```

El frontend estará en `http://10.0.0.1:3000` y se conectará automáticamente al backend en `http://10.0.0.1:8000`.

### Flujo local completo

```
Frontend (10.0.0.1:3000) → API (10.0.0.1:8000) → SQLite (apps/backend/test.db)
```

## Testing

El proyecto tiene tres suites de tests: **pytest** para el backend, **Vitest** (unitarios) y **Playwright** (end-to-end) para el frontend. Todas se ejecutan automáticamente en CI en cada push/PR (ver [CI/CD](#cicd)).

### Backend (pytest)

```bash
cd apps/backend
pip install -r requirements.txt -r requirements-dev.txt

# Ejecutar toda la suite
pytest

# Con reporte de cobertura
pytest --cov=. --cov-report=term-missing
```

Los tests viven en `apps/backend/tests/` (`test_auth.py`, `test_vcoos.py`, `test_onboarding.py`, `test_agents.py`, `test_utils.py`) y usan una base de datos SQLite temporal — no requieren PostgreSQL. La configuración está en `apps/backend/pytest.ini`.

> Los scripts en `apps/backend/scripts/manual/` son pruebas manuales ad-hoc (basadas en `print`) y **no** forman parte de la suite pytest.

### Frontend — tests unitarios (Vitest)

```bash
cd apps/frontend
npm install

npm run test          # ejecuta los tests una vez
npm run test:watch    # modo watch durante el desarrollo
```

Cubren componentes (`src/components/*.test.tsx`), el cliente HTTP con su lógica de refresco de token (`src/api/apiClient.test.ts`) y el store de Zustand (`src/store/almacen.test.ts`).

### Frontend — tests end-to-end (Playwright)

```bash
cd apps/frontend
npm install
npx playwright install --with-deps chromium   # solo la primera vez

npm run test:e2e
```

Los tests E2E (`apps/frontend/e2e/`) arrancan **automáticamente** un backend FastAPI real (uvicorn + SQLite temporal) y el frontend (`vite preview`) mediante la opción `webServer` de Playwright — no hace falta levantar nada a mano, pero sí tener Python disponible. Cubren el login del operador, la creación de VCOOs y el registro de cliente en el wizard de onboarding.

## CI/CD

Cada `push` y `pull_request` sobre `main` dispara el workflow de **GitHub Actions** (`.github/workflows/ci.yml`), con tres jobs:

| Job | Qué hace |
|-----|----------|
| **Backend (pytest)** | Instala dependencias (Python 3.11) y ejecuta `pytest` con cobertura; sube `coverage.xml` como artefacto. |
| **Frontend (lint + vitest + build)** | `npm ci`, `npm run lint`, `npm run test` (Vitest) y `npm run build`. |
| **Frontend (Playwright E2E)** | Depende del job anterior. Instala Node + Python, arranca el backend real y ejecuta `npm run test:e2e`; sube el `playwright-report/` como artefacto. |

El estado del pipeline se muestra en el badge del encabezado de este README.

## Despliegue

Cada `apps/*` se despliega como un proyecto separado en Vercel, apuntando al mismo repositorio pero con distinto **Root Directory**.

### Backend (Vercel — proyecto `vcoo-onboarding`)

| Configuración     | Valor                                    |
|-------------------|------------------------------------------|
| Root Directory    | `api/` (o raíz del repo)                |
| Build Command     | `pip install -r ../apps/backend/requirements.txt` |

```bash
vercel --prod
```

**Variables de entorno en Vercel:**

| Variable            | Valor                                      |
|---------------------|--------------------------------------------|
| `POSTGRES_URL`      | URL de PostgreSQL en Supabase              |
| `MASTER_KEY`        | Secreto seguro (64+ caracteres)            |
| `DASHBOARD_PASSWORD`| Contraseña del dashboard                   |
| `DASHBOARD_URL`     | `https://vcoo-dashboard.vercel.app`        |
| `CONTROL_PLANE`     | `https://vcoo-onboarding.vercel.app`       |

### Frontend (Vercel — proyecto `vcoo-dashboard`)

| Configuración     | Valor                                    |
|-------------------|------------------------------------------|
| Root Directory    | `apps/frontend`                          |
| Build Command     | `npm run build`                          |

```bash
cd apps/frontend
vercel --prod
```

**Variables de entorno en Vercel:**

| Variable         | Valor                                      |
|------------------|--------------------------------------------|
| `VITE_API_URL`   | `https://vcoo-onboarding.vercel.app`       |

> **Relación entre despliegues:** El backend necesita saber dónde está el frontend (`DASHBOARD_URL`), y el frontend necesita saber dónde está el backend (`VITE_API_URL`). Ambos deben configurarse explícitamente en los respectivos proyectos de Vercel. El monorepo permite que cambios en `apps/backend/` solo redeployen el backend, y cambios en `apps/frontend/` solo redeployen el frontend.

## Repositorios Relacionados

- [vcoo-dashboard](https://github.com/Versus-Strategy/vcoo-dashboard) — Frontend React SPA (integrado en `apps/frontend/`)
