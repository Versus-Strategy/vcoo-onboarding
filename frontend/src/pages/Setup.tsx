import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Terminal,
  CheckCircle,
  XCircle,
  Loader2,
  Copy,
  ArrowRight,
  Shield,
  Monitor,
  Zap,
} from 'lucide-react';

type Status = 'validating' | 'ready' | 'error' | 'expired';

export default function Setup() {
  const { token } = useParams<{ token: string }>();
  const [status, setStatus] = useState<Status>('validating');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const installCommand = `curl -sSL https://vcoo-onboarding.vercel.app/install.sh | bash -s -- ${token}`;

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('Token no proporcionado en la URL.');
      return;
    }

    // Validate token format (JWT has 3 dot-separated segments)
    if (token.split('.').length !== 3 || token.length < 30) {
      setStatus('error');
      setError('El token no tiene un formato JWT válido.');
      return;
    }

    // Decode payload to check expiration
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.exp) {
        const expDate = new Date(payload.exp * 1000);
        if (expDate < new Date()) {
          setStatus('expired');
          setError(
            `El token expiró el ${expDate.toLocaleString()}. Solicita uno nuevo al operador.`,
          );
          return;
        }
        // Warn if expiring within 5 minutes
        if (expDate.getTime() - Date.now() < 5 * 60 * 1000) {
          setError(
            `⚠ El token expira pronto (${expDate.toLocaleTimeString()}). Ejecuta el comando cuanto antes.`,
          );
        }
      }
    } catch {
      // If we can't decode, still show ready — let the backend validate
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
      <div
        className={`rounded-xl p-6 mb-8 border ${
          status === 'error' || status === 'expired'
            ? 'bg-red-950/40 border-red-800/60'
            : 'bg-emerald-950/30 border-emerald-800/40'
        }`}
      >
        <div className="flex items-center gap-3">
          {status === 'validating' && (
            <Loader2 className="w-6 h-6 text-slate-400 animate-spin shrink-0" />
          )}
          {status === 'ready' && (
            <CheckCircle className="w-6 h-6 text-emerald-400 shrink-0" />
          )}
          {(status === 'error' || status === 'expired') && (
            <XCircle className="w-6 h-6 text-red-400 shrink-0" />
          )}
          <div>
            <h1 className="text-xl font-bold">
              {status === 'validating' && 'Verificando token...'}
              {status === 'ready' && 'Token verificado — Servidor listo para VCOO'}
              {status === 'expired' && 'Token expirado'}
              {status === 'error' && 'Error de token'}
            </h1>
            {error && (
              <p className="text-sm mt-1 opacity-80">{error}</p>
            )}
          </div>
        </div>
      </div>

      {status === 'ready' && (
        <>
          {/* Install Command */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 bg-emerald-950 rounded-lg">
                <Terminal className="w-5 h-5 text-emerald-400" />
              </div>
              <h2 className="text-lg font-semibold">Comando de instalación</h2>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Ejecuta este comando en la terminal del servidor Linux/macOS donde
              quieres instalar VCOO:
            </p>

            <div className="bg-slate-950 border border-slate-700 rounded-lg p-4 flex items-start justify-between gap-3 group">
              <code className="text-sm text-emerald-300 break-all flex-1 font-mono leading-relaxed">
                {installCommand}
              </code>
              <button
                onClick={handleCopy}
                className="shrink-0 p-2 hover:bg-slate-800 rounded-lg transition mt-0.5"
                title="Copiar comando"
              >
                <Copy
                  className={`w-4 h-4 transition ${
                    copied ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                />
              </button>
            </div>
            {copied && (
              <p className="text-emerald-400 text-xs mt-2 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Copiado al portapapeles
              </p>
            )}

            <div className="mt-4 p-3 bg-amber-950/30 border border-amber-800/30 rounded-lg flex items-start gap-2">
              <span className="text-amber-400 text-sm shrink-0 mt-0.5">⚠</span>
              <p className="text-xs text-amber-300/80">
                El agente se ejecuta en primer plano. No cierres la terminal
                mientras esté activo. Para detenerlo, pulsa <kbd className="bg-slate-800 px-1.5 py-0.5 rounded text-[10px]">Ctrl+C</kbd>.
              </p>
            </div>
          </div>

          {/* Steps */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {[
              {
                icon: Monitor,
                title: '1. Copia el comando',
                desc: 'Haz clic en el botón de copiar o selecciona todo el comando manualmente.',
              },
              {
                icon: Terminal,
                title: '2. Ejecuta en tu servidor',
                desc: 'Pega el comando en la terminal del servidor Linux/macOS y pulsa Enter.',
              },
              {
                icon: Zap,
                title: '3. Conectado',
                desc: 'El agente se conecta automáticamente y empieza a escuchar comandos del operador.',
              },
            ].map((step, i) => (
              <div
                key={i}
                className="bg-slate-900 border border-slate-800 rounded-xl p-5"
              >
                <step.icon className="w-5 h-5 text-emerald-400 mb-3" />
                <h3 className="font-medium text-sm mb-1">{step.title}</h3>
                <p className="text-slate-500 text-xs leading-relaxed">
                  {step.desc}
                </p>
              </div>
            ))}
          </div>

          {/* What it does */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 bg-slate-800 rounded-lg">
                <Shield className="w-4 h-4 text-slate-400" />
              </div>
              <h2 className="text-lg font-semibold">¿Qué hace el script?</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                {
                  title: 'Descarga segura',
                  desc: 'Baja el agente con verificación SHA256 de integridad.',
                },
                {
                  title: 'Entorno aislado',
                  desc: 'Crea un virtualenv Python sin afectar al sistema.',
                },
                {
                  title: 'Modo seguro',
                  desc: 'Ejecuta en sandbox con comandos autorizados por whitelist.',
                },
                {
                  title: 'Sin root',
                  desc: 'No requiere privilegios de administrador ni acceso root.',
                },
              ].map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2.5 bg-slate-800/50 rounded-lg p-3"
                >
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-medium">{item.title}</h4>
                    <p className="text-xs text-slate-500">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CTA */}
          <div className="text-center">
            <p className="text-sm text-slate-500 mb-3">
              ¿Eres el operador? Vuelve al dashboard para ver el agente
              conectado en tiempo real.
            </p>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300 text-sm font-medium transition"
            >
              <ArrowRight className="w-4 h-4" />
              Ir al Dashboard
            </Link>
          </div>
        </>
      )}

      {(status === 'error' || status === 'expired') && (
        <div className="text-center py-8">
          <p className="text-slate-500 text-sm mb-4">
            Contacta a tu operador VCOO para obtener un token nuevo.
          </p>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300 text-sm font-medium transition"
          >
            <ArrowRight className="w-4 h-4" />
            Ir al Dashboard
          </Link>
        </div>
      )}
    </div>
  );
}
