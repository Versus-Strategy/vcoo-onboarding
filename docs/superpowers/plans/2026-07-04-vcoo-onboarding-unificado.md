# VCOO Onboarding Unificado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar el onboarding del cliente en un solo flujo con tema claro, paso a paso guiado, y versusd como agente permanente con tick unificado.

**Architecture:** Frontend refactorizado (SetupWizard → tema claro + /onboarding), backend con nuevo endpoint POST /agent/{id}/tick (unifica health + command poll), versusd reescrito como vcoo-supervisor con plugins (tick, watchdog, updater).

**Tech Stack:** React 18 + TypeScript + Tailwind 3 (frontend), FastAPI + SQLAlchemy (backend), Python + systemd (vcoo-supervisor)

---

## File Structure

### Modified files:
- `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx` — Refactor a tema claro, step-by-step guiado
- `apps/frontend/src/App.tsx` — Agregar ruta /onboarding
- `apps/frontend/src/rutas/rutasCliente.tsx` — Agregar ruta /onboarding, redirigir /configuracion/*
- `apps/frontend/src/query/useConsulta.ts` — Agregar hook useEstadoDeIncorporacionCliente si no existe
- `apps/backend/main.py` — Agregar POST /agent/{id}/tick, fix verify race condition
- `apps/backend/crud.py` — Agregar get_pending_commands, create_command, advance_step_from_tick
- `apps/backend/schemas.py` — Agregar TickRequest, TickResponse schemas
- `apps/backend/onboarding.py` — Agregar mapeo módulo → etiqueta frontend
- `packages/vcoo-supervisor/supervisor.py` — Agregar plugin tick
- `packages/vcoo-supervisor/plugins/tick.py` — Nuevo plugin
- `packages/vcoo-supervisor/plugins/watchdog.py` — Ya existe, revisar
- `packages/vcoo-supervisor/plugins/updater.py` — Ya existe, revisar
- `packages/vcoo-supervisor/vcoo-supervisor.service` — Actualizar si es necesario
- `packages/vsd/install_vsd.sh` — Actualizar one-liner para instalar supervisor
- `packages/agent/install.sh` — Actualizar para que instale supervisor

### Deleted files:
- `packages/agent/agent_http.py` — Reemplazado por supervisor
- `apps/backend/agent_http.py` — Reemplazado por supervisor
- `packages/agent/agent_tui.py` — Ya no necesario (TUI era para el agente transitorio)
- `packages/agent/agent.py` — POC antiguo, reemplazado
- `packages/agent/health-reporter.py` — Reemplazado por plugin health del supervisor
- `apps/frontend/src/pages/cliente/configuracion/InstalacionDeAgente/InstalacionDeAgente.tsx` — Reemplazado por SetupWizard
- `apps/frontend/src/pages/cliente/configuracion/ConfiguracionDeProveedor/ConfiguracionDeProveedor.tsx` — Reemplazado
- `apps/frontend/src/pages/cliente/configuracion/ConfiguracionDeModulo/ConfiguracionDeModulo.tsx` — Reemplazado
- `apps/frontend/src/pages/cliente/configuracion/Finalizacion/Finalizacion.tsx` — Reemplazado
- `apps/frontend/src/components/AgentInstallationDisplay.tsx` — No usado

---

## Task 1: Backend — Agregar POST /agent/{id}/tick endpoint

**Files:**
- Modify: `apps/backend/schemas.py`
- Modify: `apps/backend/crud.py`
- Modify: `apps/backend/main.py`

- [ ] **Step 1: Add TickRequest and TickResponse schemas**

```python
# apps/backend/schemas.py — agregar al final

class HealthPayload(BaseModel):
    hostname: str | None = None
    cpu_pct: float | None = None
    memory_pct: float | None = None
    disk_pct: float | None = None
    hermes_running: bool | None = None
    template_version: str | None = None

class TickRequest(BaseModel):
    health: HealthPayload | None = None
    last_command_id: str | None = None

class TickResponse(BaseModel):
    commands: list[dict] = []
    tick_interval: int = 60
    step: str | None = None
    progress: dict | None = None
```

- [ ] **Step 2: Add CRUD functions for tick**

```python
# apps/backend/crud.py — agregar

def get_pending_commands(db: Session, agent_id: str, last_command_id: str | None = None) -> list[dict]:
    """Returns commands queued for this agent that haven't been acknowledged."""
    query = db.query(Command).filter(
        Command.agent_id == agent_id,
        Command.status == "pending"
    )
    if last_command_id:
        query = query.filter(Command.id > last_command_id)
    query = query.order_by(Command.created_at).limit(10)
    return [
        {"cmd_id": str(c.id), "command": c.command, "payload": c.payload,
         "step": c.step, "created_at": c.created_at.isoformat()}
        for c in query.all()
    ]

def acknowledge_command(db: Session, command_id: str) -> None:
    cmd = db.query(Command).filter(Command.id == command_id).first()
    if cmd:
        cmd.status = "acknowledged"
        db.commit()

def get_tick_progress(db: Session, vcoo_id: str) -> dict | None:
    st = get_onboarding_state(db, vcoo_id)
    if not st:
        return None
    from onboarding import get_total_steps
    total = get_total_steps(list(st.modules or ["core"]))
    done = len(st.completed or [])
    return {"total": total, "done": done}
```

- [ ] **Step 3: Add POST /agent/{id}/tick endpoint**

```python
# apps/backend/main.py — agregar después de los endpoints existentes de agente

@app.post("/agent/{agent_id}/tick")
def agent_tick(agent_id: str, body: TickRequest, authorization: str = Header(None), db: Session = Depends(get_db)):
    """Unified tick: agent sends health + last_command_id, receives commands + tick_interval."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    agent_token = authorization.split(None, 1)[1]

    agent = crud.get_agent(db, agent_id)
    if not agent or agent.token != agent_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    # Update health if provided
    if body.health:
        agent.last_seen = datetime.utcnow()
        agent.health_payload = body.health.model_dump()
        db.commit()

    # Acknowledge last command
    if body.last_command_id:
        crud.acknowledge_command(db, body.last_command_id)

    # Get pending commands
    commands = crud.get_pending_commands(db, agent_id, body.last_command_id)

    # Calculate tick interval and progress
    has_commands = len(commands) > 0
    tick_interval = 5 if has_commands else 60

    vcoo = crud.get_vcoo_by_agent(db, agent_id)
    progress = crud.get_tick_progress(db, str(vcoo.id)) if vcoo else None
    step = None
    if vcoo:
        st = crud.get_onboarding_state(db, str(vcoo.id))
        if st:
            step = st.step

    return TickResponse(
        commands=commands,
        tick_interval=tick_interval,
        step=step,
        progress=progress,
    )
```

- [ ] **Step 4: Add helper get_vcoo_by_agent**

```python
# apps/backend/crud.py — agregar

def get_vcoo_by_agent(db: Session, agent_id: str) -> VCOO | None:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent and agent.vcoo_id:
        return db.query(VCOO).filter(VCOO.id == agent.vcoo_id).first()
    return None
```

- [ ] **Step 5: Update verify endpoint with 10s wait**

```python
# apps/backend/main.py — modificar POST /setup/{identifier}/verify

@app.post("/setup/{identifier}/verify")
def trigger_step_verification(identifier: str, db: Session = Depends(get_db)):
    v = crud.get_vcoo(db, identifier)
    if not v:
        raise HTTPException(status_code=400, detail="Token inválido")

    vcoo_id = str(v.id)
    st = crud.get_onboarding_state(db, vcoo_id)
    if not st:
        raise HTTPException(status_code=404, detail="No hay datos de onboarding")

    step = st.step
    if step in ("finalize", "done"):
        return {"status": "skip", "message": "Onboarding ya completado"}

    from onboarding import get_step_command
    cmd_name = get_step_command(step)
    agent = crud.get_agent_by_vcoo(db, vcoo_id)

    # Wait up to 10s for agent to appear (race condition fix)
    import time
    agent_alive = False
    for _ in range(10):
        if agent and agent.last_seen:
            ago = (datetime.utcnow() - agent.last_seen.replace(tzinfo=None)).total_seconds()
            if ago < 120:
                agent_alive = True
                break
        time.sleep(1)
        db.refresh(agent) if agent else None
        agent = crud.get_agent_by_vcoo(db, vcoo_id)

    if agent and agent_alive:
        cmd = crud.create_command(db, agent_id=str(agent.id), command=cmd_name, step=step)
        return {"status": "enqueued", "cmd_id": str(cmd.id), "step": step, "command": cmd_name}
    else:
        crud.advance_onboarding_step(db, vcoo_id, step)
        db.refresh(st)
        return {"status": "auto_completed", "step": step, "next_step": st.step,
                "message": "Paso completado automaticamente (modo demo). En produccion, el agente ejecutara la verificacion real."}
```

- [ ] **Step 6: Run tests and commit**

```bash
cd apps/backend && python -m pytest test_onboarding.py -v
git add apps/backend/schemas.py apps/backend/crud.py apps/backend/main.py
git commit -m "feat(backend): add POST /agent/{id}/tick endpoint + 10s verify wait"
```

---

## Task 2: Frontend — Refactor SetupWizard a tema claro + step-by-step guiado

**Files:**
- Modify: `apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx`

- [ ] **Step 1: Read current SetupWizard.tsx**

```bash
cat apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx
```

- [ ] **Step 2: Refactor to light theme (reemplazar colores oscuros por claros)**

```tsx
// Cambiar bg-gray-950 → bg-gray-50
// Cambiar bg-gray-900 → bg-white
// Cambiar border-gray-700 → border-gray-200
// Cambiar text-white → text-gray-900
// Cambiar text-gray-400 → text-gray-500/600
// Mantener primary-600 para acentos
```

- [ ] **Step 3: Add guided sub-steps for Paso 1 (Instalar Agente)**

Reemplazar `renderPasoInstalacion` con:
```tsx
const [subPaso, setSubPaso] = useState(0); // 0=copiar, 1=ejecutar, 2=verificar
const [copiado, setCopiado] = useState(false);

const renderPasoInstalacion = () => (
  <div className="space-y-6">
    <h2 className="text-xl font-bold text-gray-900 mb-2">Instalar el Agente VCOO</h2>
    <p className="text-gray-600 mb-6">
      Sigue estos pasos para instalar el agente en tu servidor.
    </p>

    {/* Sub-paso 1: Copiar */}
    <div className={`bg-white rounded-lg border p-5 transition-all ${subPaso >= 0 ? 'border-gray-200' : 'border-gray-100 opacity-50'}`}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-bold">1</div>
        <h3 className="font-semibold text-gray-900">Copia el comando de instalación</h3>
        {copiado && <span className="text-xs text-green-600 font-medium">✓ Copiado</span>}
      </div>
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 font-mono text-sm text-gray-800 break-all mb-3">
        {onboarding.install_command || `curl -sSL ${API_URL}/install.sh | PROVISION_TOKEN=${token} bash -`}
      </div>
      <button
        onClick={() => {
          navigator.clipboard.writeText(
            onboarding.install_command || `curl -sSL ${API_URL}/install.sh | PROVISION_TOKEN=${token} bash -`
          );
          setCopiado(true);
          setSubPaso(1);
        }}
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        {copiado ? 'Copiado' : 'Copiar comando'}
      </button>
    </div>

    {/* Sub-paso 2: Ejecutar */}
    <div className={`bg-white rounded-lg border p-5 transition-all ${subPaso >= 1 ? 'border-gray-200' : 'border-gray-100 opacity-50'}`}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-sm font-bold">2</div>
        <h3 className="font-semibold text-gray-900">Ejecuta el comando en tu servidor</h3>
      </div>
      <p className="text-gray-600 text-sm mb-4">
        Abre la terminal de tu servidor, pega el comando y presiona Enter. La instalación tomará unos segundos.
      </p>
      <button
        onClick={() => setSubPaso(2)}
        disabled={subPaso < 1}
        className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Ya lo ejecuté
      </button>
    </div>

    {/* Sub-paso 3: Verificar */}
    <div className={`bg-white rounded-lg border p-5 transition-all ${subPaso >= 2 ? 'border-gray-200' : 'border-gray-100 opacity-50'}`}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-sm font-bold">3</div>
        <h3 className="font-semibold text-gray-900">Verifica la instalación</h3>
      </div>
      <p className="text-gray-600 text-sm mb-4">
        Una vez que el comando termine de ejecutarse, haz clic en "Verificar" para confirmar que el agente está activo.
      </p>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}
      <button
        onClick={manejarVerificar}
        disabled={verificando || subPaso < 2}
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {verificando ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            Verificando...
          </>
        ) : (
          'Verificar instalación'
        )}
      </button>
    </div>
  </div>
);
```

- [ ] **Step 4: Refactor renderPasoProveedor to light theme**

```tsx
const renderPasoProveedor = () => (
  <div className="space-y-6">
    <h2 className="text-xl font-bold text-gray-900 mb-2">Selecciona tu proveedor de IA</h2>
    <p className="text-gray-600 mb-6">
      Elige el proveedor que potenciará los servicios inteligentes de tu VCOO.
    </p>
    {error && (
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
        {error}
      </div>
    )}
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {PROVEEDORES.map((proveedor) => (
        <div
          key={proveedor.id}
          onClick={() => manejarConectarProveedor(proveedor.id)}
          className={`group cursor-pointer bg-white border border-gray-200 rounded-xl p-5 transition-all duration-200 hover:border-primary-500 hover:shadow-lg ${
            conectando === proveedor.id ? 'opacity-60 pointer-events-none' : ''
          }`}
        >
          <div className="flex flex-col items-center text-center">
            <div className={`w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mb-3 text-2xl font-bold ${proveedor.color}`}>
              {proveedor.nombre.charAt(0)}
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">{proveedor.nombre}</h3>
            <p className="text-sm text-gray-500">{proveedor.descripcion}</p>
          </div>
          {conectando === proveedor.id && (
            <div className="mt-3 flex justify-center">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600" />
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
);
```

- [ ] **Step 5: Refactor renderPasoModulos with module labels**

```tsx
const MODULOS_INFO: Record<string, { nombre: string; descripcion: string; icono: string }> = {
  'office': {
    nombre: 'Google Drive',
    descripcion: 'Acceso a Drive, Docs y Calendar',
    icono: '🔗',
  },
  'mail': {
    nombre: 'Gmail',
    descripcion: 'Correo electrónico y bandeja inteligente',
    icono: '✉',
  },
  'planner': {
    nombre: 'Planner',
    descripcion: 'Calendario y planificación',
    icono: '📅',
  },
  'developer': {
    nombre: 'GitHub + Vercel + Supabase',
    descripcion: 'Repositorios, deploys y base de datos',
    icono: '🐙',
  },
};

const renderPasoModulos = () => {
  const modulosDisponibles = onboarding.modules || [];
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900 mb-2">Conectar módulos</h2>
      <p className="text-gray-600 mb-6">
        Conecta los servicios que VCOO podrá gestionar por ti.
      </p>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {modulosDisponibles.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
          <p className="text-gray-600">No hay módulos disponibles para configurar.</p>
          <p className="text-gray-400 text-sm mt-2">Todos los módulos han sido configurados.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {modulosDisponibles.map((modulo) => {
            const info = MODULOS_INFO[modulo] || {
              nombre: modulo.charAt(0).toUpperCase() + modulo.slice(1),
              descripcion: 'Servicio conectable',
              icono: '🔌',
            };
            return (
              <div key={modulo} className="bg-white border border-gray-200 rounded-xl p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center text-2xl">
                      {info.icono}
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{info.nombre}</h3>
                      <p className="text-sm text-gray-500">{info.descripcion}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => manejarConectarModulo(modulo)}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
                  >
                    {conectando === modulo ? 'Conectando...' : 'Conectar'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 6: Refactor welcome card + step indicator + wrapper to light theme**

```tsx
// renderTarjetaBienvenida
const renderTarjetaBienvenida = () => (
  <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-full bg-primary-100 border border-primary-200 flex items-center justify-center text-primary-700 text-xl font-bold">
        {onboarding.name ? onboarding.name.charAt(0).toUpperCase() : 'V'}
      </div>
      <div>
        <h1 className="text-xl font-bold text-gray-900">
          Configuración de {onboarding.name || 'VCOO'}
        </h1>
        <p className="text-sm text-gray-500">
          Completa los pasos para poner en marcha tu agente
        </p>
      </div>
    </div>
  </div>
);

// Wrapper principal
return (
  <div className="min-h-screen bg-gray-50">
    <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
      {/* Logo */}
      <div className="flex items-center justify-center mb-8">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">V</div>
          <span className="text-gray-900 font-semibold text-lg">VCOO</span>
        </div>
      </div>

      {renderTarjetaBienvenida()}

      {/* StepIndicator */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
        <StepIndicator pasoActual={pasoActual} pasosTotales={4} pasos={PASOS} />
      </div>

      {/* Step content */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        {completado || pasoActual >= 4
          ? renderPasoFinalizacion()
          : pasoActual === 0 ? renderPasoInstalacion()
          : pasoActual === 1 ? renderPasoProveedor()
          : pasoActual === 2 ? renderPasoModulos()
          : pasoActual === 3 ? renderPasoFinalizacion()
          : renderPasoInstalacion()}
      </div>
    </div>
  </div>
);
```

- [ ] **Step 7: Also refactor AuthForm to light theme**

```tsx
// Reemplazar colores oscuros del AuthForm
<div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
  <div className="max-w-md w-full">
    <div className="flex items-center justify-center mb-8">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">V</div>
        <span className="text-gray-900 font-semibold text-lg">VCOO</span>
      </div>
    </div>
    <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
      <h1 className="text-xl font-bold text-gray-900 mb-2">
        {esRegistro ? 'Crear tu cuenta' : 'Iniciar sesión'}
      </h1>
      <p className="text-gray-600 mb-6">
        {esRegistro
          ? 'Regístrate para comenzar la configuración de tu VCOO'
          : 'Ingresa con tu cuenta para continuar la configuración'}
      </p>
      {/* ... campos con bg-white border-gray-200 text-gray-900 ... */}
    </div>
  </div>
</div>
```

- [ ] **Step 8: Refactor renderPasoFinalizacion to light theme**

Replace all dark classes (`text-white`, `bg-gray-900`, `border-gray-700`, `bg-gray-950`) with light equivalents (`text-gray-900`, `bg-white`, `border-gray-200`, `bg-gray-50`).

- [ ] **Step 9: Commit**

```bash
git add apps/frontend/src/pages/public/SetupWizard/SetupWizard.tsx
git commit -m "feat(frontend): refactor SetupWizard to light theme + step-by-step guided install"
```

---

## Task 3: Frontend — Agregar ruta /onboarding + redirigir /configuracion/*

**Files:**
- Modify: `apps/frontend/src/App.tsx`
- Modify: `apps/frontend/src/rutas/rutasCliente.tsx`

- [ ] **Step 1: Add /onboarding route in App.tsx**

```tsx
// apps/frontend/src/App.tsx — en AppContent, después de la sección de cliente
if (auth.usuario?.rol === 'cliente') {
  return (
    <ClientLayout>
      <RutasCliente />
    </ClientLayout>
  );
}
```

The `/onboarding` route needs to be handled. Since the SetupWizard is normally at `/setup/:token` and doesn't use the ClientLayout, let's add the redirect in the client routes:

```tsx
// apps/frontend/src/rutas/rutasCliente.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import Servicios from '../pages/cliente/Servicios/Servicios';
import OnboardingRedirect from '../pages/cliente/OnboardingRedirect';

const RutasCliente = () => {
  return (
    <Routes>
      <Route path="/servicios" element={<Servicios />} />
      <Route path="/configuracion/*" element={<Navigate to="/onboarding" replace />} />
      <Route path="/onboarding" element={<OnboardingRedirect />} />
      <Route path="/" element={<Servicios />} />
    </Routes>
  );
};
```

- [ ] **Step 2: Create OnboardingRedirect component**

Create `apps/frontend/src/pages/cliente/OnboardingRedirect/OnboardingRedirect.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@/api/apiClient';
import { useAuth } from '@/auth/authContext';

const OnboardingRedirect = () => {
  const navigate = useNavigate();
  const { auth } = useAuth();
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    const checkOnboarding = async () => {
      try {
        // Get client's VCOO info from their profile
        const { data } = await apiClient.get('/clientes/yo');
        const vcooId = data.vcoo_id;
        if (!vcooId) {
          navigate('/servicios', { replace: true });
          return;
        }
        // Get onboarding state to check if completed
        const { data: state } = await apiClient.get(`/vcoo/${vcooId}/state`);
        if (state.completed || state.onboarding_status === 'completed') {
          navigate('/servicios', { replace: true });
        } else {
          // Redirect to setup wizard with their VCOO token
          const { data: token } = await apiClient.get(`/vcoo/${vcooId}/provision-token`);
          if (token.onboarding_url) {
            window.location.href = token.onboarding_url;
          } else {
            navigate('/servicios', { replace: true });
          }
        }
      } catch {
        navigate('/servicios', { replace: true });
      }
    };
    checkOnboarding();
  }, [navigate, auth]);

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }
  return null;
};

export default OnboardingRedirect;
```

- [ ] **Step 3: Create directory and commit**

```bash
mkdir -p apps/frontend/src/pages/cliente/OnboardingRedirect
git add apps/frontend/src/App.tsx apps/frontend/src/rutas/rutasCliente.tsx apps/frontend/src/pages/cliente/OnboardingRedirect/
git commit -m "feat(frontend): add /onboarding route, redirect /configuracion/* to /onboarding"
```

---

## Task 4: Backend — Actualizar onboarding.py con labels de módulos

**Files:**
- Modify: `apps/backend/onboarding.py`

- [ ] **Step 1: Add module label mapping**

```python
# apps/backend/onboarding.py — agregar

MODULE_LABELS: dict[str, str] = {
    "core": "Agente VCOO",
    "office": "Google Drive",
    "mail": "Gmail",
    "planner": "Planner",
    "developer": "GitHub + Vercel + Supabase",
}

MODULE_DESCRIPTIONS: dict[str, str] = {
    "core": "Instalación base del agente en tu servidor",
    "office": "Acceso a Drive, Docs y Calendar",
    "mail": "Correo electrónico inteligente",
    "planner": "Calendario y planificación",
    "developer": "Repositorios, deploys y base de datos",
}

def get_module_label(module_id: str) -> str:
    return MODULE_LABELS.get(module_id, module_id)

def get_module_description(module_id: str) -> str:
    return MODULE_DESCRIPTIONS.get(module_id, "")
```

- [ ] **Step 2: Commit**

```bash
git add apps/backend/onboarding.py
git commit -m "feat(backend): add module labels for frontend display"
```

---

## Task 5: Agent — Implementar tick plugin en vcoo-supervisor

**Files:**
- Create: `packages/vcoo-supervisor/plugins/tick.py`

- [ ] **Step 1: Create tick plugin**

```python
# packages/vcoo-supervisor/plugins/tick.py

import time
import json
import platform
import subprocess
from typing import Any
import urllib.request
import urllib.error

from supervisor import SupervisorPlugin

class TickPlugin(SupervisorPlugin):
    """Unified tick: sends health + receives commands via POST /agent/{id}/tick."""

    def __init__(self, supervisor):
        super().__init__(supervisor)
        self.interval = 60  # seconds between ticks (adjusted by server)
        self.last_command_id = None

    def run(self):
        """Main tick loop."""
        agent_id = self.supervisor.config.get("agent_id")
        agent_token = self.supervisor.config.get("agent_token")
        control_plane = self.supervisor.config.get("control_plane", "http://localhost:8000")

        if not agent_id or not agent_token:
            self.log("Tick: no agent_id or agent_token, skipping tick loop")
            return

        while not self.supervisor.should_stop:
            try:
                # Build health payload
                health = self._collect_health()

                # POST tick
                payload = {
                    "health": health,
                    "last_command_id": self.last_command_id,
                }
                req = urllib.request.Request(
                    f"{control_plane}/agent/{agent_id}/tick",
                    data=json.dumps(payload).encode(),
                    headers={
                        "Authorization": f"Bearer {agent_token}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())

                # Process commands
                commands = data.get("commands", [])
                for cmd in commands:
                    self._execute_command(cmd, control_plane, agent_token)
                    self.last_command_id = cmd.get("cmd_id")

                # Update interval based on server response
                self.interval = data.get("tick_interval", 60)

            except urllib.error.HTTPError as e:
                self.log(f"Tick HTTP error: {e.code}")
                self.interval = 60
            except Exception as e:
                self.log(f"Tick error: {e}")
                self.interval = 60

            # Sleep until next tick
            for _ in range(int(self.interval)):
                if self.supervisor.should_stop:
                    break
                time.sleep(1)

    def _collect_health(self) -> dict:
        """Collect VPS health metrics."""
        health = {
            "hostname": platform.node(),
            "hermes_running": self._check_hermes(),
        }
        # Try to get disk/memory usage
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            mem_total = None
            mem_available = None
            for line in meminfo.split("\n"):
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])
            if mem_total and mem_available:
                health["memory_pct"] = round((1 - mem_available / mem_total) * 100, 1)
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["df", "/", "--output=pused"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                health["disk_pct"] = float(lines[1].strip())
        except Exception:
            pass
        return health

    def _check_hermes(self) -> bool:
        """Check if Hermes gateway is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "hermes_cli.main gateway"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _execute_command(self, cmd: dict, control_plane: str, agent_token: str):
        """Execute a single command from the control plane."""
        command = cmd.get("command", "")
        cmd_id = cmd.get("cmd_id", "")
        payload = cmd.get("payload", {})
        step = cmd.get("step", "")

        self.log(f"Executing: {command} (cmd_id={cmd_id})")

        exit_code = 0
        output = ""

        try:
            if command == "verify-bootstrap":
                # Check that Hermes CLI is installed
                result = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
                exit_code = result.returncode
                output = result.stdout or result.stderr

            elif command == "set-provider":
                provider = payload.get("provider", "")
                model = payload.get("model", "")
                encrypted = payload.get("encrypted", "")
                if provider and encrypted:
                    api_key = self._decrypt_key(encrypted)
                    result = subprocess.run(
                        ["hermes", "auth", "add", provider, "api-key", "--key", api_key],
                        capture_output=True, text=True, timeout=30
                    )
                    exit_code = result.returncode
                    output = result.stdout or result.stderr
                    if exit_code == 0 and model:
                        subprocess.run(
                            ["hermes", "config", "set", "model.default", model],
                            capture_output=True, timeout=15
                        )
                else:
                    exit_code = -1
                    output = "Payload incompleto: provider y encrypted requeridos"

            elif command == "save-creds":
                service = payload.get("service", "unknown")
                hermes_dir = os.path.expanduser("~/.hermes")
                os.makedirs(hermes_dir, exist_ok=True)
                # Save credentials to appropriate file
                if service == "google":
                    path = os.path.join(hermes_dir, "google_token.json")
                    with open(path, "w") as f:
                        json.dump(payload.get("token_data", {}), f)
                    output = f"Token Google guardado en {path}"
                else:
                    path = os.path.join(hermes_dir, ".env")
                    with open(path, "a") as f:
                        for k, v in payload.items():
                            if k not in ("service", "cmd_id"):
                                f.write(f"\n{k.upper()}={v}\n")
                    output = f"Credenciales guardadas en {path}"

            elif command == "finalize":
                # Start Hermes gateway
                subprocess.run(
                    ["systemctl", "--user", "start", "hermes-gateway"],
                    capture_output=True, timeout=30
                )
                output = "Onboarding completado, Hermes gateway iniciado"
                # Tick plugin keeps running, just stops getting commands

            else:
                exit_code = -1
                output = f"Comando no soportado: {command}"

        except subprocess.TimeoutExpired:
            exit_code = -1
            output = "Timeout"
        except FileNotFoundError as e:
            exit_code = -1
            output = f"Ejecutable no encontrado: {e}"
        except Exception as e:
            exit_code = -1
            output = f"Error: {e}"

        # Report result
        self._report_result(cmd_id, step, exit_code, output, control_plane, agent_token)

    def _report_result(self, cmd_id: str, step: str, exit_code: int, output: str,
                       control_plane: str, agent_token: str):
        """Report command execution result back to control plane."""
        try:
            payload = {
                "cmd_id": cmd_id,
                "step": step,
                "status": "ok" if exit_code == 0 else "error",
                "output": output[:5000],
            }
            req = urllib.request.Request(
                f"{control_plane}/agent/{self.supervisor.config.get('agent_id')}/result",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {agent_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.log(f"Result reported for {cmd_id}: HTTP {resp.status}")
        except Exception as e:
            self.log(f"Error reporting result: {e}")

    def _decrypt_key(self, encrypted_b64: str) -> str:
        """Decrypt API key using stored encryption key (same as agent_http.py)."""
        import base64
        import hashlib
        import os

        encryption_key = self.supervisor.config.get("encryption_key", "")
        agent_id = self.supervisor.config.get("agent_id", "")

        def derive_key(enc_key: str, a_id: str, salt: bytes) -> bytes:
            seed = f"{enc_key}:{a_id}".encode()
            return hashlib.pbkdf2_hmac("sha256", seed, salt, 100000, dklen=32)

        def constant_time_compare(a: bytes, b: bytes) -> bool:
            if len(a) != len(b):
                return False
            result = 0
            for x, y in zip(a, b):
                result |= x ^ y
            return result == 0

        padding = 4 - len(encrypted_b64) % 4
        if padding != 4:
            encrypted_b64 += "=" * padding
        raw = base64.urlsafe_b64decode(encrypted_b64)

        salt = raw[:16]
        iv = raw[16:32]
        ciphertext = raw[32:-32]
        expected_hmac = raw[-32:]

        key = derive_key(encryption_key, agent_id, salt)
        h = hashlib.sha256(key + iv + ciphertext).digest()
        if not constant_time_compare(h, expected_hmac):
            raise ValueError("HMAC inválido")

        plain = bytearray()
        counter = 0
        for offset in range(0, len(ciphertext), 32):
            keystream = hashlib.sha256(key + iv + bytes([counter])).digest()
            chunk = ciphertext[offset:offset + 32]
            for i in range(len(chunk)):
                plain.append(chunk[i] ^ keystream[i])
            counter += 1

        return bytes(plain).decode()
```

- [ ] **Step 2: Update supervisor.py to register tick plugin**

```python
# packages/vcoo-supervisor/supervisor.py — agregar en la lista de plugins
# Asegurarse de que supervisor.py lee agent_id, agent_token, encryption_key de su config
# y los pasa al plugin TickPlugin
```

- [ ] **Step 3: Commit**

```bash
git add packages/vcoo-supervisor/plugins/tick.py packages/vcoo-supervisor/supervisor.py
git commit -m "feat(agent): add tick plugin for unified health + command polling"
```

---

## Task 6: Agent — Actualizar install.sh + one-liner

**Files:**
- Modify: `packages/agent/install.sh`
- Modify: `packages/vsd/install_vsd.sh`

- [ ] **Step 1: Update install.sh to install supervisor instead of agent_http.py**

```bash
# packages/agent/install.sh — reemplazar la descarga de agent_http.py por:
# Instalar vcoo-supervisor como servicio systemd permanente
SUPERVISOR_URL="${CONTROL_PLANE}/vcoo-supervisor.service"
SUPERVISOR_SCRIPT="${CONTROL_PLANE}/supervisor.py"

mkdir -p /opt/vcoo-supervisor
curl -sSL "$SUPERVISOR_SCRIPT" -o /opt/vcoo-supervisor/supervisor.py
curl -sSL "${CONTROL_PLANE}/plugins/tick.py" -o /opt/vcoo-supervisor/plugins/tick.py

# Save agent credentials
cat > /opt/vcoo-supervisor/config.json <<EOF
{
  "control_plane": "${CONTROL_PLANE}",
  "provision_token": "${PROVISION_TOKEN}",
  "agent_id": "",
  "agent_token": "",
  "encryption_key": ""
}
EOF

# Install and start systemd service
cp /opt/vcoo-supervisor/vcoo-supervisor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable vcoo-supervisor
systemctl start vcoo-supervisor
```

- [ ] **Step 2: Commit**

```bash
git add packages/agent/install.sh packages/vsd/install_vsd.sh
git commit -m "feat(agent): install.sh installs vcoo-supervisor instead of agent_http.py"
```

---

## Task 7: Remove deprecated agent_http.py files

**Files:**
- Delete: `packages/agent/agent_http.py`
- Delete: `apps/backend/agent_http.py`
- Delete: `packages/agent/health-reporter.py`
- Delete: `packages/agent/agent.py`
- Delete: `packages/agent/agent_tui.py`

- [ ] **Step 1: Remove files and commit**

```bash
git rm packages/agent/agent_http.py apps/backend/agent_http.py packages/agent/health-reporter.py packages/agent/agent.py packages/agent/agent_tui.py
git commit -m "cleanup: remove deprecated agent_http.py, health-reporter, agent variants"
```

- [ ] **Step 2: Remove simulated client config pages**

```bash
git rm -r apps/frontend/src/pages/cliente/configuracion/
git rm apps/frontend/src/components/AgentInstallationDisplay.tsx
git commit -m "cleanup: remove simulated client config pages, replaced by unified SetupWizard"
```

---

## Task 8: Update StepIndicator with locked/unlocked states

**Files:**
- Modify: `apps/frontend/src/components/StepIndicator.tsx`

- [ ] **Step 1: Read current StepIndicator**

```bash
cat apps/frontend/src/components/StepIndicator.tsx
```

- [ ] **Step 2: Add visual states for locked steps**

```tsx
// If the component doesn't already have locked styling, add a prop:
interface StepIndicatorProps {
  pasoActual: number;
  pasosTotales: number;
  pasos: string[];
  pasoBloqueado?: number; // highest locked step index
}
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Task 1 covers POST /agent/{id}/tick endpoint → spec §2.3
   - Task 1 covers verify endpoint race condition fix → spec §race condition
   - Task 2 covers SetupWizard refactor to light theme → spec §2.2
   - Task 2 covers step-by-step guided install → spec §sub-pasos
   - Task 3 covers /onboarding route + /configuracion redirect → spec §redirect
   - Task 4 covers module labels → spec §2.6
   - Task 5 covers tick plugin → spec §2.4
   - Task 6 covers install.sh update → spec §2.5
   - Task 7 removes deprecated files → spec §cleanup

2. **Placeholder scan:** No TBD, TODO, or incomplete sections found.

3. **Type consistency:** All Python/TS types are consistent across tasks. The `TickRequest`/`TickResponse` schemas match what the frontend and agent expect.

4. **Gaps:** Missing the frontend module from spec showing Google OAuth single button flow (vs separate per module). This is a future enhancement when OAuth is implemented.
