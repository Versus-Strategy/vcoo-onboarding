---
name: vcoo-google-workspace
description: "VCOO Virtual — Módulo OFFICE: Google Workspace (Drive, Docs, Sheets, Calendar)"
version: 1.0.1
author: VERSUS Strategy SL
tags: [vcoo, google, workspace, drive, docs, sheets, calendar]
---

# VCOO OFFICE — Google Workspace

## Descripción
El módulo OFFICE automatiza la suite ofimática de Google Workspace:
- **Drive**: Organización de carpetas por cliente, búsqueda indexada
- **Docs**: Creación automática de informes y actas
- **Sheets**: CRM ágil, hojas de control, actualización de datos
- **Calendar**: Consulta de eventos próximos

## Script
`~/.hermes/scripts/vcoo/vcoo-google.py` (usa shebang → VCOO venv automáticamente)

## Token de Google
- Archivo: `~/.hermes/google_token.json`
- Scopes activos: drive, documents, spreadsheets, gmail, calendar, contacts
- El token se refresca automáticamente al expirar
- Se configura mediante OAuth 2.0 con una Service Account de Google Cloud

## Uso

### Google Drive

```bash
# Listar archivos
~/.hermes/scripts/vcoo/vcoo-google.py drive list

# Buscar archivos por nombre
~/.hermes/scripts/vcoo/vcoo-google.py drive search "presupuesto"

# Crear carpeta
~/.hermes/scripts/vcoo/vcoo-google.py drive create-folder "Clientes/Cliente Nuevo"
```

### Google Docs

```bash
# Crear documento
~/.hermes/scripts/vcoo/vcoo-google.py docs create "Acta reunión 2026-06-22"

# Ver contenido
~/.hermes/scripts/vcoo/vcoo-google.py docs view <doc-id>

# Añadir texto al final
~/.hermes/scripts/vcoo/vcoo-google.py docs append <doc-id> "Texto a añadir"
```

### Google Sheets

```bash
# Crear hoja de cálculo
~/.hermes/scripts/vcoo/vcoo-google.py sheets create "Control de clientes"

# Leer datos
~/.hermes/scripts/vcoo/vcoo-google.py sheets read <sheet-id>

# Escribir datos
~/.hermes/scripts/vcoo/vcoo-google.py sheets write <sheet-id> A1:C3 '[["Nombre","Email","Estado"],["Cliente A","a@b.com","Activo"]]'

# Añadir filas
~/.hermes/scripts/vcoo/vcoo-google.py sheets append <sheet-id> A1:C '[["Cliente B","c@d.com","Pendiente"]]'
```

### Google Calendar

```bash
# Próximos eventos
~/.hermes/scripts/vcoo/vcoo-google.py calendar list

# Próximos 20 eventos
~/.hermes/scripts/vcoo/vcoo-google.py calendar list 20
```

## Flujos típicos
1. **Alta de cliente**: Crear carpeta en Drive → Documento de bienvenida → Hoja de seguimiento
2. **Acta de reunión**: Crear documento → Añadir puntos tratados → Enlazar en Trello
3. **Informe periódico**: Leer datos de Sheets → Generar PDF → Enviar por email
