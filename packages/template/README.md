# VCOO Virtual — Template de Repositorio
**Versión:** 1.0.1

**VCOO (Virtual COO)** es un asistente autónomo de gestión basado en Hermes Agent (Nous Research) y configurado por VERSUS Strategy SL para actuar como un COO Virtual para tu negocio.

---

## Estructura del repositorio

```
vcoo-template/
├── install.sh                  # One-liner: instalación completa + activación de cron jobs
├── run-docker.sh               # Lanzador Docker: build + run con todos los mounts
├── .env.example                # Variables de entorno del cliente
├── config.yaml                 # Configuración base de Hermes Agent (OpenRouter + NVIDIA fallback)
├── SOUL.md                     # Personalidad del agente VCOO
├── TESTING.md                  # Estrategia de testeo (unitario + comportamiento)
│
├── skills/                     # Skills VCOO → se copian a ~/.hermes/skills/
│   ├── vcoo-core/              #   Módulo CORE (base obligatoria)
│   ├── vcoo-trello/            #   Módulo PLANNER (Trello)
│   ├── vcoo-google-workspace/  #   Módulo OFFICE (Google Suite)
│   ├── vcoo-email/             #   Módulo MAIL (Gmail)
│   ├── vcoo-pdf/               #   Generación de PDFs con branding corporativo
│   ├── vcoo-testing/           #   Test suite autónomo de verificación (unitario)
│   └── vcoo-behavioral-testing/ #  Test de comportamiento del agente (LLM judge)
│
├── scripts/                    # Scripts de integración (con shebang portable)
│   ├── vcoo-trello.py
│   ├── vcoo-google.py
│   ├── vcoo-email.py
│   ├── vcoo-pdf.py
│   ├── vcoo-tester.py          # Suite de 60+ tests (estructurales, integración, Docker)
│   └── vcoo-behavior-tester.py # Tests de comportamiento del agente (10 escenarios)
│
├── configs/                    # Configuraciones editables
│   └── behavioral-tests.yaml   #   Escenarios para tests de comportamiento
│
├── assets/                     # Recursos de branding corporativo
│   ├── brand.yaml              #   Colores, tipografía, datos fiscales
│   ├── logo.svg                #   Logotipo vectorial
│   └── logo.png                #   Logotipo rasterizado
│
├── templates/                  # Plantillas YAML para documentos
│   ├── invoice.yaml
│   ├── report.yaml
│   └── quote.yaml
│
├── provision/                  # Scripts de provisionamiento
│   ├── setup-server.sh         #   Hardening + dependencias del servidor
│   └── configure-oauth.sh      #   Configuración de OAuth Google
│
├── cron-jobs/                  # Watchdogs automáticos (se activan en install.sh)
│   ├── backlog-hygiene.json    #   Cada 4h: revisar tarjetas Trello estancadas
│   ├── email-scan.json         #   Cada 1h: escanear Gmail en busca de correos urgentes
│   └── health-check.json       #   Cada 30m: health check del sistema
│
├── Dockerfile.test             # Imagen Docker para simulación de VPS limpio
├── .vcoo-root                  # Marcador para auto-detección del tester
└── test-output/                # Logs y reportes de ejecución de tests
    ├── logs/                   #   Logs individuales por test
    └── behavioral/             #   Logs de tests de comportamiento
```

## Requisitos del sistema

- **Servidor**: Linux (Ubuntu 22.04+ / Debian 12+ recomendado)
- **CPU**: 2 cores mínimo
- **RAM**: 4 GB mínimo (8 GB recomendado)
- **Disco**: 20 GB
- **Python**: 3.11+
- **Conexión**: Acceso a Internet + Discord/Telegram

## Instalación rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/Versus-Strategy/vcoo-template.git
cd vcoo-template

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus claves:
#   OPENROUTER_API_KEY
#   DISCORD_BOT_TOKEN
#   DISCORD_HOME_CHANNEL  (ID del canal principal para el agente)
#   TELEGRAM_BOT_TOKEN

# 3. Ejecutar instalación (incluye activación automática de cron jobs)
bash install.sh

# 4. Seguir el asistente de configuración OAuth
bash provision/configure-oauth.sh
```

## Testing — Dos capas

### Capa 1: Tests unitarios (verifican scripts, APIs y estructura)

```bash
# En el servidor local
python3 scripts/vcoo-tester.py

# En Docker (simula VPS limpio)
./run-docker.sh --test

# Solo behavioral tests
./run-docker.sh --behavior
```

### Capa 2: Tests de comportamiento (verifican que el agente responde correctamente)

```bash
# Tests de comportamiento standalone
python3 scripts/vcoo-behavior-tester.py

# Solo escenarios críticos (rápido, ~2 min)
python3 scripts/vcoo-behavior-tester.py --smoke

# Como parte de la suite principal
python3 scripts/vcoo-tester.py --behavioral
```

### Resultado esperado

| Entorno | PASS | FAIL | SKIP |
|---------|------|------|------|
| Host local (con credenciales) | 64+ | 0 | 2 |
| Docker (con credenciales) | 59 | 0 | 8 |
| Docker (sin Trello/Gmail) | ~47 | 0 | ~14 |

> Los SKIP corresponden a credenciales opcionales no montadas (Trello, Google OAuth). **Nunca hay FAIL si la template está íntegra.**

### Modo interactivo (el agente contesta en Discord/Telegram)

```bash
./run-docker.sh
```

El agente arranca con el gateway de Discord conectado, usando el canal configurado en `DISCORD_HOME_CHANNEL` (o `🤖・testing` por defecto).

## Módulos del producto

| Módulo | Skills | Descripción | Tests |
|--------|--------|-------------|-------|
| **CORE** | `vcoo-core` | Infraestructura base. Canales, terminal, cron | ✅ |
| **OFFICE** | `vcoo-google-workspace` | Google Drive, Calendar, Docs, Sheets | ✅ |
| **MAIL** | `vcoo-email` | Gmail: leer, buscar, enviar, borradores | ✅ |
| **PLANNER** | `vcoo-trello` | Trello: backlog, tarjetas, listas | ✅ |
| **PDF** | `vcoo-pdf` | Facturas, presupuestos, informes con branding | ✅ |
| **TESTER** | `vcoo-testing` + `vcoo-behavioral-testing` | Verificación unitaria + comportamental | ✅ |

## Providers LLM

| Provider | Modelo | Uso |
|----------|--------|-----|
| **OpenRouter** | `openrouter/free` | Principal (por defecto) |
| **NVIDIA** | `nvidia/nemotron-3-super-120b-a12b` | Fallback automático si OpenRouter da rate-limit |

## Personalización

Para adaptar el VCOO a tu negocio:

1. Edita `SOUL.md` con la personalidad y contexto de tu empresa
2. Ajusta `assets/brand.yaml` con tus colores, logo y datos fiscales
3. Modifica las plantillas en `templates/` para tu formato de documentos
4. Configura las integraciones que necesites en `provision/`
5. Ajusta los cron jobs en `cron-jobs/`
6. Añade o quita escenarios de comportamiento en `configs/behavioral-tests.yaml`

## CI / Automatización

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: VCOO Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & test
        run: |
          docker build -f Dockerfile.test -t vcoo-test .
          docker run --rm vcoo-test python3 /opt/vcoo-template/scripts/vcoo-tester.py --json
```

### Cron nocturno (Hermes)

```bash
hermes cron create \
  --name "vcoo-nightly" \
  --schedule "0 6 * * *" \
  --prompt "Ejecuta los tests de la plantilla VCOO en Docker y reporta los resultados" \
  --skills vcoo-core \
  --deliver discord
```

---

*Template VCOO Virtual — Creado por VERSUS Strategy SL · Distribuido bajo licencia privada*
