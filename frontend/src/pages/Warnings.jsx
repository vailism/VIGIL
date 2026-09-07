import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getMonitoredProjects,
  getMonitoredProjectWarnings,
  formatPercent
} from '../services/api';
import WarningResponseModal from '../components/modals/WarningResponseModal';
import { Search } from 'lucide-react';

export default function Warnings() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [warningsList, setWarningsList] = useState([]);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const [showResponseModal, setShowResponseModal] = useState(false);
  const [activeWarningItem, setActiveWarningItem] = useState(null);

  const loadWarnings = async () => {
    setLoading(true);
    try {
      const monRes = await getMonitoredProjects();
      const projects = monRes?.projects || [];

      const list = [];
      for (const p of projects) {
        try {
          const wRes = await getMonitoredProjectWarnings(p.project_id);
          const pWarnings = wRes?.warnings || [];
          for (const w of pWarnings) {
            list.push({
              ...w,
              project_name: p.project_name,
              current_project_status: p.current_status,
              warning_consecutive_count: p.warning_consecutive_count,
            });
          }
        } catch (e) {
          console.error(e);
        }
      }
      setWarningsList(list);
    } catch (err) {
      console.error('Failed to load warnings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWarnings();
  }, []);

  const activeCount = warningsList.filter((w) => w.status === 'ISSUED').length;
  const underRecoveryCount = warningsList.filter(
    (w) => w.status === 'RESPONSE_SUBMITTED' || w.current_project_status === 'UNDER_RECOVERY'
  ).length;
  const recoveredCount = warningsList.filter((w) => w.current_project_status === 'RECOVERED').length;
  const persistentCount = warningsList.filter(
    (w) => w.warning_consecutive_count >= 2 || w.current_project_status === 'ESCALATED'
  ).length;

  const filtered = warningsList.filter((w) => {
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      if (!w.project_name.toLowerCase().includes(q) && !w.project_id.toLowerCase().includes(q)) return false;
    }
    if (filterStatus === 'ACTIVE' && w.status !== 'ISSUED') return false;
    if (filterStatus === 'UNDER_RECOVERY' && w.current_project_status !== 'UNDER_RECOVERY') return false;
    if (filterStatus === 'RECOVERED' && w.current_project_status !== 'RECOVERED') return false;
    if (filterStatus === 'PERSISTENT' && w.warning_consecutive_count < 2 && w.current_project_status !== 'ESCALATED') return false;
    return true;
  });

  return (
    <div className="p-6 h-full flex flex-col min-w-0">
      
      {/* Header Info */}
      <div className="mb-5 shrink-0 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Contractor Warnings</h1>
      </div>

      <div className="p-4 bg-slate-50 border border-slate-200 rounded text-[11px] text-slate-600 mb-5 shrink-0">
        <span className="font-bold text-slate-900 uppercase tracking-widest mr-2">Notice Trigger Rule:</span>
        Early-warning notices automatically dispatched when project risk reaches or exceeds the 50% deterioration threshold.
      </div>

      {/* KPI stats strip */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm px-6 py-4 flex items-center justify-between text-xs divide-x divide-slate-100 mb-5 shrink-0">
        <div className="flex-1 flex items-baseline gap-2.5">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Active Notices</span>
          <span className="font-mono font-bold text-orange-600 text-lg">{activeCount}</span>
        </div>
        <div className="flex-1 pl-6 flex items-baseline gap-2.5">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Under Recovery</span>
          <span className="font-mono font-bold text-blue-600 text-lg">{underRecoveryCount}</span>
        </div>
        <div className="flex-1 pl-6 flex items-baseline gap-2.5">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Recovered</span>
          <span className="font-mono font-bold text-emerald-600 text-lg">{recoveredCount}</span>
        </div>
        <div className="flex-1 pl-6 flex items-baseline gap-2.5">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Persistent Deterioration</span>
          <span className="font-mono font-bold text-red-600 text-lg">{persistentCount}</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm p-4 flex flex-wrap items-center justify-between gap-3 mb-5 shrink-0">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
          <input
            type="text"
            placeholder="Filter warnings by project or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 text-slate-800 rounded text-[11px] font-medium shadow-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400 transition-all placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-1.5">
          {['ALL', 'ACTIVE', 'UNDER_RECOVERY', 'RECOVERED', 'PERSISTENT'].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors border ${
                filterStatus === st
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-500 border-slate-200 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              {st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Warnings Table */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm overflow-hidden flex-1 flex flex-col min-h-0">
        <div className="overflow-auto flex-1">
          <table className="w-full text-left text-[11px] border-collapse whitespace-nowrap">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr className="text-slate-500 font-bold uppercase tracking-wider">
                <th className="px-4 py-3">PROJECT</th>
                <th className="px-3 py-3 text-right">RISK AT WARNING</th>
                <th className="px-3 py-3">MONTH</th>
                <th className="px-3 py-3">TRIGGER REASON</th>
                <th className="px-3 py-3 text-center">CONTRACTOR STATUS</th>
                <th className="px-3 py-3 text-center">RECOVERY STATE</th>
                <th className="px-3 py-3 text-center">CYCLES</th>
                <th className="px-4 py-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-slate-400 italic">
                    Loading warning notices...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-slate-400 italic">
                    No contractor warnings matching filters.
                  </td>
                </tr>
              ) : (
                filtered.map((w) => (
                  <tr key={w.warning_id} className="hover:bg-slate-50 cursor-pointer transition-colors" onClick={() => navigate(`/projects/${encodeURIComponent(w.project_id)}`)}>
                    <td className="px-4 py-3 max-w-[220px]">
                      <div className="font-bold text-slate-900 truncate leading-tight" title={w.project_name}>
                        {w.project_name}
                      </div>
                      <div className="font-mono text-[10px] text-slate-500 truncate mt-0.5">
                        {w.project_id} · <span className="text-slate-400">{w.warning_id}</span>
                      </div>
                    </td>

                    <td className="px-3 py-3 text-right font-mono font-bold text-red-600">
                      {formatPercent(w.pred_prob, 2)}
                    </td>

                    <td className="px-3 py-3 font-mono text-slate-500">
                      {w.reporting_month}
                    </td>

                    <td className="px-3 py-3 max-w-[260px] text-slate-600 truncate" title={w.trigger_reason}>
                      {w.trigger_reason}
                    </td>

                    <td className="px-3 py-3 text-center">
                      {w.status === 'ISSUED' ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest bg-orange-50 border border-orange-200 text-orange-700">
                          Response requested
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest bg-blue-50 border border-blue-200 text-blue-700">
                          Response submitted
                        </span>
                      )}
                    </td>

                    <td className="px-3 py-3 text-center">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border ${
                        w.current_project_status === 'RECOVERED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : w.current_project_status === 'ESCALATED'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-slate-50 text-slate-600 border-slate-200'
                      }`}>
                        {(w.current_project_status || w.status || 'ACTIVE').replace(/_/g, ' ')}
                      </span>
                    </td>

                    <td className="px-3 py-3 text-center font-mono font-bold text-slate-700">
                      {w.warning_consecutive_count}
                    </td>

                    <td className="px-4 py-3 text-right space-x-3">
                      {w.status === 'ISSUED' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveWarningItem(w);
                            setShowResponseModal(true);
                          }}
                          className="text-[10px] font-bold uppercase tracking-wider text-orange-600 hover:text-orange-500 transition-colors"
                        >
                          Log Response
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/projects/${encodeURIComponent(w.project_id)}`);
                        }}
                        className="text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        View →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {activeWarningItem && (
        <WarningResponseModal
          isOpen={showResponseModal}
          onClose={() => {
            setShowResponseModal(false);
            setActiveWarningItem(null);
          }}
          projectId={activeWarningItem.project_id}
          warning={activeWarningItem}
          onSuccess={loadWarnings}
        />
      )}
    </div>
  );
}
