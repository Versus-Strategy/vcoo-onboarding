import { Link, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, Terminal } from 'lucide-react';

export default function Layout() {
  const location = useLocation();
  const isDashboard = location.pathname.startsWith('/dashboard');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <Terminal className="w-5 h-5 text-emerald-400" />
            <div>
              <div className="text-lg font-black tracking-[0.25em] text-white leading-none">
                VCOO
              </div>
              <div className="text-[9px] font-semibold tracking-[0.15em] text-slate-500 uppercase leading-none mt-0.5">
                Onboarding
              </div>
            </div>
          </Link>
          <nav className="flex gap-1">
            <Link
              to="/dashboard"
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition ${
                isDashboard
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </Link>
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
