import { useState } from 'react';
import { enqueueCommand, listPlaybooks, getProvisionToken, regenerateToken, reactivateVCOO } from '../api/client';
import type { VCOOResult } from '../api/client';
import { useRealtimeLogs } from '../hooks/useRealtime';
import { Circle, CircleDot, Terminal, Play, Clock, Activity, Copy, Check, Key, Archive, RotateCcw, Trash2, ExternalLink, ChevronDown, Zap, Wifi } from 'lucide-react';

interface Props {
  vcoos: VCOOResult[];
  label: string;
  icon: 'zap' | 'archive' | 'wifi';
  expandedId: string | null;
  onToggle: (id: string | null) => void;
  onRefresh: () => void;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
  onReactivate: (id: string) => void;
}

const SectionIcon = ({ icon }: { icon: string }) => {
  const cls = 'w-4 h-4';
  switch (icon) {
    case 'zap': return <Zap className={`${cls} text-[var(--vs-purple)]`} />;
    case 'archive': return <Archive className={`${cls} text-(--vs-muted)`} />;
    case 'wifi': return <Wifi className={`${cls} text-emerald-400`} />;
    default: return <Activity className={`${cls} text-(--vs-muted)`} />;
  }
};

function VCOOCard({
  vcoo, expanded, onToggle, onRefresh, onComplete, onDelete, onReactivate,
}: {
  vcoo: VCOOResult;
  expanded: boolean;
  onToggle: () => void;
  onRefresh: () => void;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
  onReactivate: (id: string) => void;
}) {
  const [command, setCommand] = useState('');
  const [sending, setSending] = useState(false);
  const [playbooks, setPlaybooks] = useState<string[]>([]);
  const [token, setToken] = useState<string | null>(vcoo.active_token);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const logs = useRealtimeLogs(expanded ? vcoo.id : null);

  const isActive = vcoo.status === 'active';
  const isCompleted = vcoo.status === 'completed';

  const agentOnline = isActive && vcoo.agent && vcoo.agent.last_seen &&
    Date.now() - new Date(vcoo.agent.last_seen).getTime() < 30000;

  // Token expiry check
  const tokenExpired = isActive && vcoo.token_expires_at && new Date(vcoo.token_expires_at).getTime() < Date.now();
  const tokenExpiresSoon = isActive && vcoo.token_expires_at && !tokenExpired &&
    (new Date(vcoo.token_expires_at).getTime() - Date.now()) < 86400000; // < 24h

  const loadPlaybooks = async () => {
    try { const data = await listPlaybooks(); setPlaybooks(data.playbooks || []); } catch {}
  };

  const handleToggle = () => {
    if (!expanded) { loadPlaybooks(); if (!token && isActive) loadToken(); }
    onToggle();
  };

  // Force close on complete/delete
  const collapse = () => onToggle();

  const loadToken = async () => {
    try { const { token: t } = await getProvisionToken(vcoo.id); setToken(t); } catch {}
  };

  const handleRegenerate = async () => {
    setGenerating(true);
    try { const { token: t } = await regenerateToken(vcoo.id); setToken(t); onRefresh(); }
    catch (e: any) { alert('Error: ' + e.message); }
    finally { setGenerating(false); }
  };

  const handleComplete = () => { collapse(); onComplete(vcoo.id); };
  const handleDelete = () => { collapse(); onDelete(vcoo.id); };

  const handleReactivate = async () => {
    try { const { token: t } = await reactivateVCOO(vcoo.id); setToken(t); } catch {}
    onReactivate(vcoo.id);
  };

  const installCommand = token
    ? `curl -sSL https://vcoo-onboarding.vercel.app/install.sh | PROVISION_TOKEN=${token} bash -`
    : '';
  const setupUrl = token ? `${window.location.origin}/setup/${token}` : '';

  const handleCopyCmd = () => {
    if (!token) return;
    navigator.clipboard.writeText(installCommand);
    setCopiedCmd(true); setTimeout(() => setCopiedCmd(false), 2000);
  };
  const handleCopyUrl = () => {
    navigator.clipboard.writeText(setupUrl);
    setCopiedUrl(true); setTimeout(() => setCopiedUrl(false), 2000);
  };
  const handleSend = async () => {
    if (!command.trim()) return;
    setSending(true);
    try { await enqueueCommand(vcoo.id, command.trim()); setCommand(''); }
    catch (e: any) { alert('Error: ' + e.message); }
    finally { setSending(false); }
  };


  return (
    <div className="bg-(--vs-bg-card) border border-(--vs-border) rounded-xl overflow-hidden transition"
      style={{ opacity: isCompleted ? 0.7 : 1, boxShadow: 'var(--vs-shadow)' }}>
      {/* Header */}
      <div className="p-5 flex items-center justify-between cursor-pointer transition hover:bg-(--vs-hover)" onClick={handleToggle}>
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {isActive && (agentOnline ? <CircleDot className="w-4 h-4 text-emerald-400 shrink-0" /> : <Circle className="w-4 h-4 text-(--vs-muted) shrink-0" />)}
          {isCompleted && <Archive className="w-4 h-4 text-(--vs-muted) shrink-0" />}
          <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {vcoo.name && <span className="text-sm font-medium text-(--vs-heading)">{vcoo.name}</span>}
            <code className="text-[11px] font-mono break-all text-(--vs-body)">{vcoo.id}</code>
            {isCompleted && <span className="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0 bg-(--vs-btn-secondary) text-(--vs-muted)">Completado</span>}
            {isActive && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0 ${agentOnline ? 'bg-emerald-950/20 text-emerald-400' : 'bg-(--vs-btn-secondary) text-(--vs-muted)'}`}>
                {agentOnline ? 'Online' : 'Sin agente'}
              </span>
            )}
          </div>
          {/* Module badges */}
          {vcoo.modules && vcoo.modules.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {vcoo.modules.map((m: string) => (
                <span key={m} className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-[var(--vs-purple)]/10 text-[var(--vs-purple)] uppercase tracking-wide">{m}</span>
              ))}
            </div>
          )}
          {vcoo.agent?.last_seen && <div className="flex items-center gap-1 text-xs mt-0.5 text-(--vs-muted)"><Clock className="w-3 h-3" />{new Date(vcoo.agent.last_seen).toLocaleTimeString()}</div>}
          </div>
        </div>
        <ChevronDown className={`w-5 h-5 shrink-0 ml-2 transition-transform duration-200 text-(--vs-muted) ${expanded ? 'rotate-180' : ''}`} />
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-(--vs-border) p-5 space-y-4">
          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            {isActive && <>
              <button onClick={handleComplete} className="text-xs px-3 py-1.5 rounded-lg transition font-medium flex items-center gap-1.5 bg-(--vs-btn-secondary) hover:bg-(--vs-btn-secondary-hover) text-(--vs-btn-secondary-text) hover:text-(--vs-heading)">
                <Archive className="w-3 h-3" /> Completar
              </button>
              <button onClick={handleRegenerate} disabled={generating}
                className={`text-xs px-3 py-1.5 rounded-lg transition font-medium flex items-center gap-1.5 disabled:opacity-40 ${
                  tokenExpired
                    ? 'bg-[var(--vs-warning-bg)] border border-[var(--vs-warning-border)] text-[var(--vs-warning-text)] hover:bg-amber-500/20'
                    : 'bg-(--vs-btn-secondary) hover:bg-(--vs-btn-secondary-hover) text-(--vs-btn-secondary-text) hover:text-amber-400'
                }`}>
                <Key className="w-3 h-3" /> {generating ? '...' : tokenExpired ? 'Regenerar (expirado)' : 'Regenerar token'}
              </button>
            </>}
            {isCompleted && (
              <button onClick={handleReactivate} className="text-xs px-3 py-1.5 rounded-lg transition font-medium flex items-center gap-1.5 bg-[var(--vs-purple)]/10 hover:bg-[var(--vs-purple)]/20 text-[var(--vs-purple)]">
                <RotateCcw className="w-3 h-3" /> Reactivar
              </button>
            )}
            {!confirmDelete ? (
              <button onClick={() => setConfirmDelete(true)} className="text-xs px-3 py-1.5 rounded-lg transition font-medium flex items-center gap-1.5 ml-auto bg-(--vs-btn-secondary) hover:bg-red-950/20 text-(--vs-btn-secondary-text) hover:text-red-400">
                <Trash2 className="w-3 h-3" /> Eliminar
              </button>
            ) : (
              <div className="flex items-center gap-2 ml-auto">
                <span className="text-xs text-red-400">¿Confirmar?</span>
                <button onClick={handleDelete} className="text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded-lg transition font-medium">Sí</button>
                <button onClick={() => setConfirmDelete(false)} className="text-xs px-3 py-1.5 rounded-lg transition font-medium bg-(--vs-btn-secondary) text-(--vs-btn-secondary-text)">No</button>
              </div>
            )}
          </div>

          {/* Token expiry warning */}
          {isActive && token && tokenExpired && (
            <div className="p-3 rounded-lg flex items-center gap-2 bg-(--vs-warning-bg) border border-(--vs-warning-border) text-(--vs-warning-text) text-xs font-medium">
              ⚠ Token expirado — el cliente no podrá usarlo. Regenéralo.
            </div>
          )}
          {isActive && token && tokenExpiresSoon && !tokenExpired && (
            <div className="p-3 rounded-lg flex items-center gap-2 bg-(--vs-warning-bg) border border-(--vs-warning-border) text-(--vs-warning-text) text-xs">
              ⏳ Token caduca en menos de 24h
            </div>
          )}

          {/* Token callouts — show for active AND completed if token exists */}
          {token && (
            <>
              {/* One-liner callout */}
              <div className="p-3 rounded-lg space-y-2" style={{background:'var(--vs-token-bg)', border:'1px solid var(--vs-token-border)'}}>
                <div className="flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-[var(--vs-purple)]" />
                  <span className="text-xs font-medium text-[var(--vs-purple)]">One-liner</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs rounded px-3 py-2 flex-1 break-all font-mono bg-(--vs-code-bg) text-(--vs-code-text)">{installCommand}</code>
                  <button onClick={handleCopyCmd} className="p-2 rounded-lg hover:bg-(--vs-btn-secondary) transition shrink-0" title="Copiar">
                    {copiedCmd ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-(--vs-body)" />}
                  </button>
                </div>
              </div>

              {/* Setup link callout */}
              <div className="p-3 rounded-lg space-y-2" style={{background:'var(--vs-token-bg)', border:'1px solid var(--vs-token-border)'}}>
                <div className="flex items-center gap-2">
                  <ExternalLink className="w-3.5 h-3.5 text-[var(--vs-purple)]" />
                  <span className="text-xs font-medium text-[var(--vs-purple)]">Enlace de setup</span>
                </div>
                <div className="flex items-center gap-2">
                  <a href={setupUrl} target="_blank" rel="noopener noreferrer"
                    className="text-[11px] rounded px-3 py-1.5 flex-1 break-all font-mono underline transition bg-(--vs-code-bg) text-[var(--vs-purple)] hover:opacity-80">
                    {setupUrl}
                  </a>
                  <button onClick={handleCopyUrl} className="p-2 rounded-lg hover:bg-(--vs-btn-secondary) transition shrink-0" title="Copiar">
                    {copiedUrl ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-(--vs-body)" />}
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Load token button if no token yet */}
          {isActive && !token && (
            <button onClick={loadToken} className="text-xs text-[var(--vs-purple)] hover:opacity-80 transition">Cargar token...</button>
          )}

          {/* Command input */}
          {isActive && (
            <div>
              <label className="text-xs text-(--vs-muted) block mb-1.5 flex items-center gap-1"><Terminal className="w-3 h-3" /> Enviar comando</label>
              <div className="flex gap-2">
                <input type="text" value={command} onChange={(e) => setCommand(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="ej: playbook:system-info.sh"
                  className="flex-1 bg-(--vs-input-bg) border border-(--vs-input-border) rounded-lg px-3 py-2 text-sm text-(--vs-heading) focus:outline-none focus:border-[var(--vs-purple)] font-mono" />
                <button onClick={handleSend} disabled={sending || !command.trim()}
                  className="bg-[var(--vs-purple)] hover:bg-[var(--vs-purple-hover)] disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5 shrink-0">
                  <Play className="w-3.5 h-3.5" /> {sending ? '...' : 'Run'}
                </button>
              </div>
            </div>
          )}

          {/* Playbooks */}
          {playbooks.length > 0 && isActive && (
            <div className="flex flex-wrap gap-2">
              {playbooks.map(name => (
                <button key={name} onClick={() => setCommand(`playbook:${name}`)}
                  className="text-xs px-2.5 py-1 rounded-md transition border bg-(--vs-playbook-bg) border-(--vs-playbook-border) text-(--vs-body) hover:text-[var(--vs-purple)] hover:border-[var(--vs-purple)]/30">
                  {name}
                </button>
              ))}
            </div>
          )}

          {/* Logs */}
          <div>
            <label className="text-xs text-(--vs-muted) block mb-1.5 flex items-center gap-1"><Activity className="w-3 h-3" /> Logs</label>
            <div className="bg-(--vs-code-bg) border border-(--vs-input-border) rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs">
              {logs.length === 0 ? <p className="text-(--vs-muted) italic">Esperando logs...</p>
                : logs.map((log, i) => (
                  <div key={log.id || i} className={`whitespace-pre-wrap break-all ${log.stream === 'stderr' ? 'text-red-400' : log.stream === 'system' ? 'text-amber-400' : 'text-(--vs-code-text)'}`}>{log.chunk}</div>
                ))}
              <div className="text-(--vs-muted) animate-pulse mt-1">▊</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function VCOOList({ vcoos, label, icon, expandedId, onToggle, onRefresh, onComplete, onDelete, onReactivate }: Props) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold flex items-center gap-2 uppercase tracking-wider text-(--vs-muted)">
        <SectionIcon icon={icon} /> {label} ({vcoos.length})
      </h2>
      {vcoos.map(vcoo => (
        <VCOOCard key={vcoo.id} vcoo={vcoo}
          expanded={expandedId === vcoo.id}
          onToggle={() => onToggle(expandedId === vcoo.id ? null : vcoo.id)}
          onRefresh={onRefresh} onComplete={onComplete} onDelete={onDelete} onReactivate={onReactivate} />
      ))}
    </div>
  );
}
