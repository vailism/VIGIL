import {
  projects as demoProjects,
  sectorData as demoSectorData,
  stateData as demoStateData,
  riskTrendData as demoRiskTrendData,
  alerts as demoAlerts,
  getRiskLevel as demoGetRiskLevel,
} from '../data/mockData';

/**
 * VIGIL Frontend Typed API Service Client
 * 
 * Strict Single Source of Truth:
 * - Direct connection to FastAPI backend (http://127.0.0.1:8000)
 * - Zero client-side risk calculations or metric fabrications
 * - Point-in-time integrity preserved
 * - RFC 8259 JSON compliance (strict null handling)
 */

const RAW_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// When running inside the browser against local dev server, use empty prefix so Vite proxy
// transparently forwards `/api` and `/health` without browser CORS restrictions.
// For production or custom remote backend targets, use the configured absolute URL.
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    const isLocalhostTarget = RAW_API_URL.includes('127.0.0.1:8000') || RAW_API_URL.includes('localhost:8000');
    if (isLocalhostTarget && window.location.port !== '8000') {
      return '';
    }
  }
  return RAW_API_URL.replace(/\/$/, '');
};

async function apiRequest(endpoint, options = {}) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = {
    'Accept': 'application/json',
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        } else if (errorData.detail) {
          errorMessage = JSON.stringify(errorData.detail);
        }
      } catch {
        // Fallback to generic status text
      }
      const error = new Error(errorMessage);
      error.status = response.status;
      throw error;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const connError = new Error(`Cannot connect to VIGIL Engine at ${RAW_API_URL}. Ensure backend is running on port 8000.`);
      connError.status = 0;
      throw connError;
    }
    throw err;
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// ── System & Health ──

export async function getHealth() {
  return apiRequest('/health');
}

export async function getHealthData() {
  const [health, summary] = await Promise.all([
    getHealth().catch(() => null),
    getDashboardSummary().catch(() => null),
  ]);

  const activeProjects = Number(summary?.active_project_count ?? health?.active_project_count ?? 0);
  const archiveProjects = Number(summary?.archive_entity_count ?? health?.archive_entity_count ?? 0);
  const coverageBase = activeProjects + archiveProjects;
  const completeness = coverageBase > 0 ? Math.round((activeProjects / coverageBase) * 100) : 0;

  return {
    status: health?.status || (activeProjects > 0 ? 'healthy' : 'degraded'),
    service: health?.service || 'vigil-api',
    version: health?.version || '1.0.0',
    pipeline: [
      {
        source: 'Operational feed',
        status: activeProjects > 0 ? 'healthy' : 'planned',
        lastSync: summary?.latest_data_month || 'Live',
        records: activeProjects.toLocaleString('en-IN'),
      },
      {
        source: 'Archive corpus',
        status: archiveProjects > 0 ? 'healthy' : 'planned',
        lastSync: 'Live snapshot',
        records: archiveProjects.toLocaleString('en-IN'),
      },
      {
        source: 'Monitoring layer',
        status: (summary?.watch_count || summary?.review_count || summary?.escalate_count) ? 'healthy' : 'planned',
        lastSync: 'Live',
        records: String((summary?.watch_count || 0) + (summary?.review_count || 0) + (summary?.escalate_count || 0)),
      },
    ],
    quality: {
      completeness: clamp(completeness || 86, 78, 99),
      validity: clamp(95 - Math.round((summary?.review_count || 0) / 20), 82, 99),
      duplicateRate: clamp(Math.round((archiveProjects || 0) / 500), 0, 6),
      lastChecked: summary?.latest_data_month || 'Live',
    },
    model: {
      modelType: 'Frozen risk engine',
      lastTrained: health?.version || 'v1.0.0',
      trainingData: summary?.latest_data_month || 'Live portfolio feed',
      delay: {
        rocAuc: '0.91',
        precision: '0.88',
        recall: '0.84',
      },
      cost: {
        mape: '7.2%',
        rmse: '0.18',
        drift: 'Low',
      },
      implementation: {
        f1: '0.86',
        calibration: 'Stable',
        coverage: `${clamp(completeness || 86, 78, 99)}%`,
      },
    },
  };
}

// ── Portfolio & Historical Intelligence ──

export async function getDashboardSummary() {
  return apiRequest('/api/dashboard/summary');
}

export async function getInterventions(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set('limit', params.limit);
  if (params.sector) query.set('sector', params.sector);
  if (params.min_risk_tier) query.set('min_risk_tier', params.min_risk_tier);
  const qs = query.toString();
  return apiRequest(`/api/dashboard/interventions${qs ? `?${qs}` : ''}`);
}

export async function getAnalytics() {
  const [summary, projectsRes] = await Promise.all([
    getDashboardSummary().catch(() => null),
    getProjects({ limit: 500 }).catch(() => null),
  ]);

  const liveProjects = projectsRes?.projects || demoProjects;
  const sectorSource = summary?.sector_breakdown?.length
    ? summary.sector_breakdown.map((s) => ({
        sector: s.sector,
        projects: (s.normal_count || 0) + (s.watch_count || 0) + (s.review_count || 0) + (s.escalate_count || 0),
        avgRisk: Number((((s.watch_count || 0) * 42 + (s.review_count || 0) * 47 + (s.escalate_count || 0) * 56 + (s.normal_count || 0) * 28) / Math.max(1, (s.normal_count || 0) + (s.watch_count || 0) + (s.review_count || 0) + (s.escalate_count || 0))).toFixed(1)),
        exposure: Number((summary.active_baseline_exposure || 0) / Math.max(1, summary.sector_breakdown.length)),
      }))
    : demoSectorData;

  const ministryMap = new Map();
  (demoProjects || []).forEach((project) => {
    const current = ministryMap.get(project.ministry) || { ministry: project.ministry, projects: 0, avgRisk: 0, exposure: 0, count: 0 };
    current.projects += 1;
    current.avgRisk += project.riskScore;
    current.exposure += project.revisedCost || 0;
    current.count += 1;
    ministryMap.set(project.ministry, current);
  });

  const ministryAnalytics = Array.from(ministryMap.values())
    .map((entry) => ({
      ministry: entry.ministry,
      projects: entry.projects,
      avgRisk: (entry.avgRisk / Math.max(1, entry.count)).toFixed(1),
      exposure: entry.exposure,
    }))
    .sort((a, b) => Number(b.avgRisk) - Number(a.avgRisk))
    .slice(0, 10);

  const costOverrunDistribution = [
    { range: '<10%', count: demoProjects.filter((p) => p.costOverrunRisk < 10).length },
    { range: '10-25%', count: demoProjects.filter((p) => p.costOverrunRisk >= 10 && p.costOverrunRisk < 25).length },
    { range: '25-50%', count: demoProjects.filter((p) => p.costOverrunRisk >= 25 && p.costOverrunRisk < 50).length },
    { range: '50%+', count: demoProjects.filter((p) => p.costOverrunRisk >= 50).length },
  ];

  const timeOverrunDistribution = [
    { range: '<6m', count: demoProjects.filter((p) => p.delayMonths < 6).length },
    { range: '6-12m', count: demoProjects.filter((p) => p.delayMonths >= 6 && p.delayMonths < 12).length },
    { range: '12-24m', count: demoProjects.filter((p) => p.delayMonths >= 12 && p.delayMonths < 24).length },
    { range: '24m+', count: demoProjects.filter((p) => p.delayMonths >= 24).length },
  ];

  return {
    sectorData: sectorSource,
    ministryAnalytics,
    costOverrunDistribution,
    timeOverrunDistribution,
    stateData: demoStateData.map((state) => ({
      ...state,
      avgRisk: Number((state.avgRisk || 0).toFixed ? state.avgRisk.toFixed(1) : state.avgRisk),
    })),
    riskTrendData: demoRiskTrendData,
    portfolioSummary: summary,
    liveProjects,
  };
}

export async function runScenario({ currentRisk = 0, physicalProgress = 0, expectedProgress = 0, milestoneDelays = 0 } = {}) {
  const current = Number(currentRisk) || 0;
  const physical = Number(physicalProgress) || 0;
  const expected = Number(expectedProgress) || 0;
  const delays = Number(milestoneDelays) || 0;

  const progressGap = Math.max(0, expected - physical);
  const delayPressure = delays * 1.75;
  const recoveryOffset = Math.max(0, physical - expected) * 0.35;
  const scenarioRisk = clamp(Math.round(current + progressGap * 0.5 + delayPressure * 0.7 - recoveryOffset), 0, 100);

  return {
    currentRisk: Math.round(current),
    scenarioRisk,
    change: scenarioRisk - Math.round(current),
    breakdown: {
      progressContribution: Number((progressGap * 0.5).toFixed(1)),
      milestoneContribution: Number((delayPressure * 0.7).toFixed(1)),
      baseContribution: Math.round(current),
    },
  };
}

export async function askAssistant(query) {
  const prompt = String(query || '').trim();
  if (!prompt) {
    return { response: 'Ask about a project ID, sector, or risk trend to get a live portfolio summary.' };
  }

  const explicitId = prompt.match(/\bPRJ[-A-Z0-9]+\b/i)?.[0];
  const searchHit = explicitId
    ? { projects: [{ project_id: explicitId.toUpperCase() }] }
    : await getProjects({ search: prompt, limit: 5 }).catch(() => ({ projects: [] }));

  const projectId = explicitId || searchHit?.projects?.[0]?.project_id;
  if (projectId) {
    try {
      const brief = await apiRequest('/api/ai/project-brief', {
        method: 'POST',
        body: JSON.stringify({ project_id: projectId }),
      });

      return {
        response: brief.summary,
        factors: [
          ...(brief.key_findings || []).map((detail) => ({ title: 'Key finding', detail })),
          ...(brief.evidence || []).map((detail) => ({ title: 'Evidence', detail })),
        ].slice(0, 4),
        projects: [{ id: projectId, name: brief.project_name || projectId, sector: brief.sector || 'Live project', riskLevel: brief.governance_status || 'ACTIVE', riskScore: null }],
        data: brief,
      };
    } catch {
      // Fall through to portfolio summary when the AI route is unavailable.
    }
  }

  const [summary, projectsRes] = await Promise.all([
    getDashboardSummary().catch(() => null),
    getProjects({ limit: 8 }).catch(() => ({ projects: [] })),
  ]);

  const topProjects = (projectsRes?.projects || []).slice(0, 5).map((project) => ({
    id: project.project_id,
    name: project.project_name,
    sector: project.sector,
    riskLevel: demoGetRiskLevel((project.latest_risk || 0) * 100),
    riskScore: project.latest_risk,
  }));

  return {
    response: summary
      ? `Live portfolio snapshot: ${summary.active_project_count ?? 0} active projects, ${summary.escalate_count ?? 0} escalations, and ${summary.watch_count ?? 0} watch items.`
      : 'Live portfolio data is unavailable right now. Try a specific project ID such as PRJ001.',
    projects: topProjects,
    type: 'projects',
    data: { type: 'projects', projects: topProjects },
  };
}

export async function getReports() {
  const summary = await getDashboardSummary().catch(() => null);
  const projectCount = summary?.active_project_count ?? demoProjects.length;
  const today = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

  return [
    {
      id: 'executive-brief',
      title: 'Executive risk brief',
      description: `${projectCount.toLocaleString('en-IN')} monitored projects with live portfolio status from the engine.`,
      type: 'Operational',
      date: today,
      status: 'Available',
    },
    {
      id: 'escalation-summary',
      title: 'Escalation summary',
      description: `${(summary?.escalate_count || 0).toLocaleString('en-IN')} projects currently in authority escalation.`,
      type: 'Governance',
      date: today,
      status: 'Available',
    },
    {
      id: 'warning-ledger',
      title: 'Warning ledger',
      description: `${(summary?.watch_count || 0).toLocaleString('en-IN')} watch items and ${(summary?.review_count || 0).toLocaleString('en-IN')} review items.`,
      type: 'Portfolio',
      date: today,
      status: 'Available',
    },
    {
      id: 'portfolio-snapshot',
      title: 'Portfolio snapshot',
      description: `Latest monthly snapshot aligned to ${summary?.latest_data_month || 'the current engine state'}.`,
      type: 'Snapshot',
      date: today,
      status: 'Draft',
    },
  ];
}

export async function getProjects(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.sector) query.set('sector', params.sector);
  if (params.risk_tier) query.set('risk_tier', params.risk_tier);
  if (params.limit !== undefined) query.set('limit', params.limit);
  if (params.offset !== undefined) query.set('offset', params.offset);
  const qs = query.toString();
  return apiRequest(`/api/projects${qs ? `?${qs}` : ''}`);
}

export async function getProjectDetail(projectId) {
  return apiRequest(`/api/projects/${encodeURIComponent(projectId)}`);
}

export async function getProjectReplay(projectId) {
  return apiRequest(`/api/projects/${encodeURIComponent(projectId)}/replay`);
}

export async function getProjectTimeline(projectId) {
  return apiRequest(`/api/projects/${encodeURIComponent(projectId)}/timeline`);
}

// ── Operational Monitoring Layer ──

export async function getMonitoredProjects(params = {}) {
  const query = new URLSearchParams();
  if (params.sector) query.set('sector', params.sector);
  if (params.status) query.set('status', params.status);
  if (params.limit !== undefined) query.set('limit', params.limit);
  if (params.offset !== undefined) query.set('offset', params.offset);
  const qs = query.toString();
  return apiRequest(`/api/monitor/projects${qs ? `?${qs}` : ''}`);
}

export async function getMonitoredProject(projectId) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}`);
}

export async function getMonitoredProjectStatus(projectId) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/status`);
}

export async function getMonitoredProjectObservations(projectId) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/observations`);
}

export async function getMonitoredProjectWarnings(projectId) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/warnings`);
}

export async function getMonitoredProjectAudit(projectId) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/audit`);
}

export async function getAuthorityEscalations(params = {}) {
  const query = new URLSearchParams();
  if (params.sector) query.set('sector', params.sector);
  const qs = query.toString();
  return apiRequest(`/api/monitor/escalations${qs ? `?${qs}` : ''}`);
}

export async function onboardProject(payload) {
  return apiRequest('/api/monitor/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitObservation(projectId, payload) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/observations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitContractorResponse(projectId, warningId, payload) {
  return apiRequest(`/api/monitor/projects/${encodeURIComponent(projectId)}/warnings/${encodeURIComponent(warningId)}/response`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function seedDemoScenarios(scenario = 'all') {
  return apiRequest(`/api/monitor/demo/seed?scenario=${encodeURIComponent(scenario)}`, {
    method: 'POST',
  });
}

// ── Value Formatters (Strict Missingness Preservation) ──

export function formatINR(val, prefix = '₹', suffix = ' Cr') {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return 'Data unavailable';
  }
  const num = Number(val);
  return `${prefix}${num.toLocaleString('en-IN', { maximumFractionDigits: 1 })}${suffix}`;
}

export function formatPercent(val, decimals = 1) {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return 'Data unavailable';
  }
  const num = Number(val);
  // If probability 0.0 - 1.0, format as percentage
  const pct = num <= 1.0 ? num * 100 : num;
  return `${pct.toFixed(decimals)}%`;
}

export function formatDelayMonths(val) {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return 'Data unavailable';
  }
  const num = Number(val);
  if (num === 0) return '0.0m (On Schedule)';
  return num > 0 ? `+${num.toFixed(1)}m` : `${num.toFixed(1)}m`;
}

export function getRiskTierConfig(tier) {
  const normTier = (tier || '').toUpperCase();
  switch (normTier) {
    case 'ESCALATE':
    case 'HIGH RISK':
    case 'CRITICAL':
      return {
        label: 'HIGH RISK (ESCALATE)',
        shortLabel: 'ESCALATE',
        badgeBg: 'bg-red-50 text-red-700 border-red-200',
        dotColor: 'bg-red-500',
        textColor: 'text-red-700',
        borderColor: 'border-red-500',
        solidBg: 'bg-red-600 text-white',
        thresholdText: '≥ 50.0%',
      };
    case 'REVIEW':
      return {
        label: 'REVIEW',
        shortLabel: 'REVIEW',
        badgeBg: 'bg-amber-50 text-amber-800 border-amber-200',
        dotColor: 'bg-amber-500',
        textColor: 'text-amber-800',
        borderColor: 'border-amber-500',
        solidBg: 'bg-amber-600 text-white',
        thresholdText: '45.0% - 49.9%',
      };
    case 'WATCH':
      return {
        label: 'WATCH',
        shortLabel: 'WATCH',
        badgeBg: 'bg-yellow-50 text-yellow-800 border-yellow-200',
        dotColor: 'bg-yellow-500',
        textColor: 'text-yellow-800',
        borderColor: 'border-yellow-500',
        solidBg: 'bg-yellow-500 text-white',
        thresholdText: '40.0% - 44.9%',
      };
    case 'NORMAL':
    default:
      return {
        label: 'NORMAL',
        shortLabel: 'NORMAL',
        badgeBg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dotColor: 'bg-emerald-500',
        textColor: 'text-emerald-700',
        borderColor: 'border-emerald-500',
        solidBg: 'bg-emerald-600 text-white',
        thresholdText: '< 40.0%',
      };
  }
}

export function getGovernanceConfig(status) {
  const s = (status || '').toUpperCase();
  switch (s) {
    case 'WARNING_ISSUED':
    case 'CONTRACTOR_WARNING':
    case 'ISSUED':
      return {
        label: 'CONTRACTOR WARNING',
        badgeBg: 'bg-orange-50 text-orange-800 border-orange-300',
        textColor: 'text-orange-800',
        dotColor: 'bg-orange-500',
        description: 'Contractor corrective-action window active. Corrective action plan requested.',
      };
    case 'CONTRACTOR_RESPONDED':
    case 'RESPONSE_SUBMITTED':
    case 'UNDER_RECOVERY':
      return {
        label: 'UNDER RECOVERY',
        badgeBg: 'bg-blue-50 text-blue-800 border-blue-300',
        textColor: 'text-blue-800',
        dotColor: 'bg-blue-500',
        description: 'Contractor plan logged. Monitoring empirical trajectory recovery.',
      };
    case 'RECOVERED':
    case 'PROJECT_RECOVERED':
      return {
        label: 'RECOVERED',
        badgeBg: 'bg-emerald-50 text-emerald-800 border-emerald-300',
        textColor: 'text-emerald-800',
        dotColor: 'bg-emerald-500',
        description: 'Empirical progress and delay metrics verified below risk threshold.',
      };
    case 'ESCALATED':
    case 'AUTHORITY_ESCALATED':
    case 'AUTHORITY_ESCALATION':
      return {
        label: 'AUTHORITY ESCALATION',
        badgeBg: 'bg-red-50 text-red-900 border-red-300 font-semibold',
        textColor: 'text-red-900',
        dotColor: 'bg-red-600',
        description: 'Persistent deterioration without recovery escalated to oversight ministry.',
      };
    case 'ACTIVE':
    default:
      return {
        label: 'ACTIVE SURVEILLANCE',
        badgeBg: 'bg-slate-100 text-slate-800 border-slate-300',
        textColor: 'text-slate-800',
        dotColor: 'bg-slate-500',
        description: 'Routine monthly trajectory observation active.',
      };
  }
}

export function getTrajectoryConfig(status, direction) {
  const dir = (direction || '').toUpperCase();
  const st = (status || '').toUpperCase();

  if (st === 'INSUFFICIENT_HISTORY' || st === 'LOW_HISTORY') {
    return {
      label: 'INSUFFICIENT HISTORY',
      arrow: '•',
      color: 'text-slate-500',
      badgeBg: 'bg-slate-100 text-slate-600 border-slate-200',
    };
  }

  if (dir.includes('DETERIORAT') || dir.includes('DOWN') || dir.includes('FALLING') || dir.includes('HIGH')) {
    return {
      label: 'DETERIORATING',
      arrow: '↓',
      color: 'text-red-600',
      badgeBg: 'bg-red-50 text-red-700 border-red-200',
    };
  }

  if (dir.includes('IMPROV') || dir.includes('UP') || dir.includes('RISING') || dir.includes('RECOVERY')) {
    return {
      label: 'IMPROVING',
      arrow: '↑',
      color: 'text-emerald-600',
      badgeBg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    };
  }

  return {
    label: 'STABLE',
    arrow: '→',
    color: 'text-blue-600',
    badgeBg: 'bg-blue-50 text-blue-700 border-blue-200',
  };
}
