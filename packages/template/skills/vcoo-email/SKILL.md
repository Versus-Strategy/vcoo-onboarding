---
name: vcoo-email
description: "VCOO Virtual — Módulo MAIL: gestión inteligente de Gmail (lectura, búsqueda, envío, borradores)"
version: 1.0.1
author: VERSUS Strategy SL
tags: [vcoo, email, gmail, mail, comunicacion]
---

# VCOO MAIL — Bandeja de Entrada Inteligente

## Descripción
El módulo MAIL permite al agente VCOO gestionar el correo electrónico del cliente de forma autónoma:
- Monitorización de la bandeja de entrada
- Lectura y clasificación de correos
- Búsqueda en el historial de email
- Redacción y envío de respuestas
- Creación de borradores inteligentes

## Script
`~/.hermes/scripts/vcoo/vcoo-email.py` (usa shebang → VCOO venv automáticamente)

## Uso

### Leer bandeja de entrada
```bash
# Últimos 10 correos
~/.hermes/scripts/vcoo/vcoo-email.py list

# Últimos 20 correos
~/.hermes/scripts/vcoo/vcoo-email.py list 20
```

### Leer contenido de un correo
```bash
~/.hermes/scripts/vcoo/vcoo-email.py read <message-id>
```

### Buscar correos
```bash
# Búsqueda simple
~/.hermes/scripts/vcoo/vcoo-email.py search "factura pendiente"

# Búsqueda avanzada (sintaxis Gmail)
~/.hermes/scripts/vcoo/vcoo-email.py search "from:cliente@empresa.com has:attachment"
```

### Enviar correo
```bash
~/.hermes/scripts/vcoo/vcoo-email.py send "cliente@email.com" "Presupuesto adjunto" "Buenos días,

Adjunto el presupuesto solicitado.

Saludos,
VCOO Agent"
```

### Crear borrador (sin enviar)
```bash
~/.hermes/scripts/vcoo/vcoo-email.py draft "cliente@email.com" "Respuesta pendiente" "Cuerpo del borrador..."
```

### Listar etiquetas/carpetas
```bash
~/.hermes/scripts/vcoo/vcoo-email.py labels
```

## Flujos típicos
1. **Filtrado inteligente**: Leer inbox → Identificar correos urgentes → Notificar al equipo en Discord
2. **Pre-respuesta**: Leer email → Generar borrador de respuesta → Esperar aprobación → Enviar
3. **Búsqueda**: Encontrar email de un cliente concreto → Extraer datos relevantes

## Integración con otros módulos
- **OFFICE**: Adjuntar PDF generado con vcoo-pdf a un correo
- **PLANNER**: Crear tarjeta Trello cuando llega un email de un cliente prioritario
- **CORE**: Reportar en Discord cuando se envía un correo importante

## Notas
- Usa la API de Gmail (no IMAP) para máxima fiabilidad
- Soportado por el token OAuth2 de Google con scopes gmail.readonly, gmail.modify, gmail.send
- El token se refresca automáticamente
