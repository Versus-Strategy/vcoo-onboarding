import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import apiClient from '@/api/apiClient';
import { useAuth } from '@/auth/authContext';
import StepIndicator from '@/components/StepIndicator';
import Button from '@/components/Button';
import {
  DocumentTextIcon,
  EnvelopeIcon,
  CalendarIcon,
  CodeBracketIcon,
  PuzzlePieceIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
} from '@/components/icons';
import PhoneInput from 'react-phone-number-input';
import 'react-phone-number-input/style.css';

// ── Tipos ──

interface ModuleLabel {
  label: string;
  description: string;
}

interface ProviderInfo {
  id: string;
  nombre: string;
  descripcion: string;
  auth?: { type?: string; credential?: string; hint?: string };
}

interface OnboardingProgress {
  total: number;
  done: number;
}

interface OnboardingState {
  vcoo_id: string;
  name: string;
  modules: string[];
  module_labels: Record<string, ModuleLabel>;
  providers: ProviderInfo[];
  step: string;
  wizard_step: number;
  status: string;
  completed: string[];
  all_done: boolean;
  install_command: string;
  agent_online: boolean;
  progress: OnboardingProgress;
  checks: Record<string, string>;
  models: Record<string, string[] | { list?: string[]; models?: string[]; recommended?: string }>;
  requires_registration?: boolean;
  errors: Array<{ step: string; error: string; timestamp?: string; skipped_by_operator?: boolean }>;
  retry_count: Record<string, number>;
}

const PASOS = [
  'Instalar Agente',
  'Proveedor IA',
  'Módulos',
  'Finalización',
];

const MODULE_CHECK_KEY: Record<string, string> = {
  'google-drive': 'google',
  'gmail': 'google',
};

const BG_COLORS = [
  'bg-orange-500', 'bg-green-500', 'bg-blue-500',
  'bg-purple-500', 'bg-gray-500', 'bg-red-500',
  'bg-teal-500', 'bg-pink-500', 'bg-indigo-500',
  'bg-yellow-500', 'bg-cyan-500', 'bg-rose-500',
];

// ── AuthForm: registro e inicio de sesión para clientes (tema claro) ──

interface AuthFormProps {
  setupToken: string;
  onAutenticado: () => void;
}

const AuthForm = ({ setupToken, onAutenticado }: AuthFormProps) => {
  const { iniciarSesionCliente, registrarCliente, auth } = useAuth();
  const [esRegistro, setEsRegistro] = useState(true);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  useEffect(() => {
    if (auth.estaAutenticado) {
      onAutenticado();
    }
  }, [auth.estaAutenticado, onAutenticado]);

  const manejarSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorLocal(null);
    try {
      if (esRegistro) {
        if (!nombre.trim()) {
          setErrorLocal('El nombre es obligatorio');
          return;
        }
        await registrarCliente(nombre, email, password, setupToken);
      } else {
        await iniciarSesionCliente(email, password);
      }
      onAutenticado();
    } catch (err) {
      setErrorLocal(err instanceof Error ? err.message : 'Error de autenticación');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">
              V
            </div>
            <span className="text-gray-900 font-semibold text-lg">VCOO</span>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
          <h1 className="text-xl font-bold text-gray-900 mb-2">
            {esRegistro ? 'Crear tu cuenta' : 'Iniciar sesión'}
          </h1>
          <p className="text-gray-500 mb-6">
            {esRegistro
              ? 'Regístrate para comenzar la configuración de tu VCOO'
              : 'Ingresa con tu cuenta para continuar la configuración'}
          </p>

          <form onSubmit={manejarSubmit} className="space-y-4">
            {esRegistro && (
              <div>
                <label
                  htmlFor="auth-nombre"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Nombre
                </label>
                <input
                  id="auth-nombre"
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                  placeholder="Tu nombre"
                  required={esRegistro}
                />
              </div>
            )}

            <div>
              <label
                htmlFor="auth-email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Correo electrónico
              </label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                placeholder="correo@ejemplo.com"
                required
              />
            </div>

            <div>
              <label
                htmlFor="auth-password"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Contraseña
              </label>
              <input
                id="auth-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                placeholder="••••••••"
                required
                minLength={8}
              />
            </div>

            {errorLocal && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                {errorLocal}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full"
              disabled={auth.cargando}
              loading={auth.cargando}
            >
              {esRegistro ? 'Crear cuenta y comenzar' : 'Iniciar sesión'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={() => {
                setEsRegistro(!esRegistro);
                setErrorLocal(null);
              }}
              className="text-sm text-primary-600 hover:text-primary-700 transition-colors"
            >
              {esRegistro
                ? '¿Ya tienes cuenta? Inicia sesión'
                : '¿No tienes cuenta? Regístrate'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Componente principal ──

const SetupWizard = () => {
  const params = useParams<{ token: string }>();
  const token = params.token || window.location.pathname.replace('/setup/', '').replace('/onboarding/', '');
  const { auth } = useAuth();

  // All hooks must be at the top level, before any conditional returns
  const [mostrarWizard, setMostrarWizard] = useState(false);
  const [checkBase, setCheckBase] = useState(true);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conectando, setConectando] = useState<string | null>(null);
  const [esperandoConfirmacion, setEsperandoConfirmacion] = useState<string | null>(null);
  const [proveedorSeleccionado, setProveedorSeleccionado] = useState<string | null>(null);
  const [verMas, setVerMas] = useState(false);
  const [apiKeyValue, setApiKeyValue] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [modeloEnCurso, setModeloEnCurso] = useState<string | null>(null);
  const [modoSelectorModelo, setModoSelectorModelo] = useState(false);
  const [moduloSeleccionado, setModuloSeleccionado] = useState<string | null>(null);
  const [vistaActual, setVistaActual] = useState<number | null>(null);
  const [waQr, setWaQr] = useState<string | null>(null);
  const [waStatus, setWaStatus] = useState<string>('idle');
  const [waPairingCode, setWaPairingCode] = useState<string | null>(null);
  const [waPhone, setWaPhone] = useState<string>('');
  const [waPhoneInput, setWaPhoneInput] = useState<string | undefined>('');
  const mountedRef = useRef(true);
  const liveIntervals = useRef<Set<ReturnType<typeof setInterval>>>(new Set());

  useEffect(() => {
    const intervals = liveIntervals.current;
    return () => {
      mountedRef.current = false;
      intervals.forEach(clearInterval);
      intervals.clear();
    };
  }, []);

  // Check localStorage directly on mount for existing auth
  useEffect(() => {
    try {
      const stored = localStorage.getItem('vcoo-auth');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.token && Date.now() - parsed.marcaDeTiempo < 24 * 60 * 60 * 1000) {
          setMostrarWizard(true);
        }
      }
    } catch {
      // ignore
    } finally {
      setCheckBase(false);
    }
  }, []);

  // Also react to auth context changes (e.g., after registration)
  useEffect(() => {
    if (auth.estaAutenticado) {
      setMostrarWizard(true);
    }
  }, [auth.estaAutenticado]);

  // Poll until agent confirms connection (OAuth post-espera)
  useEffect(() => {
    if (!esperandoConfirmacion) return;
    const checkKey = MODULE_CHECK_KEY[esperandoConfirmacion] || esperandoConfirmacion;
    if ((checks as any)[checkKey] === 'ok' || (checks as any)[checkKey] === 'error') {
      setEsperandoConfirmacion(null);
      return;
    }
    const timeout = setTimeout(() => {
      if (mountedRef.current) {
        setEsperandoConfirmacion(null);
        setError('Tiempo de espera: el agente no confirmó la conexión. Verifica que el VPS esté activo.');
      }
    }, 60000);
    return () => clearTimeout(timeout);
  }, [esperandoConfirmacion, checks]);

  const fetchOnboarding = useCallback(async () => {
    if (!token) {
      setCargando(false);
      setError('Token de acceso inválido. Revisa el enlace.');
      return;
    }
    try {
      const { data } = await apiClient.get(`/setup/${token}`);
      if ((data as any).requires_registration) {
        const hayToken = (() => {
          try {
            const stored = localStorage.getItem('vcoo-auth');
            return stored ? !!JSON.parse(stored).token : false;
          } catch { return false; }
        })();
        if (hayToken) {
          try {
            const { data: authed } = await apiClient.get(`/setup/${token}`);
            if (!(authed as any)?.requires_registration) {
              setOnboarding(authed as OnboardingState);
              setError(null);
              return;
            }
          } catch { /* fall through */ }
          // Token exists but can't access — clear it and show AuthForm
          localStorage.removeItem('vcoo-auth');
          setMostrarWizard(false);
          setOnboarding(null);
          setError(null);
          return;
        }
        setOnboarding(null);
        setError(null);
        return;
      }
      setOnboarding(data as OnboardingState);
      setError(null);
    } catch (e) {
      console.error('Error fetching onboarding:', e);
      setError('Error de conexión');
    } finally {
      setCargando(false);
    }
  }, [token]);

  // Fetch onboarding data once we're authenticated and showing the wizard
  useEffect(() => {
    if (mostrarWizard) {
      fetchOnboarding();
    }
  }, [mostrarWizard, fetchOnboarding]);

  // ── Auto-verify when agent comes online on step 0 ──
  useEffect(() => {
    if (!mostrarWizard) return;
    if (onboarding?.agent_online && onboarding.wizard_step === 0) {
      apiClient.post(`/setup/${token}/verify`).then(() => {
        fetchOnboarding();
      }).catch(() => {
        setError('No se pudo verificar la instalación del agente. Asegúrate de que el agente esté ejecutándose y vuelve a intentar.');
      });
    }
  }, [onboarding?.agent_online, onboarding?.wizard_step, mostrarWizard, token, fetchOnboarding]);

  // ── Polling: auto-refresh every 15s ──
  useEffect(() => {
    if (!mostrarWizard) return;
    const interval = setInterval(fetchOnboarding, 5000);
    return () => clearInterval(interval);
  }, [mostrarWizard, fetchOnboarding]);

  // Refresh when user returns to tab (browsers throttle setInterval in background)
  useEffect(() => {
    if (!mostrarWizard) return;
    const onVisible = () => { if (document.visibilityState === 'visible') fetchOnboarding(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [mostrarWizard, fetchOnboarding]);

  // ── Timeout for provider loading ──
  const [providersTimeout, setProvidersTimeout] = useState(false);
  useEffect(() => {
    if ((onboarding?.providers || []).length === 0 && onboarding) {
      const t = setTimeout(() => setProvidersTimeout(true), 30000);
      return () => clearTimeout(t);
    }
    setProvidersTimeout(false);
  }, [onboarding?.providers, onboarding]);

  // ── Sync proveedor/selector state with onboarding data ──
  useEffect(() => {
    const raw = onboarding?.providers || [];
    const proveedorConfigurado = onboarding?.checks?.provider === 'ok';
    const configured = raw.find(p => p.id === 'opencode-go') || raw[0];
    const providerFound = proveedorSeleccionado ? raw.some(p => p.id === proveedorSeleccionado) : true;

    if (proveedorConfigurado && configured) {
      setProveedorSeleccionado(configured.id);
      setModoSelectorModelo(true);
    } else if (!proveedorSeleccionado && modoSelectorModelo) {
      setModoSelectorModelo(false);
    } else if (!providerFound) {
      setModoSelectorModelo(false);
      setProveedorSeleccionado(null);
    }
  }, [onboarding, modoSelectorModelo, proveedorSeleccionado]);

  // ── Auth form (not yet authenticated) ──

  if (!mostrarWizard) {
    // Still checking localStorage on first render
    if (checkBase || auth.cargando) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4" />
            <p className="text-gray-500">Verificando sesión...</p>
          </div>
        </div>
      );
    }

    return (
      <AuthForm
        setupToken={token || ''}
        onAutenticado={() => setMostrarWizard(true)}
      />
    );
  }

  // ── Cargando onboarding ──

  if (cargando) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4" />
          <p className="text-gray-500">Cargando configuración...</p>
        </div>
      </div>
    );
  }

  // ── Error loading onboarding ──

  if (error && !onboarding) {
    const esErrorAuth = error.includes('sesión') || error.includes('acceso');
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white border border-red-200 rounded-xl p-8 max-w-md w-full text-center shadow-sm">
          <ExclamationTriangleIcon className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 mb-2">
            {esErrorAuth ? 'Acceso denegado' : 'Error de conexión'}
          </h1>
          <p className="text-gray-500 mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <Button variant="primary" onClick={fetchOnboarding}>
              Reintentar
            </Button>
            {esErrorAuth && (
              <Button variant="secondary" onClick={() => { localStorage.removeItem('vcoo-auth'); window.location.reload(); }}>
                Cerrar sesión
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!onboarding) return null;

  // ── Wizard steps ──

  const pasoActual = vistaActual ?? onboarding.wizard_step ?? 0;
  const pasoBackend = onboarding.wizard_step ?? 0;
  // Mismo mapa que WIZARD_STEP_MAP en onboarding.py: backend step -> wizard index
  const wizardStepMap: Record<string, number> = {
    bootstrap: 0,
    'google-oauth': 1,
    'gmail-setup': 2,
    'trello-setup': 2,
    'github-setup': 2,
    'vercel-setup': 2,
    'supabase-setup': 2,
    finalize: 3,
    done: 3,
  };
  const pasosCompletados = new Set(
    (onboarding.completed || [])
      .map((s: string) => wizardStepMap[s])
      .filter((s: number | undefined): s is number => s !== undefined)
  ).size;
  // Checks reportados por el agente: "ok" | "missing" | "error"
  const checks = onboarding.checks || {};
  const modules = onboarding.modules || [];
  const completed = (onboarding.completed as string[]) || [];

  // Solo marcar como degradado si el paso ya se completó y ahora falta:
  // así "pendiente" (nunca configurado) ≠ "problemático" (configurado y roto).
  const pasosDegradados: number[] = [];
  if (checks.provider === "missing" && completed.includes('google-oauth')) {
    pasosDegradados.push(1);
  }
  if (checks.provider === "error" && completed.includes('google-oauth')) {
    pasosDegradados.push(1);
  }
  // Chequeos de módulos OAuth: el paso backend correspondiente debe estar completado
  // y el módulo debe estar habilitado para este VCOO.
    const checkToBackendStep: Record<string, { steps: string[]; mod: string }> = {
      google: { steps: ['gmail-setup'], mod: 'office' },
      trello: { steps: ['trello-setup'], mod: 'planner' },
      github: { steps: ['github-setup'], mod: 'developer' },
      vercel: { steps: ['vercel-setup'], mod: 'developer' },
      supabase: { steps: ['supabase-setup'], mod: 'developer' },
      whatsapp: { steps: ['whatsapp-setup'], mod: 'whatsapp' },
    };
  for (const [check, cfg] of Object.entries(checkToBackendStep)) {
    const val = checks[check];
    if ((val === "missing" || val === "error") && modules.includes(cfg.mod) && cfg.steps.some(s => completed.includes(s))) {
      if (!pasosDegradados.includes(2)) pasosDegradados.push(2);
    }
  }
  const totalSteps = onboarding.progress?.total || 4;
  const doneSteps = onboarding.progress?.done ?? pasosCompletados;
  const progreso = totalSteps > 0 ? Math.round((doneSteps / totalSteps) * 100) : 0;

  // ── Conectar proveedor ──

  const manejarConectarProveedor = async (service: string) => {
    if (!token) return;
    setProveedorSeleccionado(service);
  };

  const enviarApiKey = async (providerId: string) => {
    if (!apiKeyValue.trim() || !token) return;
    setEnviando(true);
    setError(null);
    try {
      await apiClient.post(`/setup/${token}/set-provider`, {
        provider: providerId,
        api_key: apiKeyValue.trim(),
      });
      // Poll for agent confirmation (max 60s, check every 5s)
      let ok = false;
      for (let i = 0; i < 12; i++) {
        if (i > 0) {
          await new Promise(r => setTimeout(r, 5000));
          if (!mountedRef.current) return;
        }
        const { data } = await apiClient.get(`/setup/${token}`);
        const chk: Record<string, string> = ((data as any).checks as Record<string, string>) || {};
        if (chk.provider === 'ok') { ok = true; break; }
      }
      if (ok) {
        // El proveedor confirmó, pero los modelos pueden tardar unos segundos
        // más en aparecer en las capabilities del agente. Polleamos hasta 30s
        // adicionales esperando la lista de modelos.
        let modelList: unknown[] = [];
        for (let i = 0; i < 6; i++) {
          const { data: fresh } = await apiClient.get(`/setup/${token}`);
          const allModels = (fresh as any).models || {};
          let provModels: unknown = undefined;
          for (const key of Object.keys(allModels)) {
            const m = allModels[key];
            if (m) { provModels = m; break; }
          }
          const extractList = (pm: unknown): unknown[] => {
            if (Array.isArray(pm)) return pm;
            if (pm && typeof pm === 'object') {
              const o = pm as Record<string, unknown>;
              return (o.list || o.models || []) as unknown[];
            }
            return [];
          };
          modelList = extractList(provModels);
          if (modelList.length > 0) break;
          await new Promise(r => setTimeout(r, 5000));
          if (!mountedRef.current) return;
        }
        if (modelList.length > 0) {
          await fetchOnboarding();
          setModoSelectorModelo(true);
        } else {
          await fetchOnboarding();
          setProveedorSeleccionado(null);
          setApiKeyValue('');
        }
      } else {
        setError('El agente no confirmó la configuración. Asegúrate de que el agente esté instalado y funcionando, luego vuelve a intentar.');
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        setError('No tienes acceso a este VCOO. Asegúrate de usar el enlace correcto o vuelve a registrarte.');
      } else if (status === 400) {
        setError('El agente aún no está instalado. Completa primero el paso 1.');
      } else {
        setError(err instanceof Error ? err.message : 'Error al conectar');
      }
    } finally {
      setEnviando(false);
    }
  };

  // ── Conectar módulo ──

  const MODULE_OAUTH: Record<string, { service: string; scopes: string }> = {
    office: { service: 'google-drive', scopes: 'Drive, Docs, Sheets y Slides' },
    mail: { service: 'gmail', scopes: 'Gmail' },
  };

  const MODULE_INSTRUCTIONS: Record<string, { pasos: string[] }> = {
    planner: { pasos: [
      '1. Obtén tu API key de Trello en https://trello.com/power-ups/admin',
      '2. Ejecuta: hermes config set trello.api_key TU_API_KEY',
      '3. Ejecuta: hermes config set trello.api_token TU_TOKEN',
    ]},
    whatsapp: { pasos: [
      '1. Haz clic en "Conectar WhatsApp" para iniciar el emparejamiento',
      '2. Escanea el código QR con la app de WhatsApp en tu teléfono',
      '3. La conexión se establecerá automáticamente',
    ]},
    developer: { pasos: [
      '1. GitHub: gh auth login',
      '2. Ejecuta: hermes config set github.token $(gh auth token)',
      '3. Vercel: vercel login && hermes config set vercel.token TU_TOKEN',
      '4. Supabase: supabase login && hermes config set supabase.access_token TU_ACCESS_TOKEN',
    ]},
  };

  const conectarOAuth = async (service: string) => {
    if (!token) return;
    try {
      const { data } = await apiClient.get(`/setup/${token}/auth-url?service=${service}`);
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      const popup = window.open(
        data.url,
        'google-oauth',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      if (!popup) {
        setError('El navegador bloqueó la ventana emergente. Permite popups para este sitio.');
        return;
      }
      setConectando(service);
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          liveIntervals.current.delete(checkClosed);
          if (mountedRef.current) {
            setConectando(null);
            setEsperandoConfirmacion(service);
            fetchOnboarding();
          }
        }
      }, 500);
      liveIntervals.current.add(checkClosed);
      const safetyTimer = setTimeout(() => {
        if (!popup.closed) {
          clearInterval(checkClosed);
          liveIntervals.current.delete(checkClosed);
          if (mountedRef.current) {
            setConectando(null);
            setError('La ventana de autorización no se cerró automáticamente. Ciérrala manualmente.');
          }
        }
      }, 120000);
      const handleMessage = (e: MessageEvent) => {
        if (e.data === 'oauth-complete') {
          clearInterval(checkClosed);
          liveIntervals.current.delete(checkClosed);
          clearTimeout(safetyTimer);
          if (mountedRef.current) {
            setConectando(null);
            setEsperandoConfirmacion(service);
            fetchOnboarding();
          }
          window.removeEventListener('message', handleMessage);
        }
      };
      window.addEventListener('message', handleMessage);
      const pollCleanup = setInterval(() => {
        if (popup.closed) {
          clearInterval(pollCleanup);
          liveIntervals.current.delete(pollCleanup);
          clearTimeout(safetyTimer);
          window.removeEventListener('message', handleMessage);
        }
      }, 1000);
      liveIntervals.current.add(pollCleanup);
    } catch {
      setError('Error al iniciar la conexión con Google');
      setConectando(null);
    }
  };

  const manejarConectarModulo = async (service: string) => {
    setModuloSeleccionado(service);
  };

  // ── Renderizado de cada paso ──

  const renderPasoInstalacion = () => {
    const cmdText = onboarding.install_command;

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Instalar el Agente VCOO
          </h2>
          <p className="text-gray-600">
            Copia el comando y ejecútalo en la terminal de tu VPS. El sistema detectará automáticamente cuando el agente esté instalado.
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <code className="text-sm text-gray-800 font-mono break-all whitespace-pre-wrap">
              {cmdText}
            </code>
            <button
              onClick={() => { navigator.clipboard.writeText(cmdText); fetchOnboarding(); }}
              className="flex-shrink-0 text-gray-400 hover:text-primary-600 transition-colors"
              title="Copiar comando"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
          </div>
        </div>

        {onboarding?.agent_online && !(onboarding.completed || []).includes('bootstrap') && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
            <p className="text-blue-700 font-medium">Agente conectado</p>
            <p className="text-sm text-blue-500 mt-1">Instalando componentes en el servidor...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    );
  };

  const renderPasoProveedor = () => {
    const raw = onboarding.providers || [];
    const recomendado = raw.find(p => p.id === 'opencode-go');
    const destacadosIds = new Set(['opencode-go', 'anthropic', 'openai', 'openai-api', 'openai-codex', 'google', 'gemini', 'copilot', 'openrouter']);
    const destacados = raw.filter(p => p.id !== 'opencode-go' && destacadosIds.has(p.id));
    const resto = raw.filter(p => p.id !== 'opencode-go' && !destacadosIds.has(p.id));

    if (modoSelectorModelo) {
      if (!proveedorSeleccionado) return null;
      const prov = raw.find(p => p.id === proveedorSeleccionado);
      if (!prov) return null;
      const modelsRaw = (onboarding.models || {})[prov.id] || {};
      const list: string[] = Array.isArray(modelsRaw) ? modelsRaw : ((modelsRaw.list || modelsRaw.models || []) as string[]);
      const recommended: string = Array.isArray(modelsRaw) ? '' : (modelsRaw.recommended || '');
      const rest = list.filter(m => m !== recommended);
      const configurar = async (modelo: string) => {
        setModeloEnCurso(modelo);
        try {
          await apiClient.post(`/setup/${token}/set-provider`, { provider: prov!.id, model: modelo });
          for (let i = 0; i < 15; i++) {
            await new Promise(r => setTimeout(r, 4000));
            const { data: fresh } = await apiClient.get(`/setup/${token}`);
            const cfg = (fresh as any).checks || {};
            if (cfg.model === 'ok') break;
          }
          await apiClient.post(`/setup/${token}/advance`);
          setVistaActual(null);
          setModoSelectorModelo(false);
          await fetchOnboarding();
          setProveedorSeleccionado(null);
          setApiKeyValue('');
          setModeloEnCurso(null);
        } catch { setError('Error al configurar el modelo'); setModeloEnCurso(null); }
      };
      return (
        <div className="space-y-6 max-w-2xl">
          <button onClick={() => setProveedorSeleccionado(null)} className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Volver a proveedores
          </button>
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-2">{prov?.nombre}</h3>
            <p className="text-sm text-gray-500 mb-4">{prov?.descripcion}</p>
            <div className="space-y-4">
              {recommended && (
                <div className="bg-primary-50 border border-primary-300 rounded-xl p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <p className="text-xs text-primary-600 font-medium mb-1">RECOMENDADO</p>
                      <p className="text-sm font-semibold text-primary-900 flex items-center gap-2">
                        {recommended}
                        {modeloEnCurso === recommended && (
                          <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </p>
                      <p className="text-xs text-primary-600 mt-1">Rápido y económico — ideal para empezar</p>
                    </div>
                    {modeloEnCurso === recommended ? (
                      <div className="flex items-center gap-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600" />
                        <span className="text-sm text-primary-600">Configurando...</span>
                      </div>
                    ) : (
                      <Button variant="primary" size="sm" disabled={!!modeloEnCurso}
                        onClick={() => configurar(recommended)}
                      >Seleccionar</Button>
                    )}
                  </div>
                </div>
              )}
              {rest.length > 0 && (
                <>
                  <p className="text-xs text-gray-400 font-medium">OTROS MODELOS</p>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {rest.map((m: string) => (
                      <div key={m} className={`px-3 py-2 text-sm border rounded-lg flex items-center justify-between ${modeloEnCurso === m ? 'bg-primary-50 border-primary-200' : 'border-gray-100 hover:bg-gray-50 cursor-pointer'}`}
                        onClick={() => !modeloEnCurso && configurar(m)}
                      >
                        <span className={modeloEnCurso === m ? 'text-primary-800' : 'text-gray-600'}>{m}</span>
                        {modeloEnCurso === m && (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600" />
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      );
    }

    if (proveedorSeleccionado) {
      const prov = raw.find(p => p.id === proveedorSeleccionado);
      const auth = prov?.auth;
      return (
        <div className="space-y-6 max-w-2xl">
          <button onClick={() => { setProveedorSeleccionado(null); setError(null); }}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Volver a proveedores
          </button>

          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-2">
              {prov?.nombre || proveedorSeleccionado}
            </h3>
            <p className="text-sm text-gray-500 mb-4">{prov?.descripcion}</p>

            {!auth || auth.type === 'manual' ? (
              <div className="text-sm text-gray-500 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="font-medium text-yellow-800 mb-1">Configuración manual</p>
                <p className="text-yellow-700 mb-2">{auth?.hint || 'Conecta este proveedor directamente en tu VPS.'}</p>
                {prov && (
                  <code className="block bg-gray-800 text-gray-100 rounded-lg p-3 font-mono text-xs">
                    hermes auth add {prov.id}
                  </code>
                )}
              </div>
            ) : modoSelectorModelo ? null
            : auth.type === 'api_key' ? (
              <form onSubmit={(e) => { e.preventDefault(); enviarApiKey(prov!.id); }} className="space-y-4">
                <p className="text-sm text-gray-600">{auth.hint}</p>
                <input type="password"
                  placeholder={`API Key (${auth.credential || ''})`}
                  value={apiKeyValue}
                  onChange={e => setApiKeyValue(e.target.value)}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                />
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
                )}
                <Button type="submit"
                  disabled={!apiKeyValue.trim() || enviando}
                  loading={enviando}
                  variant="primary" size="lg" className="w-full"
                >
                  {enviando ? 'Conectando...' : 'Conectar'}
                </Button>
              </form>
            ) : auth.type === 'oauth' ? (
              <div className="text-center py-6">
                <p className="text-sm text-gray-600 mb-4">{auth.hint}</p>
                <Button variant="primary" size="lg" className="w-full" disabled>
                  Conectar con {prov?.nombre}
                </Button>
                <p className="text-xs text-gray-400 mt-2">OAuth disponible próximamente</p>
              </div>
            ) : null}
          </div>
        </div>
      );
    }

    const renderRow = (proveedor: typeof raw[0], idx: number, rec: boolean) => (
      <div key={proveedor.id}
        onClick={() => manejarConectarProveedor(proveedor.id)}
        className={`flex items-center gap-3 px-4 py-2.5 rounded-lg cursor-pointer transition-colors ${
          rec
            ? 'bg-primary-50 border border-primary-200 hover:bg-primary-100'
            : 'hover:bg-gray-50 border border-transparent'
        }`}
      >
        <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${BG_COLORS[idx % BG_COLORS.length]}`}>
          {proveedor.nombre.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-medium ${rec ? 'text-primary-900' : 'text-gray-900'}`}>
              {proveedor.nombre}
            </span>
            {rec && (
              <span className="text-xs bg-primary-200 text-primary-800 px-2 py-0.5 rounded-full font-medium">
                Recomendado
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 truncate">{proveedor.descripcion}</p>
        </div>
        <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    );

    return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">
          Selecciona tu proveedor de IA
        </h2>
        <p className="text-gray-600">
          Elige el proveedor que potenciará los servicios inteligentes de tu VCOO.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {(onboarding.providers || []).length === 0 ? (
        <div className="text-center py-12">
          {providersTimeout ? (
            <>
              <ClockIcon className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
              <p className="text-gray-700 font-medium">El agente no reportó proveedores</p>
              <p className="text-gray-500 text-sm mt-2">Asegúrate de que el agente esté instalado y funcionando, luego haz clic en <strong>Refrescar</strong>.</p>
              <div className="mt-4">
                <Button variant="primary" size="sm" onClick={() => { fetchOnboarding(); setProvidersTimeout(false); }}>
                  Reintentar
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500 mx-auto mb-4" />
              <p className="text-gray-500">Esperando a que el agente reporte los proveedores disponibles...</p>
              <p className="text-gray-400 text-sm mt-2">Completa el paso 1 (Instalar Agente) para continuar.</p>
            </>
          )}
        </div>
      ) : (
      <div className="space-y-1 max-w-2xl">
        {recomendado && renderRow(recomendado, 0, true)}
        <div className="border-t border-gray-100 pt-2 mt-2">
          <p className="text-xs text-gray-400 font-medium mb-1 px-4">POPULARES</p>
          {destacados.map((p, i) => renderRow(p, i + 1, false))}
        </div>
        {resto.length > 0 && (
          <>
            {verMas && (
              <div className="border-t border-gray-100 pt-2 mt-2">
                <p className="text-xs text-gray-400 font-medium mb-1 px-4">OTROS</p>
                {resto.map((p, i) => renderRow(p, i + 1 + destacados.length, false))}
              </div>
            )}
            <button onClick={() => setVerMas(!verMas)}
              className="text-sm text-primary-600 hover:text-primary-700 px-4 py-2">
              {verMas ? 'Mostrar menos' : `Ver más (${resto.length} proveedores)`}
            </button>
          </>
        )}
      </div>
      )}
    </div>
    );
  };

  const renderPasoModulos = () => {
    const modulosDisponibles = (onboarding.modules || []).filter(m => m !== 'core');

    const modulosInfo: Record<
      string,
      { nombre: string; descripcion: string; icono: ReactNode }
    > = {
      office: {
        nombre: onboarding.module_labels?.office?.label || 'Google Drive',
        descripcion: onboarding.module_labels?.office?.description || 'Documentos, hojas de cálculo y almacenamiento en la nube',
        icono: <DocumentTextIcon className="w-7 h-7 text-gray-600" />,
      },
      mail: {
        nombre: onboarding.module_labels?.mail?.label || 'Gmail',
        descripcion: onboarding.module_labels?.mail?.description || 'Correo electrónico y bandeja de entrada inteligente',
        icono: <EnvelopeIcon className="w-7 h-7 text-gray-600" />,
      },
      planner: {
        nombre: onboarding.module_labels?.planner?.label || 'Calendar + Trello',
        descripcion: onboarding.module_labels?.planner?.description || 'Calendario, tareas y organización del trabajo',
        icono: <CalendarIcon className="w-7 h-7 text-gray-600" />,
      },
      developer: {
        nombre: onboarding.module_labels?.developer?.label || 'Developer',
        descripcion: onboarding.module_labels?.developer?.description || 'GitHub, Vercel, Supabase y herramientas para desarrolladores',
        icono: <CodeBracketIcon className="w-7 h-7 text-gray-600" />,
      },
    };

    if (moduloSeleccionado) {
      const info = modulosInfo[moduloSeleccionado];
      const instr = MODULE_INSTRUCTIONS[moduloSeleccionado];
      const oauthConfig = MODULE_OAUTH[moduloSeleccionado];
      const googleCheck = checks.google;
      const googleOk = googleCheck === 'ok';
      const googleError = googleCheck === 'error';
      return (
        <div className="space-y-6 max-w-2xl">
          <button onClick={() => setModuloSeleccionado(null)}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Volver a módulos
          </button>
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-2">{info?.nombre || moduloSeleccionado}</h3>
            <p className="text-sm text-gray-500 mb-4">{info?.descripcion}</p>
            {oauthConfig ? (
              <div className="text-center py-6">
                {googleOk ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                      <svg className="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-green-700 font-medium">Conectado a {info?.nombre}</p>
                    <p className="text-xs text-gray-400">Acceso a {oauthConfig.scopes}</p>
                  </div>
                ) : googleError ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center">
                      <svg className="w-7 h-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01" />
                      </svg>
                    </div>
                    <p className="text-red-700 font-medium">Conexión expirada o inválida</p>
                    <Button variant="primary" size="lg" onClick={() => { setEsperandoConfirmacion(null); conectarOAuth(oauthConfig.service); }}
                      loading={conectando === oauthConfig.service}>
                      Reconectar con Google
                    </Button>
                  </div>
                ) : esperandoConfirmacion === oauthConfig.service ? (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
                    <p className="text-sm font-medium text-gray-700">Autorización recibida</p>
                    <p className="text-xs text-gray-400">Esperando confirmación del agente en tu VPS...</p>
                    <div className="w-full max-w-xs bg-gray-200 rounded-full h-1.5 mt-2">
                      <div className="bg-primary-500 h-1.5 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                    </div>
                    <button onClick={() => setEsperandoConfirmacion(null)}
                      className="mt-1 text-xs text-gray-400 hover:text-gray-600">Cancelar</button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <p className="text-sm text-gray-600 mb-2">
                      Autoriza a VCOO a acceder a tus documentos de Google:
                    </p>
                    <p className="text-xs text-gray-400 mb-4">
                      {oauthConfig.scopes}
                    </p>
                    <Button variant="primary" size="lg" onClick={() => conectarOAuth(oauthConfig.service)}
                      loading={conectando === oauthConfig.service}>
                      {conectando === oauthConfig.service ? 'Conectando...' : 'Conectar con Google'}
                    </Button>
                  </div>
                )}
              </div>
            ) : moduloSeleccionado === 'whatsapp' ? (
              <div className="flex flex-col items-center text-center py-4">
                {waStatus === 'paired' || checks.whatsapp === 'ok' ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                      <svg className="w-7 h-7 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-green-700 font-medium">WhatsApp conectado</p>
                  </div>
                ) : waQr ? (
                  <div className="flex flex-col items-center gap-3">
                    <p className="text-sm font-medium text-gray-700 mb-1">Escanea con WhatsApp</p>
                    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                      <img src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(waQr)}`}
                        alt="WhatsApp QR" className="w-64 h-64" />
                    </div>
                    <p className="text-xs text-gray-400">Abre WhatsApp en tu teléfono → Escanea este código</p>
                  </div>
                ) : waStatus === 'pairing' ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
                    <p className="text-sm text-gray-600">Iniciando emparejamiento...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <p className="text-sm text-gray-600 mb-2">
                      Conecta WhatsApp para recibir y enviar mensajes desde VCOO.
                    </p>
                    <Button variant="primary" size="lg" onClick={async () => {
                      setWaStatus('pairing');
                      setError(null);
                      try {
                        await apiClient.post(`/setup/${token}/start-pair-whatsapp`);
                        const pollQr = setInterval(async () => {
                          try {
                            const { data } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                            if (!mountedRef.current) { clearInterval(pollQr); return; }
                            if (data.status === 'qr' && data.qr) {
                              setWaQr(data.qr);
                              setWaStatus('qr_ready');
                              clearInterval(pollQr);
                              liveIntervals.current.delete(pollQr);
                              const pollDone = setInterval(async () => {
                                try {
                                  const { data: d2 } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                                  if (!mountedRef.current) { clearInterval(pollDone); return; }
                                  if (d2.status === 'done' || d2.status === 'paired') {
                                    setWaStatus('paired');
                                    setWaQr(null);
                                    clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                                clearTimeout(pairTimeout);
                                fetchOnboarding();
                              } else if (d2.status === 'error') {
                                    setError('Error al emparejar WhatsApp');
                                    setWaStatus('idle');
                                    setWaQr(null);
                                    clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                              clearTimeout(pairTimeout);
                              }
                            } catch { /* retry */ }
                              }, 3000);
                              liveIntervals.current.add(pollDone);
                            } else if (data.status === 'done' || data.status === 'paired') {
                              setWaStatus('paired');
                              clearInterval(pollQr);
                              liveIntervals.current.delete(pollQr);
                              fetchOnboarding();
                            } else if (data.status === 'error') {
                              setError('Error al emparejar WhatsApp');
                              setWaStatus('idle');
                              clearInterval(pollQr);
                              liveIntervals.current.delete(pollQr);
                            }
                          } catch { /* retry */ }
                        }, 2000);
                        liveIntervals.current.add(pollQr);
                  } catch {
                    clearTimeout(pairTimeout);
                    if (mountedRef.current) {
                      setError('Error al iniciar emparejamiento');
                      setWaStatus('idle');
                    }
                  }
                    }}>
                      Conectar WhatsApp
                    </Button>
                  </div>
                )}
              </div>
            ) : instr ? (
              <div className="space-y-3">
                <p className="text-sm font-medium text-gray-700">Pasos para conectar:</p>
                {instr.pasos.map((paso, i) => (
                  <div key={i} className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3 border border-gray-100">{paso}</div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-yellow-700 bg-yellow-50 rounded-lg p-4">
                Configura este módulo directamente desde la terminal de tu VPS.
              </p>
            )}
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Configurar módulos
          </h2>
          <p className="text-gray-600">
            Conecta los servicios que VCOO podrá gestionar por ti.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {modulosDisponibles.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm">
            <p className="text-gray-500">No hay módulos disponibles para configurar.</p>
            <p className="text-gray-400 text-sm mt-2">
              Todos los módulos han sido configurados o no aplican a esta instancia.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {modulosDisponibles.map((modulo) => {
              const info = modulosInfo[modulo] || {
                nombre: modulo.charAt(0).toUpperCase() + modulo.slice(1),
                descripcion: 'Servicio conectable',
                icono: <PuzzlePieceIcon className="w-7 h-7 text-gray-600" />,
              };
              return (
                <div
                  key={modulo}
                  onClick={() => manejarConectarModulo(modulo)}
                  className="group cursor-pointer bg-white border border-gray-200 rounded-xl p-5 transition-all duration-200 hover:border-primary-500 hover:shadow-lg hover:shadow-primary-100/50"
                >
                  <div className="flex flex-col items-center text-center">
                    <div className={`w-14 h-14 rounded-full flex items-center justify-center mb-3 ${
                      modulo === 'office' && checks.google === 'ok' ? 'bg-green-100' :
                      modulo === 'mail' && checks.google === 'ok' ? 'bg-green-100' :
                      (modulo === 'office' || modulo === 'mail') && esperandoConfirmacion ? 'bg-yellow-100' :
                      'bg-gray-100'
                    }`}>
                      {modulo === 'office' && checks.google === 'ok' ? <CheckCircleIcon className="w-7 h-7 text-green-600" /> :
                       modulo === 'mail' && checks.google === 'ok' ? <CheckCircleIcon className="w-7 h-7 text-green-600" /> :
                       (modulo === 'office' || modulo === 'mail') && esperandoConfirmacion ? (
                         <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-600"></div>
                       ) : info.icono}
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">
                      {info.nombre}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {checks.google === 'ok' && (modulo === 'office' || modulo === 'mail') ? 'Conectado' :
                       (modulo === 'office' || modulo === 'mail') && esperandoConfirmacion ? 'Confirmando...' :
                       info.descripcion}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Canales de comunicación ── */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <h3 className="text-lg font-bold text-gray-900">Canales de comunicación</h3>
          </div>
          <p className="text-sm text-gray-500 mb-4">Conecta canales para que VCOO pueda comunicarse con tus clientes.</p>

          {checks.whatsapp === 'ok' ? (
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
              <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-green-700">WhatsApp conectado</p>
                <p className="text-xs text-green-500">El canal está activo y funcionando</p>
              </div>
            </div>
          ) : waQr ? (
            <div className="flex flex-col items-center text-center py-4">
              <p className="text-sm font-medium text-gray-700 mb-3">Escanea con WhatsApp</p>
              <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
                <img src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(waQr)}`}
                  alt="WhatsApp QR" className="w-64 h-64" />
              </div>
              <p className="text-xs text-gray-400 mt-3">Abre WhatsApp en tu teléfono → Escanea este código</p>
              <button onClick={() => { setWaQr(null); setWaStatus('idle'); }}
                className="mt-3 text-sm text-primary-600 hover:text-primary-700">Cancelar</button>
            </div>
          ) : waPairingCode ? (
            <div className="flex flex-col items-center text-center py-4">
              <p className="text-sm font-medium text-gray-700 mb-1">Código de emparejamiento</p>
              <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl px-8 py-5 my-3">
                <p className="text-3xl font-mono font-bold tracking-widest text-gray-900 select-all">
                  {waPairingCode.match(/.{1,4}/g)?.join(' ') || waPairingCode}
                </p>
              </div>
              <p className="text-xs text-gray-500 max-w-xs">
                Abre WhatsApp en tu teléfono → Ajustes → Dispositivos vinculados → Vincular un dispositivo →
                Introduce este código
              </p>
              <p className="text-xs text-gray-400 mt-2">O usa el número <strong>{waPhone}</strong> en WhatsApp</p>
              <button onClick={() => { setWaPairingCode(null); setWaStatus('idle'); }}
                className="mt-3 text-sm text-primary-600 hover:text-primary-700">Cancelar</button>
            </div>
          ) : waStatus === 'pairing' ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
              <p className="text-sm text-gray-600">Iniciando emparejamiento...</p>
            </div>
          ) : waStatus === 'input_phone' ? (
            <div className="flex flex-col items-center gap-3 py-2">
              <p className="text-sm text-gray-600 mb-1">Introduce tu número de teléfono de WhatsApp:</p>
              <div className="w-full max-w-xs [&_.PhoneInput]:flex [&_.PhoneInput]:gap-2 [&_.PhoneInput_input]:flex-1 [&_.PhoneInput_input]:px-3 [&_.PhoneInput_input]:py-2 [&_.PhoneInput_input]:border [&_.PhoneInput_input]:border-gray-300 [&_.PhoneInput_input]:rounded-lg [&_.PhoneInput_input]:text-center [&_.PhoneInput_input]:text-lg [&_.PhoneInput_input]:font-mono [&_.PhoneInput_input]:focus:outline-none [&_.PhoneInput_input]:focus:ring-2 [&_.PhoneInput_input]:focus:ring-primary-500">
                <PhoneInput
                  defaultCountry="ES"
                  placeholder="612 34 56 78"
                  value={waPhoneInput}
                  onChange={setWaPhoneInput}
                  className="w-full"
                />
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setWaStatus('idle')}>Cancelar</Button>
                <Button variant="primary" size="sm" onClick={async () => {
                  const phone = waPhoneInput;
                  if (!phone) { setError('Introduce un número de teléfono'); return; }
                  setWaStatus('pairing');
                  const pairTimeout = setTimeout(() => {
                    if (mountedRef.current) {
                      setError('Tiempo de espera agotado. Verifica que el agente esté activo.');
                      setWaStatus('idle');
                    }
                  }, 30000);
                  setError(null);
                  try {
                    await apiClient.post(`/setup/${token}/start-pair-whatsapp`, { phone });
                    const pollPair = setInterval(async () => {
                      try {
                        const { data } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                        if (!mountedRef.current) { clearInterval(pollPair); return; }
                        if (data.status === 'pairing_code' && data.code) {
                          setWaPairingCode(data.code);
                          setWaPhone(data.phone || phone);
                          setWaStatus('code_ready');
                          clearInterval(pollPair);
                          liveIntervals.current.delete(pollPair);
                          clearTimeout(pairTimeout);
                          const pollDone = setInterval(async () => {
                            try {
                              const { data: d2 } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                              if (!mountedRef.current) { clearInterval(pollDone); return; }
                              if (d2.status === 'done' || d2.status === 'paired' || d2.status === 'connected') {
                                setWaStatus('paired');
                                setWaPairingCode(null);
                                clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                                fetchOnboarding();
                              } else if (d2.status === 'error') {
                                setError('Error al emparejar WhatsApp');
                                setWaStatus('idle');
                                setWaPairingCode(null);
                                clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                              }
                            } catch { /* retry */ }
                          }, 3000);
                          liveIntervals.current.add(pollDone);
                        } else if (data.status === 'done' || data.status === 'paired' || data.status === 'connected') {
                          setWaStatus('paired');
                          setWaPairingCode(null);
                          clearInterval(pollPair);
                          liveIntervals.current.delete(pollPair);
                          clearTimeout(pairTimeout);
                          fetchOnboarding();
                        } else if (data.status === 'error') {
                          setError('Error al emparejar WhatsApp');
                          setWaStatus('idle');
                          clearInterval(pollPair);
                          liveIntervals.current.delete(pollPair);
                          clearTimeout(pairTimeout);
                        }
                      } catch { /* retry */ }
                    }, 2000);
                    liveIntervals.current.add(pollPair);
                  } catch {
                    if (mountedRef.current) {
                      setError('Error al iniciar emparejamiento');
                      setWaStatus('idle');
                    }
                  }
                }}>
                  Obtener código
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
              <div className="flex items-center gap-3">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-gray-900">WhatsApp</p>
                  <p className="text-xs text-gray-500">Recibe y envía mensajes</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setWaStatus('input_phone')}>
                  Usar código
                </Button>
                <Button variant="primary" size="sm" onClick={async () => {
                  setWaStatus('pairing');
                  setError(null);
                  try {
                    await apiClient.post(`/setup/${token}/start-pair-whatsapp`);
                    const pollQr = setInterval(async () => {
                      try {
                        const { data } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                        if (!mountedRef.current) { clearInterval(pollQr); return; }
                        if (data.status === 'qr' && data.qr) {
                          setWaQr(data.qr);
                          setWaStatus('qr_ready');
                          clearInterval(pollQr);
                          liveIntervals.current.delete(pollQr);
                          const pollDone = setInterval(async () => {
                            try {
                              const { data: d2 } = await apiClient.get(`/setup/${token}/whatsapp-qr`);
                              if (!mountedRef.current) { clearInterval(pollDone); return; }
                              if (d2.status === 'done' || d2.status === 'paired' || d2.status === 'connected') {
                                setWaStatus('paired');
                                setWaQr(null);
                                clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                                fetchOnboarding();
                              } else if (d2.status === 'error') {
                                setError('Error al emparejar WhatsApp');
                                setWaStatus('idle');
                                setWaQr(null);
                                clearInterval(pollDone);
                                liveIntervals.current.delete(pollDone);
                              }
                            } catch { /* retry */ }
                          }, 3000);
                          liveIntervals.current.add(pollDone);
                        } else if (data.status === 'done' || data.status === 'paired' || data.status === 'connected') {
                          setWaStatus('paired');
                          clearInterval(pollQr);
                          liveIntervals.current.delete(pollQr);
                          fetchOnboarding();
                        } else if (data.status === 'error') {
                          setError('Error al emparejar WhatsApp');
                          setWaStatus('idle');
                          clearInterval(pollQr);
                          liveIntervals.current.delete(pollQr);
                        }
                      } catch { /* retry */ }
                    }, 2000);
                    liveIntervals.current.add(pollQr);
                  } catch {
                    if (mountedRef.current) {
                      setError('Error al iniciar emparejamiento');
                      setWaStatus('idle');
                    }
                  }
                }}>
                  Escanear QR
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderPasoFinalizacion = () => {
    const MODULE_CHECK_KEYS: Record<string, string[]> = {
      office: ['google'],
      mail: ['google'],
      planner: ['trello'],
      developer: ['github', 'vercel', 'supabase'],
    };
    const items: { label: string; ok: boolean }[] = [
      { label: 'Agente instalado y activo', ok: onboarding.agent_online === true },
      { label: 'Proveedor de IA configurado', ok: checks.provider === 'ok' },
      {
        label: 'Módulos conectados',
        ok: modules.every((m: string) =>
          m === 'core' || (MODULE_CHECK_KEYS[m] || []).every(k => checks[k] === 'ok')
        ),
      },
      { label: 'Canal de comunicación', ok: checks.whatsapp === 'ok' },
    ];
    const allOk = items.every(i => i.ok);
    return (
    <div className="text-center py-8">
      <div className={`w-16 h-16 rounded-full mx-auto mb-6 flex items-center justify-center ${allOk ? 'bg-green-100' : 'bg-yellow-100'}`}>
        {allOk ? (
          <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="h-8 w-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        )}
      </div>
      <h1 className={`text-2xl font-bold mb-2 ${allOk ? 'text-gray-900' : 'text-yellow-800'}`}>
        {allOk ? 'Todo listo' : 'Algo necesita atención'}
      </h1>
      <p className="text-gray-500 mb-8 max-w-md mx-auto">
        {allOk ? 'Tu VCOO está configurado y funcionando.' : 'Algunos componentes requieren configuración.'}
      </p>
      <div className="max-w-sm mx-auto space-y-3">
        {items.map((item, i) => (
          <div key={i} className={`flex items-center gap-3 rounded-lg px-4 py-3 ${item.ok ? 'bg-gray-50' : 'bg-yellow-50 border border-yellow-200'}`}>
            <div className={`w-2 h-2 rounded-full ${item.ok ? 'bg-green-500' : 'bg-yellow-500'}`} />
            <span className={`text-sm ${item.ok ? 'text-gray-700' : 'text-yellow-800'}`}>
              {item.label} {!item.ok && '— pendiente'}
            </span>
          </div>
        ))}
      </div>
    </div>
    );
  };

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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">
              V
            </div>
            <span className="text-gray-900 font-semibold text-lg">VCOO</span>
          </div>
        </div>

        {renderTarjetaBienvenida()}

        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
          <StepIndicator
            pasoActual={pasoActual}
            pasoCompletado={pasosCompletados}
            pasosTotales={4}
            pasos={PASOS}
            pasosDegradados={pasosDegradados}
            progreso={progreso}
            maxUnlocked={pasoBackend + 1}
            onStepClick={(idx) => {
              if (idx <= pasoBackend + 1 && idx !== pasoActual) {
                setVistaActual(idx);
                setProveedorSeleccionado(null);
                setModuloSeleccionado(null);
                setModoSelectorModelo(false);
                setModeloEnCurso(null);
                setError(null);
              }
            }}
          />
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
          {pasoActual === 3 || pasoActual >= 4
            ? renderPasoFinalizacion()
            : pasoActual === 0
            ? renderPasoInstalacion()
            : pasoActual === 1
            ? renderPasoProveedor()
            : pasoActual === 2
            ? renderPasoModulos()
            : renderPasoInstalacion()}
        </div>


      </div>
    </div>
  );
};

export default SetupWizard;
