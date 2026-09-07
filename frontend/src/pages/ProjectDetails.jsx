import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ReferenceDot
} from 'recharts';
import {
  getMonitoredProject, getMonitoredProjectStatus, getMonitoredProjectObservations,
  getMonitoredProjectWarnings, getMonitoredProjectAudit, getProjectDetail, getProjectReplay,
  formatINR, formatPercent, formatDelayMonths
} from '../services/api';
import ObservationModal from '../components/modals/ObservationModal';
import WarningResponseModal from '../components/modals/WarningResponseModal';
import { ArrowLeft, Plus, ChevronRight, Sparkles, MessageSquare } from 'lucide-react';

export default function ProjectDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOperational, setIsOperational] = useState(false);

  // Project state
  const [project, setProject] = useState(null);
  const [status, setStatus] = useState(null);
  const [observations, setObservations] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);

  // Modals
  const [showObservationModal, setShowObservationModal] = useState(false);
  const [showResponseModal, setShowResponseModal] = useState(false);
  const [selectedWarning, setSelectedWarning] = useState(null);

  // Ask VIGIL state
  const [askVigilStatus, setAskVigilStatus] = useState('idle'); // idle, loading, success, error
  const [askVigilData, setAskVigilData] = useState(null);
  const [askVigilError, setAskVigilError] = useState(null);

  const handleAskVigil = async () => {
    setAskVigilStatus('loading');
    setAskVigilError(null);
    try {
      const res = await fetch('/api/ai/project-brief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: id })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to generate intelligence brief.');
      }
      const data = await res.json();
      setAskVigilData(data);
      setAskVigilStatus('success');
    } catch (e) {
      setAskVigilError(e.message);
      setAskVigilStatus('error');
    }
  };

  const fetchProjectData = async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Try operational monitoring
      try {
        const [projRes, statusRes, obsRes, warnRes, auditRes] = await Promise.all([
          getMonitoredProject(id),
          getMonitoredProjectStatus(id).catch(() => null),
          getMonitoredProjectObservations(id).catch(() => ({ observations: [] })),
          getMonitoredProjectWarnings(id).catch(() => ({ warnings: [] })),
          getMonitoredProjectAudit(id).catch(() => ({ audit_events: [] })),
        ]);

        setIsOperational(true);
        setProject(projRes);
        setStatus(statusRes);
        setObservations(obsRes?.observations || []);
        setWarnings(warnRes?.warnings || []);
        setAuditEvents(auditRes?.audit_events || []);
        setLoading(false);
        return;
      } catch {
        // Fall back to historical portfolio
      }

      // 2. Historical portfolio fallback
      const [histDetail, histReplay] = await Promise.all([
        getProjectDetail(id),
        getProjectReplay(id),
      ]);

      setIsOperational(false);
      setProject({
        project_id: histDetail.project_id,
        project_name: histDetail.project_name,
        sector: histDetail.sector,
        ministry: histDetail.ministry,
        state: histDetail.state,
        sanctioned_cost: histDetail.approved_cost || histDetail.current_trajectory_metrics?.C_base || 0,
        current_status: 'ACTIVE',
        initial_reporting_month: histDetail.start_month,
      });

      const timeline = histReplay?.timeline || [];
      setObservations(
        timeline.map((t) => ({
          reporting_month: t.reporting_month,
          financial_progress: t.financial_progress,
          physical_progress: null,
          cumulative_expenditure: t.expenditure,
          schedule_deviation_months: t.schedule_deviation_months,
          pred_prob: t.pred_prob,
          risk_tier: t.risk_tier,
          trajectory_status: 'SUFFICIENT_HISTORY',
          top_factors_json: JSON.stringify(t.top_explanations || []),
        }))
      );

      setAuditEvents([
        {
          event_id: 'AUDIT-HIST-01',
          event_type: 'ARCHIVE_RECORD_LOADED',
          performed_by: 'HISTORICAL_ARCHIVE',
          timestamp: histDetail.start_month,
          payload_json: JSON.stringify({ notes: 'Point-in-time timeline reconstructed from official repository' }),
        },
      ]);
    } catch (err) {
      setError(err.message || `Failed to load project '${id}'.`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjectData();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-slate-500 text-sm font-medium">
        <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin mr-3" />
        Loading telemetry for project: {id}...
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-8 max-w-lg mx-auto text-center border border-slate-200 bg-white rounded shadow-sm mt-12">
        <h2 className="text-sm font-bold text-slate-800">Project Not Found</h2>
        <p className="text-xs text-slate-500 mt-2">{error || `Project ID '${id}' not in registry.`}</p>
        <button
          onClick={() => navigate('/projects')}
          className="mt-4 px-4 py-2 text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 rounded transition-colors"
        >
          Return to Registry
        </button>
      </div>
    );
  }

  const latestObs = observations.length > 0 ? observations[observations.length - 1] : null;
  const currentRisk = status?.current_risk ?? latestObs?.pred_prob ?? null;
  const currentRiskTier = status?.risk_tier ?? latestObs?.risk_tier ?? 'NORMAL';
  const rawGov = status?.status ?? project?.current_status ?? 'ACTIVE';

  const hasWarning = rawGov === 'WARNING_ISSUED' || warnings.length > 0;
  const isUnderRecovery = rawGov === 'UNDER_RECOVERY' || rawGov === 'CONTRACTOR_RESPONDED';
  const isRecovered = rawGov === 'RECOVERED';
  const isEscalated = rawGov === 'ESCALATED';

  const activeWarning = warnings.find((w) => w.status === 'ISSUED') || (warnings.length > 0 ? warnings[warnings.length - 1] : null);
  const canRespondToWarning = isOperational && activeWarning && activeWarning.status === 'ISSUED';

  let riskDrivers = [];
  try {
    if (latestObs?.top_factors_json) {
      riskDrivers = JSON.parse(latestObs.top_factors_json);
    } else if (status?.active_warning?.top_factors) {
      riskDrivers = status.active_warning.top_factors;
    }
  } catch {
    riskDrivers = [];
  }

  let trajectoryLabel = 'Stable';
  if (observations.length >= 2) {
    const prev = observations[observations.length - 2];
    if (latestObs?.pred_prob > prev.pred_prob + 0.02) trajectoryLabel = '↓ Deteriorating';
    else if (latestObs?.pred_prob < prev.pred_prob - 0.02) trajectoryLabel = '↑ Improving';
  } else if (isRecovered) {
    trajectoryLabel = '↑ Improving';
  } else if (hasWarning || isEscalated) {
    trajectoryLabel = '↓ Deteriorating';
  }

  const chartData = observations.map((obs, idx) => {
    const riskPct = obs.pred_prob !== null && obs.pred_prob !== undefined
      ? parseFloat((obs.pred_prob * 100).toFixed(2))
      : null;

    let milestoneLabel = null;
    if (warnings.some((w) => w.reporting_month === obs.reporting_month)) milestoneLabel = 'Warning Issued';
    else if (isRecovered && idx === observations.length - 1) milestoneLabel = 'Recovered';
    else if (isEscalated && idx === observations.length - 1) milestoneLabel = 'Escalated';
    else if (obs.schedule_deviation_months && obs.schedule_deviation_months >= 36 && idx === 2) milestoneLabel = 'Deterioration';

    return {
      month: obs.reporting_month,
      risk: riskPct,
      fin_progress: obs.financial_progress ?? null,
      delay_months: obs.schedule_deviation_months ?? null,
      milestoneLabel,
    };
  });

  return (
    <div className="p-5 space-y-5 min-w-0">
      
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="flex items-center gap-1 text-[12px] font-semibold uppercase tracking-wider text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft size={14} /> Registry
        </button>
        <ChevronRight size={14} className="text-slate-300" />
        <span className="text-[13px] font-bold uppercase tracking-wider text-slate-900">{project.project_id}</span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        
        {/* LEFT: Project Identity & Actions (3/12) */}
        <div className="xl:col-span-3 flex flex-col gap-6">
          <div className="bg-white border border-slate-200 p-4">
            <h2 className="text-[18px] font-bold text-slate-800 leading-snug mb-1">{project.project_name}</h2>
            <div className="text-[12px] font-mono font-medium text-slate-500 mb-4">{project.project_id}</div>
            
            <div className="space-y-3 pt-4 border-t border-slate-100 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Sector</span>
                <span className="font-medium text-slate-800">{project.sector || 'Unspecified'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Baseline</span>
                <span className="font-mono font-bold text-slate-800">{formatINR(project.sanctioned_cost)}</span>
              </div>
              {project.ministry && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Ministry</span>
                  <span className="font-medium text-slate-800 text-right max-w-[140px] truncate" title={project.ministry}>{project.ministry}</span>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white border border-slate-200 p-4 flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Model Risk Tier</div>
              <div className="flex items-baseline gap-2 mb-1">
                <span className="font-mono text-[28px] font-bold text-slate-800">
                  {formatPercent(currentRisk, 2)}
                </span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border uppercase ${
                  currentRisk >= 0.50 ? 'text-red-600 bg-red-50 border-red-200' : currentRisk >= 0.40 ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-emerald-600 bg-emerald-50 border-emerald-200'
                }`}>
                  {currentRiskTier}
                </span>
              </div>
              <div className="text-[12px] font-semibold uppercase tracking-widest text-slate-600 mb-4">
                Trajectory: <span className={trajectoryLabel.includes('Deteriorating') ? 'text-orange-500' : 'text-slate-600'}>{trajectoryLabel}</span>
              </div>

              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 mt-4 pt-4 border-t border-slate-100">Governance State</div>
              <div className="mb-2">
                {isEscalated ? (
                  <span className="text-[10px] font-bold text-red-600 bg-red-50 border border-red-200 px-2 py-1 rounded block text-center">AUTHORITY ESCALATION</span>
                ) : isRecovered ? (
                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded block text-center">RECOVERED</span>
                ) : isUnderRecovery ? (
                  <span className="text-[10px] font-bold text-blue-600 bg-blue-50 border border-blue-200 px-2 py-1 rounded block text-center">UNDER RECOVERY</span>
                ) : hasWarning ? (
                  <span className="text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-1 rounded block text-center">CONTRACTOR WARNING</span>
                ) : (
                  <span className="text-[10px] font-bold text-slate-500 bg-slate-50 border border-slate-200 px-2 py-1 rounded block text-center">ACTIVE SURVEILLANCE</span>
                )}
              </div>
            </div>

            {isOperational && (
              <div className="pt-3 mt-2 space-y-2">
                {canRespondToWarning && (
                  <button
                    onClick={() => { setSelectedWarning(activeWarning); setShowResponseModal(true); }}
                    className="w-full px-3 py-2 text-[12px] font-bold uppercase tracking-wider bg-orange-600 hover:bg-orange-500 text-white rounded transition-colors"
                  >
                    Log Response
                  </button>
                )}
                <button
                  onClick={() => setShowObservationModal(true)}
                  className="w-full px-3 py-2 text-[12px] font-bold uppercase tracking-wider bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-700 rounded transition-colors flex items-center justify-center gap-1.5"
                >
                  <Plus size={14} /> New Observation
                </button>
              </div>
            )}
          </div>
        </div>

        {/* CENTER: Trajectory Chart (6/12) */}
        <div className="xl:col-span-6 bg-white border border-slate-200 rounded-md shadow-sm p-5 h-auto flex flex-col">
          <div className="flex flex-wrap items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div>
              <h3 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest">
                Longitudinal Trajectory
              </h3>
              <p className="text-[10px] text-slate-400 mt-1">
                Calibrated deterioration probability across reporting cycles
              </p>
            </div>
            <div className="flex items-center gap-4 text-[10px] font-mono font-bold tracking-wide">
              <span className="text-amber-500">WATCH (40)</span>
              <span className="text-orange-500">REV (45)</span>
              <span className="text-red-500">ESC (50)</span>
            </div>
          </div>

          <div className="flex-1 min-h-[400px] w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
                  <YAxis domain={[30, 75]} tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={(v) => `${v}`} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload || !payload.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-white border border-slate-200 text-slate-700 p-3 rounded shadow-md text-[11px] font-mono space-y-1.5">
                          <p className="font-bold text-slate-900 border-b border-slate-100 pb-1">{label}</p>
                          <p>Risk: <strong className="text-orange-600">{d.risk}%</strong></p>
                          {d.fin_progress !== null && <p>Fin Progress: {d.fin_progress}%</p>}
                          {d.delay_months !== null && <p>Delay: {formatDelayMonths(d.delay_months)}</p>}
                          {d.milestoneLabel && (
                            <p className="text-red-600 font-bold border-t border-slate-100 pt-1 mt-1">
                              {d.milestoneLabel}
                            </p>
                          )}
                        </div>
                      );
                    }}
                  />
                  <ReferenceLine y={40} stroke="#d97706" strokeDasharray="3 3" />
                  <ReferenceLine y={45} stroke="#ea580c" strokeDasharray="3 3" />
                  <ReferenceLine y={50} stroke="#dc2626" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="risk" stroke="#ea580c" strokeWidth={3}
                    dot={(props) => {
                      const { cx, cy, payload } = props;
                      const isEsc = payload.milestoneLabel === 'Escalated' || (payload.risk && payload.risk >= 60);
                      const isWarn = payload.milestoneLabel === 'Warning Issued';
                      const fill = isEsc ? '#ef4444' : isWarn ? '#f59e0b' : '#ea580c';
                      return (
                        <circle key={props.key} cx={cx} cy={cy} r={payload.milestoneLabel ? 5 : 3.5} fill={fill} stroke="#ffffff" strokeWidth={2} />
                      );
                    }}
                  />
                  {chartData.map((pt) => {
                    if (!pt.milestoneLabel) return null;
                    return (
                      <ReferenceDot key={pt.month} x={pt.month} y={pt.risk} r={0}
                        label={{
                          value: pt.milestoneLabel,
                          position: 'top',
                          fill: pt.milestoneLabel === 'Escalated' ? '#ef4444' : '#64748b',
                          fontSize: 10,
                          fontWeight: 700,
                          fontFamily: 'JetBrains Mono',
                        }}
                      />
                    );
                  })}
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">No longitudinal observations recorded.</div>
            )}
          </div>
          
          <div className="pt-4 mt-4 border-t border-slate-100 flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-500 tracking-wide bg-slate-50 p-2 rounded">
            <span>Obs: <strong className="text-slate-800">{observations.length}</strong></span>
            <span>Latest: <strong className="text-slate-800">{latestObs?.reporting_month || '—'}</strong></span>
            <span>Delay: <strong className="text-slate-800">{formatDelayMonths(latestObs?.schedule_deviation_months)}</strong></span>
            <span>Expenditure: <strong className="text-slate-800">{formatINR(latestObs?.cumulative_expenditure)}</strong></span>
          </div>
        </div>

        {/* RIGHT: Risk Drivers & Governance Timeline (3/12) */}
        <div className="xl:col-span-3 flex flex-col gap-6">
          <div className="bg-white border border-slate-200 rounded-md shadow-sm p-4 flex flex-col h-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <h3 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest">
                Risk Drivers
              </h3>
              <span className="text-[9px] font-bold font-mono text-slate-400 uppercase tracking-widest">TreeSHAP</span>
            </div>
            
            {riskDrivers.length > 0 ? (
              <div className="space-y-2">
                {riskDrivers.map((driver, idx) => (
                  <div key={idx} className="p-2 border border-slate-100 bg-slate-50 rounded-md text-[11px] flex flex-col">
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-semibold text-slate-800 leading-tight pr-2">{driver.explanation || driver.feature}</span>
                      <span className="font-mono font-bold text-orange-600">
                        {driver.contribution !== undefined ? `${driver.contribution >= 0 ? '+' : ''}${driver.contribution.toFixed(3)}` : ''}
                      </span>
                    </div>
                    <div className="text-[9px] font-mono text-slate-400">
                      Val: {String(driver.value)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-slate-400 italic">No anomalous drivers flagged.</p>
            )}
          </div>

          {/* ASK VIGIL PANEL */}
          <div className="bg-white border border-slate-200 rounded-md shadow-sm p-4 flex flex-col h-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <h3 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest flex items-center gap-1.5">
                <Sparkles size={12} className="text-violet-600" /> ASK VIGIL
              </h3>
              <span className="text-[9px] font-bold font-mono text-slate-400 uppercase tracking-widest">AI INTEL</span>
            </div>
            
            {askVigilStatus === 'idle' && (
              <div className="flex flex-col gap-3">
                <p className="text-[10px] text-slate-500 mb-1 leading-relaxed">
                  Ask about this project's trajectory and current status.
                </p>
                <div className="grid grid-cols-1 gap-2">
                  {['Why was this project flagged?', 'What changed recently?', 'Has the project recovered?', 'Summarize the current situation.'].map(q => (
                    <button 
                      key={q}
                      onClick={handleAskVigil}
                      className="text-left text-[11px] px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-slate-700 transition-colors flex items-center gap-2"
                    >
                      <MessageSquare size={10} className="text-violet-500" /> {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {askVigilStatus === 'loading' && (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500 gap-2">
                <div className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-[10px] font-medium uppercase tracking-widest text-violet-600 animate-pulse">Compiling Intelligence...</span>
              </div>
            )}

            {askVigilStatus === 'error' && (
              <div className="text-[10px] text-red-600 bg-red-50 p-3 rounded border border-red-200">
                <div className="font-bold mb-1">Intelligence Assistant Unavailable</div>
                <div>{askVigilError}</div>
                <button onClick={() => setAskVigilStatus('idle')} className="mt-2 font-bold underline hover:text-red-700">Try Again</button>
              </div>
            )}

            {askVigilStatus === 'success' && askVigilData && (
              <div className="flex flex-col gap-3 text-[11px]">
                <div className="bg-violet-50 border border-violet-100 p-3 rounded">
                  <p className="text-slate-800 leading-relaxed font-medium">{askVigilData.summary}</p>
                </div>
                
                {askVigilData.key_findings && askVigilData.key_findings.length > 0 && (
                  <div>
                    <h4 className="font-bold text-slate-700 uppercase tracking-wider mb-1.5 text-[9px]">Key Findings</h4>
                    <ul className="list-disc list-outside ml-3 text-slate-600 space-y-1">
                      {askVigilData.key_findings.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  </div>
                )}

                {askVigilData.evidence && askVigilData.evidence.length > 0 && (
                  <div>
                    <h4 className="font-bold text-slate-700 uppercase tracking-wider mb-1.5 text-[9px]">Observed Evidence</h4>
                    <ul className="list-disc list-outside ml-3 text-slate-600 space-y-1">
                      {askVigilData.evidence.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  </div>
                )}

                <div className="flex flex-col gap-1 border-t border-slate-100 pt-3 mt-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Governance:</span>
                    <span className="font-bold text-slate-800">{askVigilData.governance_status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Rec. Review:</span>
                    <span className="font-bold text-slate-800 text-right max-w-[60%]">{askVigilData.recommended_review}</span>
                  </div>
                </div>

                <div className="mt-2 pt-2 border-t border-slate-100 text-[9px] text-slate-400 italic text-center">
                  Generated from verified VIGIL project data.
                </div>
              </div>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-md shadow-sm p-4 flex flex-col flex-1 min-h-[300px]">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
              <h3 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest">
                Audit Ledger
              </h3>
            </div>
            
            <div className="overflow-y-auto flex-1 pr-2">
              <div className="space-y-4 relative before:absolute before:inset-0 before:ml-2 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-slate-200">
                {auditEvents.length > 0 ? (
                  auditEvents.map((evt, idx) => {
                    let parsed = {};
                    try { parsed = typeof evt.payload_json === 'string' ? JSON.parse(evt.payload_json) : evt.payload_json; } catch { parsed = {}; }
                    
                    const isEsc = evt.event_type.includes('ESCALAT');
                    const isWarn = evt.event_type.includes('WARNING');
                    const isRec = evt.event_type.includes('RECOVERY');
                    const isResp = evt.event_type.includes('RESPONSE');
                    
                    return (
                      <div key={evt.event_id || idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                        <div className={`flex items-center justify-center w-4 h-4 rounded-full border-2 border-white shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 ${
                            isEsc ? 'bg-red-500' : isWarn ? 'bg-orange-500' : isRec ? 'bg-emerald-500' : isResp ? 'bg-blue-500' : 'bg-slate-400'
                          }`}></div>
                        <div className="w-[calc(100%-2rem)] md:w-[calc(50%-1.5rem)] p-3 rounded border border-slate-200 bg-white shadow-sm">
                          <div className="flex items-center justify-between mb-1">
                            <div className={`font-bold text-[10px] uppercase tracking-wider ${isEsc ? 'text-red-600' : isWarn ? 'text-orange-600' : 'text-slate-700'}`}>{evt.event_type.replace(/_/g, ' ')}</div>
                            <time className="font-mono text-[9px] text-slate-400">{evt.timestamp}</time>
                          </div>
                          <div className="text-[10px] text-slate-500 leading-tight">
                            {parsed.trigger_reason || parsed.reason || parsed.response_text || parsed.notes || 'Status updated.'}
                          </div>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-[10px] text-slate-400 py-6 text-center italic w-full">No governance events.</div>
                )}
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
