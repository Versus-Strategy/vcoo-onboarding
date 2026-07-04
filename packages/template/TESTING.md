# VCOO Virtual — Estrategia de Testeo

## Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│                    VCOO Testing Pipeline                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Fase 0 ──▶ Structure Check ──▶ ¿Archivos clave existen?         │
│  Fase 1 ──▶ Python Syntax  ──▶ ¿Los scripts compilan?            │
│  Fase 2 ──▶ Branding       ──▶ ¿assets/templates son válidos?   │
│  Fase 3 ──▶ PDF Generation ──▶ ¿Genera documentos con estilo?    │
│  Fase 4 ──▶ Docker Build   ──▶ ¿La imagen se construye bien?    │
│  Fase 5 ──▶ Docker Runtime ──▶ ¿Hermes arranca dentro del        │
│  │                    contenedor?                                 │
│  Fase 6 ──▶ Integration    ──▶ ¿Trello/Gmail/Discord            │
│  │                    responden? (con credenciales)               │
│  Fase 7 ──▶ Cleanup       ──▶ Limpieza de contenedores           │
│                                                                   │
│  Cada fase informa: PASS | FAIL | SKIP + causa                    │
└──────────────────────────────────────────────────────────────────┘
```

## Independencia del Onboarding

El test suite se ejecuta de dos formas, y **ninguna depende del control plane** (onboarding.vercel.app):

| Modo | Comando | Cuándo usarlo |
|------|---------|---------------|
| **Local** (host) | `python3 scripts/vcoo-tester.py` | Desarrollo diario, cambios en skills/scripts |
| **Solo behavioral** | `python3 scripts/vcoo-behavior-tester.py` | Verificar comportamiento del agente IA |
| **Docker** | `docker run ... vcoo-test python3 /opt/vcoo-template/scripts/vcoo-tester.py` | Validación en VPS limpio simulado |
| **Docker + behavioral** | `docker run ... vcoo-test python3 /opt/vcoo-template/scripts/vcoo-tester.py --behavioral` | Behavioral tests en contenedor |

Ambos modos leen credenciales desde `~/.hermes/.env` (sin necesidad de API de onboarding).

## Credenciales

El test suite usa los mismos secretos que esta instancia de MAGI. El flujo es:

```
~/.hermes/.env  ──(mount)──▶  /root/.hermes/.env  (Docker)
~/.hermes/google_token.json ──(mount)──▶ /root/.hermes/google_token.json
```

| Secreto | ¿De dónde se obtiene? | ¿Se puede leer? |
|---------|----------------------|-----------------|
| `OPENROUTER_API_KEY` | `.env` | ❌ Redactado por Hermes |
| `DISCORD_BOT_TOKEN` | `.env` | ❌ Redactado |
| `TELEGRAM_BOT_TOKEN` | `.env` | ❌ Redactado |
| `NVIDIA_API_KEY` | `.env` | ❌ Redactado (ya escrito) |
| `GOOGLE_CLIENT_ID` | `.env` | ✅ Visible |
| `GOOGLE_CLIENT_SECRET` | `.env` | ❌ Redactado |
| `google_token.json` | OAuth flow | ✅ Archivo JSON leíble |
| `google_client_secret.json` | OAuth flow | ✅ Archivo JSON leíble |

> **Si alguna clave no está disponible**, la fase correspondiente se marca como `SKIP` con la causa. El resto del test suite sigue ejecutándose. **Nunca se bloquea todo por una credencial faltante.**

## Ejecución

### 1. Tests locales (rápido, para desarrollo)

```bash
cd ~/versus/vcoo-template
python3 scripts/vcoo-tester.py
```

### 2. Tests en Docker (simula VPS limpio)

```bash
# Construir imagen (una vez, o tras cambios):
docker build --no-cache -f Dockerfile.test -t vcoo-test .

# Ejecutar test suite:
docker run --rm \
  -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  vcoo-test \
  python3 /opt/vcoo-template/scripts/vcoo-tester.py
```

### 3. Tests interactivos con MAGI

```bash
docker run -it --rm --name vcoo-test-agent \
  -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  -v ~/.hermes/google_client_secret.json:/root/.hermes/google_client_secret.json \
  vcoo-test \
  bash -l -c 'cd /opt/vcoo-template && hermes gateway run > /tmp/gw.log 2>&1 & disown && sleep 3 && hermes'
```

Entonces, dentro de MAGI, pídele cosas como:
- `"lee los 3 correos más recientes de mi bandeja de entrada"`
- `"genera una factura de ejemplo y envíala por Discord"`
- `"crea una tarea en Trello para el proyecto VCOO"`

### 4. Probar fallback NVIDIA

Para verificar que el fallback a NVIDIA funciona cuando OpenRouter da rate-limit:

```bash
# Forzar rate-limit configurando una API key inválida en OpenRouter
# y verificar que Hermes cae a NVIDIA automáticamente.
# O directamente: configurar NVIDIA como provider por defecto temporalmente:
docker run --rm \
  -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  vcoo-test \
  bash -c 'export HERMES_MODEL=nvidia/nemotron-3-super-120b-a12b && python3 /opt/vcoo-template/scripts/vcoo-tester.py --phase integration'
```

## Formato de resultados

Cada fase imprime:

```
━━━ Fase N: Nombre ━━━━
  ✓ Test-1: descripción                           PASS
  ✗ Test-2: descripción                           FAIL  ← causa concreta
  - Test-3: descripción                           SKIP  ← credencial faltante / prerequisito no cumplido
━━━ Resultado: 12 PASS · 1 FAIL · 2 SKIP ━━━━
```

**Causas de fallo comunes:**

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `FileNotFoundError: .../google_token.json` | Token OAuth no montado | Añadir `-v ~/.hermes/google_token.json:/root/.hermes/google_token.json` |
| `HTTP 429: Rate limited` | OpenRouter sin saldo / límite | Usar NVIDIA como fallback ya configurado |
| `ModuleNotFoundError: googleapiclient` | Dependencias no instaladas | Ejecutar `install.sh` o rebuild Docker |
| `ConnectionError: Trello` | Token Trello no configurado | Añadir `TRELLO_API_KEY/TRELLO_TOKEN` al `.env` |
| `pip install not officially supported` | Pip instalado vía get-pip.py | Ya corregido con `ensurepip` en Dockerfile.test |

## Fases del test suite

| Fase | Tests | Dependencias | Fallo bloqueante |
|------|-------|-------------|------------------|
| 0: Structure | 8 | Ninguna | ❌ Sí |
| 1: Syntax | 12 | Fase 0 OK | ❌ Sí |
| 2: Branding | 8 | Fase 0 OK | ❌ Sí |
| 3: PDF | 8 | Fase 1+2 OK | ❌ Sí |
| 4: Docker Build | 7 | Docker instalado | ❌ Sí (solo en host) |
| 5: Docker Runtime | 12 | Fase 4 OK | ❌ Moderado |
| 6: Integration | 12 | Credenciales + Fase 1 | ❌ No (SKIP si no hay) |
| 7: Cleanup | 3 | Fase 4+5 ejecutadas | ❌ No |

## Logs

Cada ejecución genera un log en `test-output/test-run-*.log`. El tester.py ya los gestiona automáticamente.

Para logs detallados de Hermes dentro del contenedor:
```bash
docker exec vcoo-test-agent cat /tmp/gw.log   # Gateway log
docker exec vcoo-test-agent cat /tmp/hermes.log  # Hermes TUI log
```

## CI / Automatización

El test suite puede ejecutarse como cron job de Hermes:

```bash
hermes cron create \
  --name "vcoo-nightly-tests" \
  --schedule "0 6 * * *" \
  --prompt "Ejecuta el test suite de VCOO en Docker y reporta los resultados" \
  --skills vcoo-core \
  --deliver discord
```

Esto ejecuta los tests cada día a las 6:00 AM y envía el resumen al canal de Discord.

## Behavioral Tests — Comportamiento del Agente IA

A partir de la versión 2.0, la suite incluye **tests de comportamiento** que verifican que el agente VCOO responde correctamente a comandos en lenguaje natural, no solo que los scripts funcionan.

### Arquitectura

```
Capa 1: Unitario/Estructural (vcoo-tester.py)     Capa 2: Comportamiento (vcoo-behavior-tester.py)
┌──────────────────────────────────────┐          ┌─────────────────────────────────────┐
│ ✓ Scripts funcionan (vcoo-pdf.py)    │          │ ✓ El agente SABE usar vcoo-pdf.py   │
│ ✓ APIs responden (Google Calendar)   │    +     │   cuando se le pide en lenguaje     │
│ ✓ Sintaxis, estructura, branding     │          │   natural sin instrucciones explícitas│
│ ✓ Despliegue, instalación, Docker    │          │ ✓ Responde con resultados concretos  │
└──────────────────────────────────────┘          └─────────────────────────────────────┘
```

### Mecanismo

1. **Escenarios**: definidos en `configs/behavioral-tests.yaml`. Cada escenario tiene un prompt en lenguaje natural y criterios de evaluación.
2. **Ejecución**: el script `vcoo-behavior-tester.py` envía cada prompt al agente VCOO mediante `hermes -z "prompt"` (modo oneshot).
3. **Evaluación dual**:
   - **LLM Judge**: usa OpenRouter (modelo económico `gpt-4o-mini`) para analizar semánticamente la respuesta del agente. Determina si el agente completó la tarea o se excusó.
   - **Side effects**: para generación de PDFs, verifica que el archivo realmente se haya creado en el sistema de archivos.

### Escenarios incluidos (11)

| ID | Capacidad | Prompt | Severidad |
|----|-----------|--------|-----------|
| 📅 `calendar-events` | Google Calendar | "¿Qué tengo esta semana?" | critical |
| 📬 `email-inbox` | Gmail inbox | "Últimos 3 correos" | high |
| 🏷️ `email-labels` | Gmail etiquetas | "Etiquetas configuradas" | low |
| 📄 `generate-invoice` | Factura PDF | "Factura VERSUS 500€" | critical |
| 📊 `generate-report` | Informe PDF | "Informe Q2-2026" | high |
| 💰 `generate-quote` | Presupuesto PDF | "Presupuesto 1200€" | high |
| 📁 `drive-files` | Google Drive | "Archivos en Drive" | medium |
| 🔍 `drive-search` | Búsqueda Drive | "Busca documento ventas" | medium |
| 📋 `trello-boards` | Trello | "Tableros Trello" | optional |
| 🌐 `web-search` | Búsqueda web | "Tipo de cambio EUR/USD" | low |

### ¿Por qué LLM Judge en vez de palabras clave?

Validar con palabras clave es frágil:
- **Falso positivo**: *"No puedo mostrarte eventos porque me falta el token"* contiene "evento" → falso OK
- **Falso negativo**: *"Tus próximas citas: 26/06 Santander, 28/06 Growing VERSUS..."* no contiene "calendario" → falso FAIL

El LLM Judge entiende la **intención semántica** de la respuesta, no solo palabras literales.

### Ejecución

```bash
# Behavioral tests standalone
python3 scripts/vcoo-behavior-tester.py

# Como parte de la suite completa (Fase 9)
python3 scripts/vcoo-tester.py --phase 9
python3 scripts/vcoo-tester.py --behavioral

# En Docker
docker run --rm -v ~/.env.test:/root/.hermes/.env \
  -v ~/.hermes/google_token.json:/root/.hermes/google_token.json \
  vcoo-test \
  python3 /opt/vcoo-template/scripts/vcoo-behavior-tester.py

# Con modelo de judge personalizado
python3 scripts/vcoo-behavior-tester.py --judge-model "openai/gpt-4o"
```

### Output

```
═══ VCOO Behavioral Test Report ═══

ID                Prompt                    Skills     Evidencia    Estado
──────────────────────────────────────────────────────────────────────────
📅 Calendario   │ ¿Qué tengo esta semana?  │ google-ws │ cumplida   │ 🟢 OK
📬 Email         │ Últimos 3 correos        │ vcoo-email│ cumplida   │ 🟢 OK
📄 Factura       │ Factura VERSUS 500€      │ vcoo-pdf  │ +PDF      │ 🟢 OK
📁 Drive         │ Archivos en Drive        │ google-ws │ falló      │ 🔴 FALLÓ
📋 Trello        │ Tableros Trello          │ trello    │ sin creds  │ ⚠ SKIP

Resumen: 8 PASS · 1 FAIL · 1 SKIP · 1 WARN
```

### Diferencias clave entre capas

| Aspecto | vcoo-tester.py | vcoo-behavior-tester.py |
|---------|---------------|------------------------|
| **Qué prueba** | Scripts, APIs, estructura | Comportamiento del agente ante lenguaje natural |
| **Cómo** | Ejecuta código directamente | Envía prompts vía `hermes -z` |
| **Evaluación** | PASS/FAIL determinista (código) | LLM judge semántico + side effects |
| **Dependencias** | Python, scripts VCOO | Hermes CLI, OpenRouter, skills |
| **Rapidez** | Segundos | ~1-2 min por escenario (10-15 min total) |
| **Determinismo** | 100% (mismo input = mismo output) | Probabilístico (depende del LLM) |

### Cómo añadir un nuevo escenario

Editar `configs/behavioral-tests.yaml` y añadir un bloque como este:

```yaml
- id: my-new-test
  name: "🧪 Mi nuevo test"
  description: "Descripción de lo que prueba"
  prompt: "El prompt en lenguaje natural para el agente"
  expected_skills: [skill-name]
  judge: true
  side_effects: null
  severity: medium
  when_skip: null
```

No requiere cambiar ningún script. El motor `vcoo-behavior-tester.py` lo procesa automáticamente.

### Coste del LLM Judge

Cada escenario consume ~200 tokens de input + ~50 de output en `gpt-4o-mini` (~$0.00015/escenario). Con 11 escenarios y asumiendo 1 ejecución/día: **~$0.0016/día, ~$0.05/mes**. Irrelevante.

