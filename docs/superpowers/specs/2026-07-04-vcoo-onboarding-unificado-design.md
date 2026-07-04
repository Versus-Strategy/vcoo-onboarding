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
| 3. Conectar Módulos | Solo si contratados | Cada módulo contratado se muestra como sub-paso. OAuth en browser. Backend guarda credenciales. |
| 4. Finalización | Siempre | Resumen de configuración. Enlace al dashboard /servicios. |

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

**Nuevo endpoint — Long Polling:**
```
GET /agent/{id}/poll?timeout=25
Headers: Authorization: Bearer <agent_token>

Respuesta inmediata si hay comandos:
  200 { commands: [{ cmd_id, command, payload }], step, progress }

Respuesta diferida si no hay comandos:
  Mantiene conexión hasta 25s
  Si aparece un comando → responde inmediatamente
  Si timeout → 204 No Content (agente reintenta)
```

**Endpoints existentes (sin cambios):**
- `POST /setup/{identifier}/verify` — verificar instalación
- `GET /setup/{identifier}/auth-url?service=xxx` — URL OAuth
- `POST /vcoo/{id}/set-provider` — encolar comando set-provider
- `POST /register` — registro del agente
- `POST /agent/{id}/result` — reportar resultado comando
- `POST /agent/{id}/health` — health report

### 2.4 Agente (versusd)

versusd se convierte en el agente permanente. Se reescribe en Python (reemplazando el bash actual) usando la arquitectura de plugins del vcoo-supervisor.

**Plugins de versusd:**

| Plugin | Loop | Función |
|--------|------|---------|
| `command_worker` | GET /agent/{id}/poll?timeout=25 | Long polling, ejecuta comandos, reporta resultados |
| `health_reporter` | POST /agent/{id}/health (60s) | Reporta métricas del VPS |
| `watchdog` | pgrep hermes (30s) | Reinicia Hermes si no responde |
| `updater` | hermes update (7 días) | Actualiza Hermes automáticamente |

**Comandos que ejecuta command_worker:**
- `verify-bootstrap` → verifica que Hermes esté instalado
- `set-provider` → `hermes auth add <provider> api-key --key <decrypted_key>`
- `save-creds` → guarda tokens OAuth en `~/.hermes/`
- `finalize` → marca onboarding como completo (no se autodestruye)

**Importante:** versusd NUNCA se autodestruye. Después del onboarding, sigue vivo haciendo health reports + watchdog.

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

| Backend ID | Frontend actual | Frontend nuevo | Descripción |
|-----------|-----------------|----------------|-------------|
| core | — | — | Instalación base (siempre incluido) |
| google-drive | office | Google Drive | Acceso a Drive, Docs y Calendar |
| gmail | mail | Gmail | Correo electrónico inteligente |
| developer | developer | GitHub + Vercel + Supabase | Repositorios, deploys y base de datos |
| planner | planner | *(pospuesto)* | Trello se implementa más adelante |

### 2.7 Comunicación: Long Polling

```
VPS:  GET /agent/{id}/poll?timeout=25
CP:   ── espera hasta 25s ──> comando disponible → 200
      ── espera 25s ──> sin comandos → 204
VPS:  si 200: ejecuta comando → POST /agent/{id}/result
      si 204: repite long poll inmediatamente
```

**Ventajas:**
- Latencia ~ms (comando llega casi inmediatamente después de encolado)
- Pasa cualquier firewall/NAT (es HTTP normal)
- Funciona con Vercel serverless (conexiones de hasta 60s en plan pro)
- Sin infraestructura extra (no WebSocket, no Supabase Realtime)

## 3. Features faltantes detectadas

1. **Flujo de onboarding unificado** — Un solo wizard en vez de dos flujos separados
2. **One-liner con token real en vista cliente** — El cliente ve su comando con su token
3. **Paso a paso guiado** — Copiar → pegar → verificar, con bloqueo/desbloqueo
4. **OAuth en el navegador** — No simulado, flujo real con redirect
5. **Nombres de módulos representativos** — google-drive, gmail, developer
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
