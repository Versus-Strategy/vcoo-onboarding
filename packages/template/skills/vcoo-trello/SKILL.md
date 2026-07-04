---
name: vcoo-trello
description: "VCOO Virtual — Módulo PLANNER: integración con Trello para gestión de backlog y tareas"
version: 1.0.1
author: VERSUS Strategy SL
tags: [vcoo, trello, planner, backlog, tareas]
---

# VCOO PLANNER — Integración con Trello

## Descripción
El módulo PLANNER permite al agente VCOO gestionar el backlog de tareas del cliente en Trello:
- Listar tableros, listas y tarjetas
- Crear tarjetas desde actas de reunión o instrucciones
- Mover tarjetas entre listas (cambio de estado)
- Añadir comentarios y etiquetas
- Detectar proactivamente tareas atrasadas o huérfanas

## Script
`~/.hermes/scripts/vcoo/vcoo-trello.py` (usa shebang → VCOO venv automáticamente)

## Uso

```bash
# Listar tableros
~/.hermes/scripts/vcoo/vcoo-trello.py boards

# Listar listas de un tablero
~/.hermes/scripts/vcoo/vcoo-trello.py lists <board-id>

# Listar tarjetas de un tablero
~/.hermes/scripts/vcoo/vcoo-trello.py cards <board-id>

# Atajo para VERSUS
~/.hermes/scripts/vcoo/vcoo-trello.py vs-cards

# Crear tarjeta
~/.hermes/scripts/vcoo/vcoo-trello.py create-card <list-id> "Nombre de la tarea" "Descripción opcional"

# Mover tarjeta entre listas
~/.hermes/scripts/vcoo/vcoo-trello.py move-card <card-id> <list-id-destino>

# Añadir comentario
~/.hermes/scripts/vcoo/vcoo-trello.py comment <card-id> "Texto del comentario"

# Listar etiquetas
~/.hermes/scripts/vcoo/vcoo-trello.py labels <board-id>

# Poner etiqueta
~/.hermes/scripts/vcoo/vcoo-trello.py add-label <card-id> <label-id>
```

## Atajos VERSUS
| Comando | Equivale a |
|---------|-----------|
| `vs-cards` | Lista tarjetas de VERSUS_Project_Management |
| `vs-lists` | Lista listas de VERSUS_Project_Management |
| `vs-labels` | Lista etiquetas de VERSUS_Project_Management |

## Tareas autónomas típicas
1. **Higiene de backlog**: Revisar tarjetas en "Pending" sin actividad >7 días
2. **Detección de tareas**: Leer actas de reunión en Drive y crear tarjetas automáticamente
3. **Cierre**: Al completar una tarea en filesystem, mover la tarjeta a "Done" y comentar el resultado

## Credenciales
- Archivo: `/home/ubuntu/versus/.env.trello`
- Formato: `TRELLO_API_KEY=...` / `TRELLO_TOKEN=...`
- La API Key se obtiene en https://trello.com/power-ups/admin
- El Token se genera en: https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=VCOO&key=TU_API_KEY
