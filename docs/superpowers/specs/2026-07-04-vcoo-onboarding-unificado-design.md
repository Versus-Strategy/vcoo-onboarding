# VCOO Onboarding Unificado — Design Spec

## 1. Problema

### 1.1 Frontend
- Dos flujos de onboarding separados: SetupWizard público (`/setup/:token`, dark theme) y páginas de configuración de cliente autenticado (`/configuracion/*`, light theme inconsistente)
- El flujo autenticado muestra `***` en vez del token real
- Los pasos son simulados (setTimeout), no conectados al backend real
- El estilo del cliente no coincide con el dashboard del operador

### 1.2 Agente
- `agent_http.py` es transitorio (se autodestruye al finalizar)
- `versusd` (watchdog bash) está separado del agente de onboarding
- No hay un proceso permanente que sincronice estado VPS ↔ dashboard
- Dos componentes hacen lo mismo (polling HTTP) con diferentes ciclos de vida

### 1.3 Nombres de módulos
- `office` → no representa que es Google Drive
- `mail` → no representa que es Gmail
- `planner` → Trello, pospuesto

## 2. Arquitectura Propuesta

### 2.1 Visión general

```
NAVEGADOR (dashboard cliente/operador)     CONTROL PLANE (FastAPI)     VPS (versusd)
│                                                │                       │
│ 1. Login → ve onboarding wizard                │                       │
│ 2. Copia one-liner                             │                       │
│    └── curl ... | PROVISION_TOKEN=X bash ──────┼─────────────────────>│
│                                                │                       │
│                                                │   3. install_vsd.sh  │
│                                                │      instala versusd │
│                                                │      + Hermes + tmpl │
│                                                │                       │
│                                                │<── POST /register ───│
│                                                │── agent_id ──────────>│
│                                                │                       │
│ 4. Dashboard detecta agente ──────────────────>│                       │
│    "✓ Agente instalado"                        │                       │
│                                                │                       │
│ 5. Cliente configura Proveedor IA              │                       │
│    [Anthropic] [API Key: sk-...]               │                       │
│    └── POST /vcoo/{id}/set-provider ──────────>│                       │
│                                                │ 6. Long poll:         │
│                                                │<── GET /agent/poll ───│
│                                                │── set-provider ──────>│
│                                                │    hermes auth add    │
│                                                │<── POST /result ─────│
│ 7. Dashboard: "✓ Proveedor configurado" <─────│                       │
│                                                │                       │
│ 8. Cliente conecta Google Drive                │                       │
│    [OAuth flow en browser]                     │                       │
│    └── Google callback ───────────────────────>│                       │
│                                                │ 9. Long poll:         │
│                                                │<── GET /agent/poll ───│
│                                                │── save-creds ────────>│
│                                                │    guarda ~/.hermes/  │
│                                                │<── POST /result ─────│
│10. Dashboard: "✓ Google Drive conectado" <─────│                       │
│                                                │                       │
│    ... (continúa para cada módulo contratado)   │                       │
│                                                │                       │
│11. Dashboard: "✓ Onboarding completado"        │                       │
│    → Redirige a /servicios                     │                       │
│                                                │                       │
│    A PARTIR DE AHORA:                          │                       │
│    (versusd SIGUE VIVO)                        │                       │
│    Cada 60s:                                   │<── POST /health ─────│
│    Cada 5s:                                    │<── GET /agent/poll ───│
│    Watchdog: cada 30s pgrep hermes             │  (interno, sin HTTP)  │
```

### 2.2 Frontend: Wizard unificado

**Ruta:** `/setup/:token` → AuthForm → WizardUnificado (4 pasos)

**Estilo:** Tema claro, mismo que dashboard del operador
- `bg-gray-50` fondo de página
- Tarjetas `bg-white rounded-lg shadow`
- `border-gray-200` bordes
- `text-gray-900` textos
- `text-primary-600` acentos

**Pasos del wizard:**

| Paso | Visible cuando | Acción |
|------|---------------|--------|
| 1. Instalar Agente | Siempre | Mostrar one-liner con token real. Copiar → Verificar. Backend llama a POST /setup/{id}/verify |
| 2. Configurar Proveedor IA | Siempre | Seleccionar proveedor (Anthropic, OpenAI, etc.). Ingresar API Key. Backend envía comando set-provider al VPS. |
| 3. Conectar Módulos | Solo si contratados | Cada módulo contratado se muestra como tarjeta con su nombre y descripción. Dentro de cada tarjeta, el botón OAuth correspondiente ("Iniciar sesión con Google", "Conectar GitHub", etc.). Todo el OAuth ocurre en el navegador. |
| 4. Finalización | Siempre | Resumen de configuración. Enlace al dashboard /servicios. |

**Paso 3 en detalle — cada módulo contratado se renderiza como:**

```
┌──────────────────────────────────────────────┐
│  Google Drive                                │
│  Acceso a Drive, Docs y Calendar             │
│  [Iniciar sesión con Google]  ✓ Conectado   │
├──────────────────────────────────────────────┤
│  Gmail                                       │
│  Correo electrónico inteligente              │
│  [Iniciar sesión con Google]  ✓ Conectado   │
├──────────────────────────────────────────────┤
│  Planner                                     │
│  Calendario y planificación                  │
│  [Iniciar sesión con Google]  [Conectar]    │
├──────────────────────────────────────────────┤
│  GitHub + Vercel + Supabase                  │
│  Repositorios, deploys y base de datos       │
│  [Conectar GitHub] [Conectar Vercel] ...    │
└──────────────────────────────────────────────┘
```

**Sub-pasos del Paso 1 (Instalar Agente):**

```
Sub-paso 1: Copiar one-liner
  [curl -sSL ... | PROVISION_TOKEN=xxx bash -]
  [Copiar al portapapeles]  →  se marca ✓

Sub-paso 2: Ejecutar en VPS
  "Pega el comando en la terminal de tu servidor"
  [Ya lo ejecuté → Verificar]

Sub-paso 3: Verificación
  Polling cada 3s a GET /setup/{id}/state
  Cuando agent_online = true → "✓ Agente detectado"
  Botón "Continuar" desbloqueado
```

### 2.3 Backend

**Nuevo endpoint — Tick unificado (reemplaza poll + health):**
```
POST /agent/{id}/tick
Headers: Authorization: Bearer <agent_token>
Body: {
  health: {
    hostname: "vps-01",
    cpu_pct: 23,
    memory_pct: 45,
    disk_pct: 67,
    hermes_running: true,
    template_version: "v1.2"
  },
  last_command_id: "cmd_abc123"  // último comando procesado (ACK)
}

Response: {
  commands: [{ cmd_id, command, payload, step }],
  tick_interval: 5,  // cuántos segundos hasta el próximo tick
  step: "bootstrap",
  progress: { done: 1, total: 4 }
}
```

**Endpoints existentes (sin cambios):**
- `POST /setup/{identifier}/verify` — verificar instalación
- `GET /setup/{identifier}/auth-url?service=xxx` — URL OAuth
- `POST /vcoo/{id}/set-provider` — encolar comando set-provider
- `POST /register` — registro del agente

### 2.4 Agente (versusd)

versusd se convierte en el agente permanente. Se reescribe en Python (reemplazando el bash actual) usando la arquitectura de plugins del vcoo-supervisor.

**Plugins de versusd:**

| Plugin | Loop | Función |
|--------|------|---------|
| `tick` | POST /agent/{id}/tick (cada N seg) | **Único loop.** Envía health report + recibe comandos en una sola request |
| `watchdog` | pgrep hermes (30s) | Reinicia Hermes si no responde |
| `updater` | hermes update (7 días) | Actualiza Hermes automáticamente |

**Plugin `tick` — el loop unificado:**

```
POST /agent/{id}/tick
Body: {
  health: { cpu, memory, hostname, disk, hermes_running, template_version },
  last_command_id: "abc"   // ID del último comando recibido (ACK implícito)
}

Response: {
  commands: [...],          // comandos pendientes (vacío si no hay)
  tick_interval: 5,         // cuántos segundos hasta el próximo tick (dinámico)
  status: "ok"
}
```

**Frecuencia dinámica del tick:**
- **Durante onboarding:** `tick_interval = 5s` (polling activo, comandos frecuentes)
- **Post-onboarding:** `tick_interval = 60s` (solo health report, sin comandos)
- **Nuevo módulo contratado:** el backend encola comandos, el próximo tick los entrega, y responde con `tick_interval = 5s` para reactivar el polling rápido
- **Nunca se detiene:** versusd SIEMPRE hace tick, pero a menor frecuencia cuando no hay trabajo

```
versusd loop:
  while true:
    response = POST /agent/{id}/tick (health + last_command_id)
    if response.commands:
      for cmd in response.commands:
        ejecutar(cmd)
    sleep(response.tick_interval)
```

**Ventajas del tick unificado:**
- 1 request en vez de 2 (health + poll) por ciclo
- El backend correlaciona estado del VPS + avance de comandos en el mismo momento
- La frecuencia se adapta automáticamente: activo cuando hay trabajo, reposo cuando no
- Sin WebSocket, sin complejidad extra

**Comandos que ejecuta versusd:**
- `verify-bootstrap` → verifica que Hermes esté instalado
- `set-provider` → `hermes auth add <provider> api-key --key <decrypted_key>`
- `save-creds` → guarda tokens OAuth en `~/.hermes/`
- `finalize` → marca onboarding como completo (versusd sigue vivo)

**Importante:** versusd NUNCA se autodestruye. Después del onboarding, sigue vivo haciendo ticks cada 60s + watchdog.

### 2.5 One-liner

El one-liner modifica el instalador para que instale versusd en vez de agent_http.py:

```bash
curl -sSL https://vcoo.dev/install.sh | PROVISION_TOKEN=xxx bash -
```

Esto descarga `install_vsd.sh` que:
1. Instala versusd (servicio systemd permanente)
2. versusd arranca y se registra con el control plane
3. versusd instala Hermes + templates como parte del onboarding

### 2.6 Renombramiento de módulos

Los scripts del backend y los IDs internos mantienen nombres **genéricos** para soportar múltiples proveedores futuros. Solo cambia la etiqueta visible en el frontend.

| Backend ID (script) | Frontend (etiqueta visible) | OAuth | Descripción |
|--------------------|---------------------------|-------|-------------|
| core | — | — | Instalación base (siempre incluido) |
| office | Google Drive | Google OAuth | Acceso a Drive, Docs |
| mail | Gmail | Google OAuth | Correo electrónico inteligente |
| planner | Planner | Google OAuth | Calendario y planificación (Calendar ahora, Trello futuro) |
| developer | GitHub + Vercel + Supabase | GitHub OAuth + Vercel OAuth + Supabase OAuth | Repositorios, deploys y base de datos |

**Regla:** El backend siempre usa `office`, `mail`, `planner`, `developer`. El frontend mapea a nombres descriptivos que el cliente entiende. Si en el futuro `office` soporta también Microsoft 365, el script `vcoo-office.py` sigue siendo válido.

### 2.7 Comunicación: Tick unificado

```
versusd loop:
  while true:
    response = POST /agent/{id}/tick (health + last_command_id)
    if response.commands:
      for cmd in response.commands:
        ejecutar(cmd)
    sleep(response.tick_interval)  // 5s si hay trabajo, 60s si no
```

**Frecuencia dinámica:**
- Comandos pendientes → `tick_interval: 5` (polling activo)
- Sin comandos → `tick_interval: 60` (solo health report)
- Nuevo módulo contratado → backend encola comando, próximo tick lo entrega con `tick_interval: 5`

**Ventajas:**
- 1 request por ciclo (health + comando ACK + poll) en vez de 2
- Estado del VPS y avance de comandos siempre correlacionados
- Pasa cualquier firewall/NAT (HTTP simple)
- Funciona con Vercel serverless (request/respuesta corta)
- Sin WebSocket, sin infraestructura extra

## 3. Features faltantes detectadas

1. **Flujo de onboarding unificado** — Un solo wizard en vez de dos flujos separados
2. **One-liner con token real en vista cliente** — El cliente ve su comando con su token
3. **Paso a paso guiado** — Copiar → pegar → verificar, con bloqueo/desbloqueo
4. **OAuth en el navegador** — No simulado, flujo real con redirect
5. **Nombres de módulos representativos en frontend** — backend mantiene IDs genéricos (office, mail, developer), frontend muestra etiquetas descriptivas (Google Drive, Gmail, GitHub + Vercel + Supabase)
6. **Agente permanente** — versusd nunca se autodestruye, siempre sincronizado
7. **Long polling** — Comandos llegan en tiempo real al VPS
8. **Estilo consistente** — Mismo tema claro en operador y cliente onboarding
9. **Módulos solo contratados** — El cliente ve solo lo que pagó
10. **Proveedor IA configurable desde onboarding** — API key se envía cifrada al VPS
11. **Estado sincronizado** — El dashboard siempre refleja el estado real del VPS

## 4. Archivos a modificar/crear

### Frontend
| Archivo | Acción |
|---------|--------|
| `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx` | Refactorizar: tema claro, paso a paso guiado, sub-pasos |
| `apps/frontend/src/pages/cliente/configuracion/*` | Eliminar o redirigir al wizard unificado |
| `apps/frontend/src/App.tsx` | Ajustar routing si es necesario |
| `apps/frontend/src/components/StepIndicator.tsx` | Mejorar con estados bloqueado/desbloqueado |

### Backend
| Archivo | Acción |
|---------|--------|
| `apps/backend/main.py` | Agregar endpoint GET /agent/{id}/poll con long polling |
| `apps/backend/onboarding.py` | Actualizar mapeo de módulos (office→google-drive, mail→gmail) |
| `apps/backend/crud.py` | Agregar función get_pending_commands para long polling |

### Agente
| Archivo | Acción |
|---------|--------|
| `packages/vsd/versusd.sh` | Reemplazar con versión Python (o mantener bash + agregar polling) |
| `packages/vsd/versusd.service` | Actualizar para el nuevo versusd |
| `packages/vsd/install_vsd.sh` | Actualizar one-liner |
| `packages/vcoo-supervisor/plugins/` | Agregar plugin command_worker para long polling |
| `apps/backend/agent_http.py` | Eliminar (reemplazado por versusd) |
| `packages/agent/agent_http.py` | Eliminar |
| `packages/agent/install.sh` | Actualizar para que instale versusd en vez de agent_http.py |
