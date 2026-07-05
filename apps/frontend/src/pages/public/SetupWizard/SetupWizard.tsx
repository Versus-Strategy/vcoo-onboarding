import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import apiClient, { API_URL } from '@/api/apiClient';
import { useAuth } from '@/auth/authContext';
import StepIndicator from '@/components/StepIndicator';
import Button from '@/components/Button';
import StatusBadge from '@/components/StatusBadge';

// ── Tipos ──

interface ModuleLabel {
  label: string;
  description: string;
}

interface ProviderInfo {
  id: string;
  nombre: string;
  descripcion: string;
}

interface OnboardingState {
  vcoo_id: string;
  name: string;
  modules: string[];
  module_labels?: Record<string, ModuleLabel>;
  providers?: ProviderInfo[];
  step: string;
  wizard_step?: number;
  status: string;
  completed: string[];
  all_done?: boolean;
  install_command: string;
  agent_online: boolean;
  progress: number | { total: number; done: number };
}

const PASOS = [
  'Instalar Agente',
  'Proveedor IA',
  'Módulos',
  'Finalización',
];

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
                minLength={6}
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
  const [proveedorSeleccionado, setProveedorSeleccionado] = useState<string | null>(null);
  const [verMas, setVerMas] = useState(false);
  const [apiKeyValue, setApiKeyValue] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [moduloSeleccionado, setModuloSeleccionado] = useState<string | null>(null);
  const [fetchCargando, setFetchCargando] = useState(false);
  const [vistaActual, setVistaActual] = useState<number | null>(null);

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

  const fetchOnboarding = useCallback(async () => {
    if (!token) return;
    try {
      const { data } = await apiClient.get(`/setup/${token}`);
      setOnboarding(data as OnboardingState);
      setError(null);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Error al cargar la configuración';
      setError(msg);
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

  // ── Polling: auto-refresh every 15s + auto-verify when agent online ──
  useEffect(() => {
    if (!mostrarWizard) return;
    if (onboarding?.agent_online && onboarding.wizard_step === 0) {
      apiClient.post(`/setup/${token}/verify`).catch(() => {});
    }
    const interval = setInterval(fetchOnboarding, 15000);
    return () => clearInterval(interval);
  }, [mostrarWizard, fetchOnboarding, onboarding?.agent_online, onboarding?.wizard_step]);

  // ── Timeout for provider loading ──
  const [providersTimeout, setProvidersTimeout] = useState(false);
  useEffect(() => {
    if ((onboarding?.providers || []).length === 0 && onboarding) {
      const t = setTimeout(() => setProvidersTimeout(true), 30000);
      return () => clearTimeout(t);
    }
    setProvidersTimeout(false);
  }, [onboarding?.providers, onboarding]);

  // ── Auth form (not yet authenticated) ──

  if (!mostrarWizard) {
    // Still checking localStorage on first render
    if (checkBase && !auth.cargando) {
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
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white border border-red-200 rounded-xl p-8 max-w-md w-full text-center shadow-sm">
          <div className="text-red-500 text-5xl mb-4">⚠</div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">
            Error de conexión
          </h1>
          <p className="text-gray-500 mb-6">{error}</p>
          <Button variant="primary" onClick={fetchOnboarding}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  if (!onboarding) return null;

  // ── Wizard steps ──

  const pasoActual = vistaActual ?? onboarding.wizard_step ?? 0;
  const completado = onboarding.all_done ?? false;
  const pasoBackend = onboarding.wizard_step ?? 0;

  // ── Conectar proveedor ──

  const manejarConectarProveedor = async (service: string) => {
    if (!token) return;
    setConectando(service);
    try {
      const { data } = await apiClient.get(
        `/setup/${token}/auth-url?service=${service}`
      );
      const { commands } = data as { commands: string[]; service: string };
      if (commands && commands.length > 0) {
        setProveedorSeleccionado(service);
        setConectando(null);
        return;
      }
    } catch {
      // fallback: show instructions anyway
    }
    setProveedorSeleccionado(service);
    setConectando(null);
  };

  const enviarApiKey = async (providerId: string) => {
    if (!apiKeyValue.trim() || !token) return;
    setEnviando(true);
    try {
      await apiClient.post(`/setup/${token}/set-provider`, {
        provider: providerId,
        api_key: apiKeyValue.trim(),
      });
      // Advance step after setting provider
      await apiClient.post(`/setup/${token}/verify`).catch(() => {});
      await fetchOnboarding();
      setProveedorSeleccionado(null);
      setApiKeyValue('');
      setError(null);
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

  const MODULE_INSTRUCTIONS: Record<string, { pasos: string[] }> = {
    office: { pasos: [
      '1. Ve a https://console.cloud.google.com y crea un proyecto',
      '2. Activa Google Drive API y obtén client_id + client_secret',
      '3. Ejecuta en tu VPS: hermes config set google.client_id TU_CLIENT_ID',
      '4. Ejecuta: hermes config set google.client_secret TU_CLIENT_SECRET',
    ]},
    mail: { pasos: [
      '1. Ve a https://console.cloud.google.com y activa Gmail API',
      '2. Obtén credenciales OAuth 2.0',
      '3. Configura las credenciales en tu VPS con hermes',
    ]},
    planner: { pasos: [
      '1. Obtén tu API key de Trello en https://trello.com/power-ups/admin',
      '2. Ejecuta: hermes config set trello.api_key TU_API_KEY',
      '3. Ejecuta: hermes config set trello.api_token TU_TOKEN',
    ]},
    developer: { pasos: [
      '1. GitHub: gh auth login',
      '2. Ejecuta: hermes config set github.token $(gh auth token)',
      '3. Vercel: vercel login && hermes config set vercel.token TU_TOKEN',
      '4. Supabase: supabase login && hermes config set supabase.access_token TU_ACCESS_TOKEN',
    ]},
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
              onClick={() => navigator.clipboard.writeText(cmdText)}
              className="flex-shrink-0 text-gray-400 hover:text-primary-600 transition-colors"
              title="Copiar comando"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
          </div>
        </div>

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

    if (proveedorSeleccionado) {
      const prov = raw.find(p => p.id === proveedorSeleccionado);
      const auth = prov?.auth as { type?: string; credential?: string; hint?: string } | undefined;
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
            ) : auth.type === 'api_key' ? (
              <div className="space-y-4">
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
                <Button onClick={() => enviarApiKey(prov!.id)}
                  disabled={!apiKeyValue.trim() || enviando}
                  loading={enviando}
                  variant="primary" size="lg" className="w-full"
                >
                  {enviando ? 'Conectando...' : 'Conectar'}
                </Button>
              </div>
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
              <div className="text-yellow-500 text-5xl mb-4">⏱</div>
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
    const modulosDisponibles = onboarding.modules || [];

    const modulosInfo: Record<
      string,
      { nombre: string; descripcion: string; icono: string }
    > = {
      office: {
        nombre: onboarding.module_labels?.office?.label || 'Google Drive',
        descripcion: onboarding.module_labels?.office?.description || 'Documentos, hojas de cálculo y almacenamiento en la nube',
        icono: '📄',
      },
      mail: {
        nombre: onboarding.module_labels?.mail?.label || 'Gmail',
        descripcion: onboarding.module_labels?.mail?.description || 'Correo electrónico y bandeja de entrada inteligente',
        icono: '✉',
      },
      planner: {
        nombre: onboarding.module_labels?.planner?.label || 'Calendar + Trello',
        descripcion: onboarding.module_labels?.planner?.description || 'Calendario, tareas y organización del trabajo',
        icono: '📅',
      },
      developer: {
        nombre: onboarding.module_labels?.developer?.label || 'Developer',
        descripcion: onboarding.module_labels?.developer?.description || 'GitHub, Vercel, Supabase y herramientas para desarrolladores',
        icono: '💻',
      },
    };

    if (moduloSeleccionado) {
      const info = modulosInfo[moduloSeleccionado];
      const instr = MODULE_INSTRUCTIONS[moduloSeleccionado];
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
            {instr ? (
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
                icono: '🔌',
              };
              return (
                <div
                  key={modulo}
                  onClick={() => manejarConectarModulo(modulo)}
                  className="group cursor-pointer bg-white border border-gray-200 rounded-xl p-5 transition-all duration-200 hover:border-primary-500 hover:shadow-lg hover:shadow-primary-100/50"
                >
                  <div className="flex flex-col items-center text-center">
                    <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mb-3 text-2xl">
                      {info.icono}
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">
                      {info.nombre}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {info.descripcion}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const renderPasoFinalizacion = () => (
    <div className="text-center py-8">
      <div className="w-16 h-16 rounded-full bg-green-100 mx-auto mb-6 flex items-center justify-center">
        <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Todo listo</h1>
      <p className="text-gray-500 mb-8 max-w-md mx-auto">
        Tu VCOO está configurado y funcionando. El agente está activo en tu servidor.
      </p>
      <div className="max-w-sm mx-auto space-y-3">
        <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-3">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm text-gray-700">Agente instalado y activo</span>
        </div>
        <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-3">
          <div className={`w-2 h-2 rounded-full ${completado ? 'bg-green-500' : 'bg-gray-300'}`} />
          <span className="text-sm text-gray-700">Proveedor de IA configurado</span>
        </div>
        <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-3">
          <div className={`w-2 h-2 rounded-full ${completado ? 'bg-green-500' : 'bg-gray-300'}`} />
          <span className="text-sm text-gray-700">Módulos conectados</span>
        </div>
      </div>
    </div>
  );

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
            pasosTotales={4}
            pasos={PASOS}
            maxUnlocked={pasoBackend + 1}
            onStepClick={(idx) => {
              if (idx <= pasoBackend + 1 && idx !== pasoActual) {
                setVistaActual(idx);
                setProveedorSeleccionado(null);
                setModuloSeleccionado(null);
                setError(null);
              }
            }}
          />
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
          {completado || pasoActual >= 4
            ? renderPasoFinalizacion()
            : pasoActual === 0
            ? renderPasoInstalacion()
            : pasoActual === 1
            ? renderPasoProveedor()
            : pasoActual === 2
            ? renderPasoModulos()
            : pasoActual === 3
            ? renderPasoFinalizacion()
            : renderPasoInstalacion()}
        </div>

        {onboarding && pasoActual > 0 && (
          <div className="flex mt-6 pt-4 border-t border-gray-100">
            <Button variant="ghost" size="sm" onClick={() => {
              setVistaActual(pasoActual - 1);
              setProveedorSeleccionado(null);
              setModuloSeleccionado(null);
              setError(null);
            }}>
              ← Anterior
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SetupWizard;
