---
name: vcoo-core
description: "VCOO Virtual — Módulo CORE: infraestructura base, comunicación y acciones autónomas del agente"
version: 1.0.0
author: VERSUS Strategy SL
tags: [vcoo, core, infraestructura, setup, comunicacion]
---

# VCOO CORE — Infraestructura Base

## Descripción
El módulo CORE es la base obligatoria de todo VCOO Virtual. Proporciona:
- Canales de comunicación (Discord/Telegram) para recibir instrucciones y emitir resúmenes
- Acción autónoma en terminal Linux: ejecución de comandos, gestión de archivos, watchdogs
- Orquestación de subagentes para tareas complejas

## Activación
Este skill se carga automáticamente en cada sesión del agente VCOO.

## Scripts disponibles en `~/.hermes/scripts/vcoo/`

| Script | Propósito |
|--------|-----------|
| Script | Cómo ejecutarlo |
|--------|----------------|
| `vcoo-trello.py` | `~/.hermes/scripts/vcoo/vcoo-trello.py boards` |
| `vcoo-google.py` | `~/.hermes/scripts/vcoo/vcoo-google.py drive list` |
| `vcoo-email.py` | `~/.hermes/scripts/vcoo/vcoo-email.py list` |
| `vcoo-pdf.py` | `~/.hermes/scripts/vcoo/vcoo-pdf.py invoice ...` |

> **Nota:** Todos los scripts usan shebang que apunta al VCOO venv. Ejecútalos directamente (sin `python3` por delante) para que usen el entorno virtual automáticamente.

## Comandos base (ejemplos)

### Sistema
```bash
# Estado del servidor
uname -a
df -h
free -h

# Procesos del agente VCOO
ps aux | grep hermes
systemctl --user status hermes-gateway
```

### Archivos
```bash
# Leer archivos del cliente
ls ~/versus/clientes/
cat ~/versus/clientes/<cliente>/notas.md
```

### Canales
- **Discord**: Canal principal para instrucciones del equipo
- **Telegram**: Canal para comunicaciones externas del cliente
- **Ambos canales soportan**: órdenes directas, preguntas, solicitudes de informes

## Acciones autónomas típicas
1. Monitoreo periódico de Trello (cron cada 4h)
2. Revisión de email entrante (cron cada 30m)
3. Watchdogs de salud del sistema
4. Reportes programados al canal del equipo

## Notas importantes
- El CORE es el módulo base obligatorio. Todos los demás módulos (OFFICE, MAIL, PLANNER, DEVELOPER) se añaden sobre él.
- Los scripts VCOO usan Python 3.11+ con las librerías instaladas en el venv de VCOO.
- Las credenciales de cada cliente se almacenan en `/home/ubuntu/versus/` con permisos 600.
- El entorno Python aislado (venv) se documenta en: `skill_view('vcoo-core', 'references/venv-setup.md')`
