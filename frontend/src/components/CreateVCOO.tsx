import { useState } from 'react';
import { createVCOO, getProvisionToken } from '../api/client';
import { Plus, Key, ExternalLink, Copy, Check } from 'lucide-react';

interface Props {
  onCreated: () => void;
}

export default function CreateVCOO({ onCreated }: Props) {
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<{
    vcooId: string;
    token: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const { id } = await createVCOO();
      const { token } = await getProvisionToken(id);
      setResult({ vcooId: id, token });
      onCreated();
    } catch (e: any) {
      alert('Error al crear VCOO: ' + e.message);
    } finally {
      setCreating(false);
    }
  };

  const setupUrl = result
    ? `${window.location.origin}/setup/${result.token}`
    : '';

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(setupUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyToken = () => {
    navigator.clipboard.writeText(result?.token || '');
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Plus className="w-5 h-5 text-emerald-400" />
        Nuevo VCOO
      </h2>

      {!result ? (
        <button
          onClick={handleCreate}
          disabled={creating}
          className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2.5 rounded-lg text-sm font-medium transition flex items-center gap-2"
        >
          {creating ? (
            <>
              <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
              Creando...
            </>
          ) : (
            'Crear VCOO'
          )}
        </button>
      ) : (
        <div className="space-y-4">
          <div className="p-4 bg-emerald-950/50 border border-emerald-800/50 rounded-lg">
            <div className="flex items-center gap-2 text-emerald-400 mb-3">
              <Key className="w-4 h-4" />
              <span className="text-sm font-medium">VCOO creado — Token generado</span>
            </div>

            {/* VCOO ID */}
            <div className="mb-3">
              <span className="text-xs text-slate-500">ID del VCOO:</span>
              <code className="ml-2 text-xs text-slate-300 bg-slate-800 px-2 py-0.5 rounded">
                {result.vcooId}
              </code>
            </div>

            {/* Setup URL */}
            <div className="mb-3">
              <span className="text-xs text-slate-500 block mb-1">Enlace de setup para el cliente:</span>
              <div className="flex items-center gap-2">
                <code className="text-xs text-emerald-300 bg-slate-800 rounded px-3 py-2 flex-1 break-all">
                  {setupUrl}
                </code>
                <button
                  onClick={handleCopyUrl}
                  className="p-2 hover:bg-slate-700 rounded-lg transition shrink-0"
                  title="Copiar enlace"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-slate-400" />
                  )}
                </button>
                <a
                  href={setupUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 hover:bg-slate-700 rounded-lg transition shrink-0"
                  title="Abrir enlace"
                >
                  <ExternalLink className="w-4 h-4 text-slate-400" />
                </a>
              </div>
            </div>

            {/* Token */}
            <div>
              <span className="text-xs text-slate-500 block mb-1">Token JWT:</span>
              <div className="flex items-center gap-2">
                <code className="text-[10px] text-slate-500 bg-slate-800 rounded px-3 py-2 flex-1 break-all font-mono">
                  {result.token.substring(0, 50)}...
                </code>
                <button
                  onClick={handleCopyToken}
                  className="p-2 hover:bg-slate-700 rounded-lg transition shrink-0"
                  title="Copiar token"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              setResult(null);
              handleCreate();
            }}
            className="text-sm text-slate-400 hover:text-white transition"
          >
            + Crear otro VCOO
          </button>
        </div>
      )}
    </div>
  );
}
