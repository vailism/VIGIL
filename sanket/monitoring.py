#!/usr/bin/env python3
"""
sanket/monitoring.py

Production Operational Monitoring Layer for VIGIL.
Enables end-to-end active project governance:
- Project onboarding (unseen projects absent from historical training corpora)
- Streaming monthly progress submissions with strict validation
- Point-in-time progressive feature calculation reusing canonical trajectory engine
- Decoupled Contractor Early-Warning workflow (at ESCALATE risk >= 0.50)
- Contractor response tracking & SLA monitoring
- Empirical recovery monitoring (measuring physical/financial trajectory improvement)
- Configurable Authority Escalation state machine
- Append-only immutable audit trail

Invariants:
1. Strict separation from frozen research dataset (DATA/model_dataset.parquet is untouched).
2. Canonical feature construction: reuses sanket.trajectory.compute_canonical_features_for_project.
3. Point-in-time invariance: prediction(t) is invariant to future additions/deletions.
4. Model/Governance decoupling: Model predicts risk; governance state machine decides interventions.
"""

import os
import json
import uuid
import sqlite3
from sanket.db import get_db, POSTGRES_POOL
from datetime import datetime, date, timezone
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
import pandas as pd

from sanket.inference import load_inference_engine, predict_point_in_time, get_risk_tier
from sanket.trajectory import (
    compute_canonical_features_for_project,
    ym_to_month_number
)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "DATA", "monitoring.db")

# Operating thresholds (frozen)
THRESHOLD_WATCH = 0.40
THRESHOLD_REVIEW = 0.45
THRESHOLD_ESCALATE = 0.50

# Governance persistence policy (default: 2 consecutive cycles >= 0.50 post-warning)
DEFAULT_PERSISTENCE_CYCLES = 2


def resolve_db_path(override_path: Optional[str] = None) -> str:
    """Resolve active database path, respecting monkeypatched DEFAULT_DB_PATH."""
    if override_path is not None:
        return override_path
    return DEFAULT_DB_PATH


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get SQLite database connection with row factory and WAL mode."""
    resolved = resolve_db_path(db_path)
    norm_path = os.path.abspath(resolved)
    os.makedirs(os.path.dirname(norm_path), exist_ok=True)
    conn = sqlite3.connect(norm_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables for operational monitoring."""
    with get_db(db_path) as conn:
        with conn:
            if POSTGRES_POOL is not None:
                # Postgres Schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_projects (
                        project_id TEXT PRIMARY KEY,
                        project_name TEXT NOT NULL,
                        sector TEXT NOT NULL,
                        ministry TEXT,
                        state TEXT,
                        approved_cost DOUBLE PRECISION NOT NULL,
                        revised_cost DOUBLE PRECISION,
                        planned_start_date TEXT,
                        planned_completion_date TEXT,
                        contractor TEXT,
                        initial_reporting_month TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monthly_observations (
                        id SERIAL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        observation_number INTEGER NOT NULL,
                        financial_progress DOUBLE PRECISION,
                        physical_progress DOUBLE PRECISION,
                        expenditure DOUBLE PRECISION,
                        revised_cost DOUBLE PRECISION,
                        completion_date TEXT,
                        schedule_deviation_months DOUBLE PRECISION,
                        milestone_status TEXT,
                        milestone_slippage DOUBLE PRECISION,
                        notes TEXT,
                        supporting_documents TEXT,
                        raw_prob DOUBLE PRECISION,
                        calibrated_prob DOUBLE PRECISION,
                        risk_tier TEXT,
                        alert INTEGER,
                        trajectory_status TEXT,
                        history_confidence TEXT,
                        trajectory_history_months INTEGER,
                        top_explanations TEXT,
                        features_snapshot TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        UNIQUE (project_id, reporting_month)
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS contractor_warnings (
                        warning_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        risk_probability DOUBLE PRECISION NOT NULL,
                        risk_tier TEXT NOT NULL,
                        warning_reason TEXT NOT NULL,
                        deterministic_evidence TEXT,
                        observed_trajectory TEXT,
                        required_response TEXT NOT NULL,
                        response_deadline TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS contractor_responses (
                        response_id TEXT PRIMARY KEY,
                        warning_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        acknowledged INTEGER NOT NULL,
                        response_text TEXT NOT NULL,
                        corrective_action TEXT NOT NULL,
                        expected_recovery_date TEXT,
                        responsible_person TEXT,
                        supporting_documents TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS authority_escalations (
                        escalation_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        warning_id TEXT NOT NULL,
                        escalation_date TEXT NOT NULL,
                        risk_at_warning DOUBLE PRECISION NOT NULL,
                        current_risk DOUBLE PRECISION NOT NULL,
                        persistence_duration_months INTEGER NOT NULL,
                        evidence TEXT,
                        contractor_response TEXT,
                        response_status TEXT NOT NULL,
                        reason_for_escalation TEXT NOT NULL,
                        full_audit_trail TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        reporting_month TEXT,
                        event_type TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        risk_probability DOUBLE PRECISION,
                        evidence_snapshot TEXT,
                        metadata TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_proj_month ON monthly_observations(project_id, reporting_month)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_warnings_proj ON contractor_warnings(project_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_proj ON audit_events(project_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_escalations_proj ON authority_escalations(project_id)")
                
            else:
                # SQLite Schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_projects (
                        project_id TEXT PRIMARY KEY,
                        project_name TEXT NOT NULL,
                        sector TEXT NOT NULL,
                        ministry TEXT,
                        state TEXT,
                        approved_cost REAL NOT NULL,
                        revised_cost REAL,
                        planned_start_date TEXT,
                        planned_completion_date TEXT,
                        contractor TEXT,
                        initial_reporting_month TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monthly_observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        observation_number INTEGER NOT NULL,
                        financial_progress REAL,
                        physical_progress REAL,
                        expenditure REAL,
                        revised_cost REAL,
                        completion_date TEXT,
                        schedule_deviation_months REAL,
                        milestone_status TEXT,
                        milestone_slippage REAL,
                        notes TEXT,
                        supporting_documents TEXT,
                        raw_prob REAL,
                        calibrated_prob REAL,
                        risk_tier TEXT,
                        alert INTEGER,
                        trajectory_status TEXT,
                        history_confidence TEXT,
                        trajectory_history_months INTEGER,
                        top_explanations TEXT,
                        features_snapshot TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        UNIQUE (project_id, reporting_month)
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS contractor_warnings (
                        warning_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        risk_probability REAL NOT NULL,
                        risk_tier TEXT NOT NULL,
                        warning_reason TEXT NOT NULL,
                        deterministic_evidence TEXT,
                        observed_trajectory TEXT,
                        required_response TEXT NOT NULL,
                        response_deadline TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS contractor_responses (
                        response_id TEXT PRIMARY KEY,
                        warning_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        acknowledged INTEGER NOT NULL,
                        response_text TEXT NOT NULL,
                        corrective_action TEXT NOT NULL,
                        expected_recovery_date TEXT,
                        responsible_person TEXT,
                        supporting_documents TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS authority_escalations (
                        escalation_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        warning_id TEXT NOT NULL,
                        escalation_date TEXT NOT NULL,
                        risk_at_warning REAL NOT NULL,
                        current_risk REAL NOT NULL,
                        persistence_duration_months INTEGER NOT NULL,
                        evidence TEXT,
                        contractor_response TEXT,
                        response_status TEXT NOT NULL,
                        reason_for_escalation TEXT NOT NULL,
                        full_audit_trail TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        reporting_month TEXT,
                        event_type TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        risk_probability REAL,
                        evidence_snapshot TEXT,
                        metadata TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                """)

                conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_proj_month ON monthly_observations(project_id, reporting_month)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_warnings_proj ON contractor_warnings(project_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_proj ON audit_events(project_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_escalations_proj ON authority_escalations(project_id)")


def append_audit_event(
    conn,
    project_id: str,
    event_type: str,
    actor: str,
    reporting_month: Optional[str] = None,
    risk_probability: Optional[float] = None,
    evidence_snapshot: Optional[Any] = None,
    metadata: Optional[Any] = None
) -> str:
    """Append an immutable audit entry to the audit_events ledger."""
    event_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"
    ts = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT INTO audit_events (
            event_id, project_id, timestamp, reporting_month,
            event_type, actor, risk_probability, evidence_snapshot, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        project_id,
        ts,
        reporting_month,
        event_type,
        actor,
        float(risk_probability) if risk_probability is not None else None,
        json.dumps(evidence_snapshot) if evidence_snapshot is not None else None,
        json.dumps(metadata) if metadata is not None else None
    ))
    return event_id


def get_history_confidence(n_obs: int) -> str:
    """
    Evidence-sufficiency rating based on sequential observation count:
    1 observation  = LOW_HISTORY
    2 observations = LIMITED_HISTORY
    3–5 observations = DEVELOPING_HISTORY
    6+ observations = ESTABLISHED_HISTORY
    """
    if n_obs <= 1:
        return "LOW_HISTORY"
    elif n_obs == 2:
        return "LIMITED_HISTORY"
    elif 3 <= n_obs <= 5:
        return "DEVELOPING_HISTORY"
    else:
        return "ESTABLISHED_HISTORY"


def get_trajectory_status(n_obs: int) -> str:
    """
    Trajectory availability status:
    1 observation  = INSUFFICIENT_HISTORY
    2 observations = INITIAL_TRAJECTORY
    3+ observations = ESTABLISHED_TRAJECTORY
    """
    if n_obs <= 1:
        return "INSUFFICIENT_HISTORY"
    elif n_obs == 2:
        return "INITIAL_TRAJECTORY"
    else:
        return "ESTABLISHED_TRAJECTORY"


def register_project(
    project_id: str,
    project_name: str,
    sector: str,
    approved_cost: float,
    initial_reporting_month: str,
    ministry: Optional[str] = None,
    state: Optional[str] = None,
    revised_cost: Optional[float] = None,
    planned_start_date: Optional[str] = None,
    planned_completion_date: Optional[str] = None,
    contractor: Optional[str] = None,
    initial_metrics: Optional[Dict[str, Any]] = None,
    actor: str = "SYSTEM_ONBOARDING",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Register a newly onboarded project into VIGIL active monitoring.
    Project does NOT need to exist in the historical training dataset.
    """
    init_db(db_path)
    pid = str(project_id).strip()
    pname = str(project_name).strip()
    sec = str(sector).strip()
    init_m = str(initial_reporting_month).strip()

    if not pid:
        raise ValueError("project_id cannot be empty.")
    if not pname:
        raise ValueError("project_name cannot be empty.")
    if approved_cost <= 0:
        raise ValueError("approved_cost must be strictly positive.")
    if ym_to_month_number(init_m) is None:
        raise ValueError(f"Invalid initial_reporting_month '{init_m}'. Expected YYYY-MM.")

    if planned_start_date and ym_to_month_number(planned_start_date) is None:
        raise ValueError(f"Invalid planned_start_date '{planned_start_date}'. Expected YYYY-MM.")
    if planned_completion_date and ym_to_month_number(planned_completion_date) is None:
        raise ValueError(f"Invalid planned_completion_date '{planned_completion_date}'. Expected YYYY-MM.")

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        with conn:
            # Check existing
            cur = conn.execute("SELECT project_id FROM monitored_projects WHERE project_id = ?", (pid,))
            if cur.fetchone() is not None:
                raise ValueError(f"Project '{pid}' is already registered in active monitoring.")

            conn.execute("""
                INSERT INTO monitored_projects (
                    project_id, project_name, sector, ministry, state,
                    approved_cost, revised_cost, planned_start_date, planned_completion_date,
                    contractor, initial_reporting_month, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (
                pid, pname, sec, ministry, state,
                float(approved_cost),
                float(revised_cost) if revised_cost is not None else None,
                planned_start_date, planned_completion_date,
                contractor, init_m, now_iso, now_iso
            ))

            append_audit_event(
                conn,
                project_id=pid,
                event_type="PROJECT_REGISTERED",
                actor=actor,
                reporting_month=init_m,
                metadata={
                    "project_name": pname,
                    "sector": sec,
                    "approved_cost": approved_cost,
                    "contractor": contractor
                }
            )

        # If initial metrics supplied, submit observation 1 immediately
        initial_obs_result = None
        if initial_metrics:
            obs_payload = dict(initial_metrics)
            obs_payload["reporting_month"] = init_m
            initial_obs_result = submit_observation(
                project_id=pid,
                observation=obs_payload,
                actor=actor,
                db_path=db_path
            )

        project_record = get_project(pid, db_path=db_path)
        return {
            "project": project_record,
            "initial_observation": initial_obs_result
        }


def get_project(project_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve monitored project profile."""
    with get_db(db_path) as conn:
        cur = conn.execute("SELECT * FROM monitored_projects WHERE project_id = ?", (project_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Monitored project '{project_id}' not found.")
        return dict(row)


def list_projects(
    sector: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """List monitored projects with optional sector and status filtering."""
    init_db(db_path)
    with get_db(db_path) as conn:
        query = "SELECT * FROM monitored_projects WHERE 1=1"
        params: List[Any] = []

        if sector:
            query += " AND LOWER(sector) = LOWER(?)"
            params.append(sector.strip())
        if status:
            query += " AND UPPER(status) = UPPER(?)"
            params.append(status.strip())

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur = conn.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

        # Total count
        count_q = "SELECT COUNT(*) AS c FROM monitored_projects WHERE 1=1"
        count_params: List[Any] = []
        if sector:
            count_q += " AND LOWER(sector) = LOWER(?)"
            count_params.append(sector.strip())
        if status:
            count_q += " AND UPPER(status) = UPPER(?)"
            count_params.append(status.strip())
        total = conn.execute(count_q, count_params).fetchone()["c"]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "projects": rows
        }


def submit_observation(
    project_id: str,
    observation: Dict[str, Any],
    actor: str = "CONTRACTOR_REPORTING",
    persistence_cycles: int = DEFAULT_PERSISTENCE_CYCLES,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submit a monthly progress observation for an actively monitored project.
    Executes:
    1. Chronology and boundary validation.
    2. Canonical feature construction through month t (sanket.trajectory).
    3. Production LightGBM inference & calibration.
    4. Operational governance state machine evaluation.
    5. Immutable audit logging.
    """
    init_db(db_path)
    pid = str(project_id).strip()
    proj = get_project(pid, db_path=db_path)

    if "persistence_cycles" in observation and observation["persistence_cycles"] is not None:
        persistence_cycles = int(observation["persistence_cycles"])

    m_ym = str(observation.get("reporting_month", "")).strip()
    m_idx = ym_to_month_number(m_ym)
    if m_idx is None:
        raise ValueError(f"Invalid reporting_month '{m_ym}'. Expected YYYY-MM format.")

    # Validation: numeric bounds
    fin_prog = observation.get("financial_progress")
    if fin_prog is not None:
        fin_prog = float(fin_prog)
        if fin_prog < 0:
            raise ValueError(f"financial_progress cannot be negative ({fin_prog}).")

    phys_prog = observation.get("physical_progress")
    if phys_prog is not None and not pd.isna(phys_prog):
        phys_prog = float(phys_prog)
        if phys_prog < 0 or phys_prog > 100:
            raise ValueError(f"physical_progress must be within [0, 100] ({phys_prog}).")
    else:
        phys_prog = None  # Explicitly preserve missingness; never fabricate!

    expenditure = observation.get("expenditure")
    if expenditure is not None:
        expenditure = float(expenditure)
        if expenditure < 0:
            raise ValueError(f"expenditure cannot be negative ({expenditure}).")

    rev_cost = observation.get("revised_cost")
    if rev_cost is not None:
        rev_cost = float(rev_cost)
        if rev_cost <= 0:
            raise ValueError(f"revised_cost must be strictly positive ({rev_cost}).")

    sch_dev = observation.get("schedule_deviation_months")
    if sch_dev is None and "schedule_deviation" in observation:
        sch_dev = observation["schedule_deviation"]
    if sch_dev is not None:
        sch_dev = float(sch_dev)

    with get_db(db_path) as conn:
        # Check duplicate
        cur = conn.execute(
            "SELECT id FROM monthly_observations WHERE project_id = ? AND reporting_month = ?",
            (pid, m_ym)
        )
        if cur.fetchone() is not None:
            raise ValueError(
                f"Duplicate monthly observation: '{m_ym}' has already been submitted for project '{pid}'."
            )

        # Check chronology: must be strictly > latest prior observation
        cur = conn.execute(
            "SELECT reporting_month FROM monthly_observations WHERE project_id = ? ORDER BY reporting_month DESC LIMIT 1",
            (pid,)
        )
        last_row = cur.fetchone()
        if last_row is not None:
            last_ym = last_row["reporting_month"]
            last_idx = ym_to_month_number(last_ym)
            if last_idx is not None and m_idx <= last_idx:
                raise ValueError(
                    f"Chronological order violation: Submitted month '{m_ym}' must be strictly after prior month '{last_ym}'."
                )

        # Retrieve all historical observations to assemble chronological series through month t
        cur = conn.execute("""
            SELECT * FROM monthly_observations WHERE project_id = ? ORDER BY reporting_month ASC
        """, (pid,))
        prior_obs = [dict(r) for r in cur.fetchall()]

        # Prepare new observation row dictionary
        new_obs_dict = {
            "project_id": pid,
            "reporting_month": m_ym,
            "financial_progress": fin_prog if fin_prog is not None else np.nan,
            "physical_progress": phys_prog if phys_prog is not None else np.nan,
            "expenditure": expenditure if expenditure is not None else np.nan,
            "approved_cost": proj["approved_cost"],
            "revised_cost": rev_cost if rev_cost is not None else (proj.get("revised_cost") or np.nan),
            "schedule_deviation": sch_dev if sch_dev is not None else np.nan,
            "original_completion_date": proj.get("planned_completion_date") or "",
            "revised_completion_date": observation.get("completion_date") or "",
            "sector": proj["sector"]
        }

        # Build full historical panel through month t
        history_list = []
        for p in prior_obs:
            history_list.append({
                "project_id": pid,
                "reporting_month": p["reporting_month"],
                "financial_progress": p["financial_progress"] if p["financial_progress"] is not None else np.nan,
                "physical_progress": p["physical_progress"] if p["physical_progress"] is not None else np.nan,
                "expenditure": p["expenditure"] if p["expenditure"] is not None else np.nan,
                "approved_cost": proj["approved_cost"],
                "revised_cost": p["revised_cost"] if p["revised_cost"] is not None else (proj.get("revised_cost") or np.nan),
                "schedule_deviation": p["schedule_deviation_months"] if p["schedule_deviation_months"] is not None else np.nan,
                "original_completion_date": proj.get("planned_completion_date") or "",
                "revised_completion_date": p["completion_date"] or "",
                "sector": proj["sector"]
            })
        history_list.append(new_obs_dict)

        # CANONICAL FEATURE PIPELINE
        # Invokes shared feature builder; respects project_start_date; preserves missingness
        features_df = compute_canonical_features_for_project(
            observations=history_list,
            project_start_date=proj.get("planned_start_date"),
            peer_benchmarks=None
        )

        curr_features = features_df.iloc[-1]
        n_obs = len(features_df)

        # PRODUCTION MODEL INFERENCE
        engine = load_inference_engine()
        pred_res = predict_point_in_time(curr_features, engine=engine)

        traj_status = get_trajectory_status(n_obs)
        hist_confidence = get_history_confidence(n_obs)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Extract features snapshot for transparency (convert NaN to None for JSON safety)
        def _json_val(v: Any) -> Optional[float]:
            if v is None or pd.isna(v):
                return None
            return float(v)

        features_snapshot = {
            "C_base": _json_val(curr_features.get("C_base")),
            "expenditure_to_baseline": _json_val(curr_features.get("expenditure_to_baseline")),
            "cost_revision_ratio": _json_val(curr_features.get("cost_revision_ratio")),
            "schedule_deviation_months": _json_val(curr_features.get("schedule_deviation_months")),
            "schedule_deviation_change": _json_val(curr_features.get("schedule_deviation_change")),
            "V_fin_1m": _json_val(curr_features.get("V_fin_1m")),
            "V_fin_3m": _json_val(curr_features.get("V_fin_3m")),
            "A_fin": _json_val(curr_features.get("A_fin")),
            "EWMA_V_fin": _json_val(curr_features.get("EWMA_V_fin")),
            "trajectory_risk_score": _json_val(curr_features.get("trajectory_risk_score")),
            "project_age_months": _json_val(curr_features.get("project_age_months")),
            "observation_number": int(curr_features.get("observation_number", n_obs)),
            "months_since_previous_observation": _json_val(curr_features.get("months_since_previous_observation")),
            "reporting_gap_flag": int(curr_features.get("reporting_gap_flag", 0))
        }

        with conn:
            # Insert observation record
            conn.execute("""
                INSERT INTO monthly_observations (
                    project_id, reporting_month, observation_number,
                    financial_progress, physical_progress, expenditure, revised_cost,
                    completion_date, schedule_deviation_months,
                    milestone_status, milestone_slippage, notes, supporting_documents,
                    raw_prob, calibrated_prob, risk_tier, alert,
                    trajectory_status, history_confidence, trajectory_history_months,
                    top_explanations, features_snapshot, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pid, m_ym, n_obs,
                fin_prog, phys_prog, expenditure, rev_cost,
                observation.get("completion_date"),
                sch_dev,
                observation.get("milestone_status"),
                float(observation["milestone_slippage"]) if observation.get("milestone_slippage") is not None else None,
                observation.get("notes"),
                json.dumps(observation.get("supporting_documents")) if observation.get("supporting_documents") else None,
                pred_res["raw_prob"],
                pred_res["calibrated_prob"],
                pred_res["risk_tier"],
                1 if pred_res["alert"] else 0,
                traj_status,
                hist_confidence,
                n_obs,
                json.dumps(pred_res["top_explanations"]),
                json.dumps(features_snapshot),
                now_iso
            ))

            # Audit events
            append_audit_event(
                conn,
                project_id=pid,
                event_type="MONTHLY_REPORT_SUBMITTED",
                actor=actor,
                reporting_month=m_ym,
                metadata={
                    "observation_number": n_obs,
                    "financial_progress": fin_prog,
                    "physical_progress": phys_prog,
                    "expenditure": expenditure
                }
            )

            append_audit_event(
                conn,
                project_id=pid,
                event_type="PREDICTION_GENERATED",
                actor="VIGIL_INFERENCE_ENGINE",
                reporting_month=m_ym,
                risk_probability=pred_res["calibrated_prob"],
                evidence_snapshot=pred_res["top_explanations"],
                metadata={
                    "risk_tier": pred_res["risk_tier"],
                    "trajectory_status": traj_status,
                    "history_confidence": hist_confidence
                }
            )

            if pred_res["risk_tier"] in ["WATCH", "REVIEW"]:
                append_audit_event(
                    conn,
                    project_id=pid,
                    event_type=f"{pred_res['risk_tier']}_ENTERED",
                    actor="VIGIL_GOVERNANCE",
                    reporting_month=m_ym,
                    risk_probability=pred_res["calibrated_prob"]
                )

            # GOVERNANCE STATE MACHINE EVALUATION
            governance_outcome = evaluate_governance_workflow(
                conn=conn,
                project_id=pid,
                reporting_month=m_ym,
                calibrated_prob=pred_res["calibrated_prob"],
                risk_tier=pred_res["risk_tier"],
                curr_features=curr_features,
                prior_observations=prior_obs,
                top_explanations=pred_res["top_explanations"],
                persistence_cycles=persistence_cycles
            )

        return {
            "project_id": pid,
            "reporting_month": m_ym,
            "observation_number": n_obs,
            "prediction": {
                "raw_prob": pred_res["raw_prob"],
                "calibrated_probability": pred_res["calibrated_prob"],
                "risk_tier": pred_res["risk_tier"],
                "alert": pred_res["alert"]
            },
            "calibrated_prob": pred_res["calibrated_prob"],
            "raw_prob": pred_res["raw_prob"],
            "risk_tier": pred_res["risk_tier"],
            "alert": pred_res["alert"],
            "features_snapshot": features_snapshot,
            "trajectory_status": traj_status,
            "trajectory_history_months": n_obs,
            "history_confidence": hist_confidence,
            "top_deterministic_explanations": pred_res["top_explanations"],
            "governance_status": governance_outcome,
            "governance_outcome": governance_outcome
        }


def evaluate_governance_workflow(
    conn,
    project_id: str,
    reporting_month: str,
    calibrated_prob: float,
    risk_tier: str,
    curr_features: pd.Series,
    prior_observations: List[Dict[str, Any]],
    top_explanations: List[Dict[str, Any]],
    persistence_cycles: int = DEFAULT_PERSISTENCE_CYCLES
) -> Dict[str, Any]:
    """
    Operational Governance State Machine:
    Decoupled from the ML model. The model predicts risk; this workflow
    decides contractor warnings, recovery tracking, and authority escalations.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # Query active warning for this project
    cur = conn.execute("""
        SELECT * FROM contractor_warnings
        WHERE project_id = ? AND status IN ('ISSUED', 'ACKNOWLEDGED', 'RESPONSE_SUBMITTED', 'UNDER_RECOVERY', 'PERSISTENT_DETERIORATION')
        ORDER BY issued_at DESC LIMIT 1
    """, (project_id,))
    active_warning = cur.fetchone()

    outcome = {
        "action": "NONE",
        "active_warning_id": active_warning["warning_id"] if active_warning else None,
        "escalation_id": None,
        "recovery_status": None,
        "details": None
    }

    # -------------------------------------------------------------
    # CASE 1: NO ACTIVE WARNING
    # -------------------------------------------------------------
    if active_warning is None:
        if calibrated_prob >= THRESHOLD_ESCALATE:
            # Trigger Contractor Warning
            warning_id = f"WARN-{uuid.uuid4().hex[:8].upper()}"
            deadline_date = date.today().replace(day=min(date.today().day + 15, 28)).isoformat()

            # Neutral, non-accusatory warning reason grounded in verified features
            signals = [exp["explanation"] for exp in top_explanations[:3]]
            signals_str = "\n".join([f"- {s}" for s in signals])
            warning_reason = (
                f"VIGIL detected sustained deterioration in project trajectory.\n"
                f"Current calibrated 12-month deterioration probability: {calibrated_prob * 100.0:.1f}% ({risk_tier}).\n"
                f"Primary contributing signals:\n{signals_str}\n"
                f"Contractor acknowledgment and recovery plan requested."
            )

            obs_traj = {
                "V_fin_1m": float(curr_features.get("V_fin_1m", 0) or 0) if not pd.isna(curr_features.get("V_fin_1m")) else None,
                "schedule_deviation_months": float(curr_features.get("schedule_deviation_months", 0) or 0) if not pd.isna(curr_features.get("schedule_deviation_months")) else None,
                "trajectory_risk_score": float(curr_features.get("trajectory_risk_score", 0) or 0) if not pd.isna(curr_features.get("trajectory_risk_score")) else None
            }

            conn.execute("""
                INSERT INTO contractor_warnings (
                    warning_id, project_id, issued_at, reporting_month,
                    risk_probability, risk_tier, warning_reason,
                    deterministic_evidence, observed_trajectory,
                    required_response, response_deadline, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ISSUED')
            """, (
                warning_id,
                project_id,
                now_iso,
                reporting_month,
                calibrated_prob,
                risk_tier,
                warning_reason,
                json.dumps(top_explanations),
                json.dumps(obs_traj),
                "Contractor acknowledgment and corrective recovery plan requested.",
                deadline_date
            ))

            conn.execute(
                "UPDATE monitored_projects SET status = 'WARNING_ISSUED', updated_at = ? WHERE project_id = ?",
                (now_iso, project_id)
            )

            append_audit_event(
                conn,
                project_id=project_id,
                event_type="CONTRACTOR_WARNING_ISSUED",
                actor="VIGIL_GOVERNANCE",
                reporting_month=reporting_month,
                risk_probability=calibrated_prob,
                evidence_snapshot=top_explanations,
                metadata={
                    "warning_id": warning_id,
                    "deadline": deadline_date,
                    "reason": warning_reason
                }
            )

            outcome["action"] = "CONTRACTOR_WARNING_ISSUED"
            outcome["active_warning_id"] = warning_id
            outcome["details"] = f"Contractor warning {warning_id} issued. Response deadline: {deadline_date}."

        return outcome

    # -------------------------------------------------------------
    # CASE 2: ACTIVE WARNING EXISTS — RECOVERY OR DETERIORATION TRACKING
    # -------------------------------------------------------------
    warn_id = active_warning["warning_id"]
    warn_prob = float(active_warning["risk_probability"])
    warn_traj = json.loads(active_warning["observed_trajectory"]) if active_warning["observed_trajectory"] else {}

    # Check contractor response status
    cur = conn.execute("SELECT * FROM contractor_responses WHERE warning_id = ?", (warn_id,))
    resp = cur.fetchone()
    has_responded = resp is not None

    # Check recovery criteria
    # Recovery rule (empirical):
    # 1. Calibrated probability drops below ESCALATE (< 0.50).
    # 2. Measurable trajectory improvement according to available metrics:
    #    - Financial velocity resumed or accelerated (V_fin_1m > 0 and V_fin_1m > warn_V), OR
    #    - Schedule deviation did not worsen / stabilized (sch_dev <= warn_sch_dev), OR
    #    - Trajectory risk score decreased.
    is_risk_reduced = (calibrated_prob < THRESHOLD_ESCALATE)
    
    # Trajectory metric comparisons
    curr_v_fin = float(curr_features.get("V_fin_1m")) if not pd.isna(curr_features.get("V_fin_1m")) else None
    warn_v_fin = warn_traj.get("V_fin_1m")
    
    curr_sch_dev = float(curr_features.get("schedule_deviation_months")) if not pd.isna(curr_features.get("schedule_deviation_months")) else None
    warn_sch_dev = warn_traj.get("schedule_deviation_months")

    curr_score = float(curr_features.get("trajectory_risk_score")) if not pd.isna(curr_features.get("trajectory_risk_score")) else None
    warn_score = warn_traj.get("trajectory_risk_score")

    has_trajectory_evidence = (curr_v_fin is not None or curr_sch_dev is not None or curr_score is not None)

    trajectory_improved = False
    improvement_reasons = []

    if curr_v_fin is not None and curr_v_fin > 0:
        if warn_v_fin is None or curr_v_fin > warn_v_fin:
            trajectory_improved = True
            improvement_reasons.append(f"Financial progress velocity accelerated to {curr_v_fin:.2f}%/month")

    if curr_sch_dev is not None and warn_sch_dev is not None and curr_sch_dev <= warn_sch_dev:
        trajectory_improved = True
        improvement_reasons.append(f"Schedule deviation stabilized at {curr_sch_dev:.1f} months")

    if curr_score is not None and warn_score is not None and curr_score < warn_score:
        trajectory_improved = True
        improvement_reasons.append(f"Kinematic trajectory risk index decreased ({warn_score:.1f} -> {curr_score:.1f})")

    # Evaluate recovery
    if is_risk_reduced:
        if not has_trajectory_evidence:
            outcome["recovery_status"] = "INSUFFICIENT_EVIDENCE"
            outcome["details"] = "Risk probability decreased but trajectory evidence is unavailable to confirm physical/financial recovery."
            return outcome

        if trajectory_improved:
            # RECOVERED!
            conn.execute(
                "UPDATE contractor_warnings SET status = 'RECOVERED' WHERE warning_id = ?",
                (warn_id,)
            )
            conn.execute(
                "UPDATE monitored_projects SET status = 'RECOVERED', updated_at = ? WHERE project_id = ?",
                (now_iso, project_id)
            )

            recovery_note = (
                f"Trajectory improved following the warning. "
                f"Calibrated 12-month deterioration risk decreased from {warn_prob*100.0:.1f}% to {calibrated_prob*100.0:.1f}%. "
                f"Measured improvements: {'; '.join(improvement_reasons)}."
            )

            append_audit_event(
                conn,
                project_id=project_id,
                event_type="RECOVERY_DETECTED",
                actor="VIGIL_GOVERNANCE",
                reporting_month=reporting_month,
                risk_probability=calibrated_prob,
                metadata={
                    "warning_id": warn_id,
                    "recovery_note": recovery_note,
                    "prior_risk": warn_prob,
                    "current_risk": calibrated_prob
                }
            )

            outcome["action"] = "PROJECT_RECOVERED"
            outcome["recovery_status"] = "RECOVERED"
            outcome["details"] = recovery_note
            return outcome

    # Project did NOT recover: risk remains >= 0.50
    # Track persistence duration across observations since warning issuance
    cur = conn.execute("""
        SELECT COUNT(*) AS c FROM monthly_observations
        WHERE project_id = ? AND reporting_month >= ? AND calibrated_prob >= ?
    """, (project_id, active_warning["reporting_month"], THRESHOLD_ESCALATE))
    persistent_count = cur.fetchone()["c"]

    # Update warning status to PERSISTENT_DETERIORATION
    conn.execute(
        "UPDATE contractor_warnings SET status = 'PERSISTENT_DETERIORATION' WHERE warning_id = ?",
        (warn_id,)
    )

    append_audit_event(
        conn,
        project_id=project_id,
        event_type="PERSISTENT_DETERIORATION_DETECTED",
        actor="VIGIL_GOVERNANCE",
        reporting_month=reporting_month,
        risk_probability=calibrated_prob,
        metadata={
            "warning_id": warn_id,
            "persistent_cycle_count": persistent_count,
            "required_for_escalation": persistence_cycles
        }
    )

    outcome["recovery_status"] = "PERSISTENT_DETERIORATION"

    # Check Authority Escalation Condition
    # Escalates when risk remains >= 0.50 for persistence_cycles post-warning without recovery
    if persistent_count >= persistence_cycles:
        esc_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

        # Build full audit trail snapshot
        cur = conn.execute("""
            SELECT event_id, timestamp, event_type, actor, risk_probability, metadata
            FROM audit_events WHERE project_id = ? ORDER BY timestamp ASC
        """, (project_id,))
        audit_records = [dict(r) for r in cur.fetchall()]

        esc_reason = (
            f"Calibrated 12-month deterioration risk remained in ESCALATE tier (>=50.0%) "
            f"across {persistent_count} consecutive reporting cycles following Contractor Warning {warn_id} "
            f"without demonstrated trajectory recovery."
        )

        resp_snapshot = dict(resp) if resp else None
        resp_status = "RESPONSE_SUBMITTED" if has_responded else "UNRESPONSIVE"

        conn.execute("""
            INSERT INTO authority_escalations (
                escalation_id, project_id, warning_id, escalation_date,
                risk_at_warning, current_risk, persistence_duration_months,
                evidence, contractor_response, response_status,
                reason_for_escalation, full_audit_trail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            esc_id,
            project_id,
            warn_id,
            now_iso,
            warn_prob,
            calibrated_prob,
            persistent_count,
            json.dumps(top_explanations),
            json.dumps(resp_snapshot),
            resp_status,
            esc_reason,
            json.dumps(audit_records)
        ))

        # Update warning and project status to ESCALATED
        conn.execute("UPDATE contractor_warnings SET status = 'ESCALATED' WHERE warning_id = ?", (warn_id,))
        conn.execute("UPDATE monitored_projects SET status = 'ESCALATED', updated_at = ? WHERE project_id = ?", (now_iso, project_id))

        append_audit_event(
            conn,
            project_id=project_id,
            event_type="AUTHORITY_ESCALATION_ISSUED",
            actor="VIGIL_GOVERNANCE",
            reporting_month=reporting_month,
            risk_probability=calibrated_prob,
            metadata={
                "escalation_id": esc_id,
                "warning_id": warn_id,
                "persistent_cycles": persistent_count,
                "reason": esc_reason
            }
        )

        outcome["action"] = "AUTHORITY_ESCALATION_ISSUED"
        outcome["escalation_id"] = esc_id
        outcome["details"] = f"Authority Escalation {esc_id} issued to government oversight authority. Reason: {esc_reason}"

    return outcome


def submit_contractor_response(
    project_id: str,
    warning_id: str,
    acknowledged: bool,
    response_text: str,
    corrective_action: str,
    expected_recovery_date: Optional[str] = None,
    responsible_person: Optional[str] = None,
    supporting_documents: Optional[List[Dict[str, Any]]] = None,
    actor: str = "CONTRACTOR_REPRESENTATIVE",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submit a formal contractor response/recovery plan to an active warning.
    Records immutable contractor response and advances warning state to UNDER_RECOVERY.
    """
    init_db(db_path)
    pid = str(project_id).strip()
    wid = str(warning_id).strip()

    if not acknowledged:
        raise ValueError("Contractor response must acknowledge receipt of the warning.")
    if not response_text.strip():
        raise ValueError("response_text cannot be empty.")
    if not corrective_action.strip():
        raise ValueError("corrective_action cannot be empty.")

    now_iso = datetime.now(timezone.utc).isoformat()
    resp_id = f"RESP-{uuid.uuid4().hex[:8].upper()}"

    with get_db(db_path) as conn:
        with conn:
            # Check warning
            cur = conn.execute(
                "SELECT * FROM contractor_warnings WHERE warning_id = ? AND project_id = ?",
                (wid, pid)
            )
            warn = cur.fetchone()
            if warn is None:
                raise ValueError(f"Warning '{wid}' not found for project '{pid}'.")

            if warn["status"] in ["RECOVERED", "ESCALATED", "RESPONSE_SUBMITTED"]:
                raise ValueError(f"Cannot respond to warning '{wid}': already in state '{warn['status']}'.")

            cur_resp = conn.execute("SELECT response_id FROM contractor_responses WHERE warning_id = ?", (wid,))
            if cur_resp.fetchone() is not None:
                raise ValueError(f"A response has already been submitted for warning '{wid}'.")

            conn.execute("""
                INSERT INTO contractor_responses (
                    response_id, warning_id, project_id, acknowledged,
                    response_text, corrective_action, expected_recovery_date,
                    responsible_person, supporting_documents, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resp_id,
                wid,
                pid,
                1 if acknowledged else 0,
                response_text.strip(),
                corrective_action.strip(),
                expected_recovery_date,
                responsible_person,
                json.dumps(supporting_documents) if supporting_documents else None,
                now_iso
            ))

            # Update warning status to RESPONSE_SUBMITTED / UNDER_RECOVERY
            conn.execute(
                "UPDATE contractor_warnings SET status = 'RESPONSE_SUBMITTED' WHERE warning_id = ?",
                (wid,)
            )
            conn.execute(
                "UPDATE monitored_projects SET status = 'UNDER_RECOVERY', updated_at = ? WHERE project_id = ?",
                (now_iso, pid)
            )

            append_audit_event(
                conn,
                project_id=pid,
                event_type="CONTRACTOR_RESPONSE_RECEIVED",
                actor=actor,
                metadata={
                    "response_id": resp_id,
                    "warning_id": wid,
                    "corrective_action": corrective_action.strip(),
                    "expected_recovery_date": expected_recovery_date
                }
            )

            append_audit_event(
                conn,
                project_id=pid,
                event_type="RECOVERY_MONITORING_STARTED",
                actor="VIGIL_GOVERNANCE",
                metadata={
                    "warning_id": wid,
                    "response_id": resp_id
                }
            )

        return {
            "response_id": resp_id,
            "warning_id": wid,
            "project_id": pid,
            "status": "RESPONSE_SUBMITTED",
            "submitted_at": now_iso
        }


def get_project_status(project_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Get holistic governance status for a monitored project."""
    init_db(db_path)
    proj = get_project(project_id, db_path=db_path)

    with get_db(db_path) as conn:
        # Latest observation
        cur = conn.execute("""
            SELECT * FROM monthly_observations WHERE project_id = ? ORDER BY reporting_month DESC LIMIT 1
        """, (project_id,))
        latest_obs = cur.fetchone()

        # Active warning
        cur = conn.execute("""
            SELECT * FROM contractor_warnings WHERE project_id = ? ORDER BY issued_at DESC LIMIT 1
        """, (project_id,))
        latest_warn = cur.fetchone()

        # Contractor response if warning exists
        latest_resp = None
        if latest_warn:
            cur = conn.execute("""
                SELECT * FROM contractor_responses WHERE warning_id = ? ORDER BY submitted_at DESC LIMIT 1
            """, (latest_warn["warning_id"],))
            latest_resp = cur.fetchone()

        # Active escalation
        cur = conn.execute("""
            SELECT * FROM authority_escalations WHERE project_id = ? ORDER BY escalation_date DESC LIMIT 1
        """, (project_id,))
        latest_esc = cur.fetchone()

        return {
            "project": proj,
            "latest_observation": dict(latest_obs) if latest_obs else None,
            "active_warning": dict(latest_warn) if latest_warn else None,
            "contractor_response": dict(latest_resp) if latest_resp else None,
            "active_escalation": dict(latest_esc) if latest_esc else None,
            "governance_state": proj["status"]
        }


def get_project_observations(project_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve full chronological observations for a monitored project."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cur = conn.execute("""
            SELECT * FROM monthly_observations WHERE project_id = ? ORDER BY reporting_month ASC
        """, (project_id,))
        return [dict(r) for r in cur.fetchall()]


def get_project_warnings(project_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all contractor warnings issued for a project."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cur = conn.execute("""
            SELECT * FROM contractor_warnings WHERE project_id = ? ORDER BY issued_at ASC
        """, (project_id,))
        return [dict(r) for r in cur.fetchall()]


def get_authority_escalations(sector: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve portfolio-wide authority escalations with full dossier."""
    init_db(db_path)
    with get_db(db_path) as conn:
        query = """
            SELECT e.*, p.project_name, p.sector, p.ministry, p.approved_cost
            FROM authority_escalations e
            JOIN monitored_projects p ON e.project_id = p.project_id
            WHERE 1=1
        """
        params: List[Any] = []
        if sector:
            query += " AND LOWER(p.sector) = LOWER(?)"
            params.append(sector.strip())
        query += " ORDER BY e.escalation_date DESC"

        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def get_audit_trail(project_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve immutable chronological audit trail for a monitored project."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cur = conn.execute("""
            SELECT * FROM audit_events WHERE project_id = ? ORDER BY timestamp ASC
        """, (project_id,))
        return [dict(r) for r in cur.fetchall()]
