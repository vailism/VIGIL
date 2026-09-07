import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getMonitoredProjects,
  getMonitoredProjectAudit
} from '../services/api';
import { Search } from 'lucide-react';

export default function AuditTrail() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState('ALL');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    async function loadAudit() {
      setLoading(true);
      try {
        const monRes = await getMonitoredProjects();
        const projects = monRes?.projects || [];

        let allEvents = [];
        for (const p of projects) {
          try {
            const aRes = await getMonitoredProjectAudit(p.project_id);
            const pEvents = aRes?.audit_events || [];
            pEvents.forEach((e) => {
              allEvents.push({ ...e, project_name: p.project_name });
            });
          } catch (e) {
            console.error(e);
          }
        }
        allEvents.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
        setEvents(allEvents);
      } catch (err) {
        console.error('Failed to load audit log:', err);
      } finally {
        setLoading(false);
      }
    }
    loadAudit();
  }, []);

  const types = ['ALL', ...new Set(events.map((e) => e.event_type).filter(Boolean))];

  const filtered = events.filter((e) => {
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      if (!e.project_id.toLowerCase().includes(q) && !(e.project_name || '').toLowerCase().includes(q) && !e.event_type.toLowerCase().includes(q)) {
        return false;
      }
    }
    if (selectedType !== 'ALL' && e.event_type !== selectedType) return false;
    return true;
  });

  return (
    <div className="p-6 h-full flex flex-col min-w-0">
      
      {/* Header Info */}
      <div className="mb-5 shrink-0 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">System Audit Trail</h1>
      </div>

      {/* Governance banner */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded text-[11px] text-slate-600 mb-5 shrink-0">
        <span className="font-bold text-slate-900 uppercase tracking-widest mr-2">Immutable Governance Ledger:</span>
        Records all observation submissions, LightGBM model inferences, warning notices, and authority escalations with cryptographic integrity.
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm p-4 flex flex-wrap items-center justify-between gap-3 mb-5 shrink-0">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
          <input
            type="text"
            placeholder="Filter audit log by project or event..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 text-slate-800 rounded text-[11px] font-medium shadow-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400 transition-all placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-500 text-[10px] font-bold uppercase tracking-wider">Event Type:</span>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-3 py-2 bg-white border border-slate-200 text-slate-800 text-[11px] font-medium rounded shadow-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400 transition-all"
          >
            {types.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-white border border-slate-200 rounded-md shadow-sm overflow-hidden flex-1 flex flex-col min-h-0">
        <div className="overflow-auto flex-1">
          <table className="w-full text-left text-[11px] border-collapse whitespace-nowrap">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr className="text-slate-500 font-bold uppercase tracking-wider">
                <th className="px-4 py-3">TIMESTAMP</th>
                <th className="px-3 py-3">PROJECT</th>
                <th className="px-3 py-3">EVENT TYPE</th>
                <th className="px-3 py-3">ACTOR</th>
                <th className="px-3 py-3">PAYLOAD SUMMARY</th>
                <th className="px-4 py-3 text-right">RECORD</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-400 italic">
                    Loading audit ledger...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-400 italic">
                    No audit records logged.
                  </td>
                </tr>
              ) : (
                filtered.map((ev, idx) => {
                  const key = ev.event_id || idx;
                  const isExpanded = expandedId === key;

                  let parsedJson = null;
                  try {
                    parsedJson = typeof ev.payload_json === 'string' ? JSON.parse(ev.payload_json) : ev.payload_json;
                  } catch {
                    parsedJson = ev.payload_json;
                  }

                  return (
                    <React.Fragment key={key}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : key)}
                        className={`hover:bg-slate-50 cursor-pointer transition-colors ${isExpanded ? 'bg-slate-50' : ''}`}
                      >
                        <td className="px-4 py-3 font-mono text-[10px] text-slate-500 whitespace-nowrap">
                          {ev.timestamp}
                        </td>
                        <td className="px-3 py-3 max-w-[200px]" onClick={(e) => { e.stopPropagation(); navigate(`/projects/${encodeURIComponent(ev.project_id)}`); }}>
                          <div className="font-bold text-slate-900 truncate hover:text-orange-600 transition-colors" title={ev.project_name}>
                            {ev.project_name || ev.project_id}
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{ev.project_id}</div>
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-bold uppercase tracking-wider">
                            {ev.event_type}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-slate-600 font-mono text-[10px] whitespace-nowrap">
                          {ev.performed_by}
                        </td>
                        <td className="px-3 py-3 max-w-sm truncate text-slate-500 text-[11px]">
                          {typeof ev.payload_json === 'string' ? ev.payload_json : JSON.stringify(ev.payload_json)}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:text-slate-800 transition-colors">
                            {isExpanded ? 'Hide ▲' : 'Inspect ▼'}
                          </span>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="p-4 border-b border-slate-200 shadow-inner">
                            <div className="p-4 bg-slate-900 border border-slate-800 text-slate-300 text-[11px] rounded font-mono space-y-3">
                              <div className="text-slate-500 border-b border-slate-800 pb-2 flex flex-wrap justify-between items-center text-[10px]">
                                <span>RECORD ID: <strong className="text-slate-300">{ev.event_id}</strong></span>
                                <span>TIMESTAMP: <strong className="text-slate-300">{ev.timestamp}</strong></span>
                                <span>PERFORMED BY: <strong className="text-slate-300">{ev.performed_by}</strong></span>
                              </div>
                              <pre className="text-emerald-400 whitespace-pre-wrap overflow-x-auto pt-1 leading-relaxed text-[11px]">
                                {JSON.stringify(parsedJson, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
