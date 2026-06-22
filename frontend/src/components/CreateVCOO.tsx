import { useState } from 'react';
import { createVCOO, getProvisionToken } from '../api/client';
import { Plus, Key, ExternalLink, Copy, Check, Terminal, Boxes } from 'lucide-react';

interface Props {
  onCreated: () => void;
}

const AVAILABLE_MODULES = [
  { id: 'core', label: 'Core', desc: 'Hermes + scripts base (obligatorio)', icon: '⚙️' },
  { id: 'office', label: 'Office', desc: 'Google OAuth + Drive', icon: '📄' },
  { id: 'mail', label: 'Mail', desc: 'Gmail SMTP/IMAP', icon: '✉️' },
  { id: 'planner', label: 'Planner', desc: 'Trello boards', icon: '📋' },
  { id: 'developer', label: 'Developer', desc: 'GitHub + Vercel + Supabase', icon: '🛠️' },
];

export default function CreateVCOO({ onCreated }: Props) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [selectedModules, setSelectedModules] = useState<string[]>(['core']);
  const [result, setResult] = useState<{ vcooId: string; token: string } | null>(null);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  const toggleModule = (modId: string) => {
    if (modId === 'core') return; // core siempre obligatorio
    setSelectedModules(prev =>
      prev.includes(modId) ? prev.filter(m => m !== modId) : [...prev, modId]
    );
  };

  const handleCreate = async () => {
    setCreating(true);
    try {
      const modules = selectedModules.length > 0 ? selectedModules : ['core'];
      const { id } = await createVCOO(name.trim() || undefined, modules);
      const { token } = await getProvisionToken(id);
      setResult({ vcooId: id, token });
      onCreated();
    } catch (e: any) { alert('Error: ' + e.message); }
    finally { setCreating(false); }
  };

  const installCommand = result
    ? `curl -sSL https://vcoo-onboarding.vercel.app/install.sh | PROVISION_TOKEN=${result.token} bash -`
    : '';
  const setupUrl = result ? `${window.location.origin}/setup/${result.token}` : '';

  const handleCopyCmd = () => { navigator.clipboard.writeText(installCommand); setCopiedCmd(true); setTimeout(() => setCopiedCmd(false), 2000); };
  const handleCopyUrl = () => { navigator.clipboard.writeText(setupUrl); setCopiedUrl(true); setTimeout(() => setCopiedUrl(false), 2000); };

  return (
    <div className="bg-(--vs-bg-card) border border-(--vs-border) rounded-xl p-6" style={{boxShadow:'var(--vs-shadow)'}}>
      <h2 className="text-lg font-semibold text-(--vs-heading) mb-4 flex items-center gap-2">
        <Plus className="w-5 h-5 text-[var(--vs-purple)]" /> Nuevo VCOO
      </h2>

      {!result ? (
        <div className="space-y-4">
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Nombre (opcional) — ej: Cliente Acme"
            className="w-full bg-(--vs-input-bg) border border-(--vs-input-border) rounded-lg px-4 py-2.5 text-sm text-(--vs-heading) focus:outline-none focus:border-[var(--vs-purple)] transition" />

          {/* Module selection */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-(--vs-muted)">
              <Boxes className="w-3.5 h-3.5" /> MÓDULOS A INCLUIR
            </div>
            <div className="grid grid-cols-2 gap-2">
              {AVAILABLE_MODULES.map(mod => (
                <button
                  key={mod.id}
                  onClick={() => toggleModule(mod.id)}
                  className={`text-left px-3 py-2.5 rounded-lg border text-xs transition ${
                    selectedModules.includes(mod.id)
                      ? 'border-[var(--vs-purple)] bg-[var(--vs-purple)]/10 text-(--vs-heading)'
                      : 'border-(--vs-border) bg-(--vs-input-bg) text-(--vs-muted) hover:border-(--vs-muted)'
                  } ${mod.id === 'core' ? 'cursor-default' : 'cursor-pointer'}`}
                >
                  <div className="flex items-center gap-1.5">
                    <span>{mod.icon}</span>
                    <span className="font-semibold">{mod.label}</span>
                  </div>
                  <div className="mt-0.5 text-[10px] text-(--vs-muted) leading-tight">{mod.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <button onClick={handleCreate} disabled={creating}
            className="bg-[var(--vs-purple)] hover:bg-[var(--vs-purple-hover)] disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2.5 rounded-lg text-sm font-medium transition flex items-center gap-2">
            {creating ? <><span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> Creando...</> : 'Crear VCOO'}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-4 rounded-lg space-y-3" style={{background:'var(--vs-token-bg)', border:'1px solid var(--vs-token-border)'}}>
            <div className="flex items-center gap-2 text-[var(--vs-purple)]">
              <Key className="w-4 h-4" /> <span className="text-sm font-medium">VCOO creado</span>
            </div>
            <div>
              <span className="text-xs text-(--vs-muted)">ID:</span>
              <code className="ml-2 text-[11px] px-2 py-0.5 rounded break-all font-mono bg-(--vs-code-bg) text-(--vs-body)">{result.vcooId}</code>
            </div>

            {/* One-liner callout */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5"><Terminal className="w-3 h-3 text-[var(--vs-purple)]" /><span className="text-xs font-medium text-[var(--vs-purple)]">One-liner</span></div>
              <div className="flex items-center gap-2">
                <code className="text-xs rounded px-3 py-2 flex-1 break-all font-mono bg-(--vs-code-bg) text-(--vs-code-text)">{installCommand}</code>
                <button onClick={handleCopyCmd} className="p-2 rounded-lg hover:bg-(--vs-btn-secondary) transition shrink-0">
                  {copiedCmd ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-(--vs-body)" />}
                </button>
              </div>
            </div>

            {/* Setup link callout */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5"><ExternalLink className="w-3 h-3 text-[var(--vs-purple)]" /><span className="text-xs font-medium text-[var(--vs-purple)]">Enlace de setup</span></div>
              <div className="flex items-center gap-2">
                <a href={setupUrl} target="_blank" rel="noopener noreferrer"
                  className="text-[11px] rounded px-3 py-1.5 flex-1 break-all font-mono underline transition bg-(--vs-code-bg) text-[var(--vs-purple)] hover:opacity-80">{setupUrl}</a>
                <button onClick={handleCopyUrl} className="p-2 rounded-lg hover:bg-(--vs-btn-secondary) transition shrink-0">
                  {copiedUrl ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-(--vs-body)" />}
                </button>
              </div>
            </div>
          </div>
          <button onClick={() => { setResult(null); setName(''); handleCreate(); }} className="text-sm text-(--vs-body) hover:text-(--vs-heading) transition">+ Crear otro VCOO</button>
        </div>
      )}
    </div>
  );
}
