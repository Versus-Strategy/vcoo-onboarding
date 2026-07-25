# VCOO Onboarding — Revisión de Arquitectura v2.3

> **Autor:** MAGI (Melchior-1, Balthasar-2, Casper-3)  
> **Fecha:** 2026-06-22  
> **Versión analizada:** v2.3 (agente v3 con Rich TUI, OAuth dinámico, save-creds)

---

## 1. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENTE (VPS Linux)                        │
│                                                                 │
│  ┌──────────────────────────────────┐                           │
│  │    install_vsd.sh (one-liner)   │                           │
│  │  • Instala versusd (watchdog)   │                           │
│  │  • Instala Hermes Agent + tick  │                           │
│  │  • Aplica template del producto │                           │
│  └──────────────┬───────────────────┘                           │
│                 │ exec (via systemd)                               │
│  ┌──────────────▼───────────────────┐                           │
│  │     versusd (watchdog bash)      │                           │
│  │  • Corre permanentemente         │                           │
│  │  • Ejecuta tick.py cada 60s      │                           │
│  │  • 5s si hay comandos pendientes │                           │
│  │  • No ephemeral — permanece      │                           │
│  └──────────────┬───────────────────┘                           │
│                 │                                                  │
│  ┌──────────────▼───────────────────┐                           │
│  │     tick.py (supervisor plugin)  │                           │
│  │  • POST /agent/{id}/tick (unif.) │                           │
│  │  • Ejecuta COMMAND_MAP fijo      │                           │
│  │  • _handle_save_creds() → disco  │                           │
│  │  • Estado local en ~/.vcoo/      │                           │
│  └──────────────┬───────────────────┘                           │
│                 │                                                  │
│  ┌──────────────▼───────────────────┐                           │
│  │     vsctl (VCOO CLI)             │                           │
│  │  • Diagnóstico y control local   │                           │
│  │  • consultar estado, logs        │                           │
│  └──────────────────────────────────┘                           │
│                                                                 │
│  Fuentes: packages/vsd/ + packages/template/                    │
│                 │ HTTP (tick + report)                              │
└─────────────────┼───────────────────────────────────────────────┘
                  │
                  │  Internet (HTTPS)
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│               VERCEL (Serverless Functions)                      │
│                                                                 │
│  ┌──────────────────────────────────┐                           │
│  │     FastAPI Backend (main.py)    │                           │
│  │  • /register, /agent/{id}/poll   │                           │
│  │  • /agent/{id}/result (ACK)      │                           │
│  │  • /setup/{token} (wizard)       │                           │
│  │  • /setup/{token}/auth-url       │  ← NUEVO v2.3             │
│  │  • /auth/callback (OAuth)        │  ← NUEVO v2.3             │
│  │  • /playbooks/{name}[/raw]       │                           │
│  └──────────────┬───────────────────┘                           │
│                 │                                                 │
└─────────────────┼───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│               SUPABASE (PostgreSQL + Realtime)                   │
│                                                                 │
│  Tablas: vcoos, agents, commands, command_logs,                 │
│          provision_tokens, onboarding_state                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│            FRONTEND (Vercel SPA — Vite + React)                  │
│                                                                 │
│  /dashboard  →  Dashboard.tsx (gestión de VCOOs)                 │
│  /setup/:token → Setup.tsx (wizard con OAuth dinámico)          │
│                                                                 │
│  Polling cada 3s a GET /setup/{token}                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Flujos de Interacción

### 2.1 Registro y tick unificado
```
install_vsd.sh → versusd → POST /register (provision_token)
                           ← {agent_id, agent_token, vcoo_id}
                           → versusd ejecuta tick.py (foreground)
                           → tick.py: POST /agent/{id}/tick cada 60s
                           ← {commands: [...], interval: N}
                           → ejecuta comando → POST /agent/{id}/result
                           → tick.py: _handle_save_creds() en save-creds
```

### 2.2 Wizard de onboarding (cliente)
```
Cliente → abre /setup/{token} en navegador
        ← wizard muestra pasos según módulos
        → clic "Verificar" → POST /setup/{token}/verify
        ← {status: "enqueued" | "auto_completed"}
        → polling cada 3s detecta avance de paso
        
Para OAuth:
        → clic "Autorizar con Google" → GET /setup/{token}/auth-url?service=google
        ← {url: "https://accounts.google.com/o/oauth2/..."}
        → window.open(url) → autoriza → callback a /auth/callback
        → backend encola save-creds → agente guarda token
        → clic "Verificar" → verify-google → OK
```

### 2.3 Flujo de error y reintento
```
Agente reporta status="error" → backend:
  - add_onboarding_error(step, output)
  - retry_count[step]++
  - Si retry_count < 3: reencola comando (nuevo cmd_id)
  - Si retry_count >= 3: marca status="blocked"
  - Operador puede: POST /vcoo/{id}/onboarding/retry | /skip
```

---

## 3. Fortalezas

| Fortaleza | Evidencia |
|-----------|-----------|
| **One-liner sin fricción** | `curl -sSL ... \| PROVISION_TOKEN=*** bash -` — el cliente solo pega un comando |
| **Auto-reparación** | `install.sh` (3-tier venv fallback) + `vcoo-bootstrap.py` (descarga scripts faltantes) |
| **Seguridad por diseño** | COMMAND_MAP fijo → el agente solo ejecuta comandos predefinidos. Sin shell arbitraria |
| **Persistencia efímera** | Agente foreground, sin systemd. Al terminar se autoborra. No deja huella |
| **ACK con idempotencia** | Backoff 5s/15s/30s, acepta 200/201/409. Evita comandos duplicados |
| **TUI informativa** | Rich Live panel con progreso, logs en vivo, estado de conexión |
| **Log streaming** | Popen+select streamea stdout/stderr en tiempo real al backend |
| **Serverless escalable** | Vercel + Supabase free tier. Sin servidores que mantener |
| **OAuth dinámico** | URLs generadas server-side, no hardcodeadas. Callback unificado |

---

## 4. Debilidades y Riesgos

| # | Debilidad | Impacto | Severidad |
|---|-----------|---------|-----------|
| 1 | **Polling introduce latencia** | 15s + jitter por ciclo. Un paso puede tardar hasta 30s en ejecutarse. Peor caso: 3 reintentos × 30s = 90s | Media |
| 2 | **Sin push notifications** | El frontend hace polling cada 3s. Si hay 100 clientes simultáneos, son 33 req/s al backend | Baja (volumen bajo) |
| 3 | **OAuth en VPS headless** | `gh auth login` abre navegador, pero en un VPS sin GUI no funciona. El cliente debe hacer port-forwarding o usar token manual | Alta |
| 4 | **Sin timeout automático** | Si un paso falla 3 veces → BLOCKED. No hay auto-skip para pasos opcionales | Media |
| 5 | **Estado local mitigado** | tick.py mantiene estado local en `~/.vcoo/`. Si Supabase cae, el agente reintenta y no pierde progreso | Media |
| 6 | **Credenciales en texto plano** | `~/.hermes/google_token.json` y `~/.hermes/.env` sin cifrar. Un atacante con acceso al VPS las lee. Mitigación parcial: endpoint `/setup/{id}/encrypt-creds` disponible | Alta |
| 7 | **Sin verificación de integridad** | `install_vsd.sh` no verifica checksums del agente/scripts descargados | Media |

---

## 5. Propuestas de Mejora (priorizadas)

### 🟢 Prioridad Alta

| # | Mejora | Esfuerzo | Descripción |
|---|--------|----------|-------------|
| **P1** | **Cifrado de credenciales** | Medio | ✅ Implementado. Endpoint `/setup/{id}/encrypt-creds` cifra credenciales con Fernet antes de escribirlas a disco. El agente las descifra en memoria |
| **P2** | **Timeout + auto-skip** | Bajo | Añadir `step_timeout` (e.g., 10 min). Si el paso no avanza, marcarlo como opcional y auto-skippear si `optional: true` |
| **P3** | **Webhook HTTP en vez de polling** | Medio | El agente expone un endpoint HTTP efímero. El backend le hace POST cuando hay comandos. Reduce latencia a <1s |

### 🟡 Prioridad Media

| # | Mejora | Esfuerzo | Descripción |
|---|--------|----------|-------------|
| **P4** | **Supabase Realtime** | Bajo | El frontend se suscribe a cambios en `onboarding_state`. Sin polling cada 3s. Ya tenemos Supabase |
| **P5** | **Verificación de integridad** | Bajo | `install_vsd.sh` descarga SHA256SUMS + verifica. Previene MITM |
| **P6** | **Rate limiting** | Bajo | Añadir límite a `/register` y `/agent/{id}/tick` por IP. Evita abuso |

### 🔵 Prioridad Baja

| # | Mejora | Esfuerzo | Descripción |
|---|--------|----------|-------------|
| **P7** | **Dominio propio** | Bajo | `vcoo.versus.fyi` en vez de `vcoo-onboarding.vercel.app`. Mejor branding |
| **P8** | **Tests E2E automatizados** | Medio | ✅ Implementado. Playwright para wizard + pytest para agente versusd/tick |

---

## 6. Recomendaciones — Próximas 3 Acciones

1. **Cifrar credenciales** (P1) — Mayor impacto en seguridad. Usar `hermes config set --encrypt`. 2-3h de implementación.

2. **Timeout + auto-skip** (P2) — Evita que pasos opcionales bloqueen todo el onboarding. 1h de implementación.

3. **Supabase Realtime** (P4) — Elimina polling del frontend. Mejor UX. 1-2h de implementación.

---

## 7. Decisiones Arquitectónicas Firmes

Estas decisiones NO deben renegociarse sin consultar al equipo VERSUS:

1. **versusd permanent watchdog + foreground supervisor tick** — sistema permanente, tick cada 60s
2. **Vercel + Supabase** — no WebSocket en producción (limitación de Vercel)
3. **COMMAND_MAP fijo** — seguridad por diseño, no comandos arbitrarios
4. **Tick unificado cada 60s** — tick reemplaza poll + heartbeat, 60s normal / 5s con comandos
5. **Archivar > Borrar** — VCOOs completados se conservan

---

*Documento generado automáticamente por MAGI. Consenso tripartito: 3/3.*
