import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import apiClient from '@/api/apiClient';
import { useAuth } from '@/auth/authContext';
import StepIndicator from '@/components/StepIndicator';
import Button from '@/components/Button';
import StatusBadge from '@/components/StatusBadge';

// ── Tipos ──

interface OnboardingState {
  vcoo_id: string;
  name: string;
  modules: string[];
  step: number;
  status: string;
  completed: boolean;
  install_command: string;
  agent_online: boolean;
  progress: number;
}

interface ProviderInfo {
  id: string;
  nombre: string;
  descripcion: string;
  logo: string;
  color: string;
}

const PASOS = [
  'Instalar Agente',
  'Proveedor IA',
  'Módulos',
  'Finalización',
];

const PROVEEDORES: ProviderInfo[] = [
  {
    id: 'anthropic',
    nombre: 'Anthropic',
    descripcion: 'Claude — modelos de última generación',
    logo: 'https://www.anthropic.com/favicon.ico',
    color: 'text-orange-400',
  },
  {
    id: 'openai',
    nombre: 'OpenAI',
    descripcion: 'GPT-4, GPT-4o y más',
    logo: 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg',
    color: 'text-green-400',
  },
  {
    id: 'google',
    nombre: 'Google IA',
    descripcion: 'Gemini y modelos de Google',
    logo: 'https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png',
    color: 'text-blue-400',
  },
  {
    id: 'mistral',
    nombre: 'Mistral AI',
    descripcion: 'Modelos abiertos y eficientes',
    logo: 'https://mistral.ai/favicon.ico',
    color: 'text-purple-400',
  },
  {
    id: 'xai',
    nombre: 'xAI',
    descripcion: 'Grok y modelos de xAI',
    logo: 'https://x.ai/favicon.ico',
    color: 'text-gray-300',
  },
  {
    id: 'cohere',
    nombre: 'Cohere',
    descripcion: 'Modelos empresariales',
    logo: 'https://cohere.com/favicon.ico',
    color: 'text-red-400',
  },
];

// ── AuthForm: registro e inicio de sesión para clientes ──

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
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(125,58,237,0.08),transparent_50%)] pointer-events-none" />

      <div className="relative max-w-md w-full">
        {/* Logo / branding */}
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">
              V
            </div>
            <span className="text-white font-semibold text-lg">VCOO</span>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-xl p-8">
          <h1 className="text-xl font-bold text-white mb-2">
            {esRegistro ? 'Crear tu cuenta' : 'Iniciar sesión'}
          </h1>
          <p className="text-gray-400 mb-6">
            {esRegistro
              ? 'Regístrate para comenzar la configuración de tu VCOO'
              : 'Ingresa con tu cuenta para continuar la configuración'}
          </p>

          <form onSubmit={manejarSubmit} className="space-y-4">
            {esRegistro && (
              <div>
                <label
                  htmlFor="auth-nombre"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Nombre
                </label>
                <input
                  id="auth-nombre"
                  type="text"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  className="w-full px-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                  placeholder="Tu nombre"
                  required={esRegistro}
                />
              </div>
            )}

            <div>
              <label
                htmlFor="auth-email"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Correo electrónico
              </label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                placeholder="correo@ejemplo.com"
                required
              />
            </div>

            <div>
              <label
                htmlFor="auth-password"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Contraseña
              </label>
              <input
                id="auth-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none transition-colors"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>

            {errorLocal && (
              <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-sm text-red-300">
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
              className="text-sm text-primary-400 hover:text-primary-300 transition-colors"
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
  const { token } = useParams<{ token: string }>();
  const { auth } = useAuth();

  // All hooks must be at the top level, before any conditional returns
  const [mostrarWizard, setMostrarWizard] = useState(false);
  const [checkBase, setCheckBase] = useState(true);
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(false);
  const [conectando, setConectando] = useState<string | null>(null);

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

  // ── Auth form (not yet authenticated) ──

  if (!mostrarWizard) {
    // Still checking localStorage on first render
    if (checkBase && !auth.cargando) {
      return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-400 mx-auto mb-4" />
            <p className="text-gray-400">Verificando sesión...</p>
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
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-400 mx-auto mb-4" />
          <p className="text-gray-400">Cargando configuración...</p>
        </div>
      </div>
    );
  }

  // ── Error loading onboarding ──

  if (error && !onboarding) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
        <div className="bg-gray-900 border border-red-800 rounded-xl p-8 max-w-md w-full text-center">
          <div className="text-red-400 text-5xl mb-4">⚠</div>
          <h1 className="text-xl font-bold text-white mb-2">
            Error de conexión
          </h1>
          <p className="text-gray-400 mb-6">{error}</p>
          <Button variant="primary" onClick={fetchOnboarding}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  if (!onboarding) return null;

  // ── Wizard steps ──

  const pasoActual = onboarding.step;
  const completado = onboarding.completed;

  // ── Verificar instalación del agente ──

  const manejarVerificar = async () => {
    if (!token) return;
    setVerificando(true);
    try {
      await apiClient.post(`/setup/${token}/verify`);
      await fetchOnboarding();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Error al verificar instalación';
      setError(msg);
    } finally {
      setVerificando(false);
    }
  };

  // ── Conectar proveedor ──

  const manejarConectarProveedor = async (service: string) => {
    if (!token) return;
    setConectando(service);
    try {
      const { data } = await apiClient.get(
        `/setup/${token}/auth-url?service=${service}`
      );
      const { url } = data as { url: string; service: string };
      if (url) {
        window.location.href = url;
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Error al conectar proveedor';
      setError(msg);
      setConectando(null);
    }
  };

  // ── Conectar módulo ──

  const manejarConectarModulo = async (service: string) => {
    if (!token) return;
    setConectando(service);
    try {
      const { data } = await apiClient.get(
        `/setup/${token}/auth-url?service=${service}`
      );
      const { url } = data as { url: string; service: string };
      if (url) {
        window.location.href = url;
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Error al conectar módulo';
      setError(msg);
      setConectando(null);
    }
  };

  // ── Renderizado de cada paso ──

  const renderPasoInstalacion = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-2">
          Instalar el Agente VCOO
        </h2>
        <p className="text-gray-400">
          Ejecuta el siguiente comando en tu servidor para instalar el agente:
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
        <div className="flex items-start justify-between gap-4">
          <code className="text-sm text-gray-100 font-mono break-all whitespace-pre-wrap">
            {onboarding.install_command ||
              'curl -sSL https://instalar.vcoo.dev | sudo bash'}
          </code>
          <button
            onClick={() => {
              navigator.clipboard.writeText(
                onboarding.install_command ||
                  'curl -sSL https://instalar.vcoo.dev | sudo bash'
              );
            }}
            className="flex-shrink-0 text-gray-500 hover:text-white transition-colors"
            title="Copiar comando"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
      </div>

      <p className="text-sm text-gray-500">
        Una vez que el comando termine de ejecutarse, haz clic en "Verificar"
        para continuar.
      </p>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <Button
          onClick={manejarVerificar}
          disabled={verificando}
          variant="primary"
          size="lg"
        >
          {verificando ? 'Verificando...' : 'Verificar instalación'}
        </Button>
      </div>
    </div>
  );

  const renderPasoProveedor = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-2">
          Selecciona tu proveedor de IA
        </h2>
        <p className="text-gray-400">
          Elige el proveedor que potenciará los servicios inteligentes de tu VCOO.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {PROVEEDORES.map((proveedor) => (
          <div
            key={proveedor.id}
            onClick={() => manejarConectarProveedor(proveedor.id)}
            className={`group cursor-pointer bg-gray-900 border border-gray-700 rounded-xl p-5 transition-all duration-200 hover:border-primary-500 hover:shadow-lg hover:shadow-primary-900/20 ${
              conectando === proveedor.id ? 'opacity-60 pointer-events-none' : ''
            }`}
          >
            <div className="flex flex-col items-center text-center">
              <div
                className={`w-14 h-14 rounded-full bg-gray-800 flex items-center justify-center mb-3 text-2xl font-bold ${proveedor.color}`}
              >
                {proveedor.nombre.charAt(0)}
              </div>
              <h3 className="font-semibold text-white mb-1">
                {proveedor.nombre}
              </h3>
              <p className="text-sm text-gray-500">{proveedor.descripcion}</p>
            </div>
            {conectando === proveedor.id && (
              <div className="mt-3 flex justify-center">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-400" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderPasoModulos = () => {
    const modulosDisponibles = onboarding.modules || [];

    const modulosInfo: Record<
      string,
      { nombre: string; descripcion: string; icono: string }
    > = {
      gmail: {
        nombre: 'Gmail',
        descripcion: 'Correo electrónico y bandeja de entrada inteligente',
        icono: '✉',
      },
      trello: {
        nombre: 'Trello',
        descripcion: 'Gestión de tareas y tableros',
        icono: '📋',
      },
      google: {
        nombre: 'Google Workspace',
        descripcion: 'Docs, Drive, Calendar y más',
        icono: '🔗',
      },
      slack: {
        nombre: 'Slack',
        descripcion: 'Mensajería y colaboración en equipo',
        icono: '💬',
      },
      notion: {
        nombre: 'Notion',
        descripcion: 'Documentación y bases de conocimiento',
        icono: '📝',
      },
      github: {
        nombre: 'GitHub',
        descripcion: 'Repositorios y control de versiones',
        icono: '🐙',
      },
    };

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white mb-2">
            Configurar módulos
          </h2>
          <p className="text-gray-400">
            Conecta los servicios que VCOO podrá gestionar por ti.
          </p>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {modulosDisponibles.length === 0 ? (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-8 text-center">
            <p className="text-gray-400">No hay módulos disponibles para configurar.</p>
            <p className="text-gray-500 text-sm mt-2">
              Todos los módulos han sido configurados o no aplican a esta instancia.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
                  className={`group cursor-pointer bg-gray-900 border border-gray-700 rounded-xl p-5 transition-all duration-200 hover:border-primary-500 hover:shadow-lg hover:shadow-primary-900/20 ${
                    conectando === modulo
                      ? 'opacity-60 pointer-events-none'
                      : ''
                  }`}
                >
                  <div className="flex flex-col items-center text-center">
                    <div className="w-14 h-14 rounded-full bg-gray-800 flex items-center justify-center mb-3 text-2xl">
                      {info.icono}
                    </div>
                    <h3 className="font-semibold text-white mb-1">
                      {info.nombre}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {info.descripcion}
                    </p>
                  </div>
                  {conectando === modulo && (
                    <div className="mt-3 flex justify-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-400" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const renderPasoFinalizacion = () => (
    <div className="space-y-6">
      <div className="text-center">
        <div className="flex items-center justify-center mb-6">
          <div className="bg-green-900/40 border border-green-700 rounded-full p-4">
            <svg
              className="h-12 w-12 text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-white mb-4">
          ¡Configuración Completada!
        </h1>
        <p className="text-gray-400 mb-6 max-w-md mx-auto">
          Tu instancia de VCOO ha sido configurada exitosamente y está lista
          para usar.
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-lg mx-auto">
        <h3 className="font-semibold text-white mb-4">
          Resumen de Configuración
        </h3>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge
              estado={
                onboarding.agent_online ? 'en-linea' : 'fuera-de-linea'
              }
            />
            <div>
              <h4 className="font-medium text-white">Agente VCOO</h4>
              <p className="text-sm text-gray-500">
                {onboarding.agent_online
                  ? 'Instalado y activo'
                  : 'Pendiente de activación'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge
              estado={
                pasoActual >= 2 ? 'en-linea' : 'fuera-de-linea'
              }
            />
            <div>
              <h4 className="font-medium text-white">Proveedor de IA</h4>
              <p className="text-sm text-gray-500">
                {pasoActual >= 2 ? 'Conectado' : 'No conectado'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge
              estado={
                completado && onboarding.modules?.length === 0
                  ? 'en-linea'
                  : pasoActual >= 3
                  ? 'en-linea'
                  : 'fuera-de-linea'
              }
            />
            <div>
              <h4 className="font-medium text-white">Módulos Configurados</h4>
              <p className="text-sm text-gray-500">
                {completado
                  ? 'Todos los módulos conectados'
                  : `${onboarding.modules?.length || 0} módulo(s) pendiente(s)`}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto">
        <h3 className="font-semibold text-white mb-3">Próximos Pasos</h3>
        <ol className="space-y-2 text-gray-400">
          <li className="flex items-start gap-2">
            <span className="text-primary-400 font-bold">1.</span>
            <span>Explora el panel de control para ver tus servicios activos</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-400 font-bold">2.</span>
            <span>Configura notificaciones y alertas según tus preferencias</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-400 font-bold">3.</span>
            <span>Invita a miembros de tu equipo para colaborar</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary-400 font-bold">4.</span>
            <span>Programa tu primera tarea de automatización</span>
          </li>
        </ol>
      </div>
    </div>
  );

  const renderTarjetaBienvenida = () => (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full bg-primary-900/40 border border-primary-700 flex items-center justify-center text-primary-300 text-xl font-bold">
          {onboarding.name ? onboarding.name.charAt(0).toUpperCase() : 'V'}
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">
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
    <div className="min-h-screen bg-gray-950">
      {/* Fondo decorativo */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(125,58,237,0.08),transparent_50%)] pointer-events-none" />

      <div className="relative max-w-4xl mx-auto px-4 py-8 sm:py-12">
        {/* Logo / branding */}
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm">
              V
            </div>
            <span className="text-white font-semibold text-lg">VCOO</span>
          </div>
        </div>

        {/* Bienvenida */}
        {renderTarjetaBienvenida()}

        {/* StepIndicator */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
          <StepIndicator
            pasoActual={pasoActual}
            pasosTotales={4}
            pasos={PASOS}
          />
        </div>

        {/* Contenido del paso actual */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
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
      </div>
    </div>
  );
};

export default SetupWizard;
