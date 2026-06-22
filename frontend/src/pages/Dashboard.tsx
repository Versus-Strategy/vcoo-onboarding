import { useState, useEffect } from 'react';
import { setMasterKey, healthCheck, listVCOOs } from '../api/client';
import CreateVCOO from '../components/CreateVCOO';
import VCOOList from '../components/VCOOList';
import { LogIn, LogOut, ShieldCheck } from 'lucide-react';

export default function Dashboard() {
  const [authenticated, setAuthenticated] = useState(false);
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [vcooIds, setVcooIds] = useState<string[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadVCOOs = async () => {
    try {
      const data = await listVCOOs();
      setVcooIds(data.map((v) => v.id));
    } catch {
      // backend might not be reachable yet
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMasterKey(key);
    try {
      const health = await healthCheck();
      if (health.status === 'ok') {
        setAuthenticated(true);
        sessionStorage.setItem('vcoo_master_key', key);
        loadVCOOs();
      }
    } catch (err: any) {
      setError('Clave inválida o el backend no responde');
      setMasterKey('');
    }
  };

  const handleLogout = () => {
    setMasterKey('');
    sessionStorage.removeItem('vcoo_master_key');
    setAuthenticated(false);
    setKey('');
    setVcooIds([]);
  };

  // Restore session on mount
  useEffect(() => {
    const saved = sessionStorage.getItem('vcoo_master_key');
    if (saved) {
      setMasterKey(saved);
      setKey(saved);
      setAuthenticated(true);
      loadVCOOs();
    }
  }, []);

  // Poll for updates every 5s
  useEffect(() => {
    if (!authenticated) return;
    const interval = setInterval(loadVCOOs, 5000);
    return () => clearInterval(interval);
  }, [authenticated, refreshKey]);

  const handleVCOOCreated = () => {
    loadVCOOs();
    setRefreshKey((k) => k + 1);
  };

  if (!authenticated) {
    return (
      <div className="max-w-md mx-auto mt-20">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-emerald-950 rounded-lg">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Operator Access</h1>
              <p className="text-sm text-slate-500">Autenticación requerida</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">
                MASTER_KEY
              </label>
              <input
                type="password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 transition font-mono"
                placeholder="••••••••••••••••••••••••"
                autoFocus
              />
            </div>

            {error && (
              <div className="p-3 bg-red-950/50 border border-red-800/50 rounded-lg text-red-400 text-sm flex items-center gap-2">
                <span className="text-base">⚠</span>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={!key.trim()}
              className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-lg font-medium transition flex items-center justify-center gap-2"
            >
              <LogIn className="w-4 h-4" />
              Acceder al Dashboard
            </button>
          </form>

          <p className="text-xs text-slate-600 mt-6 text-center">
            VCOO Onboarding Platform · v1.0
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            Gestión de VCOOs y agentes conectados
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="text-sm text-slate-400 hover:text-white transition flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-slate-800"
        >
          <LogOut className="w-3.5 h-3.5" />
          Salir
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'VCOOs', value: vcooIds.length, color: 'text-emerald-400' },
          { label: 'Agentes online', value: '—', color: 'text-blue-400' },
          { label: 'Comandos hoy', value: '—', color: 'text-amber-400' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4"
          >
            <div className="text-xs text-slate-500 mb-1">{stat.label}</div>
            <div className={`text-2xl font-bold ${stat.color}`}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Create VCOO */}
      <CreateVCOO onCreated={handleVCOOCreated} />

      {/* VCOO List */}
      <VCOOList vcooIds={vcooIds} />
    </div>
  );
}
