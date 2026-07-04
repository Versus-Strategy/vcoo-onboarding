# VCOO Dashboard

Panel de control para gestionar instancias de **VCOO** (Virtual Cognitive Orchestration Operator). Permite a los operadores crear y supervisar VCOOs, y a los clientes configurar su agente mediante un asistente de onboarding.

## Stack Tecnológico

| Capa          | Tecnología                                                                 |
|---------------|---------------------------------------------------------------------------|
| Framework     | React 18 + Vite 4                                                        |
| Lenguaje      | TypeScript 5 + TSX                                                       |
| Estilos       | Tailwind CSS 3                                                            |
| Estado global | Zustand 4                                                                 |
| Datos remotos | TanStack React Query 4                                                    |
| HTTP          | Axios                                                                     |
| Enrutamiento  | React Router DOM v6                                                       |
| Empaquetado   | Vite                                                                      |

## Arquitectura

SPA (Single Page Application) que se comunica con una API REST alojada en **Vercel** (`https://vcoo-onboarding.vercel.app`). No hay backend propio — toda la lógica de negocio, autenticación y persistencia reside en el repositorio [vcoo-onboarding](https://github.com/Versus-Strategy/vcoo-onboarding).

```
┌─────────────────┐      HTTP/JSON      ┌──────────────────┐
│  VCOO Dashboard  │ ──────────────────→ │  vcoo-onboarding  │
│  (React SPA)     │ ←────────────────── │  (FastAPI +      │
│  Vercel          │                     │   PostgreSQL)     │
└─────────────────┘                     └──────────────────┘
```

## Estructura del Proyecto

```
src/
├── api/
│   └── apiClient.ts          # Cliente Axios con interceptores de auth y refresh
├── auth/
│   └── authContext.tsx        # Contexto de autenticación (login, registro, roles)
├── components/
│   ├── AgentInstallationDisplay.tsx
│   ├── Button.tsx
│   ├── Grid.tsx
│   ├── OAuthButton.tsx
│   ├── StepIndicator.tsx
│   └── StatusBadge.tsx
├── layouts/
│   ├── ClientLayout.tsx       # Layout para rutas de cliente autenticado
│   └── OperatorLayout.tsx     # Layout para rutas de operador
├── pages/
│   ├── Login/                 # Pantalla de login de operador
│   ├── cliente/
│   │   ├── Servicios/         # Lista de servicios del cliente
│   │   └── configuracion/     # Wizard de configuración del cliente
│   │       ├── InstalacionDeAgente/
│   │       ├── ConfiguracionDeProveedor/
│   │       ├── ConfiguracionDeModulo/
│   │       └── Finalizacion/
│   ├── operador/
│   │   └── Clientes/          # CRUD de clientes para operador
│   │       ├── Clientes.tsx
│   │       ├── NuevoCliente.tsx
│   │       └── DetalleCliente.tsx
│   └── public/
│       └── SetupWizard/       # Wizard público de onboarding (requiere token)
├── query/
│   └── useConsulta.ts         # Hooks genéricos de React Query (consulta + mutations)
├── rutas/
│   └── rutasCliente.tsx       # Definición de rutas para clientes autenticados
├── store/
│   ├── almacen.ts             # Configuración de Zustand
│   ├── tipos.ts               # Tipos compartidos
│   └── useAppStore.ts         # Store de aplicación
├── App.tsx                    # Componente raíz con enrutamiento
└── main.tsx                   # Punto de entrada
```

### Descripción de cada directorio

- **`api/`** — Configuración de Axios con interceptores que añaden automáticamente el token JWT a las peticiones y gestionan el refresco automático ante 401.
- **`auth/`** — Contexto de React (`ProveedorDeAuth`) que expone `iniciarSesion`, `iniciarSesionCliente`, `registrarCliente` y `cerrarSesion`. Persiste la sesión en `localStorage` con expiración de 24h.
- **`components/`** — Componentes reutilizables (botones, indicadores de paso, badges de estado, etc.).
- **`layouts/`** — Layouts con navegación y estructura para cada rol.
- **`pages/`** — Páginas organizadas por rol: `public/` (accesible sin auth), `cliente/` (requiere rol cliente), `operador/` (requiere rol operador).
- **`query/`** — Hooks wrapper sobre `@tanstack/react-query` con tipado genérico.
- **`routes/`** — Definición centralizada de rutas de cliente.
- **`store/`** — Estado global con Zustand para datos de UI que no vienen del backend.

## Rutas Disponibles

| Ruta                          | Acceso     | Descripción                                      |
|-------------------------------|------------|--------------------------------------------------|
| `/login`                      | Público    | Login de operador con email + contraseña         |
| `/servicios`                  | Cliente    | Lista de servicios VCOO del cliente              |
| `/setup/:token`               | Público    | Wizard público de onboarding con registro        |
| `/configuracion/*`            | Cliente    | Wizard de configuración (instalar, proveedor, módulos, finalizar) |
| `/operador/clientes`          | Operador   | Lista de clientes                                |
| `/operador/clientes/nuevo`    | Operador   | Crear nuevo cliente con VCOO                     |
| `/operador/clientes/:id`      | Operador   | Detalle de un cliente específico                 |

## Configuración para Desarrollo Local

```bash
git clone https://github.com/Versus-Strategy/vcoo-dashboard
cd vcoo-dashboard
npm install
npm run dev
```

El servidor de desarrollo se inicia en `http://localhost:5173`.

### Variables de Entorno

| Variable         | Valor por defecto                                  | Descripción                        |
|------------------|----------------------------------------------------|------------------------------------|
| `VITE_API_URL`   | `https://vcoo-onboarding.vercel.app`               | URL base de la API backend         |

Copia el archivo `.env.example` a `.env` si existe, o crea uno:

```bash
echo "VITE_API_URL=https://vcoo-onboarding.vercel.app" > .env
```

## Autenticación

El sistema maneja **dos roles** mediante JWT:

### Operador
- Inicia sesión en `/login` con email y contraseña.
- La contraseña se valida contra `DASHBOARD_PASSWORD` en el backend (por defecto `versus` en desarrollo).
- Obtiene un JWT con `role: operador` que expira en 24h.
- Puede crear VCOOs, generar tokens de provision, y supervisar clientes.

### Cliente
- Llega al sistema mediante un **token de provision** en la URL (`/setup/:token`).
- En el wizard público, el cliente **se registra** por primera vez (nombre, email, contraseña) o **inicia sesión** si ya tiene cuenta.
- El registro enlaza automáticamente al cliente con el VCOO asociado al token.
- Obtiene un JWT con `role: cliente` que expira en 30 días.
- Una vez autenticado, accede a sus servicios y al wizard de configuración.

## Despliegue

El proyecto está preparado para desplegarse en **Vercel**.

```bash
npm run build
vercel --prod
```

El archivo `vercel.json` contiene las reglas de reescritura necesarias para SPA routing:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

## Repositorios Relacionados

- [vcoo-onboarding](https://github.com/Versus-Strategy/vcoo-onboarding) — Backend FastAPI con PostgreSQL, autenticación JWT, endpoints de onboarding y registro de agentes.
