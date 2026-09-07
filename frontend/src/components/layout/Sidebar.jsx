import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, TriangleAlert, Radar, Activity, ChartNoAxesCombined, LogIn, KeyRound } from 'lucide-react';
import { getHealth } from '../../services/api';

const nav = [
  { path: '/', label: 'Executive Overview', icon: LayoutDashboard },
  { path: '/projects', label: 'Intervention Triage', icon: TriangleAlert, badge: '214' },
  { path: '/warnings', label: 'Corridor Inspector', icon: Radar },
  { path: '/escalations', label: 'Telemetry & Sensors', icon: Activity, statusDot: true },
  { path: '/audit', label: 'Early-Warning Models', icon: ChartNoAxesCombined },
];

export default function Sidebar() {
  const loc = useLocation();
  const [health, setHealth] = useState(null);
  useEffect(() => { getHealth().then(d => setHealth({ ok: true, d })).catch(() => setHealth({ ok: false })); }, []);

  return (
    <aside className="h-full w-full flex flex-col panel-strong rounded-none lg:rounded-r-[2rem] lg:border-r-0 overflow-hidden">
      {/* Brand */}
      <div className="px-5 pt-6 pb-5 border-b border-slate-200 text-white" style={{ backgroundColor: 'var(--color-sidebar-bg)' }}>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-12 h-12 rounded-md bg-white/6 border border-white/8 flex items-center justify-center overflow-hidden shrink-0">
                <span className="text-[11px] uppercase tracking-[0.18em] text-white/90">VIGIL</span>
              </div>
            <div className="min-w-0">
              <div className="text-[15px] font-bold tracking-[0.24em] truncate">VIGIL</div>
              <div className="text-[10px] uppercase tracking-[0.32em] text-white/60 mt-1 truncate">Public Works Oversight</div>
            </div>
          </div>
          <span className="text-[9px] uppercase tracking-[0.3em] text-emerald-300 bg-transparent border border-white/10 rounded px-2 py-1">Live</span>
        </div>
        <div className="flex gap-2">
          <button className="flex-1 rounded-xl border border-white/10 bg-white/6 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.22em] text-white/80 hover:bg-white/10 transition-colors inline-flex items-center justify-center gap-2">
            <LogIn size={12} /> GovNet Login
          </button>
          <button className="flex-1 rounded-xl border border-white/10 bg-white/6 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.22em] text-white/80 hover:bg-white/10 transition-colors inline-flex items-center justify-center gap-2">
            <KeyRound size={12} /> Credential Key
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 bg-white/80">
        <div className="px-3 mb-2 text-[10px] font-bold text-slate-400 uppercase tracking-[0.3em]">Operational Portals</div>
        {nav.map(item => {
          const Icon = item.icon;
          const active = item.path === '/'
            ? ['/', '/dashboard', '/overview'].includes(loc.pathname)
            : loc.pathname.startsWith(item.path);
          return (
            <NavLink key={item.path} to={item.path}
              className={`group flex items-center gap-3 px-3 py-2.5 text-[12px] font-medium rounded-2xl transition-all duration-200 ${
                active
                  ? 'bg-navy-900 text-white shadow-[0_10px_25px_rgba(11,28,79,0.22)]'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
              }`}>
              <span className={`w-8 h-8 rounded-xl flex items-center justify-center transition-colors ${active ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-500 group-hover:bg-white'}`}>
                <Icon size={14} strokeWidth={active ? 2.4 : 2} />
              </span>
              <span className="flex-1 text-left">{item.label}</span>
              {item.statusDot && <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.12)]" />}
              {item.badge && <span className="ml-auto text-[9px] font-bold rounded-full bg-red-500 text-white px-1.5 py-0.5">{item.badge}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Engine status */}
      <div className="px-5 py-4 border-t border-slate-200 bg-gradient-to-br from-slate-50 to-white">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-2xl flex items-center justify-center bg-navy-900 text-white text-[10px] font-bold shadow-md">DO</span>
          <div>
            <div className="text-[11px] font-bold text-slate-900">Duty Officer Protocol</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${health?.ok ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-[10px] text-slate-500 font-mono">{health?.ok ? 'Node ID: 384-GovNet' : 'Connecting to engine...'}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
