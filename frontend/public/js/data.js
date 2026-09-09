/* ═══════════════════════════════════════════════════════════
   SANKET // RISKSYS  —  Mock Dashboard Data
   ═══════════════════════════════════════════════════════════ */

window.SANKET_DATA = {
  /* ── Portfolio-level metrics ─────────────────────────── */
  portfolio: {
    totalMonitored: '--',
    yoyChange: '--',
    addedThisQuarter: '--',
    activeTelemetryPct: '--',
    highRiskExcursions: '--',
    riskPct: '--',
    sec14Pending: '--',
    momChange: '--',
    riskSegments: { normal: 0, elevated: 0, divergent: 0 },
    valueAtRisk: '--',
    riskPortfolioPct: '--',
    sectorBreakdown: [],
    capexVelocity: '--',
    capex30d: '--',
    medianWarningLead: '--',
    modelCalibration: '--',
    calibrationStandard: '--',
  },

  /* ── Sparkline data (mini trend) ────────────────────── */
  sparkline: [],

  /* ── Selected project ────────────────────────── */
  selectedProject: {
    name: '--',
    score: 0,
    scoreMax: 100,
    severity: '--',
    discrepancy: 0,
    physicalProgress: 0,
    financialDrawdown: 0,
    spread: 0,
    stagnation: {
      days: 0,
      chainage: '--',
    },
    sensors: {},
    causalAttribution: {},
  },

  /* ── Trajectory divergence chart data ───────────────── */
  trajectoryChart: {
    labels: [],
    target: [],
    contractorReport: [],
    sanketTelemetry: [],
    anomalyPoint: null,
    discrepancyGap: null,
  },

  /* ── All projects list ──────────────────────────────── */
  projects: [],

  /* ── Build context object for Gemini ────────────────── */
  getAssistantContext() {
    return {
      portfolioSnapshot: {
        totalMonitored: this.portfolio.totalMonitored,
        highRiskExcursions: this.portfolio.highRiskExcursions,
        riskPct: this.portfolio.riskPct,
        valueAtRisk_Cr: this.portfolio.valueAtRisk,
        medianWarningLead_Mo: this.portfolio.medianWarningLead,
        sec14Pending: this.portfolio.sec14Pending,
      },
      selectedProject: {
        name: this.selectedProject.name,
        score: `${this.selectedProject.score}/${this.selectedProject.scoreMax}`,
        severity: this.selectedProject.severity,
        discrepancy: `${this.selectedProject.discrepancy}%`,
        physicalProgress: `${this.selectedProject.physicalProgress}%`,
        financialDrawdown: `${this.selectedProject.financialDrawdown}%`,
        spread: `${this.selectedProject.spread}%`,
        stagnation: this.selectedProject.stagnation,
        sensors: this.selectedProject.sensors,
        causalAttribution: this.selectedProject.causalAttribution,
      },
      activeAlerts: [
        `${this.portfolio.sec14Pending} Sec. 14 Notices pending`,
        `${this.portfolio.highRiskExcursions} corridors in divergent status`,
      ],
    };
  },

  /* ── Hydrate from API data ──────────────────────────── */
  hydrateFromAPI(summary, interventions) {
    if (summary) {
      this.portfolio.totalMonitored = summary.active_project_count || this.portfolio.totalMonitored;
      this.portfolio.highRiskExcursions = (summary.watch_count || 0) + (summary.review_count || 0) + (summary.escalate_count || 0);
      if (this.portfolio.totalMonitored > 0) {
        this.portfolio.riskPct = ((this.portfolio.highRiskExcursions / this.portfolio.totalMonitored) * 100).toFixed(1);
      }
      this.portfolio.valueAtRisk = summary.risk_weighted_exposure ? Math.round(summary.risk_weighted_exposure) : this.portfolio.valueAtRisk;
      if (summary.active_baseline_exposure > 0) {
        this.portfolio.riskPortfolioPct = ((summary.risk_weighted_exposure / summary.active_baseline_exposure) * 100).toFixed(1);
      }
      this.portfolio.yoyChange = 14.2; // Simulated YoY increase in monitored projects
      this.portfolio.modelCalibration = 92.4; // Simulated predictive accuracy

      this.portfolio.medianWarningLead = summary.historical_median_warning_lead ? Number(summary.historical_median_warning_lead.toFixed(1)) : this.portfolio.medianWarningLead;
      this.portfolio.riskSegments.normal = summary.normal_count || 0;
      this.portfolio.riskSegments.elevated = summary.watch_count || 0;
      this.portfolio.riskSegments.divergent = (summary.review_count || 0) + (summary.escalate_count || 0);

      if (summary.sector_breakdown && Array.isArray(summary.sector_breakdown)) {
        this.portfolio.sectorBreakdown = summary.sector_breakdown.map((item, i) => ({
          name: item.sector, value: Math.round(item.total_exposure), color: ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'][i % 5]
        }));
      }
    }

    if (interventions && interventions.projects && interventions.projects.length > 0) {
      this.projects = interventions.projects.map(p => ({
        id: p.project_id,
        name: p.project_name.length > 35 ? p.project_name.substring(0, 32) + '...' : p.project_name,
        location: `${p.state} • ${p.sector}`,
        severity: p.risk_tier === 'ESCALATE' ? 'CRITICAL DIVERGENCE' : (p.risk_tier === 'REVIEW' ? 'HIGH STAGNATION' : (p.risk_tier === 'WATCH' ? 'MODERATE WATCH' : 'NORMAL')),
        severityClass: p.risk_tier === 'ESCALATE' ? 'critical' : (p.risk_tier === 'REVIEW' ? 'high' : (p.risk_tier === 'WATCH' ? 'moderate' : 'vendor')),
        score: Math.round(p.latest_risk * 100),
        ministry: p.ministry || p.sector,
        variance: -Math.round(p.priority_score * 10) / 10,
        varianceLabel: 'Exposure',
        value: Math.round(p.baseline_exposure)
      }));
    }
  }
};
