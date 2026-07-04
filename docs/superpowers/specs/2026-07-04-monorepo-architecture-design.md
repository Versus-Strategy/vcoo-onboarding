# Monorepo Architecture — VCOO Onboarding

Date: 2026-07-04  
Status: Draft

## Context

El proyecto VCOO tiene 3 repositorios separados que evolucionan juntos pero están aislados:

- `vcoo-onboarding` — backend FastAPI + infraestructura
- `vcoo-dashboard` — frontend React SPA
- `vcoo-template` — plantillas de provisioning para el agente

Se intentó usar git submodules (`frontend/` apuntando a `vcoo-dashboard`), pero la experiencia de desarrollo se siente fragmentada: hay que acordarse de `git submodule update`, los cambios cruzados (frontend + backend) requieren commits en dos repos, y tener la plantilla separada añade más dispersión.

## Goal

Unificar todo en un **monorepo** con una estructura limpia donde cada aplicación se despliega independientemente, pero todo vive en un solo repositorio. Sin submodules, sin repos múltiples.

## Directory Structure

```
vcoo-onboarding/
├── apps/
│   ├── backend/            ← FastAPI (actual backend/)
│   └── frontend/           ← vcoo-dashboard (React SPA)
├── packages/
│   ├── agent/              ← scripts del agente (agent_http.py, install.sh, health-reporter.py)
│   ├── vsd/                ← watchdog systemd (vsctl, servicios, onboard.sh)
│   └── template/           ← vcoo-template (plantillas de provisioning)
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── vercel.json         ← catch-all routing para backend
│   └── supabase/
│       └── supabase.sql
├── api/
│   └── [...slug].py        ← entrypoint serverless Vercel (se queda aquí, importa backend)
├── docs/
│   └── superpowers/
├── .env.production
├── .gitignore
└── README.md
```

### Criterios de la estructura

- `apps/` — aplicaciones desplegables independientemente. Cada una tiene su propio `package.json`/`requirements.txt`, su configuración de build, y se despliega por separado en Vercel.
- `packages/` — código compartido o utilidades que no se despliegan solas (scripts del agente, watchdog, plantillas).
- `infra/` — configuración de infraestructura compartida (Docker, Vercel, base de datos).
- `api/` — el entrypoint serverless de Vercel se queda a nivel raíz porque Vercel lo espera en `api/[...slug].py`.

## Deploys en Vercel

Cada `apps/*` se despliega como un proyecto separado en Vercel apuntando al mismo repo pero con distinto **Root Directory**:

| Proyecto Vercel | Root Directory | Build Command | Output |
|---|---|---|---|
| `vcoo-onboarding` | `api/` (o repo root) | `pip install -r apps/backend/requirements.txt` | Python serverless |
| `vcoo-dashboard` | `apps/frontend` | `npm run build` | Static SPA |

### Ignorar builds según qué cambió

Vercel soporta ignorar builds con [`vercel.json` > `github.ignoredBuildStep`](https://vercel.com/docs/projects/overview#ignored-build-step). Se puede configurar para que:

- El backend solo redeploye si cambia `apps/backend/**` o `api/**`
- El frontend solo redeploye si cambia `apps/frontend/**`

## Migration Plan

### 1. Remove submodule

```
git submodule deinit frontend
git rm frontend
rm -rf .gitmodules
```

### 2. Create new structure

```
mkdir -p apps packages infra

# Move existing code
mv backend apps/backend
mv agent packages/agent
mv vsd packages/vsd
mv docker-compose.yml infra/
mv Dockerfile.backend infra/
mv vercel.json infra/
mv supabase/ infra/
```

### 3. Integrate vcoo-dashboard

```
cp -r /home/ubuntu/vcoo-dashboard/* apps/frontend/
```

Ajustar referencias de path si es necesario (el API client usa `import.meta.env.VITE_API_URL`, no paths relativos, así que no debería necesitar cambios).

### 4. Integrate vcoo-template

```
cp -r /home/ubuntu/versus/vcoo-template/* packages/template/
```

### 5. Update vercel.json for backend

El backend necesita que `vercel.json` esté en la raíz del proyecto para el catch-all routing. Se queda en `infra/vercel.json` como referencia, y el activo en la raíz se mantiene o se actualiza para que funcione con la nueva estructura.

### 6. Update Docker paths

`Dockerfile.backend` y `docker-compose.yml` actualizan sus rutas para reflejar que el backend está en `apps/backend/`.

### 7. Update .gitignore

Consolidar `.gitignore` del root para cubrir todos los `apps/*` y `packages/*`.

## Path Adjustments

### api/[...slug].py import path

Actualmente importa `from backend.main import app`. Con el backend en `apps/backend/`, hay que ajustar el sys.path:

```python
# Antes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.main import app

# Después
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apps'))
from backend.main import app
```

### Dockerfile.backend

Actualmente copia `backend/requirements.txt` y `backend/`. Pasa a copiar `apps/backend/requirements.txt` y `apps/backend/`:

```dockerfile
# Antes
COPY backend/requirements.txt /app/requirements.txt
COPY backend /app

# Después
COPY apps/backend/requirements.txt /app/requirements.txt
COPY apps/backend /app
```

### docker-compose.yml

El `build.context` y Dockerfile path se actualizan:

```yaml
# Antes
build:
  context: .
  dockerfile: Dockerfile.backend

# Después
build:
  context: ..
  dockerfile: infra/Dockerfile.backend
```

Y el `env_file` apunta a la nueva ruta de `.env` (que se queda en `apps/backend/.env`):

```yaml
env_file:
  - apps/backend/.env
```

## Unchanged

- `api/[...slug].py` — se queda en raíz (solo cambia el import path)
- `backend/.env` — se mueve a `apps/backend/.env`
- `.env.production` — se queda en raíz
- `README.md` — se actualiza con la nueva estructura
