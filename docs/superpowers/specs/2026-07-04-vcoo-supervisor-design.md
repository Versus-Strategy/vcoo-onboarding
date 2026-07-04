# VCOO Supervisor — Modular Agent + Monitoring + Audit

Date: 2026-07-04  
Status: Draft

## Context

Actualmente hay 3 sistemas de reporte superpuestos:

- `versusd` — watchdog bash local (no habla con el backend)
- `health-reporter.py` — Python script que envía métricas VPS al backend
- `agent_http.py` heartbeat — keepalive mínimo durante onboarding

Problemas: código duplicado, sin autenticación en health-reporter, versusd en bash frágil, sin versión tracking, sin auditoría, sin dashboard de métricas.

## Goal

Unificar todo en un **supervisor Python modular** que corre como servicio systemd en cada VPS. Añadir dashboards de monitoreo, tracking de versiones, y auditoría de acciones.

## Architecture

```
VPS del cliente                          Backend (FastAPI)
┌─────────────────────────┐              ┌─────────────────────┐
│ vcoo-supervisor (systemd) │            │                     │
│  ┌─────────────────────┐ │  POST /health│  GET /agents        │
│  │ HealthReporter (60s)│─┼─────────────→│  GET /agent/{id}    │
│  │  + métricas sistema │ │              │  GET /audit         │
│  │  + versión template │ │              │                     │
│  └─────────────────────┘ │              │  Tabla: agents      │
│  ┌─────────────────────┐ │              │  Tabla: audit_log   │
│  │ Watchdog (30s)      │ │ (local only) │                     │
│  │  + pgrep hermes     │ │              │  Dashboard React    │
│  │  + restart si caído │ │              │  /operador/monitoreo│
│  └─────────────────────┘ │              │  /operador/clientes │
│  ┌─────────────────────┐ │              │  /operador/auditoria│
│  │ Updater (7d)        │ │              │                     │
│  │  + hermes update    │ │              └─────────────────────┘
│  │  + self-update      │ │
│  └─────────────────────┘ │
│  Config: supervisor.yaml │
└─────────────────────────┘
```

## Plugins

### Plugin interface

```python
class Plugin:
    name: str
    interval: int  # segundos entre ticks

    def start(self, config: dict) -> None
    def stop(self) -> None
    def tick(self) -> None
```

### HealthReporter

- Interval: 60s
- Recoge: hostname, uptime_seconds, disk_used_pct, hermes_running, template_version
- Envía `POST /agent/{id}/health` con `Authorization: Bearer <token>`
- Payload:
  ```json
  {
    "hostname": "vcoo-test",
    "uptime_seconds": 3600,
    "hermes_running": true,
    "disk_total_gb": 19.2,
    "disk_free_gb": 15.0,
    "disk_used_pct": 21.8,
    "template_version": "1.2.0",
    "supervisor_version": "0.1.0"
  }
  ```

### Watchdog

- Interval: 30s
- `pgrep -f "hermes.*gateway"` — si no encuentra proceso, ejecuta `systemctl restart hermes-gateway`
- Si hubo restart: escribe al log y lo reporta en el próximo tick del HealthReporter
- No necesita llamar al backend directamente

### Updater

- Interval: 7 días (configurable)
- Ejecuta `hermes update` y captura resultado
- Descarga nueva versión del supervisor desde el control plane
- No necesita llamar al backend directamente (la próxima vez que haga health report, envía la nueva versión)

## Backend: nuevos endpoints

### GET /agents

Devuelve lista de agentes con métricas resumidas para el dashboard de monitoreo:

```json
[
  {
    "agent_id": "uuid",
    "vcoo_id": "uuid",
    "vcoo_name": "demo",
    "hostname": "vcoo-test",
    "status": "online",
    "last_seen": "2026-07-04T15:34:50",
    "version": "1.2.0",
    "disk_used_pct": 21.8,
    "uptime_seconds": 3600,
    "hermes_running": true
  }
]
```

No requiere auth (el dashboard environment maneja la autenticación a nivel de página).

### GET /agent/{id}/metrics

Devuelve histórico de health_payloads (últimas 24h, se guarda cada reporte del health reporter ~60s):

```json
{
  "agent_id": "uuid",
  "metrics": [
    { "timestamp": "...", "disk_used_pct": 21.8, "uptime_seconds": 3600, "hermes_running": true }
  ]
}
```

### GET /vcoo/{vcoo_id}/audit

Devuelve los últimos 20 registros de `audit_log` para un VCOO:

```json
{
  "audit_log": [
    {
      "id": "uuid",
      "action": "agent.health_reported",
      "actor_email": null,
      "metadata": {"hostname": "vcoo-test", "version": "1.2.0"},
      "created_at": "2026-07-04T15:34:50"
    }
  ]
}
```

### POST /audit (escritura desde endpoints existentes)

No es un endpoint nuevo — cada endpoint crítico escribe directamente a la tabla `audit_log`:

```python
crud.create_audit_log(db, action="vcoo.created", actor_email="admin@...", vcoo_id="...", metadata={...})
```

## Backend: nuevos modelos

### Tabla: audit_log

| Columna | Tipo | Descripción |
|---|---|---|
| id | UUID | PK |
| action | String | `vcoo.created`, `vcoo.deleted`, `token.regenerated`, `operator.login`, `client.registered`, `agent.registered` |
| actor_email | String | Email del operador/cliente que ejecutó la acción |
| vcoo_id | String | VCOO afectado (nullable) |
| metadata | JSON | Detalles adicionales (nombre, módulos, etc.) |
| created_at | DateTime | Timestamp |

### Tabla: agents (se extiende)

| Columna (nuevas) | Tipo | Descripción |
|---|---|---|
| template_version | String | Versión del template que reporta el health reporter |
| supervisor_version | String | Versión del supervisor |

## Frontend: cambios en página existente

### /operador/clientes/{id} (DetalleClientePage)

Se añaden dos secciones nuevas a la página de detalle que ya existe:

#### Sección: Métricas del VPS

Se inserta después de "Estado del Agente". Muestra los datos del `health_payload`:

```
┌────────────────────────────────────────┐
│  📊 Métricas del servidor              │
│                                        │
│  Hostname: vcoo-test                   │
│  Disco:   ████████░░░░ 78% (15/19 GB) │
│  Uptime:  3h 12m                       │
│  Hermes:  ● En ejecución               │
│  Versión template: v1.2.0              │
│  Versión supervisor: v0.1.0            │
└────────────────────────────────────────┘
```

Si no hay datos de health_payload (agente nunca reportó), se muestra "Esperando primer reporte de métricas..." en gris.

#### Sección: Auditoría (timeline)

Se inserta al final, antes de "Zona de peligro". Muestra los últimos eventos del `audit_log` para este VCOO:

```
┌────────────────────────────────────────┐
│  📋 Actividad reciente                 │
│                                        │
│  ── hoy ──                             │
│  15:34  Agente reportó métricas        │
│  15:30  Token de provision regenerado  │
│  12:03  VCOO creado por operador       │
│  ── ayer ──                            │
│  09:15  Cliente se registró            │
└────────────────────────────────────────┘
```

Endpoint: `GET /vcoo/{vcoo_id}/audit` — devuelve los últimos 20 registros de `audit_log` para ese VCOO, ordenados por fecha descendente.

#### Indicador de versión desactualizada

Si `template_version` existe y tiene más de 7 días desde el `last_seen`, se muestra un badge "📦 Actualización disponible" en la cabecera del cliente.

## Frontend: página de estadísticas globales (futuro)

Pendiente para cuando sea necesario — se añadirá `/operador/estadisticas` con gráficos globales de todos los agentes. No forma parte de este plan.

## Dashboard de monitoreo: colores de estado

| Estado | Color | Significado |
|---|---|---|
| online | verde | last_seen < 2 min |
| offline | rojo | last_seen > 2 min |
| warning | amarillo | versión desactualizada (> 7 días sin update) |
| error | rojo intenso | watchdog reportó crash recovery reciente |

## Implementation notes

- El supervisor se despliega en cada VPS como parte del template (vcoo-template)
- Reemplaza a `versusd`, `health-reporter.py` y el heartbeat de `agent_http.py`
- Config en YAML: `/etc/vcoo/supervisor.yaml`
- Logs: `/var/log/vcoo-supervisor.log` + journald
- Systemd service: `vcoo-supervisor.service`
- La BD de métricas históricas se almacena en el backend (tabla `agents` columna `health_payload` — se mantiene el último valor; para histórico se añade endpoint con muestreo)
