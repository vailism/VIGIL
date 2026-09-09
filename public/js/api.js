/* ═══════════════════════════════════════════════════════════
   VIGIL // RISKSYS  —  API Service Layer
   ═══════════════════════════════════════════════════════════ */

const API = (() => {
  const isLocalStatic = window.location.port === '5500' || window.location.port === '8080' || window.location.protocol === 'file:';
  const BASE_URL = isLocalStatic ? 'http://localhost:3001/api' : '/api';
  const HEALTH_URL = isLocalStatic ? 'http://localhost:3001/health' : '/health';

  async function fetchJson(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (e) {
      console.warn(`[API] Failed to fetch ${url}:`, e);
      throw e;
    }
  }

  return {
    async healthCheck() {
      // Use raw fetch to avoid the /api prefix, as Express handles /health separately
      const response = await fetch(HEALTH_URL);
      if (!response.ok) throw new Error('Health check failed');
      return await response.json();
    },
    async getDashboardSummary() {
      return fetchJson('/dashboard/summary');
    },
    async getInterventions(limit = 30, sector = '', minRiskTier = '') {
      let url = `/dashboard/interventions?limit=${limit}`;
      if (sector) url += `&sector=${encodeURIComponent(sector)}`;
      if (minRiskTier) url += `&min_risk_tier=${encodeURIComponent(minRiskTier)}`;
      return fetchJson(url);
    },
    async getProjects(search = '', sector = '', riskTier = '', limit = 50, offset = 0) {
      let url = `/projects?limit=${limit}&offset=${offset}`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (sector) url += `&sector=${encodeURIComponent(sector)}`;
      if (riskTier) url += `&risk_tier=${encodeURIComponent(riskTier)}`;
      return fetchJson(url);
    },
    async getProjectDetails(projectId) {
      return fetchJson(`/projects/${encodeURIComponent(projectId)}`);
    },
    async getProjectReplay(projectId) {
      return fetchJson(`/projects/${encodeURIComponent(projectId)}/replay`);
    },
    async getProjectTimeline(projectId) {
      return fetchJson(`/projects/${encodeURIComponent(projectId)}/timeline`);
    }
  };
})();
