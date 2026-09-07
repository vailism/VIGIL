import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import {
  getDashboardSummary,
  getMonitoredProjects,
  getAuthorityEscalations,
  getMonitoredProjectWarnings,
  getAnalytics
} from '../services/api';

function KPI({ label, value, sub }) {
  return (
    <div className="p-3 border border-transparent">
      <div className="text-[11px] font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-[26px] font-mono font-bold text-slate-900">{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

function CompactDonut({ data }) {
  const COLORS = ['#059669', '#f59e0b', '#ea580c', '#dc2626'];
  const total = data.reduce((s, d) => s + (d.count || 0), 0);
  return (
    <div className="flex items-center gap-3">
      <div style={{ width: 120, height: 120 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="count" innerRadius={36} outerRadius={52} startAngle={90} endAngle={-270}>
              {data.map((entry, idx) => (
                <Cell key={`cell-${idx}`} fill={COLORS[idx % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[12px]">
        <div className="font-bold text-slate-900 text-[16px]">{total.toLocaleString()}</div>
        <div className="text-slate-500 text-[11px]">Total monitored</div>
      </div>
    </div>
  );
}

function ProjectRow({ p, onClick }) {
  const riskPct = p.risk !== null && p.risk !== undefined ? Math.round((p.risk || 0) * 100) : '—';
  const tier = p.risk >= 0.5 ? 'ESC' : p.risk >= 0.45 ? 'REV' : p.risk >= 0.4 ? 'WATCH' : 'NORMAL';
  return (
    <div onClick={onClick} className="flex items-center gap-3 px-3 py-2 border-b border-slate-100 hover:bg-slate-50 cursor-pointer">
      <div className="w-8 text-[12px] font-mono text-slate-600">{p.project_id}</div>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold text-slate-900 truncate">{p.project_name}</div>
        <div className="text-[11px] text-slate-500 truncate">{p.sector || '—'}</div>
      </div>
      <div className="text-right w-24">
        <div className="text-[14px] font-mono font-bold">{riskPct}{riskPct !== '—' ? '%' : ''}</div>
        <div className="text-[11px] text-slate-500">{tier}</div>
      </div>
    </div>
  );
}

export default function InterventionTriage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [projects, setProjects] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [sum, mon, esc, anl] = await Promise.all([
          getDashboardSummary().catch(() => null),
          getMonitoredProjects({ limit: 200 }).catch(() => ({ projects: [] })),
          getAuthorityEscalations().catch(() => ({ escalations: [] })),
          getAnalytics().catch(() => null),
        ]);
        setSummary(sum);
        setEscalations(esc?.escalations || []);
        setAnalytics(anl || null);
        const raw = mon?.projects || [];
        setProjects(raw.map((p) => ({ project_id: p.project_id, project_name: p.project_name, sector: p.sector, risk: p.latest_risk ?? null })));

        // fetch warnings separately for governance panel
        const warns = [];
        await Promise.all(raw.slice(0, 40).map(async (p) => {
          try {
            const res = await getMonitoredProjectWarnings(p.project_id).catch(() => ({ warnings: [] }));
            (res.warnings || []).forEach((w) => warns.push({ ...w, project_name: p.project_name }));
          } catch (e) { /* ignore */ }
        }));
        setWarnings(warns);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="p-6">Loading dashboard...</div>;

  const total = summary?.active_project_count ?? projects.length;
  const atRisk = (summary?.watch_count || 0) + (summary?.review_count || 0) + (summary?.escalate_count || 0);
  const highRisk = summary?.escalate_count ?? projects.filter(p => p.risk >= 0.5).length;
  const openWarnings = warnings.filter(w => w.status === 'ISSUED').length;
  const authorityEsc = escalations.length;
  const exposure = summary?.active_baseline_exposure ?? '—';

  const riskDistribution = [
    { name: 'Normal', count: summary?.normal_count || 0 },
    { name: 'Watch', count: summary?.watch_count || 0 },
    { name: 'Review', count: summary?.review_count || 0 },
    { name: 'High Risk', count: summary?.escalate_count || 0 },
  ];

  // Build compact panels using analytics when available
  const sectorData = analytics?.sectorData || [];
  const ministry = analytics?.ministryAnalytics || [];

  return (
    <div className="min-w-0">
      {/* KPI strip */}
      <div className="grid grid-cols-6 gap-4 mb-4">
        <KPI label="Total monitored" value={(total || 0).toLocaleString()} sub="Active projects" />
        <KPI label="Projects at risk" value={(atRisk || 0).toLocaleString()} />
        <KPI label="High risk" value={(highRisk || 0).toLocaleString()} />
        <KPI label="Open warnings" value={(openWarnings || 0).toLocaleString()} />
        <KPI label="Authority escalations" value={(authorityEsc || 0).toLocaleString()} />
        <KPI label="Capital exposure" value={exposure !== '—' ? exposure : '—'} sub={exposure !== '—' ? 'Baseline exposure' : ''} />
      </div>

      <div className="grid grid-cols-12 gap-4 min-h-[720px]">
        <div className="col-span-3 bg-white border border-slate-200 p-2 flex flex-col">
          <div className="text-[12px] font-semibold text-slate-700 mb-2">Projects Requiring Attention</div>
          <div className="flex-1 overflow-y-auto border-t border-slate-100">
            {projects.length === 0 ? <div className="p-4 text-[11px] text-slate-500">NO ACTIVE ITEMS</div> : projects.slice(0, 40).map((p) => (
              <ProjectRow key={p.project_id} p={p} onClick={() => navigate(`/projects/${encodeURIComponent(p.project_id)}`)} />
            ))}
          </div>
        </div>

        <div className="col-span-6 bg-white border border-slate-200 p-3 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[12px] font-semibold text-slate-700">Portfolio Risk Distribution</div>
              <div className="text-[11px] text-slate-500">Risk tiers across the active portfolio</div>
            </div>
            <div className="text-[11px] text-slate-500">As of {summary?.latest_data_month || 'Live'}</div>
          </div>
          <div className="flex gap-6 items-start">
            <div style={{width:140,height:140}} className="flex-shrink-0">
              <CompactDonut data={riskDistribution} />
            </div>
            <div className="flex-1">
              <div className="grid grid-cols-2 gap-2">
                {riskDistribution.map((r) => (
                  <div key={r.name} className="p-2 border border-slate-100">
                    <div className="text-[11px] text-slate-500">{r.name}</div>
                    <div className="text-[18px] font-mono font-bold mt-1 text-slate-900">{(r.count || 0).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-3">
            <div className="p-3 border border-slate-100">
              <div className="text-[12px] font-semibold text-slate-700">Risk by Sector</div>
              <div className="mt-2 text-[11px] text-slate-600">
                {sectorData.length === 0 ? 'No sector breakdown available' : sectorData.slice(0,4).map(s => (
                  <div key={s.sector} className="flex justify-between py-1"><span>{s.sector}</span><span className="font-mono">{s.projects}</span></div>
                ))}
              </div>
            </div>
            <div className="p-3 border border-slate-100">
              <div className="text-[12px] font-semibold text-slate-700">Top Ministries</div>
              <div className="mt-2 text-[11px] text-slate-600">
                {ministry.length === 0 ? 'No ministry analytics' : ministry.slice(0,4).map(m => (
                  <div key={m.ministry} className="flex justify-between py-1"><span className="truncate">{m.ministry}</span><span className="font-mono">{m.projects}</span></div>
                ))}
              </div>
            </div>
            <div className="p-3 border border-slate-100">
              <div className="text-[12px] font-semibold text-slate-700">Recent Top Projects</div>
              <div className="mt-2 text-[11px] text-slate-600">
                {projects.slice(0,5).map(p => (
                  <div key={p.project_id} className="flex justify-between py-1"><span className="truncate">{p.project_name}</span><span className="font-mono">{p.project_id}</span></div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-3 bg-white border border-slate-200 p-3 flex flex-col">
          <div className="text-[12px] font-semibold text-slate-700 mb-2">Governance Activity</div>
          <div className="flex-1 overflow-y-auto border-t border-slate-100 p-1">
            {warnings.length + escalations.length === 0 ? (
              <div className="p-4 text-[11px] text-slate-500">NO ACTIVE ITEMS</div>
            ) : (
              <div className="space-y-2 p-1">
                {warnings.slice(0, 60).map((w, i) => (
                  <div key={`w-${i}`} className="p-2 border border-slate-100">
                    <div className="text-[12px] font-semibold text-slate-900">{w.project_name}</div>
                    <div className="text-[11px] text-slate-500">{w.description || w.reason || w.reporting_month}</div>
                    <div className="text-[11px] text-slate-500 mt-1">Status: {w.status}</div>
                  </div>
                ))}
                {escalations.slice(0, 60).map((e, i) => (
                  <div key={`e-${i}`} className="p-2 border border-slate-100 bg-rose-50/40">
                    <div className="text-[12px] font-semibold text-slate-900">{e.project_name}</div>
                    <div className="text-[11px] text-slate-700">{e.reason || e.reporting_month}</div>
                    <div className="text-[11px] text-slate-700 mt-1">Escalation</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
