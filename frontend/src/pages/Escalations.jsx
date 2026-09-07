import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAuthorityEscalations, formatPercent } from '../services/api';

export default function Escalations() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [escalations, setEscalations] = useState([]);

  useEffect(() => {
    getAuthorityEscalations()
      .then(res => setEscalations(res?.escalations || []))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 h-full flex flex-col min-w-0">
      
      {/* Header Info */}
      <div className="mb-5 shrink-0 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Authority Escalations</h1>
      </div>

      {/* Policy */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded text-[11px] text-slate-600 mb-5 shrink-0">
        <span className="font-bold text-slate-900 uppercase tracking-widest mr-2">Governance policy:</span>
        Persistent deterioration across consecutive cycles triggers formal referral to the supervisory ministry.
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm overflow-hidden flex-1 flex flex-col min-h-0">
        <div className="overflow-auto flex-1">
          <table className="w-full text-left text-[11px] border-collapse whitespace-nowrap">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr className="text-slate-500 font-bold uppercase tracking-wider">
                <th className="px-4 py-3">ID</th>
                <th className="px-3 py-3">PROJECT</th>
                <th className="px-3 py-3">SECTOR</th>
                <th className="text-right px-3 py-3">RISK</th>
                <th className="text-center px-3 py-3">CYCLES</th>
                <th className="px-3 py-3">DETERMINATION</th>
                <th className="px-3 py-3">ESCALATED TO</th>
                <th className="text-right px-4 py-3">DATE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400 italic">Loading telemetry...</td></tr>
              ) : escalations.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-400 italic">No authority escalations issued.</td></tr>
              ) : escalations.map(e => (
                <tr key={e.escalation_id} onClick={() => navigate(`/projects/${encodeURIComponent(e.project_id)}`)} className="hover:bg-slate-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3 font-mono text-[10px] text-red-600 font-bold uppercase tracking-wider">{e.escalation_id}</td>
                  <td className="px-3 py-3 max-w-[200px]">
                    <div className="text-slate-900 font-bold truncate leading-tight">{e.project_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">{e.project_id}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-600 truncate max-w-[120px]">{e.sector || '—'}</td>
                  <td className="px-3 py-3 text-right font-mono font-bold text-red-600">{formatPercent(e.pred_prob, 2)}</td>
                  <td className="px-3 py-3 text-center font-mono text-slate-700 font-bold">{e.persistence_cycles}</td>
                  <td className="px-3 py-3 text-slate-600 max-w-[240px] truncate">{e.reason || 'Persistent deterioration'}</td>
                  <td className="px-3 py-3 text-slate-600 truncate max-w-[140px]">{e.escalated_to}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-500">{e.reporting_month}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
