# Decisiones de Diseño — VCOO Onboarding

## 1. Wizard Público + Registro de Cliente (Opción D — Flujo Magic Link)

### Contexto

Necesitábamos un mecanismo por el cual un operador pudiera invitar a un cliente a configurar su instancia VCOO, sin requerir que el cliente tuviera una cuenta pre-creada.

### Alternativas consideradas

| Opción | Descripción | Problemas |
|--------|-------------|-----------|
| **A** | Operador crea cuenta para el cliente y le envía credenciales | Fricción, inseguro (contraseñas enviadas por canales no seguros) |
| **B** | Cliente se registra con código de invitación de un solo uso | Similar a token pero sin JWT; más difícil de validar/revocar |
| **C** | OAuth social obligatorio | Dependencia de terceros, no todos los clientes quieren usarlo |
| **D (elegida)** | Token JWT en URL + registro self-service del cliente | Simple, seguro, sin estado compartido |

### Decisión

Elegimos la **Opción D**: el token de provision es un JWT firmado incluido en la URL de onboarding. El cliente abre la URL, ve el wizard público, y si no está registrado, completa un formulario de registro que incluye el token. El backend valida el token y enlaza al cliente con el VCOO en el momento del registro.

### Razones

1. **Seguridad**: El token es un JWT firmado con `MASTER_KEY`, con expiración configurable. No puede ser forjado ni modificado.
2. **Usabilidad**: El cliente solo necesita abrir un enlace. No requiere código adicional ni credenciales pre-compartidas.
3. **Patrón enterprise SaaS**: Similar a los "magic links" de Slack, Notion, etc. El cliente elige su propia contraseña.
4. **Idempotencia**: El token se almacena en BD con estado `used`; si expira, el operador puede regenerarlo sin perder el progreso del onboarding.
5. **Doble validación**: `lookup_provision_token()` para el wizard (read-only, no consume) y `validate_provision_token()` para el registro (consume atómicamente).

### Mecanismo

```
1. Operador → POST /vcoo → recibe onboarding_url con token JWT
2. Cliente abre onboarding_url → GET /setup/{token} (read-only)
3. Cliente se registra → POST /auth/client/register {token, name, email, password}
4. Backend valida token, lo marca used=true, crea cliente, lo enlaza al vcoo_id
5. Cliente recibe JWT y procede con el wizard
```

---

## 2. Dos Repositorios Separados (Frontend / Backend)

### Contexto

El proyecto consta de un frontend React (SPA) y un backend Python (FastAPI). Podríamos haberlos unificado en un monorepo o mantenerlos separados.

### Decisión

Elegimos **dos repositorios independientes**: `vcoo-dashboard` (frontend) y `vcoo-onboarding` (backend).

### Razones

1. **Ciclos de despliegue independientes**: El frontend se despliega en Vercel como sitio estático. El backend se despliega como funciones serverless. No hay razón para que compartan el mismo ciclo de release.
2. **Stacks tecnológicos diferentes**: React + TypeScript + Vite vs. Python + FastAPI + SQLAlchemy. Cada uno tiene sus propias dependencias, herramientas de build y configuraciones de CI/CD.
3. **Separación de concerns clara**: El frontend solo sabe de la URL de la API. El backend no sabe del frontend más allá de generar URLs de onboarding. Esto permite cambiar cualquiera de los dos sin afectar al otro.
4. **Escalabilidad del equipo**: Diferentes equipos o personas pueden trabajar en frontend y backend sin conflictos de merge ni coordinación de toolchains.

---

## 3. vcoo-supervisor (Reemplazo de versusd + health-reporter)

### Contexto

Originalmente había 3 sistemas de reporte superpuestos: `versusd` (watchdog bash), `health-reporter.py` (métricas Python) y el heartbeat del agente. Cada uno tenía configuraciones, ciclos y formatos diferentes.

### Decisión (Jul 2026)

Unificamos todo en **vcoo-supervisor**: un proceso Python modular con sistema de plugins que corre como servicio systemd.

### Arquitectura

```
vcoo-supervisor/
├── supervisor.py          ← Core con scheduler y plugin manager
├── plugins/
│   ├── health_reporter.py ← Métricas VPS + heartbeat al backend
│   ├── watchdog.py        ← pgrep Hermes, restart si caído
│   └── updater.py         ← Auto-update semanal
├── config.json            ← Config centralizada
└── vcoo-supervisor.service ← systemd unit
```

### Razones del cambio

1. **Centralización**: Un solo proceso, un solo cron, una sola configuración.
2. **Modularidad**: Cada plugin tiene una interfaz `start/tick/stop` y se activa/desactiva desde config.
3. **Autenticación**: El health reporter ahora envía `Authorization: Bearer` (antes no autenticaba).
4. **Métricas enriquecidas**: Reporta hostname, uptime, disco, versión del template y del supervisor.
5. **Mantenibilidad**: Python en lugar de bash permite mejor testing y manejo de errores.

### Componentes

- **`packages/vcoo-supervisor/supervisor.py`** — Core del supervisor.
- **`packages/vcoo-supervisor/plugins/health_reporter.py`** — Envía métricas VPS al backend cada 60s.
- **`packages/vcoo-supervisor/plugins/watchdog.py`** — Monitorea Hermes cada 30s y lo reinicia si es necesario.
- **`packages/vcoo-supervisor/plugins/updater.py`** — Ejecuta `hermes update` semanalmente.
- **`packages/vcoo-supervisor/vcoo-supervisor.service`** — Unidad systemd.

---

## 4. Hashing de Contraseñas con hashlib en Lugar de passlib + bcrypt

### Contexto

Python tiene librerías estándar para hashing de contraseñas: `passlib` con `bcrypt`. Sin embargo, al momento del desarrollo, `passlib 1.7.4` no era compatible con `bcrypt 5.0.0` (cambio en la API interna de bcrypt que rompió passlib).

### Alternativas consideradas

| Opción | Descripción | Problemas |
|--------|-------------|-----------|
| **passlib + bcrypt** | La solución "estándar" | Incompatibilidad entre passlib 1.7.4 y bcrypt 5.0.0. Solucionar requería versiones pinned o forks no oficiales. |
| **bcrypt directo** | Usar solo `bcrypt` | Dependencia externa, y `bcrypt` requiere compilación de C extensivo. |
| **hashlib (elegida)** | SHA-256 con salt aleatorio | Cero dependencias externas, suficiente para el caso de uso. |

### Decisión

Usamos **`hashlib`** con el algoritmo SHA-256 y un salt aleatorio de 16 bytes por contraseña.

### Formato

```
{salt_hex}:{sha256(salt + password).hexdigest()}
```

### Razones

1. **Evitar dependency hell**: No lidiamos con incompatibilidades entre passlib y bcrypt. No necesitamos versiones específicas ni forks.
2. **Cero dependencias externas**: `hashlib` es parte de la biblioteca estándar de Python. No requiere compilación de C ni extensiones nativas.
3. **Adecuado para el caso de uso**: Este no es un sistema bancario ni de alta seguridad. Es un panel de control interno para clientes empresariales. SHA-256 con salt por-password es más que suficiente para proteger contra ataques de tabla arcoíris y fuerza bruta básica.
4. **Migración futura**: Si en el futuro se requiere mayor seguridad (Argon2, bcrypt), la interfaz `hash_password`/`verify_password` está aislada en `auth.py` y es trivial de cambiar.

### Nota sobre bcrypt en el entorno

El directorio `backend/.venv/` contiene `bcrypt 5.0.0` y `passlib 1.7.4` instalados, pero **no se usan**. Quedan como artefactos de intentos previos. El código activo usa exclusivamente `hashlib`.

---

## 5. El Modelo VCOO No Tiene Relación Directa con Cliente

### Contexto

En el esquema de base de datos, la tabla `clients` tiene una FK `vcoo_id` que apunta a `vcoos.id`. La tabla `vcoos` no tiene una FK inversa hacia `clients`.

### Decisión

La relación es **unidireccional**: el cliente sabe a qué VCOO pertenece, pero el VCOO no sabe (a nivel de modelo) qué cliente lo posee.

### Razones

1. **VCOOs pre-provisionados**: Un operador puede crear VCOOs antes de que exista un cliente. El VCOO existe independientemente. Cuando el cliente se registra, se enlaza mediante `clients.vcoo_id`.
2. **Flexibilidad futura**: Un VCOO podría reasignarse a otro cliente (cambiando `clients.vcoo_id`). Un cliente podría tener múltiples VCOOs (añadiendo una tabla intermedia). El diseño actual no impide ninguna de estas evoluciones.
3. **Evolución planeada**: En el futuro, los operadores podrán crear VCOOs primero, configurar sus módulos, y luego asignarlos a clientes. La dirección actual de la FK soporta este flujo: el cliente se "cuelga" del VCOO.
4. **Simplicidad del modelo**: `VCOO` = recurso, `Client` = owner. El owner puede cambiar. El recurso no necesita saber quién lo posee actualmente.

### Representación actual

```
vcoos (id, name, status, created_at)
  ↑
  │ FK (vcoo_id)
clients (id, email, password_hash, name, vcoo_id)
```

Si en el futuro necesitamos la relación inversa:

```python
# En models.py, dentro de VCOO:
clients = relationship("Client", backref="vcoo")
```
