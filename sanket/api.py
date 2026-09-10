#!/usr/bin/env python3
"""
sanket/api.py

Production FastAPI Service for VIGIL.
Thin REST layer exposing point-in-time inference, historical replay,
longitudinal timelines, and portfolio governance summaries.

Guarantees:
- Strictly backed by frozen inference and replay engines
- Point-in-time integrity preserved across all responses
- Validated operating thresholds: WATCH=0.40, REVIEW=0.45, ESCALATE=0.50
- Zero LLM generation: deterministic, TreeSHAP-grounded explanations
- Strict RFC 8259 JSON output (no NaN tokens)
"""

import os
import math
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import dotenv
from google import genai
from google.genai import types

dotenv.load_dotenv()

from sanket.inference import load_inference_engine, get_risk_tier
from sanket.replay import get_project_replay
from sanket.portfolio import get_portfolio, SanitizedPortfolio, format_inr_currency
from sanket import monitoring

# Initialize FastAPI application
app = FastAPI(
    title="VIGIL Governance & Early Warning API",
    description="Early-warning risk inference and historical replay service for public infrastructure projects.",
    version="1.0.0"
)

# Global in-memory cache for fast portfolio querying
_APP_CONTEXT: Optional[Dict[str, Any]] = None


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize objects to guarantee valid RFC 8259 JSON.
    Converts NaN, Infinity, and numpy types to Python primitives or None.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating, np.integer)):
        val = obj.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if isinstance(obj, np.ndarray):
        return [sanitize_for_json(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj


def get_app_context(dataset_path: str = "DATA/model_dataset.parquet") -> Dict[str, Any]:
    """
    Lazily load and index the sanitized portfolio on first request.
    Single source of truth consuming the governance-safe portfolio layer.
    """
    global _APP_CONTEXT
    if _APP_CONTEXT is not None:
        return _APP_CONTEXT

    portfolio = get_portfolio(dataset_path=dataset_path)

    _APP_CONTEXT = {
        "engine": None, # Lazily loaded
        "portfolio": portfolio,
        "portfolio_df": portfolio.active_projects_df,
        "genuine_df": portfolio.genuine_projects_df,
        "median_warning_lead_time": portfolio.historical_median_warning_lead,
        "dataset_path": dataset_path
    }
    return _APP_CONTEXT

def get_lazy_engine(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Lazily load inference engine and cache it in the app context."""
    if ctx.get("engine") is None:
        from sanket.inference import load_inference_engine
        ctx["engine"] = load_inference_engine()
    return ctx["engine"]


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint returning system status and model readiness.
    """
    ctx = get_app_context()
    portfolio = ctx["portfolio"]
    return {
        "status": "healthy",
        "service": "vigil-api",
        "version": "1.0.0",
        "model_loaded": ctx.get("engine") is not None,
        "total_projects_indexed": portfolio.active_project_count,
        "active_project_count": portfolio.active_project_count,
        "archive_entity_count": portfolio.total_archive_entities
    }


@app.get("/api/projects")
def list_projects(
    search: Optional[str] = Query(None, description="Search term for project ID or name"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    risk_tier: Optional[str] = Query(None, description="Filter by risk tier: WATCH, REVIEW, ESCALATE, NORMAL"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset")
) -> Dict[str, Any]:
    """
    Searchable, filterable project portfolio list returning latest state
    for genuine infrastructure projects.
    """
    ctx = get_app_context()
    df = ctx["portfolio_df"].copy()

    # Filter by search - if searching specific project ID/name, also check genuine archive if not found in active
    if search:
        s_term = search.strip().lower()
        id_match = df["project_id"].astype(str).str.lower().str.contains(s_term)
        name_match = df["project_name"].astype(str).str.lower().str.contains(s_term)
        matched_df = df[id_match | name_match]
        if len(matched_df) == 0 and "genuine_df" in ctx:
            g_df = ctx["genuine_df"]
            g_id = g_df["project_id"].astype(str).str.lower().str.contains(s_term)
            g_name = g_df["project_name"].astype(str).str.lower().str.contains(s_term)
            matched_df = g_df[g_id | g_name].copy()
            if "latest_risk" not in matched_df.columns:
                matched_df["latest_risk"] = 0.0
                matched_df["latest_risk_tier"] = "NORMAL"
                matched_df["baseline_cost"] = pd.to_numeric(matched_df.get("C_base", 0), errors="coerce").fillna(0)
                matched_df["sector_display"] = matched_df.get("sector_clean", "OTHER")
        df = matched_df

    # Filter by sector
    if sector:
        sec_term = sector.strip().lower()
        df = df[df["sector_display"].astype(str).str.lower() == sec_term]

    # Filter by risk tier
    if risk_tier:
        tier_term = risk_tier.strip().upper()
        df = df[df["latest_risk_tier"] == tier_term]

    total_count = len(df)
    page_df = df.iloc[offset: offset + limit]

    results = []
    for _, r in page_df.iterrows():
        results.append({
            "project_id": str(r["project_id"]),
            "project_name": str(r.get("project_name", r["project_id"])),
            "sector": str(r.get("sector_display", "OTHER")),
            "latest_observation": str(r.get("reporting_month", "")),
            "latest_risk": float(r.get("latest_risk", 0.0)),
            "latest_risk_tier": str(r.get("latest_risk_tier", "NORMAL")),
            "baseline_cost": float(r.get("baseline_cost", 0.0))
        })

    return sanitize_for_json({
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "projects": results
    })


@app.get("/api/projects/{project_id}")
def get_project_details(project_id: str) -> Dict[str, Any]:
    """
    Retrieve project metadata, latest point-in-time prediction,
    latest trajectory metrics, current risk tier, and top explanations.
    Optimized to use precomputed portfolio state where possible to avoid massive parquet reads.
    """
    ctx = get_app_context()
    df = ctx.get("genuine_df")

    if df is None or project_id not in df["project_id"].values:
        # True fallback if completely unknown
        try:
            rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
            if not rep["timeline"]:
                raise HTTPException(status_code=404, detail=f"No timeline observations for project '{project_id}'.")
            latest_rec = rep["timeline"][-1]
            return sanitize_for_json({
                "project_id": rep["project_id"],
                "project_name": rep["project_name"],
                "sector": rep["sector"],
                "ministry": rep["ministry"],
                "state": rep["state"],
                "approved_cost": rep["approved_cost"],
                "total_observations": rep["total_observations"],
                "start_month": rep["start_month"],
                "end_month": rep["end_month"],
                "latest_observation": latest_rec["reporting_month"],
                "latest_prediction": {
                    "raw_prob": latest_rec["raw_prob"],
                    "pred_prob": latest_rec["pred_prob"],
                    "risk_tier": latest_rec["risk_tier"],
                    "alert": latest_rec["alert"]
                },
                "current_trajectory_metrics": {
                    "C_base": latest_rec["C_base"],
                    "expenditure": latest_rec["expenditure"],
                    "financial_progress": latest_rec["financial_progress"],
                    "schedule_deviation_months": latest_rec["schedule_deviation_months"],
                    "V_fin_1m": latest_rec.get("V_fin_1m"),
                    "V_fin_3m": latest_rec.get("V_fin_3m"),
                    "A_fin": latest_rec.get("A_fin"),
                    "EWMA_V_fin": latest_rec.get("EWMA_V_fin"),
                    "Z_peer_V_fin": latest_rec.get("Z_peer_V_fin"),
                    "trajectory_risk_score": latest_rec.get("trajectory_risk_score")
                },
                "current_risk_tier": latest_rec["risk_tier"],
                "top_explanations": latest_rec.get("top_explanations", [])
            })
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    # Extract from memory (zero parquet overhead!)
    row = df[df["project_id"] == str(project_id)]
    rec = row.iloc[0]

    from sanket.inference import predict_point_in_time
    engine = get_lazy_engine(ctx)
    pred = predict_point_in_time(row, engine)

    return sanitize_for_json({
        "project_id": str(rec["project_id"]),
        "project_name": str(rec.get("project_name", rec["project_id"])),
        "sector": str(rec.get("sector_display", rec.get("sector_clean", "OTHER"))),
        "ministry": str(rec.get("ministry", "—")),
        "state": str(rec.get("state", "—")),
        "approved_cost": float(rec.get("approved_cost", 0.0)),
        "total_observations": int(rec.get("observation_number", 1)),
        "start_month": str(rec.get("start_month", "Unknown")),
        "end_month": str(rec.get("reporting_month", "")),
        "latest_observation": str(rec.get("reporting_month", "")),
        "latest_prediction": {
            "raw_prob": pred["raw_prob"],
            "pred_prob": pred["pred_prob"],
            "risk_tier": pred["risk_tier"],
            "alert": pred["alert"]
        },
        "current_trajectory_metrics": {
            "C_base": float(rec.get("C_base", 0.0)),
            "expenditure": float(rec.get("expenditure", 0.0)),
            "financial_progress": float(rec.get("financial_progress", 0.0)),
            "schedule_deviation_months": float(rec.get("schedule_deviation_months", 0.0)),
            "V_fin_1m": float(rec.get("V_fin_1m", 0.0)),
            "V_fin_3m": float(rec.get("V_fin_3m", 0.0)),
            "A_fin": float(rec.get("A_fin", 0.0)),
            "EWMA_V_fin": float(rec.get("EWMA_V_fin", 0.0)),
            "Z_peer_V_fin": float(rec.get("Z_peer_V_fin", 0.0)),
            "trajectory_risk_score": float(rec.get("trajectory_risk_score", 0.0))
        },
        "current_risk_tier": pred["risk_tier"],
        "top_explanations": pred["top_explanations"]
    })


@app.get("/api/projects/{project_id}/replay")
def get_project_historical_replay(project_id: str) -> Dict[str, Any]:
    """
    Reconstruct full historical point-in-time replay:
    - Monthly predictions and trajectory kinematics
    - Historical alert points
    - Actual deterioration milestone detection
    - Warning lead time calculation
    """
    ctx = get_app_context()
    try:
        rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    return sanitize_for_json(rep)


@app.get("/api/projects/{project_id}/timeline")
def get_project_timeline(project_id: str) -> Dict[str, Any]:
    """
    Return longitudinal timeline of monthly trajectory and prediction records.
    """
    ctx = get_app_context()
    try:
        rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    return sanitize_for_json({
        "project_id": rep["project_id"],
        "project_name": rep["project_name"],
        "total_observations": rep["total_observations"],
        "timeline": rep["timeline"]
    })


@app.get("/api/dashboard/summary")
def get_dashboard_summary() -> Dict[str, Any]:
    """
    Portfolio governance overview backed by the sanitized portfolio layer:
    - active_project_count
    - archive_entity_count
    - latest_data_month
    - active_baseline_exposure
    - watch_count
    - review_count
    - escalate_count
    - risk_weighted_exposure
    - historical_median_warning_lead
    """
    ctx = get_app_context()
    portfolio: SanitizedPortfolio = ctx["portfolio"]
    return sanitize_for_json(portfolio.get_summary_dict())


@app.get("/api/dashboard/interventions")
def get_intervention_priorities(
    limit: int = Query(30, ge=1, le=100, description="Number of priority projects to return"),
    sector: Optional[str] = Query(None, description="Optional sector filter"),
    min_risk_tier: Optional[str] = Query(None, description="Minimum risk tier filter: WATCH, REVIEW, ESCALATE")
) -> Dict[str, Any]:
    """
    Prioritized genuine active infrastructure projects ranked by risk-weighted exposure:
    Priority Score = Calibrated Risk × Baseline Exposure.
    Strictly excludes macro-summary entities and historical-only projects.
    """
    ctx = get_app_context()
    portfolio: SanitizedPortfolio = ctx["portfolio"]
    return sanitize_for_json(portfolio.get_interventions(
        limit=limit,
        sector=sector,
        min_risk_tier=min_risk_tier
    ))


# ==============================================================================
# OPERATIONAL MONITORING LAYER ENDPOINTS (/api/monitor/...)
# ==============================================================================

class ProjectOnboardPayload(BaseModel):
    project_id: str
    project_name: str
    sector: str
    approved_cost: float
    initial_reporting_month: str
    ministry: Optional[str] = None
    state: Optional[str] = None
    revised_cost: Optional[float] = None
    planned_start_date: Optional[str] = None
    planned_completion_date: Optional[str] = None
    contractor: Optional[str] = None
    initial_metrics: Optional[Dict[str, Any]] = None


class MonthlyObservationPayload(BaseModel):
    reporting_month: str
    financial_progress: Optional[float] = None
    physical_progress: Optional[float] = None
    expenditure: Optional[float] = None
    revised_cost: Optional[float] = None
    completion_date: Optional[str] = None
    schedule_deviation_months: Optional[float] = None
    milestone_status: Optional[str] = None
    milestone_slippage: Optional[float] = None
    notes: Optional[str] = None
    supporting_documents: Optional[List[Dict[str, Any]]] = None
    persistence_cycles: Optional[int] = None


class ContractorResponsePayload(BaseModel):
    acknowledged: bool = True
    response_text: str
    corrective_action: str
    expected_recovery_date: Optional[str] = None
    responsible_person: Optional[str] = None
    supporting_documents: Optional[List[Dict[str, Any]]] = None


@app.post("/api/monitor/projects", status_code=201)
def onboard_new_project(payload: ProjectOnboardPayload) -> Dict[str, Any]:
    """
    Onboard a newly registered project into VIGIL active monitoring.
    Project does NOT need to exist in the historical training dataset.
    """
    try:
        res = monitoring.register_project(
            project_id=payload.project_id,
            project_name=payload.project_name,
            sector=payload.sector,
            approved_cost=payload.approved_cost,
            initial_reporting_month=payload.initial_reporting_month,
            ministry=payload.ministry,
            state=payload.state,
            revised_cost=payload.revised_cost,
            planned_start_date=payload.planned_start_date,
            planned_completion_date=payload.planned_completion_date,
            contractor=payload.contractor,
            initial_metrics=payload.initial_metrics
        )
        return sanitize_for_json(res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal onboarding error: {str(e)}")


@app.get("/api/monitor/projects")
def list_monitored_projects(
    sector: Optional[str] = Query(None, description="Optional sector filter"),
    status: Optional[str] = Query(None, description="Optional governance status filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    List all actively monitored projects.
    """
    try:
        res = monitoring.list_projects(sector=sector, status=status, limit=limit, offset=offset)
        return sanitize_for_json(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/projects/{project_id}")
def get_monitored_project(project_id: str) -> Dict[str, Any]:
    """
    Retrieve details for an actively monitored project.
    """
    try:
        proj = monitoring.get_project(project_id)
        return sanitize_for_json(proj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/monitor/projects/{project_id}/observations", status_code=201)
def submit_monthly_progress(project_id: str, payload: MonthlyObservationPayload) -> Dict[str, Any]:
    """
    Submit a monthly progress observation for a monitored project.
    Triggers canonical feature calculation, model prediction, and governance state machine.
    """
    try:
        res = monitoring.submit_observation(
            project_id=project_id,
            observation=payload.model_dump()
        )
        return sanitize_for_json(res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process observation: {str(e)}")


@app.get("/api/monitor/projects/{project_id}/observations")
def list_project_observations(project_id: str) -> Dict[str, Any]:
    """
    List all chronological monthly progress observations for a project.
    """
    try:
        obs = monitoring.get_project_observations(project_id)
        return sanitize_for_json({"project_id": project_id, "total": len(obs), "observations": obs})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/projects/{project_id}/status")
def get_project_governance_status(project_id: str) -> Dict[str, Any]:
    """
    Get current holistic governance status, active warning, and recovery state for a project.
    """
    try:
        res = monitoring.get_project_status(project_id)
        return sanitize_for_json(res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/monitor/projects/{project_id}/warnings")
def list_project_warnings(project_id: str) -> Dict[str, Any]:
    """
    List all contractor warnings issued for a project.
    """
    try:
        warnings = monitoring.get_project_warnings(project_id)
        return sanitize_for_json({"project_id": project_id, "total": len(warnings), "warnings": warnings})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/projects/{project_id}/warnings/{warning_id}/response", status_code=200)
def submit_contractor_warning_response(
    project_id: str,
    warning_id: str,
    payload: ContractorResponsePayload
) -> Dict[str, Any]:
    """
    Submit a formal contractor response / recovery action plan to an active warning.
    """
    try:
        res = monitoring.submit_contractor_response(
            project_id=project_id,
            warning_id=warning_id,
            acknowledged=payload.acknowledged,
            response_text=payload.response_text,
            corrective_action=payload.corrective_action,
            expected_recovery_date=payload.expected_recovery_date,
            responsible_person=payload.responsible_person,
            supporting_documents=payload.supporting_documents
        )
        return sanitize_for_json(res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit response: {str(e)}")


@app.get("/api/monitor/projects/{project_id}/audit")
def get_project_audit_trail(project_id: str) -> Dict[str, Any]:
    """
    Retrieve immutable chronological audit trail for a monitored project.
    """
    try:
        events = monitoring.get_audit_trail(project_id)
        return sanitize_for_json({"project_id": project_id, "total": len(events), "audit_events": events})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitor/escalations")
def list_authority_escalations(sector: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    List portfolio-wide authority escalations submitted to government oversight bodies.
    """
    try:
        escalations = monitoring.get_authority_escalations(sector=sector)
        return sanitize_for_json({"total": len(escalations), "escalations": escalations})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/demo/seed", status_code=200)
def seed_demo_scenarios_endpoint(scenario: str = Query("all", pattern="^(1|2|all)$")) -> Dict[str, Any]:
    """
    Seed canonical deterministic VIGIL demo scenarios:
    - scenario=1: The Contractor Recovery Workflow (5 months)
    - scenario=2: The Authority Escalation Workflow (7 months)
    - scenario=all: Both scenarios
    """
    from sanket import demo_scenarios
    try:
        if scenario == "1":
            res = demo_scenarios.execute_scenario_1()
            return sanitize_for_json({"status": "SUCCESS", "scenario_1": res})
        elif scenario == "2":
            res = demo_scenarios.execute_scenario_2()
            return sanitize_for_json({"status": "SUCCESS", "scenario_2": res})
        else:
            res = demo_scenarios.seed_all_demo_scenarios()
            return sanitize_for_json({"status": "SUCCESS", **res})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to seed demo scenarios: {str(e)}")


# ==============================================================================
# AI INTELLIGENCE ASSISTANT (GEMINI)
# ==============================================================================

class ProjectBriefRequest(BaseModel):
    project_id: str

class AIFindingsResponse(BaseModel):
    summary: str
    key_findings: List[str]
    evidence: List[str]
    governance_status: str
    recommended_review: str

@app.post("/api/ai/project-brief", response_model=AIFindingsResponse)
def generate_project_brief(payload: ProjectBriefRequest) -> Dict[str, Any]:
    """
    Generate a natural language brief using Gemini, based strictly on verified VIGIL data.
    """
    # 1. Validate project ID and fetch verified data
    project_id = payload.project_id
    ctx = get_app_context()

    # Try operational monitoring first
    try:
        proj = monitoring.get_project(project_id)
        obs = monitoring.get_project_observations(project_id)
        status_info = monitoring.get_project_status(project_id)
        warnings = monitoring.get_project_warnings(project_id)
        audit_events = monitoring.get_audit_trail(project_id)

        rep = {
            "project_id": proj["project_id"],
            "project_name": proj["project_name"],
            "sector": proj["sector"],
            "timeline": obs
        }
    except Exception:
        # Fallback to historical/genuine dataframe (no heavy parquet reading!)
        df = ctx.get("genuine_df")
        if df is None or project_id not in df["project_id"].values:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found in monitoring DB or archive.")

        row = df[df["project_id"] == str(project_id)]
        rec = row.iloc[0]

        from sanket.inference import predict_point_in_time
        engine = get_lazy_engine(ctx)
        pred = predict_point_in_time(row, engine)

        status_info = {}
        warnings = []
        audit_events = []

        rep = {
            "project_id": str(project_id),
            "project_name": str(rec.get("project_name", project_id)),
            "sector": str(rec.get("sector_display", rec.get("sector", "OTHER"))),
            "ministry": str(rec.get("ministry", "—")),
            "state": str(rec.get("state", "—")),
            "approved_cost": float(rec.get("approved_cost", 0.0)),
            "total_observations": int(rec.get("observation_number", 1)),
            "timeline": [{
                "reporting_month": str(rec.get("reporting_month", "")),
                "C_base": float(rec.get("C_base", 0.0)),
                "expenditure": float(rec.get("expenditure", 0.0)),
                "financial_progress": float(rec.get("financial_progress", 0.0)),
                "schedule_deviation_months": float(rec.get("schedule_deviation_months", 0.0)),
                "pred_prob": pred["pred_prob"],
                "raw_prob": pred["raw_prob"],
                "risk_tier": pred["risk_tier"],
                "alert": pred["alert"],
                "top_explanations": pred["top_explanations"]
            }]
        }

    if not rep["timeline"]:
        raise HTTPException(status_code=404, detail=f"No timeline observations for project '{project_id}'.")

    latest_rec = rep["timeline"][-1]

    # 2. Build verified context
    def safe_val(val):
        if val is None:
            return "unavailable"
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return "unavailable"
        return val

    context = {
        "project_identity": {
            "id": rep["project_id"],
            "name": rep["project_name"],
            "sector": rep["sector"]
        },
        "latest_observation_month": safe_val(latest_rec.get("reporting_month")),
        "trajectory_metrics": {
            "financial_progress_pct": safe_val(latest_rec.get("financial_progress")),
            "schedule_deviation_months": safe_val(latest_rec.get("schedule_deviation_months")),
            "financial_velocity_1m": safe_val(latest_rec.get("V_fin_1m"))
        },
        "model_risk": {
            "calibrated_probability": safe_val(latest_rec.get("pred_prob")),
            "risk_tier": safe_val(latest_rec.get("risk_tier")),
            "top_drivers": latest_rec.get("top_explanations", [])
        },
        "governance_state": {
            "current_status": safe_val(status_info.get("current_status")),
            "is_escalated": safe_val(status_info.get("escalation_status", {}).get("is_escalated", False)),
            "is_recovering": safe_val(status_info.get("recovery_status", {}).get("is_recovering", False))
        },
        "active_warnings": len(warnings),
        "recent_audit_events": [e["event_type"] for e in audit_events[-3:]] if audit_events else []
    }

    # 3. Invoke Gemini
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI interpretation layer is currently unavailable (missing configuration).")

    try:
        client = genai.Client(api_key=api_key)

        system_instruction = (
            "You are the VIGIL Intelligence Assistant. "
            "VIGIL is an infrastructure early-warning system. "
            "You explain verified information produced by the VIGIL backend. "
            "You MUST NOT invent facts. "
            "You MUST NOT calculate or modify risk probabilities. "
            "You MUST NOT create new thresholds. "
            "You MUST NOT determine contractor fault. "
            "You MUST NOT independently decide whether authority escalation is required. "
            "You MUST distinguish model risk from governance action. "
            "If information is unavailable, explicitly say so. "
            "Use only the supplied project context. "
            "When explaining a warning, identify the actual observed evidence supplied by VIGIL. "
            "When describing recovery, only call it recovery if the supplied governance state/evidence indicates recovery. "
            "Keep answers concise, professional and suitable for an infrastructure monitoring officer. "
            "For 'recommended_review', phrase it as something an officer may review (e.g. 'Review the contractor's next reported progress'), DO NOT issue enforcement decisions."
        )

        response = client.models.generate_content(
            model="gemini-3.0-flash",
            contents=f"Project Context: {context}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=AIFindingsResponse,
                temperature=0.0
            )
        )

        import json
        return json.loads(response.text)

    except Exception as e:
        # Fallback without breaking VIGIL
        raise HTTPException(status_code=503, detail=f"AI interpretation layer encountered an error: {str(e)}")

