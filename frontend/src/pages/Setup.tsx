import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Terminal, CheckCircle, XCircle, Loader2, Copy, ArrowRight,
  Zap, AlertTriangle, SkipForward, RefreshCw, Server,
  Key, ExternalLink, ChevronDown,
} from 'lucide-react';
import { getSetupInfo, verifyStep, getAuthUrl } from '../api/client';
import type { SetupInfo } from '../api/client';

type StepState = 'pending' | 'active' | 'verifying' | 'waiting' | 'done' | 'error' | 'blocked' | 'skipped';

interface StepDef {
  id: string;
  label: string;
  icon: string;
  instructions: string[];
  extra?: 'vps-recommendation' | 'provider-config';
}

const STEP_DEFS: Record<string, StepDef> = {
  bootstrap: {
    id: 'bootstrap',
    label: 'Instalación base',
    icon: 'Monitor',
    instructions: [
      'Ejecuta el comando de instalación en la terminal de tu servidor.',
      'El agente verificará que Python, Hermes y los scripts VCOO están instalados.',
      'Haz clic en "Verificar" cuando hayas ejecutado el comando.',
    ],
    extra: 'vps-recommendation',
  },
  'google-oauth': {
    id: 'google-oauth',
    label: 'Google Workspace',
    icon: 'Shield',
    instructions: [
      'Abre el enlace de autorización de Google OAuth.',
      'Inicia sesión con tu cuenta de Google Workspace.',
      'Concede los permisos solicitados.',
      'Haz clic en "Verificar" para comprobar la conexión.',
    ],
  },
  'gmail-setup': {
    id: 'gmail-setup',
    label: 'Gmail',
    icon: 'Mail',
    instructions: [
      'Asegúrate de haber completado la autorización de Google.',
      'Haz clic en "Verificar" para comprobar el acceso a Gmail.',
    ],
  },
  'trello-setup': {
    id: 'trello-setup',
    label: 'Trello',
    icon: 'Trello',
    instructions: [
      'Abre el enlace de autorización de Trello.',
      'Autoriza a VCOO para acceder a tus tableros.',
      'Haz clic en "Verificar" para comprobar la conexión.',
    ],
  },
  'github-setup': {
    id: 'github-setup',
    label: 'GitHub',
    icon: 'Github',
    instructions: [
      'Asegúrate de tener GitHub CLI instalado.',
      'Ejecuta "gh auth login" en tu servidor.',
      'Haz clic en "Verificar" para comprobar la conexión.',
    ],
  },
  'vercel-setup': {
    id: 'vercel-setup',
    label: 'Vercel',
    icon: 'Zap',
    instructions: [
      'Asegúrate de tener Vercel CLI instalado.',
      'Ejecuta "vercel login" en tu servidor.',
      'Haz clic en "Verificar" para comprobar la conexión.',
    ],
  },
  'supabase-setup': {
    id: 'supabase-setup',
    label: 'Supabase',
    icon: 'Database',
    instructions: [
      'Asegúrate de tener Supabase CLI instalado.',
      'Ejecuta "supabase login" en tu servidor.',
      'Haz clic en "Verificar" para comprobar la conexión.',
    ],
  },
  'provider-config': {
    id: 'provider-config',
    label: 'Proveedor de modelos IA',
    icon: 'Key',
    instructions: [
      'Configura el modelo de IA que usará tu VCOO.',
      'Recomendamos OpenCode Go (mejor calidad-precio) o Anthropic (más potente).',
      'Haz clic en "Verificar" cuando hayas configurado tu proveedor.',
    ],
    extra: 'provider-config',
  },
  finalize: {
    id: 'finalize',
    label: 'Finalizar',
    icon: 'CheckCircle',
    instructions: [
      'Todos los pasos están completos.',
      'El agente hará la limpieza final y MAGI estará lista.',
    ],
  },
};

// ── Error detail component ──

interface ErrorItem {
  step: string;
  error: string;
  timestamp?: string;
  skipped_by_operator?: boolean;
}

function ErrorDetail({ error, idx }: { error: ErrorItem; idx: number }) {
  const [expanded, setExpanded] = useState(false);
  const maxLen = 200;
  const isLong = error.error.length > maxLen;
  const display = expanded || !isLong ? error.error : error.error.slice(0, maxLen) + '...';

  return (
    <div className="rounded-lg bg-red-950/30 border border-red-800/20 p-3">
      <div className="flex items-start gap-2">
        <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-red-300">
              {error.skipped_by_operator ? 'Omitido por operador' : 'Fallo #' + (idx + 1)}
            </span>
            {error.timestamp && (
              <span className="text-[10px] text-(--vs-muted)">
                {new Date(error.timestamp).toLocaleTimeString()}
              </span>
            )}
          </div>
          <pre className="text-xs text-red-200/80 whitespace-pre-wrap break-all font-mono leading-relaxed">
            {display}
          </pre>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-red-400 hover:text-red-300 mt-1.5 transition"
            >
              {expanded ? '▼ Ver menos' : '▶ Ver más'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Service auth button ──

const SERVICE_AUTH: Record<string, { label: string; service: string; icon: string }> = {
  'google-oauth': { label: 'Autorizar con Google', service: 'google', icon: 'Shield' },
  'gmail-setup': { label: 'Autorizar Gmail', service: 'google', icon: 'Mail' },
  'trello-setup': { label: 'Autorizar con Trello', service: 'trello', icon: 'Trello' },
  'github-setup': { label: 'Autorizar con GitHub', service: 'github', icon: 'Github' },
  'vercel-setup': { label: 'Autorizar con Vercel', service: 'vercel', icon: 'Zap' },
  'supabase-setup': { label: 'Autorizar con Supabase', service: 'supabase', icon: 'Database' },
};

function ServiceAuthButton({ stepId, token }: { stepId: string; token: string }) {
  const info = SERVICE_AUTH[stepId];
  if (!info) return null;

  const handleAuth = async () => {
    try {
      const { url } = await getAuthUrl(token, info.service);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e: any) {
      console.error('Error getting auth URL:', e);
    }
  };

  return (
    <div className="mt-3 pt-3 border-t border-(--vs-border)">
      <button
        onClick={handleAuth}
        className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 rounded-lg text-sm font-medium transition border border-amber-600/30"
      >
        <ExternalLink className="w-4 h-4" /> {info.label}
      </button>
      <p className="text-xs text-(--vs-muted) mt-2">
        Se abrirá una pestaña para autorizar. Después haz clic en "Verificar conexión".
      </p>
    </div>
  );
}

const STEP_ORDER = [
  'bootstrap', 'provider-config', 'google-oauth', 'gmail-setup',
  'trello-setup', 'github-setup', 'vercel-setup',
  'supabase-setup', 'finalize',
];

function getStepState(
  stepId: string,
  currentStep: string,
  completed: string[],
  errors: { step: string; error: string; skipped_by_operator?: boolean }[],
  status: string,
  waitingStep: string,
): StepState {
  if (completed.includes(stepId)) return 'done';
  const skippedErr = errors.find(e => e.step === stepId && e.skipped_by_operator);
  if (skippedErr) return 'skipped';
  if (stepId === currentStep && status === 'blocked') return 'blocked';
  if (stepId === currentStep && waitingStep === stepId) return 'waiting';
  if (stepId === currentStep) return 'active';
  const hasError = errors.some(e => e.step === stepId);
  if (hasError && status === 'blocked') return 'blocked';
  if (hasError) return 'error';
  return 'pending';
}

export default function Setup() {
  const params = useParams<{ token: string }>();
  const token = params.token || '';

  const [data, setData] = useState<SetupInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState('');
  const [showVPSInfo, setShowVPSInfo] = useState(false);
  const [waitingStep, setWaitingStep] = useState<string>('');

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const info = await getSetupInfo(token);
      setData(info);
      setError('');
      setLoading(false);
    } catch (e: any) {
      setError(e.message || 'Error al cargar los datos del wizard');
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!token || error) return;
    const interval = setInterval(async () => {
      const info = await getSetupInfo(token).catch(() => null);
      if (info) {
        setData(info);
        // Si el paso cambió, limpiar el spinner de espera
        if (waitingStep && info.step !== waitingStep) {
          setWaitingStep('');
          setVerifying(false);
          setVerifyMsg('');
        }
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [token, error, waitingStep]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleVerify = async () => {
    if (!token) return;
    setVerifying(true);
    setVerifyMsg('');
    try {
      const result = await verifyStep(token);
      if (result.status === 'auto_completed') {
        setVerifyMsg('Completado. Pasando al siguiente paso...');
        loadData();
        setTimeout(() => { setVerifying(false); setVerifyMsg(''); }, 2000);
      } else if (result.status === 'enqueued') {
        // Spinner persistente — no limpiar, el polling detectará el avance
        setWaitingStep(step);
        setVerifyMsg('');
      } else if (result.status === 'skip') {
        setVerifyMsg('Onboarding ya completado.');
        setTimeout(() => { setVerifying(false); setVerifyMsg(''); }, 2000);
      }
    } catch (e: any) {
      setVerifyMsg('Error: ' + (e.message || 'No se pudo verificar'));
      setTimeout(() => { setVerifying(false); setVerifyMsg(''); }, 3000);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <Loader2 className="w-8 h-8 text-(--vs-accent) animate-spin mx-auto mb-4" />
        <p className="text-(--vs-muted)">Verificando token...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <div className="rounded-xl p-8 mb-8 border bg-red-950/40 border-red-800/60 text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-bold mb-2">{error ? 'Error' : 'Token inválido'}</h1>
          <p className="text-sm text-red-300/80 mb-6">{error || 'El token de provision no es válido o ha expirado.'}</p>
          <Link to="/dashboard" className="inline-flex items-center gap-2 text-(--vs-accent) hover:underline text-sm font-medium">
            <ArrowRight className="w-4 h-4" /> Ir al Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const { name, modules, step, status, completed, errors, progress, install_command, agent_online } = data;
  const progressPercent = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  const isBlocked = status === 'blocked';
  const isComplete = step === 'done' || status === 'completed';

  const relevantSteps = STEP_ORDER.filter(sid => {
    if (completed.includes(sid)) return true;
    if (sid === 'finalize') return true;
    if (sid === 'provider-config') return true; // always show
    const stepModule: Record<string, string> = {
      bootstrap: 'core',
      'google-oauth': 'office',
      'gmail-setup': 'mail',
      'trello-setup': 'planner',
      'github-setup': 'developer',
      'vercel-setup': 'developer',
      'supabase-setup': 'developer',
    };
    const mod = stepModule[sid];
    return mod && modules.includes(mod);
  });

  const isBootstrap = step === 'bootstrap';
  const isProviderConfig = step === 'provider-config';

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-(--vs-accent)/10 rounded-lg">
            <Zap className="w-6 h-6 text-(--vs-accent)" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-(--vs-heading)">{name || 'Configuración VCOO'}</h1>
            <p className="text-sm text-(--vs-muted)">
              {isComplete ? 'Onboarding completado' : isBlocked ? 'Configuración bloqueada — contacta con soporte' : agent_online ? 'Agente conectado — el proceso avanza automáticamente' : 'Sigue los pasos para configurar tu VCOO'}
            </p>
            {agent_online && <span className="inline-flex items-center gap-1.5 text-xs mt-1 px-2 py-0.5 rounded-full bg-emerald-950/30 text-emerald-400 border border-emerald-800/30"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Conectado</span>}
          </div>
        </div>
        <div className="mt-6">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-(--vs-muted)">Progreso: {progress.done}/{progress.total}</span>
            <span className="text-(--vs-accent) font-medium">{progressPercent}%</span>
          </div>
          <div className="h-2 bg-(--vs-bg-card) rounded-full overflow-hidden border border-(--vs-border)">
            <div className="h-full bg-(--vs-accent) rounded-full transition-all duration-700 ease-out" style={{ width: progressPercent + '%' }} />
          </div>
        </div>
      </div>

      {/* Blocked banner */}
      {isBlocked && (
        <div className="rounded-xl p-5 mb-6 border bg-amber-950/30 border-amber-800/40 flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-amber-300 mb-1">Configuración bloqueada</h3>
            <p className="text-sm text-amber-300/70">El paso actual ha fallado 3 veces. Contacta con el equipo de VERSUS para recibir ayuda.</p>
          </div>
        </div>
      )}

      {isComplete && (
        <div className="rounded-xl p-5 mb-6 border bg-emerald-950/30 border-emerald-800/40 flex items-start gap-3">
          <CheckCircle className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-emerald-300 mb-1">¡MAGI está lista!</h3>
            <p className="text-sm text-emerald-300/70">La configuración ha finalizado. MAGI se presentará en Discord/Telegram de tu equipo.</p>
          </div>
        </div>
      )}

      {/* VPS Recommendation (during bootstrap) */}
      {isBootstrap && !isComplete && (
        <div className="mb-6">
          <button
            onClick={() => setShowVPSInfo(!showVPSInfo)}
            className="w-full rounded-xl border border-(--vs-border) bg-(--vs-bg-card) p-4 text-left hover:bg-(--vs-hover) transition flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-blue-950/30 rounded-lg"><Server className="w-4 h-4 text-blue-400" /></div>
              <div>
                <span className="text-sm font-medium text-(--vs-heading)">¿No tienes servidor?</span>
                <span className="text-xs text-(--vs-muted) ml-2">Te recomendamos un VPS</span>
              </div>
            </div>
            <ChevronDown className={'w-4 h-4 text-(--vs-muted) transition-transform ' + (showVPSInfo ? 'rotate-180' : '')} />
          </button>
          {showVPSInfo && (
            <div className="border border-(--vs-border) border-t-0 rounded-b-xl bg-(--vs-bg-card) p-5 space-y-3">
              <div>
                <h3 className="font-semibold text-(--vs-heading) mb-1">OVHcloud VPS Starter</h3>
                <p className="text-xs text-(--vs-muted) mb-3">La opción que recomendamos para alojar tu VCOO:</p>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {[
                    { label: 'Precio', value: 'Desde $4.54/mes' },
                    { label: 'vCores', value: '2' },
                    { label: 'RAM', value: '4 GB' },
                    { label: 'Almacenamiento', value: '40 GB SSD NVMe' },
                    { label: 'Backup', value: 'Diario (24h)' },
                    { label: 'Tráfico', value: 'Ilimitado' },
                    { label: 'Ancho de banda', value: '200 Mbps' },
                    { label: 'SO', value: 'Linux (Ubuntu, Debian...)' },
                  ].map(spec => (
                    <div key={spec.label} className="flex justify-between bg-(--vs-bg) rounded-lg px-3 py-2">
                      <span className="text-(--vs-muted)">{spec.label}</span>
                      <span className="font-medium text-(--vs-heading)">{spec.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <a
                href="https://www.ovhcloud.com/en/vps/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-(--vs-accent) hover:underline font-medium mt-2"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Ver OVHcloud VPS
              </a>
            </div>
          )}
        </div>
      )}

      {/* Provider config info (during provider-config step) */}
      {isProviderConfig && !isComplete && (
        <div className="mb-6 rounded-xl border border-(--vs-border) bg-(--vs-bg-card) p-5 space-y-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-purple-950/30 rounded-lg"><Key className="w-4 h-4 text-[var(--vs-purple)]" /></div>
            <h3 className="font-semibold text-(--vs-heading)">Configura tu proveedor de IA</h3>
          </div>
          <p className="text-sm text-(--vs-body)">
            Tu VCOO necesita un modelo de lenguaje para funcionar. Elige uno y configura la API key en tu servidor:
          </p>

          <div className="space-y-3">
            {/* OpenCode Go */}
            <div className="rounded-lg border border-emerald-800/30 bg-emerald-950/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-emerald-300">OpenCode Go</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/30 text-emerald-400 font-medium">Recomendado</span>
              </div>
              <p className="text-xs text-emerald-200/70 mb-3">Mejor calidad-precio. Modelos potentes a precio competitivo.</p>
              <div className="bg-(--vs-bg) rounded-lg p-3 font-mono text-xs text-(--vs-code-text) mb-2">
                hermes config set model.provider opencode<br />
                hermes config set model.default opencode/claude-sonnet-4
              </div>
              <a
                href="https://opencode.ai/go?ref=C9DPFB6SSV"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:underline font-medium"
              >
                <ExternalLink className="w-3 h-3" /> Crear cuenta en OpenCode Go
              </a>
            </div>

            {/* Anthropic */}
            <div className="rounded-lg border border-(--vs-border) bg-(--vs-bg)/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-(--vs-heading)">Anthropic</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--vs-btn-secondary) text-(--vs-muted) font-medium">Más potente</span>
              </div>
              <p className="text-xs text-(--vs-muted) mb-3">Modelos Claude de última generación. Mayor capacidad de razonamiento.</p>
              <div className="bg-(--vs-bg) rounded-lg p-3 font-mono text-xs text-(--vs-code-text) mb-2">
                export ANTHROPIC_API_KEY=sk-ant-...<br />
                hermes config set model.provider anthropic<br />
                hermes config set model.default anthropic/claude-sonnet-4
              </div>
            </div>

            {/* Other providers */}
            <details className="text-sm">
              <summary className="text-(--vs-muted) cursor-pointer hover:text-(--vs-body) transition">
                Otros proveedores disponibles (OpenAI, DeepSeek, OpenRouter...)
              </summary>
              <div className="mt-2 bg-(--vs-bg) rounded-lg p-3 font-mono text-xs text-(--vs-code-text) space-y-1">
                <div># OpenAI</div>
                <div>export OPENAI_API_KEY=sk-tu-clave</div>
                <div>hermes config set model.provider openai</div>
                <div className="mt-2"># OpenRouter (acceso a múltiples modelos)</div>
                <div>export OPENROUTER_API_KEY=sk-or-tu-clave</div>
                <div>hermes config set model.provider openrouter</div>
                <div className="mt-2"># DeepSeek</div>
                <div>export DEEPSEEK_API_KEY=sk-tu-clave</div>
                <div>hermes config set model.provider deepseek</div>
              </div>
            </details>
          </div>

          <p className="text-xs text-(--vs-muted)">
            Ejecuta estos comandos en la terminal de tu servidor VPS. Luego haz clic en "Verificar".
          </p>
        </div>
      )}

      {/* Install command */}
      <div className="bg-(--vs-bg-card) border border-(--vs-border) rounded-xl p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 bg-emerald-950/30 rounded-lg"><Terminal className="w-5 h-5 text-emerald-400" /></div>
          <h2 className="text-lg font-semibold text-(--vs-heading)">Comando de instalación</h2>
        </div>
        <p className="text-sm text-(--vs-muted) mb-4">Ejecuta este comando en la terminal de tu servidor Linux/macOS:</p>
        <div className="bg-(--vs-bg) border border-(--vs-border) rounded-lg p-4 flex items-start justify-between gap-3">
          <code className="text-sm text-emerald-300 break-all flex-1 font-mono leading-relaxed select-all">{install_command}</code>
          <button onClick={() => handleCopy(install_command)} className="shrink-0 p-2 hover:bg-(--vs-bg-card) rounded-lg transition" title="Copiar comando">
            <Copy className={'w-4 h-4 transition ' + (copied ? 'text-emerald-400' : 'text-(--vs-muted)')} />
          </button>
        </div>
        {copied && <p className="text-emerald-400 text-xs mt-2 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Copiado</p>}
      </div>

      {/* Steps */}
      <div className="space-y-3 mb-8">
        <h2 className="text-lg font-semibold text-(--vs-heading) mb-4">Pasos de configuración</h2>
        {relevantSteps.map((stepId, idx) => {
          const def = STEP_DEFS[stepId];
          if (!def) return null;
          const state = getStepState(stepId, step, completed, errors, status, waitingStep);
          const isCurrent = stepId === step && !isComplete;
          const stepErrors = errors.filter(e => e.step === stepId);

          return (
            <div
              key={stepId}
              className={'rounded-xl border p-4 transition-all ' + (
                isCurrent ? 'border-(--vs-accent)/40 bg-(--vs-accent)/5' :
                state === 'done' || state === 'skipped' ? 'border-(--vs-border) bg-(--vs-bg-card)/50 opacity-75' :
                state === 'error' || state === 'blocked' ? 'border-red-800/40 bg-red-950/20' :
                'border-(--vs-border) bg-(--vs-bg-card)')}
            >
              <div className="flex items-center gap-3">
                <div className="shrink-0">
                  {state === 'done' && <CheckCircle className="w-6 h-6 text-emerald-400" />}
                  {state === 'waiting' && <Loader2 className="w-6 h-6 text-(--vs-accent) animate-spin" />}
                  {state === 'active' && (verifying ? <Loader2 className="w-6 h-6 text-(--vs-accent) animate-spin" /> :
                    <div className="w-6 h-6 rounded-full border-2 border-(--vs-accent) flex items-center justify-center">
                      <div className="w-3 h-3 rounded-full bg-(--vs-accent)" />
                    </div>)}
                  {state === 'error' && <XCircle className="w-6 h-6 text-red-400" />}
                  {state === 'blocked' && <AlertTriangle className="w-6 h-6 text-amber-400" />}
                  {state === 'skipped' && <SkipForward className="w-6 h-6 text-(--vs-muted)" />}
                  {state === 'pending' && <div className="w-6 h-6 rounded-full border-2 border-(--vs-muted)/30" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={'font-medium ' + (state === 'done' || state === 'skipped' ? 'text-(--vs-muted)' : 'text-(--vs-body)')}>
                      {idx + 1}. {def.label}
                    </span>
                    {state === 'skipped' && <span className="text-xs text-(--vs-muted) bg-(--vs-bg-card) px-2 py-0.5 rounded">Omitido</span>}
                    {state === 'error' && <span className="text-xs text-red-400 bg-red-950/30 px-2 py-0.5 rounded">Error</span>}
                    {state === 'blocked' && <span className="text-xs text-amber-400 bg-amber-950/30 px-2 py-0.5 rounded">Bloqueado</span>}
                    {stepErrors.length > 0 && (
                      <span className="text-xs text-(--vs-muted)">({stepErrors.length} {stepErrors.length === 1 ? 'fallo' : 'fallos'})</span>
                    )}
                  </div>
                  {(isCurrent || state === 'active') && !isComplete && (
                    <div className="mt-3">
                      <ul className="space-y-2 mb-4">
                        {def.instructions.map((inst, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-(--vs-body)">
                            <span className="text-(--vs-accent) mt-0.5 shrink-0">•</span> {inst}
                          </li>
                        ))}
                      </ul>
                      {state === 'active' && !isBlocked && !agent_online && (
                        <div>
                          <button
                            onClick={handleVerify}
                            disabled={verifying}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-(--vs-accent) hover:bg-(--vs-accent)/80 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                          >
                            {verifying ? (
                              <><Loader2 className="w-4 h-4 animate-spin" /> Verificando...</>
                            ) : (
                              <><RefreshCw className="w-4 h-4" /> Verificar conexión</>
                            )}
                          </button>
                          {verifyMsg && (
                            <p className="text-xs mt-2 text-(--vs-muted)">{verifyMsg}</p>
                          )}
                        </div>
                      )}
                      {state === 'waiting' && (
                        <div>
                          <button
                            disabled
                            className="inline-flex items-center gap-2 px-4 py-2 bg-(--vs-accent)/50 text-white/70 rounded-lg text-sm font-medium cursor-wait"
                          >
                            <Loader2 className="w-4 h-4 animate-spin" /> Esperando al agente...
                          </button>
                        </div>
                      )}
                      {/* Auth buttons for OAuth/service steps */}
                      {(state === 'active' || state === 'waiting') && stepId !== 'bootstrap' && stepId !== 'provider-config' && stepId !== 'finalize' && (
                        <ServiceAuthButton stepId={stepId} token={token} />
                      )}
                    </div>
                  )}
                  {stepErrors.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {stepErrors.map((e, i) => (
                        <ErrorDetail key={i} error={e} idx={i} />
                      ))}
                    </div>
                  )}
                </div>
                {state === 'done' && <span className="text-xs text-emerald-400 shrink-0">Completado</span>}
                {state === 'pending' && <span className="text-xs text-(--vs-muted) shrink-0">Pendiente</span>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="text-center pb-8">
        <p className="text-sm text-(--vs-muted) mb-3">¿Eres el operador? Vuelve al dashboard para gestionar este VCOO.</p>
        <Link to="/dashboard" className="inline-flex items-center gap-2 text-(--vs-accent) hover:underline text-sm font-medium">
          <ArrowRight className="w-4 h-4" /> Ir al Dashboard
        </Link>
      </div>
    </div>
  );
}
