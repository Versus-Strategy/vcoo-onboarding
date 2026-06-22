import { useEffect, useState } from 'react';
import { getVCOOState, enqueueCommand, listPlaybooks } from '../api/client';
import { useRealtimeLogs } from '../hooks/useRealtime';
import { Circle, CircleDot, Terminal, Play, RefreshCw, Clock, Activity } from 'lucide-react';

interface AgentData {
  id: string;
  status: string;
  last_seen: string | null;
}

interface VCOOData {
  id: string;
  agent: AgentData | null;
}

interface Props {
  vcooIds: string[];
}

function VCOOCard({ vcooId }: { vcooId: string }) {
  const [vcoo, setVcoo] = useState<VCOOData | null>(null);
  const [command, setCommand] = useState('');
  const [sending, setSending] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [playbooks, setPlaybooks] = useState<string[]>([]);
  const logs = useRealtimeLogs(expanded ? vcooId : null);

  const loadState = async () => {
    try {
      const state = await getVCOOState(vcooId);
      setVcoo(state);
    } catch {
      // VCOO may not exist yet
    }
  };

  useEffect(() => {
    loadState();
    const interval = setInterval(loadState, 5000);
    return () => clearInterval(interval);
  }, [vcooId]);

  useEffect(() => {
    if (expanded) {
      listPlaybooks().then((data) => setPlaybooks(data.playbooks || []));
    }
  }, [expanded]);

  const agentOnline =
    vcoo?.agent &&
    vcoo.agent.last_seen &&
    Date.now() - new Date(vcoo.agent.last_seen).getTime() < 30000;

  const handleSend = async () => {
    if (!command.trim()) return;
    setSending(true);
    try {
      await enqueueCommand(vcooId, command.trim());
      setCommand('');
    } catch (e: any) {
      alert('Error: ' + e.message);
    } finally {
      setSending(false);
    }
  };

  const handlePlaybook = (name: string) => {
    setCommand(`playbook:${name}`);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div
        className="p-5 flex items-center justify-between cursor-pointer hover:bg-slate-800/30 transition"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {agentOnline ? (
            <CircleDot className="w-4 h-4 text-emerald-400" />
          ) : (
            <Circle className="w-4 h-4 text-slate-600" />
          )}
          <div>
            <div className="flex items-center gap-2">
              <code className="text-sm font-mono text-slate-300">{vcooId.substring(0, 12)}...</code>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                  agentOnline
                    ? 'bg-emerald-950 text-emerald-400'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                {agentOnline ? 'Online' : 'Sin agente'}
              </span>
            </div>
            {vcoo?.agent?.last_seen && (
              <div className="flex items-center gap-1 text-xs text-slate-600 mt-0.5">
                <Clock className="w-3 h-3" />
                {new Date(vcoo.agent.last_seen).toLocaleTimeString()}
              </div>
            )}
          </div>
        </div>
        <RefreshCw className="w-4 h-4 text-slate-600" />
      </div>

      {/* Expanded panel */}
      {expanded && (
        <div className="border-t border-slate-800 p-5 space-y-4">
          {/* Command input */}
          <div>
            <label className="text-xs text-slate-500 block mb-1.5 flex items-center gap-1">
              <Terminal className="w-3 h-3" />
              Enviar comando
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="ej: system-info.sh o comando personalizado..."
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 font-mono"
              />
              <button
                onClick={handleSend}
                disabled={sending || !command.trim()}
                className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-1.5 shrink-0"
              >
                <Play className="w-3.5 h-3.5" />
                {sending ? '...' : 'Run'}
              </button>
            </div>
          </div>

          {/* Playbooks quick-select */}
          {playbooks.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {playbooks.map((name) => (
                <button
                  key={name}
                  onClick={() => handlePlaybook(name)}
                  className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-emerald-400 px-2.5 py-1 rounded-md transition border border-slate-700 hover:border-emerald-800"
                >
                  {name}
                </button>
              ))}
            </div>
          )}

          {/* Live logs */}
          <div>
            <label className="text-xs text-slate-500 block mb-1.5 flex items-center gap-1">
              <Activity className="w-3 h-3" />
              Logs en tiempo real
            </label>
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs">
              {logs.length === 0 ? (
                <p className="text-slate-600 italic">Esperando logs...</p>
              ) : (
                logs.map((log, i) => (
                  <div
                    key={log.id || i}
                    className={`whitespace-pre-wrap break-all ${
                      log.stream === 'stderr'
                        ? 'text-red-400'
                        : log.stream === 'system'
                          ? 'text-amber-400'
                          : 'text-slate-300'
                    }`}
                  >
                    {log.chunk}
                  </div>
                ))
              )}
              <div className="text-slate-700 animate-pulse mt-1">▊</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function VCOOList({ vcooIds }: Props) {
  if (vcooIds.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <Terminal className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No hay VCOOs todavía</p>
        <p className="text-xs text-slate-600 mt-1">Crea uno con el botón de arriba</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-slate-400" />
        VCOOs activos ({vcooIds.length})
      </h2>
      {vcooIds.map((id) => (
        <VCOOCard key={id} vcooId={id} />
      ))}
    </div>
  );
}
