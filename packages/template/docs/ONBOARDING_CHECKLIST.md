# 📋 Checklist de Onboarding — VCOO Virtual

**Versión:** 1.0.0  
**Cliente:** ______________________________  
**Fecha de inicio:** ______________________  
**Responsable VERSUS:** ___________________

Este documento lista todo lo que el cliente DEBE aportar SÍ o SÍ antes de que MAGI pueda empezar a operar. Está organizado por módulo contratado y prioridad.

---

## 🔴 Fase 0 — Imprescindible (CORE)

*Estos elementos son obligatorios para cualquier cliente, independientemente de los módulos contratados.*

### Infraestructura

| # | Elemento | Formato | Quién lo aporta | Para qué sirve |
|---|---|---|---|---|
| 1 | **Servidor Linux (VPS)** | IP + usuario SSH + clave pública (o acceso root) | Cliente (o VERSUS lo gestiona) | Donde se aloja MAGI |
| 2 | **Dominio o subdominio** (opcional) | `vcoo.clientedemo.com` | Cliente | Para el control panel |
| 3 | **Cuenta de correo corporativa** | email@cliente.com | Cliente | Para emitir facturas y comunicaciones |

### API Keys

| # | Elemento | Cómo obtenerlo | Formato |
|---|---|---|---|
| 4 | **API Key de OpenRouter** (recomendado) o Anthropic / DeepSeek | [openrouter.ai/keys](https://openrouter.ai/keys) → Crear API Key | `sk-or-v1-...` |
| 5 | **Token de Bot de Discord** | [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot → Reset Token | `MTIzNDU2Nzg5...` |
| 6 | **Token de Bot de Telegram** | [@BotFather](https://t.me/BotFather) en Telegram → `/newbot` | `123456:ABC-DEF...` |

> **⚠️ Intents de Discord necesarios:** Message Content Intent + Server Members Intent. Sin ellos, MAGI no puede leer los mensajes del equipo.

### Conocimiento del Negocio

| # | Elemento | Formato | Para qué sirve |
|---|---|---|---|
| 7 | **Documentación interna de la empresa** | PDFs, Google Docs, manuales, FAQs, tarifarios | Base de conocimiento que MAGI consulta para responder preguntas |
| 8 | **Reglas de negocio y procesos** | Documento escrito o sesión de entrevista | Define qué automatizar, cómo y cuándo |
| 9 | **Estructura del equipo** | Lista de nombres + roles + canales de Discord | Quién puede dar órdenes a MAGI y en qué canales |
| 10 | **Horario laboral / disponibilidad** | Texto (ej: "L-V 9:00-18:00") | Para que MAGI sepa cuándo reportar vs. cuándo esperar |

### Checklist de verificación CORE

- [ ] Servidor Linux provisionado y accesible vía SSH
- [ ] API Key de OpenRouter/Anthropic cargada en `.env`
- [ ] Bot de Discord creado, invitado al servidor, con intents activados
- [ ] Bot de Telegram creado
- [ ] Equipo notificado de los canales donde operará MAGI

---

## 🟡 Fase 1 — Módulo OFFICE (Google Workspace)

*Solo si el cliente contrata el módulo OFFICE.*

| # | Elemento | Cómo obtenerlo | Formato |
|---|---|---|---|
| 11 | **Cuenta de Google Workspace con permisos de admin** | El admin del dominio concede acceso | Email del admin |
| 12 | **Google Cloud Project** | [console.cloud.google.com](https://console.cloud.google.com) → Crear proyecto | Project ID |
| 13 | **APIs habilitadas** | Desde Cloud Console: habilitar Drive API, Docs API, Sheets API, Gmail API, Calendar API | — |
| 14 | **Credenciales OAuth 2.0** (descargar JSON) | Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID → Web application → Download JSON | `credentials.json` |
| 15 | **Autorización de dominio amplio** (domain-wide delegation) | Cloud Console → Security → API Controls → Domain-wide Delegation → Añadir Client ID + Scopes | — |
| 16 | **Estructura deseada de Google Drive** | Diagrama o lista de carpetas. Ej: `/Clientes/`, `/Finanzas/`, `/Recursos Humanos/` | Documento o entrevista |
| 17 | **Plantillas de documentos existentes** | Enlaces a Google Docs/Sheets actuales | URLs |
| 18 | **Cuenta de Google Calendar a sincronizar** | Email asociado al calendario | Email |

### Checklist OFFICE

- [ ] Google Cloud Project creado
- [ ] Drive API, Docs API, Sheets API, Gmail API habilitadas
- [ ] OAuth consent screen configurada (External + scopes)
- [ ] Credenciales OAuth descargadas
- [ ] Domain-wide delegation configurada
- [ ] Primer test: MAGI puede listar archivos en Drive

---

## 🟡 Fase 2 — Módulo MAIL (Bandeja Inteligente)

*Solo si el cliente contrata el módulo MAIL.*

| # | Elemento | Cómo obtenerlo | Formato |
|---|---|---|---|
| 19 | **Cuenta(s) de Gmail a monitorizar** | La(s) dirección(es) de email | Email(s) |
| 20 | **Contraseña de aplicación** (si 2FA activado) | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) | 16 caracteres |
| 21 | **OAuth Gmail** (recomendado, ya incluido en paso OFFICE) | Mismas credenciales OAuth que OFFICE + scope `gmail.modify` | — |
| 22 | **Reglas de filtrado y prioridades** | Criterios escritos. Ej: *"Si el asunto contiene 'urgente' notificar inmediatamente"* | Texto |
| 23 | **Plantillas de respuesta frecuentes** | Texto de respuestas habituales. Ej: acuse de recibo, confirmación de presupuesto, etc. | Texto |
| 24 | **Firmas de email** | Texto HTML de la firma corporativa | HTML o texto |
| 25 | **Lista de remitentes bloqueados o spam** | Direcciones a ignorar | Lista de emails |

### Checklist MAIL

- [ ] Cuenta(s) de Gmail identificadas
- [ ] OAuth/Gmail API habilitada
- [ ] MAGI puede leer la bandeja de entrada
- [ ] Reglas de filtrado definidas
- [ ] Plantillas de respuesta cargadas

---

## 🟡 Fase 3 — Módulo PLANNER (Trello)

*Solo si el cliente contrata el módulo PLANNER.*

| # | Elemento | Cómo obtenerlo | Formato |
|---|---|---|---|
| 26 | **API Key de Trello** | [trello.com/power-ups/admin](https://trello.com/power-ups/admin) → Crear Power-Up → API Key | `apikey` |
| 27 | **Token de Trello** | URL: `https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=VCOO&key=TU_API_KEY` | Token string |
| 28 | **ID(s) de tablero(s) a gestionar** | En la URL del tablero: `https://trello.com/b/XXXXXXXX/nombre` → la parte `XXXXXXXX` | Board ID |
| 29 | **Nombre de listas/columnas** (To Do, Doing, Done, etc.) | Lista de nombres. Ej: "Pendiente", "En progreso", "En revisión", "Completado" | Lista de strings |
| 30 | **Definición de "Done"** | Criterios. Ej: *"Una tarea está hecha cuando MAGI la ejecuta y adjunta el resultado como comentario"* | Texto |
| 31 | **Reuniones recurrentes** | Días/horario de reuniones de equipo | Calendario o texto |

### Checklist PLANNER

- [ ] API Key + Token de Trello generados
- [ ] Archivo `.env.trello` creado con las credenciales
- [ ] Tablero(s) identificado(s)
- [ ] MAGI puede leer tarjetas del tablero
- [ ] Columnas/flujo validado con el equipo
- [ ] Cron de higiene de backlog configurado

---

## 🟡 Fase 4 — Módulo DEVELOPER (Ingeniería)

*Solo si el cliente contrata el módulo DEVELOPER.*

| # | Elemento | Cómo obtenerlo | Formato |
|---|---|---|---|
| 32 | **GitHub Personal Access Token** (clásico o fine-grained) | [github.com/settings/tokens](https://github.com/settings/tokens) → scopes: `repo`, `workflow` | Token |
| 33 | **URLs de repositorios a gestionar** | `https://github.com/organizacion/repo` | URLs |
| 34 | **Organización de GitHub** (si aplica) | Nombre de la org | String |
| 35 | **Vercel Access Token** | [vercel.com/account/tokens](https://vercel.com/account/tokens) | Token |
| 36 | **Team ID de Vercel** | Vercel Dashboard → Team Settings → ID | ID |
| 37 | **Supabase Service Role Key** | Supabase Dashboard → Project Settings → API → `service_role` key | Key |
| 38 | **Supabase Project ID** | Supabase Dashboard → Project Settings → General → Reference ID | ID |
| 39 | **Estrategia de ramas (branch strategy)** | Documento. Ej: "main → producción, develop → staging, feature/* → PR" | Texto |
| 40 | **Reglas de CI/CD** | Cuándo se despliega automáticamente vs. manualmente | Texto |

### Checklist DEVELOPER

- [ ] GitHub Token generado con scopes `repo` + `workflow`
- [ ] MAGI añadido como colaborador a los repos (o GitHub App configurada)
- [ ] Vercel Token generado
- [ ] Supabase Service Key obtenida
- [ ] Estrategia de ramas y CI/CD documentada

---

## 📊 Resumen del Progreso

| Fase | Items | Checklist |
|---|---|---|
| **0 — CORE** | 10 items | [ ] |
| **1 — OFFICE** | 8 items | [ ] |
| **2 — MAIL** | 7 items | [ ] |
| **3 — PLANNER** | 6 items | [ ] |
| **4 — DEVELOPER** | 9 items | [ ] |

### Tiempo estimado por fase

| Fase | Tiempo cliente | Tiempo VERSUS |
|---|---|---|
| CORE | 30-60 min (crear bots, reunión inicial) | 2-3h (setup servidor + configuración) |
| OFFICE | 20-30 min (crear proyecto Google Cloud) | 1-2h (OAuth + pruebas) |
| MAIL | 10 min (compartir reglas) | 30 min (configurar filtros) |
| PLANNER | 10 min (generar token) | 30 min (configurar cron + pruebas) |
| DEVELOPER | 15 min (generar tokens) | 1h (configurar CI/CD) |

**Total cliente:** ~1-2 horas  
**Total VERSUS:** ~5-8 horas por cliente

---

## 🔐 Seguridad

- Todas las credenciales se almacenan con permisos `600` (solo lectura para el usuario)
- Los tokens de API viajan cifrados en el control plane
- MAGI nunca expone las credenciales en informes o mensajes
- Los tokens de Trello, GitHub, etc. pueden revocarse individualmente desde sus respectivas consolas

---

*Documento generado por MAGI (VCOO Virtual) — VERSUS Strategy SL · Junio 2026*
