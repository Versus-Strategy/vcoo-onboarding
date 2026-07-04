---
name: vcoo-testing
description: "VCOO Virtual — Módulo TESTER: verificación autónoma de la plantilla VCOO. Ejecuta la suite completa y reporta resultados estructurados indicando qué falla y por qué."
version: 1.0.0
author: VERSUS Strategy SL
tags: [vcoo, testing, qa, verificacion, calidad]
---

# VCOO TESTER — Verificación Autónoma de la Plantilla

## ⚠ INSTRUCCIÓN DE EJECUCIÓN DIRECTA — NO PREGUNTAR

Cuando el usuario diga cualquiera de las frases de activación (especialmente *"ejecuta el test de la plantilla"*):

- **"La plantilla"** se refiere SIEMPRE a la template VCOO, ubicada en `/opt/vcoo-template/` (Docker) o `~/versus/vcoo-template/` (host). No hay ambigüedad.
- **NO preguntar** "¿qué plantilla?" ni usar el tool `clarify`. El usuario ya ha sido específico.
- **Ejecutar inmediatamente** el script de testeo.
- **Reportar el resultado** en el mismo canal donde el usuario preguntó, usando la tabla estructurada de más abajo.

Orden de ejecución:
1. Detectar el directorio de la template:
   - Si `~/versus/vcoo-template/` existe → esa es la template.
   - Si no, si `/opt/vcoo-template/` existe → esa es la template.
   - Si no, si `~/.hermes/scripts/vcoo/` existe → usar esa ruta.
2. Ejecutar: `python3 {TEMPLATE_DIR}/scripts/vcoo-tester.py` desde `{TEMPLATE_DIR}` como working directory.
3. Capturar la salida (stdout + stderr).
4. Analizar el resultado: contar PASS, FAIL, SKIP, WARN.
5. Reportar con el formato de tabla de la sección "Formato de reporte".
6. Si hay FAIL, listar las causas concretas (el script ya las muestra).
7. Concluir con recomendación (OK / revisar warnings / reparar fallos).

## Cuándo activarse

Esta skill se activa cuando el usuario dice frases como:
- *"ejecuta el test de la plantilla"*
- *"verifica VCOO"*
- *"prueba la plantilla"*
- *"vcoo tester"*
- *"pasa los tests"*
- *"revisa que todo funcione"*
- *"ejecuta la suite de pruebas"*
- *"estado de la plantilla"*

También se activa automáticamente **después de hacer cambios** en skills, scripts o config, para verificar que no se ha roto nada.

## Script de testeo

El motor de pruebas es `vcoo-tester.py`, ejecutable directamente:

```bash
# Local (entorno actual):
~/.hermes/scripts/vcoo/vcoo-tester.py

# O desde el directorio de la template:
python3 /opt/vcoo-template/scripts/vcoo-tester.py
```

El script es autónomo: lee los secretos del entorno Hermes, ejecuta todas las fases y genera logs.

## Fases de testeo

El test suite tiene **8 fases**, cada una con un propósito específico. Ninguna fase bloquea a las siguientes (excepto Fase 0 y 1 que son prerequisitos estructurales).

### Fase 0 — Preparación del entorno
**Comando:** (se ejecuta automáticamente al iniciar el tester)
**Qué prueba:**
- Versión de Python ≥ 3.10
- El directorio de la template existe
- Los scripts tienen permisos de ejecución
- Los secretos están accesibles (OPENROUTER_API_KEY, DISCORD_BOT_TOKEN, etc.)
**Resultado esperado:** ✅ 4 PASS · 0 FAIL
**Fallo crítico si:** Python < 3.10 o falta el directorio de la template

### Fase 1 — Tests estructurales
**Qué prueba:**
- `README.md`, `SOUL.md`, `config.yaml`, `.env.example` existen
- `config.yaml` es YAML válido
- `.env.example` tiene todas las variables necesarias
- `install.sh` existe y es ejecutable
- Skills y scripts VCOO existen en sus directorios
- Cron jobs JSON son válidos
- `.gitignore` cubre secretos
**Resultado esperado:** ✅ 10 PASS · 0 FAIL
**Fallo crítico si:** `config.yaml` o `install.sh` faltan

### Fase 2 — Tests de sintaxis
**Qué prueba:**
- Cada script `*.py` compila sin errores
- Cada script `*.sh` pasa `bash -n` (validación de sintaxis)
**Resultado esperado:** ✅ 7 PASS · 0 FAIL
**Fallo si:** Algún script tiene errores de sintaxis

### Fase 3 — Tests de integración (con secretos reales)
**Qué prueba:**
- **Trello** (si hay credenciales): listar boards y lists
- **Google Drive**: listar archivos
- **Google Calendar**: listar eventos
- **Gmail**: leer bandeja de entrada y etiquetas
- **PDF**: generar factura, informe y presupuesto
**Resultado esperado:**
- ✅ Google/PDF: 8 PASS · 0 FAIL
- ⊘ Trello: SKIP si no hay credenciales (no bloquea)
**Fallo si:** Google Drive, Calendar, Gmail o PDF fallan. Fallo en PDF es bloqueante.

### Fase 4 — Error handling
**Qué prueba:**
- Scripts sin argumentos → muestran usage
- Scripts con API key inválida → error controlado
- Scripts con token faltante → error claro
**Resultado esperado:** ✅ 6 PASS · 0 FAIL
**Fallo si:** Un script crashea en vez de mostrar un mensaje de error

### Fase 5 — Tests de instalación (dry-run)
**Qué prueba:**
- Shebang correcto (`#!/usr/bin/env python3`)
- `set -euo pipefail` en scripts bash
- Rutas correctas en install.sh
**Resultado esperado:** ✅ 4 PASS · 0 FAIL

### Fase 6 — Readiness (estado de secretos)
**Qué prueba:**
- OPENROUTER_API_KEY configurada
- DISCORD_BOT_TOKEN configurado
- TELEGRAM_BOT_TOKEN configurado
- TRELLO_API_KEY+TOKEN (opcional)
- Google OAuth funcional
- CONTROL_PLANE_URL configurada
- Google OAuth token válido (no expirado)
**Resultado esperado:** ⚠ Puede tener warnings (Trello opcional), pero 0 FAIL

### Fase 7 — Docker VPS Simulation (solo en host)
**Qué prueba:**
- Dockerfile.test existe
- Build de imagen Docker (si Docker está disponible)
- Tests estructurales dentro del contenedor
- Error handling dentro del contenedor
**Resultado esperado:** ⊘ SKIP si Docker no está disponible

## Cómo ejecutar los tests

### Modo 1: Test rápido (local, recomendado para desarrollo)

```bash
~/.hermes/scripts/vcoo/vcoo-tester.py
```

### Modo 2: Test en Docker (simula VPS limpio)

```bash
docker run --rm \
  -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  vcoo-test \
  python3 /opt/vcoo-template/scripts/vcoo-tester.py
```

### Modo 3: Test interactivo con agente VCOO (con pairing y home channel preservados)

Para que el agente VCOO reconozca a tu usuario sin tener que aprobarlo cada vez, monta también los archivos de estado:

```bash
docker run -it --rm --name vcoo-test-agent \
  -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  -v ~/.hermes/google_client_secret.json:/root/.hermes/google_client_secret.json \
  -v ~/.hermes/auth.json:/root/.hermes/auth.json \
  -v ~/.hermes/channel_directory.json:/root/.hermes/channel_directory.json \
  vcoo-test \
  bash -l -c 'cd /opt/vcoo-template && hermes gateway run > /tmp/gw.log 2>&1 & disown && sleep 3 && hermes'
```

Una vez dentro, solo pide *"ejecuta el test de la plantilla"* — el agente VCOO correrá el tester automáticamente sin preguntar nada.

### Modo 4: Test tras cambios (post-commit)

Tras modificar skills, scripts o config, ejecutar automáticamente el tester para verificar que no se ha introducido ninguna regresión.

## Formato de reporte

Cuando el usuario pida el test de la plantilla, agente VCOO debe:

1. **Ejecutar** la suite con `vcoo-tester.py`
2. **Interpretar** el resultado
3. **Reportar** con esta estructura:

---

### 📋 Reporte de verificación — VCOO Template

**Fecha:** {timestamp}
**Entorno:** {local | docker | vps}
**Commit/versión:** {git hash si aplica}

| Fase | Estado | Detalle |
|------|--------|---------|
| 0. Preparación | 🟢 PASÓ | 4/4 tests |
| 1. Estructural | 🟢 PASÓ | 10/10 tests |
| 2. Sintaxis | 🟢 PASÓ | 7/7 tests |
| 3. Integración | 🟢 PASÓ | 8/10 (2 SKIP: Trello) |
| 4. Error handling | 🟢 PASÓ | 6/6 tests |
| 5. Instalación | 🟢 PASÓ | 4/4 tests |
| 6. Readiness | ⚠ ADVERTENCIA | Ver detalles |
| 7. Docker VPS | ⊘ NO APLICA | Docker no disponible |

**Resultado global: {N} PASS · 0 FAIL · {M} SKIP · {W} WARN**

**⚠ Advertencias:**
- {detalle de cada warning}
- ...

**✅ Conclusión:** {TODO OK / Revisar warnings / FALLOS CRÍTICOS — lista}

---

### Interpretación de resultados

| Indicador | Significado |
|-----------|-------------|
| 🟢 PASÓ | Todo correcto. No requiere acción. |
| ⚠ ADVERTENCIA | Algo configurable no está presente (ej: Trello sin API key). No es fallo. |
| 🔴 FALLO | Algo está roto. Requiere intervención. |
| ⊘ SKIP | Test saltado por prerequisito no cumplido (ej: Docker no instalado). |

### Causas de fallo frecuentes

| Falla | Síntoma | Causa probable | Solución |
|-------|---------|----------------|----------|
| T3.3–T3.6 | Google APIs no responden | Token OAuth no montado o expirado | `-v ~/.hermes/google_token.json:/root/.hermes/google_token.json` |
| T3.7–T3.9 | PDF no se genera | reportlab no instalado | Rebuild Docker o reinstalar venv |
| Fase 6 | OPENROUTER_API_KEY ausente | `.env` no montado o sin clave | `-v ~/.env.test:/root/.hermes/.env` |
| HTTP 429 | Rate limited | OpenRouter sin saldo | Usar fallback NVIDIA (ya configurado) |
| T1.4 | .env.example incompleto | Se añadió variable sin documentarla | Añadir a .env.example con placeholder |

## Verificación post-cambio

Siempre que el agente VCOO realice cambios en la plantilla (skills, scripts, config, Dockerfile), debe:

1. Ejecutar `vcoo-tester.py` localmente
2. Verificar que no haya FAIL nuevos respecto a la ejecución anterior
3. Si hay FAIL nuevos, reportarlos antes de continuar
4. Solo si todo pasa, considerar el cambio como completado

## Notas

- El test suite es **independiente del control plane** (onboarding.vercel.app) — no necesita API externa
- Los secretos se reutilizan de la instancia del agente VCOO actual vía `.env` o mounts Docker
- Los logs de cada ejecución se guardan en `test-output/logs/` con timestamp
- El tester puede ejecutarse como cron job de Hermes para verificaciones periódicas
- La skill NO ejecuta el tester automáticamente al cargarse; espera a que el usuario lo solicite o a que el agente VCOO detecte un cambio relevante
