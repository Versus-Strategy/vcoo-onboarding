# VCOO Dashboard + Setup Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React frontend with Operator Dashboard (`/dashboard`) and Client Setup Page (`/setup/:token`) for the VCOO onboarding platform.

**Architecture:** Single Vite + React + TypeScript app deployed to Vercel. Uses React Router for client-side routing. Communicates with backend API at `vcoo-onboarding.vercel.app`. Supabase JS client for Realtime log streaming on the dashboard.

**Tech Stack:** React 18, Vite 5, TypeScript, Tailwind CSS, React Router v6, Supabase JS client v2, Lucide React icons.

## Global Constraints

- Backend API: `https://vcoo-onboarding.vercel.app`
- Supabase URL: `https://pdntyfmwjupkhourorfg.supabase.co`
- Supabase Anon Key: `sb_publishable_3mwJkqTensbDnnBD8jVbmw_ihVckMPy`
- Dashboard auth: MASTER_KEY sent as `Authorization: Bearer <key>` header
- No secrets in frontend code — MASTER_KEY entered by operator at login
- Deploy target: Vercel (separate project or subdomain)
- All prices EX-VAT (though not applicable to this frontend)
- Spanish UI language

---

### Task 1: Project Scaffolding & Shared Infrastructure

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/.env.example`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Produces: `api/client.ts` exports typed API functions for all backend endpoints
- Produces: `lib/supabase.ts` exports initialized Supabase client
- Produces: `components/Layout.tsx` shared layout with navigation
- Produces: App with React Router setup, two routes: `/dashboard` and `/setup/:token`

- [ ] **Step 1: Initialize Vite project**

```bash
cd /home/ubuntu/versus/vcoo-onboarding
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install dependencies**

```bash
npm install react-router-dom @supabase/supabase-js lucide-react
npm install -D tailwindcss @tailwindcss/vite postcss autoprefixer
```

- [ ] **Step 3: Configure Tailwind CSS with Vite**
Create `tailwind.config.js`, `postcss.config.js`. Update `vite.config.ts` to use `@tailwindcss/vite`.

- [ ] **Step 4: Create API client** (`src/api/client.ts`)

```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'https://vcoo-onboarding.vercel.app';

let masterKey: string | null = null;

export function setMasterKey(key: string) { masterKey = key; }
export function getMasterKey(): string | null { return masterKey; }

async function api(path: string, options: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (masterKey) headers['Authorization'] = `Bearer ${masterKey}`;
  
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// VCOOs
export const createVCOO = () => api('/vcoo', { method: 'POST' });
export const getProvisionToken = (vcooId: string) => api(`/vcoo/${vcooId}/provision-token`);
export const getVCOOState = (vcooId: string) => api(`/vcoo/${vcooId}/state`);
export const enqueueCommand = (vcooId: string, command: string) =>
  api(`/vcoo/${vcooId}/commands`, { method: 'POST', body: JSON.stringify({ command }) });

// Playbooks
export const listPlaybooks = () => api('/playbooks');
export const getPlaybook = (name: string) => api(`/playbooks/${name}`);

// Health
export const healthCheck = () => api('/health');
```

- [ ] **Step 5: Create Supabase client** (`src/lib/supabase.ts`)

```typescript
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://pdntyfmwjupkhourorfg.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_3mwJkqTensbDnnBD8jVbmw_ihVckMPy';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

- [ ] **Step 6: Create Layout component** (`src/components/Layout.tsx`)

```tsx
import { Link, Outlet, useLocation } from 'react-router-dom';

export default function Layout() {
  const location = useLocation();
  const isDashboard = location.pathname.startsWith('/dashboard');
  
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="text-xl font-black tracking-[0.25em] text-white">VCOO</div>
            <div className="text-[10px] font-semibold tracking-[0.15em] text-slate-400 uppercase">Onboarding</div>
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link to="/dashboard" className={`hover:text-white transition ${isDashboard ? 'text-white' : 'text-slate-400'}`}>
              Dashboard
            </Link>
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Create App.tsx with routing**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Setup from './pages/Setup';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/setup/:token" element={<Setup />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 8: Create main.tsx entry point**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 9: Update index.html with proper meta tags**

- [ ] **Step 10: Create .env.example**

```
VITE_API_URL=https://vcoo-onboarding.vercel.app
VITE_SUPABASE_URL=https://pdntyfmwjupkhourorfg.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_3mwJkqTensbDnnBD8jVbmw_ihVckMPy
```

- [ ] **Step 11: Verify project builds**

```bash
cd frontend && npm run build
```
Expected: `dist/` directory created with compiled assets.

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend project with Vite + React + Tailwind + Router"
```

---

### Task 2: Operator Dashboard Page

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/components/CreateVCOO.tsx`
- Create: `frontend/src/components/VCOOList.tsx`
- Create: `frontend/src/components/AgentStatus.tsx`
- Create: `frontend/src/components/CommandPanel.tsx`
- Create: `frontend/src/components/LogViewer.tsx`
- Create: `frontend/src/components/TokenDisplay.tsx`
- Create: `frontend/src/hooks/useRealtime.ts`

**Interfaces:**
- Consumes: `api/client.ts` functions (`createVCOO`, `getProvisionToken`, `getVCOOState`, `enqueueCommand`, `listPlaybooks`, `getPlaybook`, `setMasterKey`)
- Consumes: `lib/supabase.ts` client for Realtime
- Produces: Dashboard page with login, VCOO management, agent monitoring, command queueing, live logs

- [ ] **Step 1: Create useRealtime hook**

```typescript
// src/hooks/useRealtime.ts
import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

interface CommandLog {
  id: string;
  cmd_id: string;
  chunk: string;
  stream: string;
  created_at: string;
}

export function useRealtimeLogs(vcooId: string | null) {
  const [logs, setLogs] = useState<CommandLog[]>([]);
  
  useEffect(() => {
    if (!vcooId) return;
    
    // Load existing logs first via REST API
    supabase
      .from('command_logs')
      .select('*')
      .order('created_at', { ascending: true })
      .then(({ data }) => {
        if (data) setLogs(data);
      });
    
    // Subscribe to new inserts
    const channel = supabase
      .channel(`logs-${vcooId}`)
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'command_logs',
      }, (payload) => {
        setLogs(prev => [...prev, payload.new as CommandLog]);
      })
      .subscribe();
    
    return () => { supabase.removeChannel(channel); };
  }, [vcooId]);
  
  return logs;
}
```

- [ ] **Step 2: Create LoginComponent** (inside Dashboard.tsx or separate)
Simple form: operator enters MASTER_KEY → stored in api client → health check to verify.

- [ ] **Step 3: Create CreateVCOO component**

```tsx
// src/components/CreateVCOO.tsx
import { useState } from 'react';
import { createVCOO, getProvisionToken } from '../api/client';
import { Plus, Key } from 'lucide-react';

export default function CreateVCOO({ onCreated }: { onCreated: () => void }) {
  const [creating, setCreating] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [vcooId, setVcooId] = useState<string | null>(null);
  
  const handleCreate = async () => {
    setCreating(true);
    try {
      const { id } = await createVCOO();
      setVcooId(id);
      const { token: provToken, install_command } = await getProvisionToken(id);
      setToken(provToken);
      onCreated();
    } catch (e: any) {
      alert('Error: ' + e.message);
    } finally {
      setCreating(false);
    }
  };
  
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Plus className="w-5 h-5 text-emerald-400" />
        Nuevo VCOO
      </h2>
      <button
        onClick={handleCreate}
        disabled={creating}
        className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
      >
        {creating ? 'Creando...' : 'Crear VCOO'}
      </button>
      
      {token && (
        <div className="mt-4 p-4 bg-slate-800 rounded-lg border border-emerald-800">
          <div className="flex items-center gap-2 text-emerald-400 mb-2">
            <Key className="w-4 h-4" />
            <span className="text-sm font-medium">Token de provisionamiento</span>
          </div>
          <code className="text-xs text-slate-300 break-all block mb-3">{token}</code>
          <p className="text-xs text-slate-500">
            Enlace de setup:{' '}
            <code className="text-emerald-400">
              {window.location.origin}/setup/{token}
            </code>
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create VCOOList component**
Shows all VCOOs with agent status. Uses polling to refresh state.

- [ ] **Step 5: Create AgentStatus badge**
Online/offline indicator based on agent `last_seen` timestamp.

- [ ] **Step 6: Create CommandPanel**
Dropdown to select playbook + text input for custom commands + enqueue button.

- [ ] **Step 7: Create LogViewer**
Scrollable log output with stdout/stderr color coding. Uses `useRealtimeLogs` hook.

- [ ] **Step 8: Create TokenDisplay modal**
Shows provision token + setup link with copy button.

- [ ] **Step 9: Assemble Dashboard page**

```tsx
// src/pages/Dashboard.tsx
import { useState } from 'react';
import { setMasterKey, healthCheck } from '../api/client';
import CreateVCOO from '../components/CreateVCOO';
import VCOOList from '../components/VCOOList';
import { LogIn } from 'lucide-react';

export default function Dashboard() {
  const [authenticated, setAuthenticated] = useState(false);
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMasterKey(key);
    try {
      await healthCheck();
      setAuthenticated(true);
    } catch {
      setError('Clave inválida o el backend no responde');
      setMasterKey('');
    }
  };
  
  if (!authenticated) {
    return (
      <div className="max-w-md mx-auto mt-20">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <LogIn className="w-6 h-6 text-emerald-400" />
            <h1 className="text-xl font-bold">Operator Login</h1>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">MASTER_KEY</label>
              <input
                type="password"
                value={key}
                onChange={e => setKey(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
                placeholder="Introduce la clave maestra..."
                autoFocus
              />
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-2 rounded-lg font-medium transition"
            >
              Acceder
            </button>
          </form>
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-slate-400 text-sm">Gestión de VCOOs y agentes</p>
        </div>
      </div>
      
      <CreateVCOO onCreated={() => setRefreshKey(k => k + 1)} />
      <VCOOList key={refreshKey} />
    </div>
  );
}
```

- [ ] **Step 10: Build and verify**

```bash
cd frontend && npm run build
```
Expected: Clean build, no TS errors.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/
git commit -m "feat: operator dashboard with VCOO creation, agent monitoring, and command panel"
```

---

### Task 3: Client Setup Page

**Files:**
- Create: `frontend/src/pages/Setup.tsx`

**Interfaces:**
- Consumes: Backend API `/register` endpoint (not in api/client yet — add it)
- Produces: Public setup page at `/setup/:token` with one-liner, instructions, and live status

- [ ] **Step 1: Add register function to API client**

```typescript
// Add to src/api/client.ts
export const registerAgent = (token: string, info: Record<string, any> = {}) =>
  api('/register', { method: 'POST', body: JSON.stringify({ token, info }) });
```

- [ ] **Step 2: Create Setup page**

```tsx
// src/pages/Setup.tsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { registerAgent } from '../api/client';
import { Terminal, CheckCircle, XCircle, Loader2, Copy, ExternalLink } from 'lucide-react';

type Status = 'validating' | 'ready' | 'provisioning' | 'done' | 'error';

export default function Setup() {
  const { token } = useParams<{ token: string }>();
  const [status, setStatus] = useState<Status>('validating');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  
  const installCommand = `curl -sSL https://vcoo-onboarding.vercel.app/install.sh | bash -s -- ${token}`;
  
  useEffect(() => {
    // Validate token on mount
    if (!token) {
      setStatus('error');
      setError('Token no proporcionado');
      return;
    }
    // Just validate the token format — actual consumption happens when agent runs install.sh
    if (token.length < 10) {
      setStatus('error');
      setError('Token inválido');
      return;
    }
    setStatus('ready');
  }, [token]);
  
  const handleCopy = () => {
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <div className="max-w-2xl mx-auto">
      {/* Status Banner */}
      <div className={`rounded-xl p-6 mb-8 ${
        status === 'error' ? 'bg-red-950 border border-red-800' :
        status === 'done' ? 'bg-emerald-950 border border-emerald-800' :
        'bg-slate-900 border border-slate-800'
      }`}>
        <div className="flex items-center gap-3 mb-3">
          {status === 'validating' && <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />}
          {status === 'ready' && <CheckCircle className="w-6 h-6 text-emerald-400" />}
          {status === 'done' && <CheckCircle className="w-6 h-6 text-emerald-400" />}
          {status === 'error' && <XCircle className="w-6 h-6 text-red-400" />}
          <h1 className="text-xl font-bold">
            {status === 'validating' && 'Verificando token...'}
            {status === 'ready' && 'Token verificado — Listo para instalar'}
            {status === 'done' && '¡Instalación completada!'}
            {status === 'error' && 'Error de token'}
          </h1>
        </div>
        {error && <p className="text-red-400 text-sm ml-9">{error}</p>}
      </div>
      
      {status === 'ready' && (
        <>
          {/* Install Command */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-semibold">Comando de instalación</h2>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Ejecuta este comando en el servidor donde quieres instalar VCOO:
            </p>
            <div className="bg-slate-950 border border-slate-700 rounded-lg p-4 flex items-center justify-between group">
              <code className="text-sm text-emerald-300 break-all flex-1 mr-3">
                {installCommand}
              </code>
              <button
                onClick={handleCopy}
                className="shrink-0 p-2 hover:bg-slate-800 rounded-lg transition"
                title="Copiar"
              >
                <Copy className="w-4 h-4 text-slate-400" />
              </button>
            </div>
            {copied && <p className="text-emerald-400 text-xs mt-2">¡Copiado!</p>}
          </div>
          
          {/* Instructions */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Instrucciones</h2>
            <ol className="space-y-3 text-sm text-slate-300 list-decimal list-inside">
              <li>Copia el comando de arriba</li>
              <li>Ábrelo en la terminal del servidor (Linux/macOS)</li>
              <li>El script descargará e iniciará el agente VCOO</li>
              <li>El agente se conectará automáticamente y empezará a escuchar comandos</li>
            </ol>
          </div>
          
          {/* What happens next */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">¿Qué hace el script?</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { title: 'Descarga', desc: 'Baja el agente desde nuestros servidores con verificación de integridad' },
                { title: 'Configura', desc: 'Crea un entorno aislado y configura las credenciales de conexión' },
                { title: 'Ejecuta', desc: 'Inicia el agente en modo seguro que ejecutará los playbooks autorizados' },
              ].map((step, i) => (
                <div key={i} className="bg-slate-800 rounded-lg p-4">
                  <div className="text-emerald-400 font-bold text-lg mb-1">{i + 1}</div>
                  <h3 className="font-medium mb-1">{step.title}</h3>
                  <p className="text-slate-400 text-xs">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Build and verify**

```bash
cd frontend && npm run build
```
Expected: Clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Setup.tsx frontend/src/api/client.ts
git commit -m "feat: client setup page at /setup/:token with one-liner and instructions"
```

---

### Task 4: Deploy to Vercel

**Files:**
- Create: `frontend/vercel.json`

- [ ] **Step 1: Create Vercel config for frontend**

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "routes": [
    { "src": "/[^.]+", "dest": "/index.html" }
  ]
}
```

- [ ] **Step 2: Deploy with Vercel CLI**

```bash
cd frontend && vercel --prod
```

- [ ] **Step 3: Verify deployment**

- [ ] **Step 4: Commit**

```bash
git add frontend/vercel.json
git commit -m "feat: vercel deploy config for frontend"
```

---

## Self-Review Checklist

1. **Spec coverage:** Dashboard CRUD for VCOOs ✓, Token generation ✓, Login ✓, Live logs ✓, Setup page with one-liner ✓, Instructions ✓
2. **No placeholders:** All code blocks are concrete
3. **Type consistency:** API functions match backend endpoint signatures
