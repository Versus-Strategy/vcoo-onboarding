import { useState, useEffect, useRef, useCallback } from 'react';
import { setMasterKey, verifyAuth, listVCOOs, completeVCOO, deleteVCOO } from '../api/client';
import type { VCOOResult } from '../api/client';
import CreateVCOO from '../components/CreateVCOO';
import VCOOList from '../components/VCOOList';
import { LogIn, LogOut, ShieldCheck, Search, X, Sun, Moon, Monitor } from 'lucide-react';

type Filter = 'all' | 'active' | 'completed' | 'online';
type Theme = 'light' | 'dark' | 'auto';

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
  return 'light';
}

function resolveTheme(theme: Theme): 'light' | 'dark' {
  return theme === 'auto' ? getSystemTheme() : theme;
}

export default function Dashboard() {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [vcoos, setVcoos] = useState<VCOOResult[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('vcoo_theme') as Theme) || 'auto');
  const [toast, setToast] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  const resolvedTheme = resolveTheme(theme);

  useEffect(() => {
    const root = document.documentElement;
    if (resolvedTheme === 'dark') { root.classList.add('dark'); root.classList.remove('light'); }
    else { root.classList.add('light'); root.classList.remove('dark'); }
  }, [resolvedTheme]);

  useEffect(() => {
    if (theme !== 'auto') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => { const next = getSystemTheme(); document.documentElement.classList.toggle('dark', next === 'dark'); document.documentElement.classList.toggle('light', next === 'light'); };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme]);

  const cycleTheme = () => {
    const order: Theme[] = ['light', 'dark', 'auto'];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    localStorage.setItem('vcoo_theme', next);
  };

  const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor;

  const loadVCOOs = useCallback(async () => {
    try {
      const data = await listVCOOs();
      setVcoos(data);
      // Clear deletingIds for VCOOs that no longer exist in backend
      setDeletingIds(prev => {
        const backendIds = new Set(data.map(v => v.id));
        const next = new Set(prev);
        for (const id of prev) { if (!backendIds.has(id)) next.delete(id); }
        return next;
      });
    } catch {}
    finally { setLoading(false); }
  }, []);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setMasterKey(password);
    try { await verifyAuth(password); setAuthenticated(true); sessionStorage.setItem('vcoo_password', password); loadVCOOs(); }
    catch (err: any) { setError(err.message || 'Contraseña incorrecta'); setMasterKey(''); }
  };

  const handleLogout = () => {
    setMasterKey(''); sessionStorage.removeItem('vcoo_password'); setAuthenticated(false); setPassword(''); setVcoos([]);
  };

  useEffect(() => {
    const saved = sessionStorage.getItem('vcoo_password');
    if (saved) { setMasterKey(saved); setPassword(saved); setAuthenticated(true); loadVCOOs(); }
  }, [loadVCOOs]);

  useEffect(() => {
    if (!authenticated) return;
    const interval = setInterval(loadVCOOs, 5000);
    return () => clearInterval(interval);
  }, [authenticated, loadVCOOs]);

  const handleVCOOCreated = () => loadVCOOs();

  const handleComplete = async (vcooId: string) => {
    setVcoos(prev => prev.map(v => v.id === vcooId ? { ...v, status: 'completed' } : v));
    try { await completeVCOO(vcooId); }
    catch (e: any) { loadVCOOs(); showToast('Error al completar: ' + e.message); }
  };

  const handleDelete = async (vcooId: string) => {
    // Mark as deleting (visual indicator, no optimistic removal)
    setDeletingIds(prev => { const next = new Set(prev); next.add(vcooId); return next; });
    setExpandedId(null);
    try {
      await deleteVCOO(vcooId);
      // Deletion confirmed — refresh list; deletingIds auto-cleared when backend confirms gone
      await loadVCOOs();
    }
    catch (e: any) {
      setDeletingIds(prev => { const next = new Set(prev); next.delete(vcooId); return next; });
      showToast('Error al eliminar: ' + e.message);
    }
  };

  const handleReactivate = async (vcooId: string) => {
    setVcoos(prev => prev.map(v => v.id === vcooId ? { ...v, status: 'active' } : v));
    try { const { reactivateVCOO } = await import('../api/client'); await reactivateVCOO(vcooId); loadVCOOs(); }
    catch (e: any) { loadVCOOs(); showToast('Error al reactivar: ' + e.message); }
  };

  // Filter logic
  const filtered = vcoos.filter(v => {
    const q = search.toLowerCase();
    if (q && !v.id.toLowerCase().includes(q) && !(v.name && v.name.toLowerCase().includes(q))) return false;
    if (filter === 'all') return true;
    if (filter === 'active') return v.status === 'active';
    if (filter === 'completed') return v.status === 'completed';
    if (filter === 'online') return v.status === 'active' && v.agent && v.agent.last_seen && (Date.now() - new Date(v.agent.last_seen).getTime() < 30000);
    return true;
  });

  const onlineVCOOs = filtered.filter(v => v.status === 'active' && v.agent && v.agent.last_seen && (Date.now() - new Date(v.agent.last_seen).getTime() < 30000));
  const activeVCOOs = filtered.filter(v => v.status === 'active' && !(v.agent && v.agent.last_seen && (Date.now() - new Date(v.agent.last_seen).getTime() < 30000)));
  const completedVCOOs = filtered.filter(v => v.status === 'completed');

  const totalActive = vcoos.filter(v => v.status === 'active').length;
  const totalOnline = vcoos.filter(v => v.status === 'active' && v.agent && v.agent.last_seen && (Date.now() - new Date(v.agent.last_seen).getTime() < 30000)).length;
  const totalCompleted = vcoos.filter(v => v.status === 'completed').length;

  // ── LOGIN ──
  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-(--vs-bg)">
        <div className="max-w-md w-full mx-4">
          <div className="bg-(--vs-bg-card) border border-(--vs-border) rounded-xl p-8" style={{boxShadow: 'var(--vs-shadow)'}}>
            <div className="flex flex-col items-center mb-8">
              <span className="versus-logo-text text-3xl text-(--vs-heading)">VERSUS</span>
              <span className="versus-logo-sub text-xs mt-1 text-(--vs-muted)">Strategy & Tech</span>
            </div>
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-purple-950/20">
                <ShieldCheck className="w-6 h-6 text-[var(--vs-purple)]" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-(--vs-heading)">Operator Access</h1>
                <p className="text-sm text-(--vs-muted)">Autenticación requerida</p>
              </div>
            </div>
            <form onSubmit={handleLogin} className="space-y-4">
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-(--vs-input-bg) border border-(--vs-input-border) rounded-lg px-4 py-2.5 text-sm text-(--vs-heading) focus:outline-none focus:border-[var(--vs-purple)] focus:ring-1 focus:ring-[var(--vs-purple)]/20 transition font-mono"
                placeholder="••••••••" autoFocus />
              {error && <div className="p-3 bg-(--vs-red-bg) border border-(--vs-red-border) rounded-lg text-(--vs-red-text) text-sm flex items-center gap-2">⚠ {error}</div>}
              <button type="submit" disabled={!password.trim()}
                className="w-full bg-[var(--vs-purple)] hover:bg-[var(--vs-purple-hover)] disabled:opacity-40 text-white py-2.5 rounded-lg font-medium transition flex items-center justify-center gap-2">
                <LogIn className="w-4 h-4" /> Acceder
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // ── DASHBOARD ──
  return (
    <div className="min-h-screen bg-(--vs-bg)">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Header — VERSUS | VCOO Onboarding */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <span className="versus-logo-text text-xl text-(--vs-heading)">VERSUS</span>
              <span className="versus-logo-sub text-[8px] text-(--vs-muted)">Strategy & Tech</span>
            </div>
            <div className="w-px h-10 bg-(--vs-border) mx-1" />
            <div className="flex flex-col">
              <span className="text-lg font-black tracking-[0.25em] uppercase text-(--vs-heading)">VCOO</span>
              <span className="text-[10px] font-semibold tracking-[0.15em] uppercase text-(--vs-muted)">Onboarding</span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded font-medium bg-[var(--vs-purple)]/10 text-[var(--vs-purple)] ml-1">Dashboard</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={cycleTheme} className="p-2 rounded-lg hover:bg-(--vs-btn-secondary) text-(--vs-body) transition" title={`Tema: ${theme === 'light' ? 'Claro' : theme === 'dark' ? 'Oscuro' : 'Auto'}`}>
              <ThemeIcon className="w-4 h-4" />
            </button>
            <button onClick={handleLogout} className="text-sm text-(--vs-body) hover:text-(--vs-heading) transition flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-(--vs-btn-secondary)">
              <LogOut className="w-3.5 h-3.5" /> Salir
            </button>
          </div>
        </div>

        {/* Loading skeleton */}
        {loading ? (
          <div className="space-y-4 animate-pulse">
            <div className="grid grid-cols-4 gap-3">
              {[1,2,3,4].map(i => (
                <div key={i} className="rounded-xl p-4 border border-(--vs-border) bg-(--vs-bg-card)" style={{boxShadow: 'var(--vs-shadow)'}}>
                  <div className="h-3 w-12 bg-(--vs-border) rounded mb-2" />
                  <div className="h-6 w-8 bg-(--vs-border) rounded" />
                </div>
              ))}
            </div>
            <div className="h-10 bg-(--vs-bg-card) rounded-xl border border-(--vs-border)" />
            <div className="space-y-3">
              {[1,2,3].map(i => (
                <div key={i} className="h-20 bg-(--vs-bg-card) rounded-xl border border-(--vs-border)" style={{boxShadow: 'var(--vs-shadow)'}} />
              ))}
            </div>
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Online', value: totalOnline, f: 'online' as Filter, color: 'text-emerald-400' },
                { label: 'Activos', value: totalActive, f: 'active' as Filter, color: 'text-[var(--vs-purple)]' },
                { label: 'Completados', value: totalCompleted, f: 'completed' as Filter, color: 'text-(--vs-muted)' },
                { label: 'Total', value: vcoos.length, f: 'all' as Filter, color: 'text-(--vs-heading)' },
              ].map(stat => (
                <button key={stat.label} onClick={() => setFilter(filter === stat.f ? 'all' : stat.f)}
                  className="rounded-xl p-4 text-left transition cursor-pointer"
                  style={{
                    background: filter === stat.f ? 'var(--vs-stat-active-bg)' : 'var(--vs-stat-bg)',
                    border: filter === stat.f ? '1px solid var(--vs-stat-active-border)' : '1px solid var(--vs-stat-border)',
                    boxShadow: 'var(--vs-shadow)'
                  }}>
                  <div className="text-xs text-(--vs-muted) mb-1">{stat.label}</div>
                  <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                </button>
              ))}
            </div>

            {/* Filter badge */}
            {filter !== 'all' && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm" style={{background:'var(--vs-stat-active-bg)', color:'var(--vs-purple)'}}>
                Filtrando: {filter === 'active' ? 'Activos' : filter === 'completed' ? 'Completados' : 'Online'}
                <button onClick={() => setFilter('all')} className="hover:opacity-70"><X className="w-3.5 h-3.5" /></button>
              </div>
            )}

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-(--vs-muted)" />
              <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por nombre o ID..."
                className="w-full bg-(--vs-input-bg) border border-(--vs-input-border) rounded-lg pl-10 pr-8 py-2.5 text-sm text-(--vs-heading) focus:outline-none focus:border-[var(--vs-purple)] focus:ring-1 focus:ring-[var(--vs-purple)]/20 transition" />
              {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-(--vs-muted) hover:text-(--vs-heading)"><X className="w-3.5 h-3.5" /></button>}
            </div>

            {/* Create */}
            <CreateVCOO onCreated={handleVCOOCreated} />

            {/* Sections — always visible */}
            <VCOOList vcoos={onlineVCOOs} label="Online" icon="wifi" expandedId={expandedId} onToggle={setExpandedId}
              onRefresh={loadVCOOs} onComplete={handleComplete} onDelete={handleDelete} onReactivate={handleReactivate} deletingIds={deletingIds} />
            <VCOOList vcoos={activeVCOOs} label="Activos" icon="zap" expandedId={expandedId} onToggle={setExpandedId}
              onRefresh={loadVCOOs} onComplete={handleComplete} onDelete={handleDelete} onReactivate={handleReactivate} deletingIds={deletingIds} />
            <VCOOList vcoos={completedVCOOs} label="Completados" icon="archive" expandedId={expandedId} onToggle={setExpandedId}
              onRefresh={loadVCOOs} onComplete={handleComplete} onDelete={handleDelete} onReactivate={handleReactivate} deletingIds={deletingIds} />
          </>
        )}

        {/* Toast */}
        {toast && (
          <div className="fixed bottom-6 right-6 z-50">
            <div className="px-4 py-3 rounded-lg shadow-lg text-sm font-medium bg-(--vs-red-bg) border border-(--vs-red-border) text-(--vs-red-text)">{toast}</div>
          </div>
        )}
      </div>
    </div>
  );
}
