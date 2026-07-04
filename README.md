# VCOO Onboarding API

API REST que orquesta el ciclo de vida completo de las instancias **VCOO** (Virtual Cognitive Orchestration Operator): provisionamiento, autenticación, onboarding de clientes, registro de agentes y ejecución de comandos de verificación.

## Stack Tecnológico

| Capa              | Tecnología                                     |
|-------------------|------------------------------------------------|
| Framework web     | FastAPI (Python 3.11+)                         |
| ORM               | SQLAlchemy 2.0                                 |
| Base de datos     | PostgreSQL (Supabase)                          |
| Autenticación     | JWT (PyJWT) + hashlib (password hashing)       |
| Despliegue        | Vercel (serverless functions via `api/index.py`) |
| Cliente HTTP      | httpx + requests (agente)                      |
| WebSockets        | FastAPI WebSocket + bridge (entorno local)     |

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

┌─────────────────┐  HTTP Polling     ┌──────────────────────┐
│  VCOO Agent      │ ────────────────→│  VCOO Onboarding API  │
│  (VPS del        │←─────────────────│  (register, poll,     │
│   cliente)       │                  │   result, heartbeat)  │
└─────────────────┘                  └──────────────────────┘
```

La aplicación se despliega como **funciones serverless** en Vercel. El módulo `backend/` contiene la aplicación FastAPI completa, mientras que `api/index.py` es el punto de entrada para Vercel. En entorno local, los WebSockets están disponibles para comunicación en tiempo real agente-UI.

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

| Método | Ruta      | Descripción                                         |
|--------|-----------|-----------------------------------------------------|
| GET    | `/health` | Healthcheck con información de conexión a BD.       |

## Esquema de Base de Datos

La base de datos se ejecuta en **Supabase (PostgreSQL)**. Las tablas principales son:

| Tabla              | Descripción                                                    |
|--------------------|----------------------------------------------------------------|
| `vcoos`            | Instancias VCOO (id, name, status, created_at).                |
| `provision_tokens` | Tokens de provision para vincular clientes (token, vcoo_id, expires_at, used). |
| `clients`          | Clientes registrados (email, password_hash, name, vcoo_id).    |
| `agents`           | Agentes VCOO registrados (vcoo_id, info, status, last_seen, health_payload). |
| `commands`         | Comandos encolados para los agentes (command, status, step, result, ttl). |
| `command_logs`     | Logs chunked de ejecución de comandos (command_id, stream, chunk). |
| `onboarding_state` | Estado del wizard de onboarding por VCOO (step, status, modules, completed, errors, retry_count). |

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

| Variable              | Local (backend/.env)     | Producción (Vercel)                             | Descripción                                                     |
|-----------------------|--------------------------|-------------------------------------------------|-----------------------------------------------------------------|
| `POSTGRES_URL`        | `sqlite:///./test.db`    | PostgreSQL URL (Supabase)                       | URL de conexión a base de datos.                                |
| `MASTER_KEY`          | `vcoo-test-master-key-…` | Secreto seguro (64+ chars)                      | Clave HMAC para firmar/verificar todos los JWT.                 |
| `DASHBOARD_PASSWORD`  | `versus`                 | Contraseña del dashboard de operador            | Login del operador en `/auth/verify`.                           |
| `DASHBOARD_URL`       | `http://localhost:5173`  | `https://vcoo-dashboard.vercel.app`             | URL del frontend SPA (dashboard + wizard).                      |
| `CONTROL_PLANE`       | `http://localhost:8000`  | `https://vcoo-onboarding.vercel.app`            | URL de esta API (para el agente y scripts).                     |
| `FRONTEND_URL`        | — (usa DASHBOARD_URL)    | — (usa DASHBOARD_URL)                           | Deprecated — mantiene compatibilidad. Usar `DASHBOARD_URL`.     |
| `OP_TOKEN`            | `op-test-token`          | Token para WebSocket operator                   | Autenticación del operador en WebSockets (local only).          |
| `SECRET_KEY`          | `vcoo-test-secret-key-…` | Secreto secundario                              | Comodín para futuros usos.                                      |
| `GOOGLE_CLIENT_ID`    | —                        | Google OAuth Client ID                          | Para autenticación OAuth con Google Workspace.                  |
| `GOOGLE_CLIENT_SECRET`| —                        | Google OAuth Client Secret                      | Para autenticación OAuth con Google Workspace.                  |
| `GOOGLE_REDIRECT_URI` | —                        | `https://vcoo-onboarding.vercel.app/auth/callback` | URI de redirect OAuth.                                          |
| `TRELLO_API_KEY`      | —                        | Trello API Key                                  | Para integración con Trello.                                    |

> **Importante:** En producción, las URLs `DASHBOARD_URL` y `CONTROL_PLANE` deben referenciarse mutuamente:
> - `DASHBOARD_URL` → apunta al frontend SPA (p.ej. `https://vcoo-dashboard.vercel.app`)
> - `CONTROL_PLANE` → apunta a esta API (p.ej. `https://vcoo-onboarding.vercel.app`)
> - El frontend a su vez apunta al backend mediante `VITE_API_URL` (configurado en Vercel)

## Desarrollo Local

### Backend (Docker — recomendado)

```bash
# Reconstruir e iniciar backend + base de datos
docker compose up -d --build backend

# La API está en http://localhost:8000
# Documentación interactiva: http://localhost:8000/docs
```

### Backend (Python directo)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (submódulo)

El frontend es una SPA React (Vite + TypeScript) en `frontend/`, que es un **submódulo** de [`vcoo-dashboard`](https://github.com/Versus-Strategy/vcoo-dashboard).

```bash
# Primera vez: inicializar submódulo
git submodule update --init --recursive

# Desarrollo
cd frontend
npm install
npm run dev
```

El frontend estará en `http://10.0.0.1:3000` y se conectará automáticamente al backend en `http://10.0.0.1:8000`.

#### Actualizar el submódulo

```bash
git submodule update --remote frontend
```

#### Clonar todo desde cero

```bash
git clone --recurse-submodules git@github.com:Versus-Strategy/vcoo-onboarding.git
```

### Flujo local completo

```
Frontend (10.0.0.1:3000) → API (10.0.0.1:8000) → SQLite (./test.db)
```

Las variables en `backend/.env` ya están preconfiguradas para desarrollo local:
- `DASHBOARD_URL=http://10.0.0.1:3000`
- `CONTROL_PLANE=http://10.0.0.1:8000`

## Despliegue

### Backend (Vercel)

```bash
vercel --prod
```

El punto de entrada serverless es `api/[...slug].py`. Vercel enruta todas las rutas mediante la configuración en `vercel.json`. Las rutas de WebSocket no están disponibles en serverless (solo local).

**Configurar variables de entorno en Vercel:**

| Variable            | Valor                                      |
|---------------------|--------------------------------------------|
| `POSTGRES_URL`      | URL de PostgreSQL en Supabase              |
| `MASTER_KEY`        | Secreto seguro (64+ caracteres)            |
| `DASHBOARD_PASSWORD`| Contraseña del dashboard                   |
| `DASHBOARD_URL`     | `https://vcoo-dashboard.vercel.app`        |
| `CONTROL_PLANE`     | `https://vcoo-onboarding.vercel.app`       |

### Frontend (Vercel — proyecto separado)

El frontend se despliega como proyecto independiente en Vercel.

```bash
cd frontend
vercel --prod
```

**Configurar variable de entorno en el frontend:**

| Variable         | Valor                                      |
|------------------|--------------------------------------------|
| `VITE_API_URL`   | `https://vcoo-onboarding.vercel.app`       |

> **Relación entre despliegues:** El backend necesita saber dónde está el frontend (`DASHBOARD_URL`), y el frontend necesita saber dónde está el backend (`VITE_API_URL`). Ambos deben configurarse explícitamente en los respectivos proyectos de Vercel — no hay defaults fiables en producción.

## Submódulo

`frontend/` es un submódulo que apunta a [`vcoo-dashboard`](https://github.com/Versus-Strategy/vcoo-dashboard). Para más detalles sobre el frontend, consulta su [README](frontend/README.md).
