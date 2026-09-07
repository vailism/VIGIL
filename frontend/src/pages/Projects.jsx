import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMonitoredProjects, getMonitoredProjectObservations, getProjects, formatINR, formatPercent, formatDelayMonths } from '../services/api';
import OnboardModal from '../components/modals/OnboardModal';

const SECTORS = ['ALL','Road Transport and Highways','Railways','Power','Petroleum','Urban Development','Atomic Energy','OTHER'];
const RISK_TIERS = ['ALL','NORMAL','WATCH','REVIEW','ESCALATE'];
const GOV_STATES = ['ALL','ACTIVE','WARNING_ISSUED','UNDER_RECOVERY','RECOVERED','ESCALATED'];

const riskColor = r => r >= 0.50 ? '#dc2626' : r >= 0.45 ? '#ea580c' : r >= 0.40 ? '#d97706' : '#64748b';

export default function Projects() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('monitored');
  const [loading, setLoading] = useState(true);
  const [showOnboard, setShowOnboard] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState('ALL');
  const [selectedRisk, setSelectedRisk] = useState('ALL');
  const [selectedGov, setSelectedGov] = useState('ALL');
  const [monitoredList, setMonitoredList] = useState([]);
  const [portfolioList, setPortfolioList] = useState([]);
  const [totalPortfolio, setTotalPortfolio] = useState(0);

  const loadData = async () => {
    setLoading(true);
    try {
      const monRes = await getMonitoredProjects();
      const rawMon = monRes?.projects || [];
      const enriched = await Promise.all(rawMon.map(async (p) => {
        try {
          const obsRes = await getMonitoredProjectObservations(p.project_id).catch(() => ({ observations: [] }));
          const obsList = obsRes?.observations || [];
          const latest = obsList.length > 0 ? obsList[obsList.length - 1] : null;
          let trajectory = 'Stable';
          if (obsList.length >= 2) {
            const prev = obsList[obsList.length - 2];
            if (latest.pred_prob > prev.pred_prob + 0.02) trajectory = '↓ Deteriorating';
            else if (latest.pred_prob < prev.pred_prob - 0.02) trajectory = '↑ Improving';
          } else if (p.current_status === 'RECOVERED') trajectory = '↑ Improving';
          else if (p.current_status === 'WARNING_ISSUED' || p.current_status === 'ESCALATED') trajectory = '↓ Deteriorating';
          return { ...p, financial_progress: latest?.financial_progress ?? null, schedule_deviation_months: latest?.schedule_deviation_months ?? null, latest_risk: latest?.pred_prob ?? null, latest_risk_tier: latest?.risk_tier ?? 'NORMAL', latest_observation: latest?.reporting_month ?? p.initial_reporting_month, trajectory };
        } catch { return { ...p, financial_progress: null, schedule_deviation_months: null, latest_risk: null, latest_risk_tier: 'NORMAL', latest_observation: p.initial_reporting_month, trajectory: 'Stable' }; }
      }));
      setMonitoredList(enriched);
      const portRes = await getProjects({ limit: 100 });
      setPortfolioList(portRes?.projects || []);
      setTotalPortfolio(portRes?.total || 0);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, []);

  const filteredMon = monitoredList.filter(p => {
    if (searchTerm) { const q = searchTerm.toLowerCase(); if (!(p.project_id||'').toLowerCase().includes(q) && !(p.project_name||'').toLowerCase().includes(q)) return false; }
    if (selectedSector !== 'ALL' && p.sector !== selectedSector) return false;
    if (selectedRisk !== 'ALL' && p.latest_risk_tier !== selectedRisk) return false;
    if (selectedGov !== 'ALL') { const s = p.current_status; if (selectedGov === 'UNDER_RECOVERY' && (s === 'CONTRACTOR_RESPONDED' || s === 'UNDER_RECOVERY')) {} else if (s !== selectedGov) return false; }
    return true;
  });
  const filteredPort = portfolioList.filter(p => {
    if (searchTerm) { const q = searchTerm.toLowerCase(); if (!(p.project_id||'').toLowerCase().includes(q) && !(p.project_name||'').toLowerCase().includes(q)) return false; }
    if (selectedSector !== 'ALL' && p.sector !== selectedSector) return false;
    if (selectedRisk !== 'ALL' && p.latest_risk_tier !== selectedRisk) return false;
    return true;
  });

  const sel = 'border-b-2 border-slate-900 text-slate-900 font-bold';
  const unsel = 'border-b-2 border-transparent text-slate-500 hover:text-slate-700 font-semibold';
  const inputCls = 'px-3 py-2 bg-white/90 border border-slate-200 text-slate-800 text-[11px] font-medium rounded-2xl shadow-sm focus:outline-none focus:border-navy-300 focus:ring-2 focus:ring-navy-100 transition-all';

  return (
    <div className="p-4 min-w-0 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h1 className="text-[20px] font-bold text-slate-900 tracking-tight">Project Registry</h1>
        <button onClick={() => setShowOnboard(true)} className="px-3 py-2 bg-navy-900 hover:bg-navy-800 text-white text-[12px] font-bold uppercase rounded-md transition-colors">
          + Onboard project
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-6 border-b border-slate-200 mb-4 text-[11px] uppercase tracking-[0.16em] shrink-0">
        <button onClick={() => setActiveTab('monitored')} className={`pb-2.5 transition-colors ${activeTab === 'monitored' ? sel : unsel}`}>
          Active monitoring ({monitoredList.length})
        </button>
        <button onClick={() => setActiveTab('portfolio')} className={`pb-2.5 transition-colors ${activeTab === 'portfolio' ? sel : unsel}`}>
          National archive ({totalPortfolio.toLocaleString()})
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4 shrink-0">
        <input type="text" placeholder="Search project ID or name..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className={`${inputCls} w-64`} />
        <select value={selectedSector} onChange={e => setSelectedSector(e.target.value)} className={inputCls}>
          <option value="ALL">Sector: All</option>
          {SECTORS.filter(s => s !== 'ALL').map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={selectedRisk} onChange={e => setSelectedRisk(e.target.value)} className={inputCls}>
          <option value="ALL">Risk: All</option>
          {RISK_TIERS.filter(r => r !== 'ALL').map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        {activeTab === 'monitored' && (
          <select value={selectedGov} onChange={e => setSelectedGov(e.target.value)} className={inputCls}>
            <option value="ALL">Governance: All</option>
            {GOV_STATES.filter(g => g !== 'ALL').map(g => <option key={g} value={g}>{g.replace(/_/g, ' ')}</option>)}
          </select>
        )}
      </div>

      {/* Table */}
      <div className="panel-strong overflow-hidden flex-1 flex flex-col min-h-0">
        <div className="overflow-auto flex-1">
          <table className="w-full text-left text-[13px] border-collapse whitespace-nowrap">
            <thead className="bg-slate-50/95 backdrop-blur sticky top-0 z-10 border-b border-slate-200">
              <tr className="text-slate-500 font-bold uppercase tracking-[0.28em]">
                <th className="px-4 py-3">Project</th>
                <th className="px-3 py-3">Sector</th>
                <th className="text-right px-3 py-3">Cost</th>
                {activeTab === 'monitored' && <><th className="text-right px-3 py-3">Fin. prog</th><th className="text-right px-3 py-3">Delay</th></>}
                <th className="text-right px-3 py-3">Risk</th>
                <th className="px-3 py-3 text-center">Tier</th>
                {activeTab === 'monitored' && <><th className="px-3 py-3 text-center">Trajectory</th><th className="px-3 py-3">Status</th></>}
                <th className="text-right px-3 py-3">Report</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading ? (
                <tr><td colSpan={10} className="px-4 py-12 text-center text-slate-400 italic">Loading telemetry...</td></tr>
              ) : activeTab === 'monitored' ? filteredMon.map(p => (
                <tr key={p.project_id} onClick={() => navigate(`/projects/${encodeURIComponent(p.project_id)}`)} className="hover:bg-slate-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3 max-w-[220px]">
                    <div className="text-slate-900 font-bold truncate leading-tight">{p.project_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">{p.project_id}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-600 truncate max-w-[120px]">{p.sector}</td>
                  <td className="px-3 py-3 text-right font-mono text-slate-700">{formatINR(p.sanctioned_cost)}</td>
                  <td className="px-3 py-3 text-right font-mono text-slate-700">{p.financial_progress !== null ? formatPercent(p.financial_progress) : '—'}</td>
                  <td className="px-3 py-3 text-right font-mono text-slate-700">{p.schedule_deviation_months !== null ? formatDelayMonths(p.schedule_deviation_months) : '—'}</td>
                  <td className="px-3 py-3 text-right font-mono font-bold" style={{ color: p.latest_risk !== null ? riskColor(p.latest_risk) : '#94a3b8' }}>
                    {p.latest_risk !== null ? formatPercent(p.latest_risk) : '—'}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest ${
                      p.latest_risk_tier === 'ESCALATE' ? 'text-red-700 bg-red-50 border border-red-200' :
                      p.latest_risk_tier === 'WATCH' ? 'text-amber-700 bg-amber-50 border border-amber-200' :
                      'text-slate-500 bg-slate-50 border border-slate-200'
                    }`}>{p.latest_risk_tier}</span>
                  </td>
                  <td className="px-3 py-3 text-center font-bold text-[10px]" style={{ color: p.trajectory.includes('Deteriorating') ? '#ea580c' : p.trajectory.includes('Improving') ? '#64748b' : '#94a3b8' }}>{p.trajectory}</td>
                  <td className="px-3 py-3">
                    <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: p.current_status === 'ESCALATED' ? '#dc2626' : p.current_status === 'WARNING_ISSUED' ? '#ea580c' : '#64748b' }}>
                      <span className={`w-1.5 h-1.5 rounded-full ${p.current_status === 'ESCALATED' ? 'bg-red-600' : p.current_status === 'WARNING_ISSUED' ? 'bg-orange-500' : p.current_status === 'RECOVERED' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                      {(p.current_status || 'ACTIVE').replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-slate-500">{p.latest_observation}</td>
                </tr>
              )) : filteredPort.map(p => (
                <tr key={p.project_id} onClick={() => navigate(`/projects/${encodeURIComponent(p.project_id)}`)} className="hover:bg-slate-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3 max-w-[260px]">
                    <div className="text-slate-900 font-bold truncate leading-tight">{p.project_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">{p.project_id}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-600 truncate max-w-[130px]">{p.sector}</td>
                  <td className="px-3 py-3 text-right font-mono text-slate-700">{formatINR(p.baseline_cost)}</td>
                  <td className="px-3 py-3 text-right font-mono font-bold" style={{ color: riskColor(p.latest_risk) }}>{formatPercent(p.latest_risk)}</td>
                  <td className="px-3 py-3 text-center">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest ${
                      p.latest_risk_tier === 'ESCALATE' ? 'text-red-700 bg-red-50 border border-red-200' :
                      p.latest_risk_tier === 'WATCH' ? 'text-amber-700 bg-amber-50 border border-amber-200' :
                      'text-slate-500 bg-slate-50 border border-slate-200'
                    }`}>{p.latest_risk_tier}</span>
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-slate-500">{p.latest_observation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <OnboardModal isOpen={showOnboard} onClose={() => setShowOnboard(false)} onSuccess={loadData} />
    </div>
  );
}
