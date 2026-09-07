import React from 'react';
import { useLocation } from 'react-router-dom';
import { Search, Bell, Sparkles, Radio, Clock3 } from 'lucide-react';

const titles = {
  '/': 'Intervention Triage Panorama',
  '/dashboard': 'Intervention Triage Panorama',
  '/projects': 'Longitudinal Surveillance Roster',
  '/warnings': 'Active Early-Warning Notices',
  '/escalations': 'Intervention Referrals',
  '/audit': 'Immutable Governance Log',
  '/demo': 'Deterministic Validation Runs',
};

export default function Topbar() {
  const loc = useLocation();
  const title = titles[loc.pathname] || (
    loc.pathname.startsWith('/projects/') ? 'Project Intelligence Dossier' : 'Overview'
  );

  return (
    <header className="sticky top-0 z-30 min-w-0 px-4 sm:px-6 lg:px-7 pt-4">
      <div className="px-3 py-3 bg-white border-b border-slate-200 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <div className="flex flex-col">
            <div className="text-[12px] font-semibold text-slate-500 uppercase tracking-[0.18em]">Cabinet Oversight — National Infrastructure</div>
            <div className="text-[20px] font-bold text-slate-900 truncate">{title}</div>
          </div>
          <div className="hidden lg:flex items-center gap-2 text-[11px] text-slate-600">
            <span className="px-2 py-1 border border-slate-100 text-slate-700">Live · {new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
            <span className="px-2 py-1 border border-slate-100 text-slate-700">Telemetry · 0.8s</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input type="text" placeholder="Search project, corridor, package..."
              className="pl-10 pr-3 py-2 bg-slate-50 border border-slate-200 text-slate-700 text-[13px] w-80 rounded-md focus:outline-none focus:border-navy-300 placeholder:text-slate-400 transition-colors" />
          </div>
          <button className="w-10 h-10 flex items-center justify-center text-slate-500 hover:text-slate-800 border border-slate-200 bg-white rounded-md transition-all relative">
            <Bell size={16} />
            <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-red-500" />
          </button>
        </div>
      </div>
    </header>
  );
}
