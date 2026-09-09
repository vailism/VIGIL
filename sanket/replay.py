#!/usr/bin/env python3
"""
sanket/replay.py

Historical Replay & Trajectory Audit Engine for VIGIL.
Reconstructs the point-in-time state of an infrastructure project across its longitudinal lifecycle:
- Exact historical trajectory kinematics at month t
- Point-in-time calibrated risk probability and tier
- Deterministic "WHY?" explanation factors
- Genuine observable deterioration events (zero t+12 artificial fallbacks)
- First-alert lead time calculation
"""

import os
from typing import Dict, List, Any, Optional, Union
import numpy as np
import pandas as pd

from sanket.inference import load_inference_engine, predict_point_in_time

def ym_to_int(ym: Any) -> Optional[int]:
    if not isinstance(ym, str) or not ym or ym == "nan":
        return None
    parts = ym.strip().split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) * 12 + int(parts[1])
    return None

def int_to_ym(val: int) -> str:
    y = val // 12
    m = val % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y:04d}-{m:02d}"

def replay_project_from_dataframe(
    df_proj: pd.DataFrame,
    engine: Optional[Dict[str, Any]] = None,
    cost_escalation_thresh: float = 0.05,
    delay_escalation_thresh: float = 6.0
) -> Dict[str, Any]:
    """
    Reconstruct point-in-time predictions and detect actual deterioration milestones
    from an in-memory project history DataFrame.
    Guarantees strict point-in-time integrity: row t NEVER accesses information from rows > t.
    """
    if engine is None:
        engine = load_inference_engine()

    if df_proj.empty:
        raise ValueError("Cannot replay empty project DataFrame.")

    # Sort strictly by reporting_month
    p_df = df_proj.sort_values(by="reporting_month", ascending=True).reset_index(drop=True).copy()

    pid = str(p_df["project_id"].iloc[0])
    pname = str(p_df["project_name"].iloc[0]) if "project_name" in p_df.columns else pid
    sector = str(p_df["sector"].iloc[0]) if "sector" in p_df.columns else (str(p_df["sector_clean"].iloc[0]) if "sector_clean" in p_df.columns else "UNKNOWN")
    ministry = str(p_df["ministry"].iloc[0]) if "ministry" in p_df.columns else "UNKNOWN"
    state = str(p_df["state"].iloc[0]) if "state" in p_df.columns else "UNKNOWN"
    approved_cost = float(pd.to_numeric(p_df["approved_cost"], errors="coerce").fillna(0).iloc[0]) if "approved_cost" in p_df.columns else 0.0

    n_obs = len(p_df)
    timeline_records = []
    alert_points = []

    # Fast arrays for deterioration detection
    cbase_series = pd.to_numeric(p_df["C_base"], errors="coerce").fillna(0).values if "C_base" in p_df.columns else np.zeros(n_obs)
    sdev_series = pd.to_numeric(p_df["schedule_deviation_months"], errors="coerce").values if "schedule_deviation_months" in p_df.columns else np.full(n_obs, np.nan)
    months_series = p_df["reporting_month"].values

    # Step 1: Detect
    # An actual deterioration occurs when C_base increases by >= 5% or schedule_deviation increases by >= 6m
    # compared to the established historical baseline (high-water mark prior to this observation)
    actual_events = []
    max_seen_cbase = 0.0
    max_seen_sdev = -np.inf

    for i in range(n_obs):
        m_curr = months_series[i]
        c_curr = cbase_series[i]
        d_curr = sdev_series[i]

        is_event = False
        event_reasons = []

        # True cost escalation: current C_base expands by >= 5% beyond the highest established baseline seen so far
        if max_seen_cbase > 0 and c_curr > 0:
            cost_increase_ratio = (c_curr - max_seen_cbase) / max_seen_cbase
            if cost_increase_ratio >= cost_escalation_thresh:
                is_event = True
                event_reasons.append(f"Cost escalated +{cost_increase_ratio*100.0:.1f}% (₹{max_seen_cbase:,.1f} Cr -> ₹{c_curr:,.1f} Cr)")

        # True schedule deterioration: current schedule deviation expands by >= 6 months beyond highest prior delay
        if not np.isneginf(max_seen_sdev) and not np.isnan(max_seen_sdev) and not np.isnan(d_curr):
            delay_increase = d_curr - max_seen_sdev
            if delay_increase >= delay_escalation_thresh:
                is_event = True
                event_reasons.append(f"Schedule deviation jumped +{delay_increase:.1f} months ({max_seen_sdev:.1f}m -> {d_curr:.1f}m)")

        if is_event:
            actual_events.append({
                "event_index": i,
                "event_month": m_curr,
                "reasons": event_reasons,
                "prior_cbase": max_seen_cbase,
                "new_cbase": c_curr,
                "prior_sdev": max_seen_sdev if not np.isneginf(max_seen_sdev) else None,
                "new_sdev": d_curr
            })

        if c_curr > max_seen_cbase:
            max_seen_cbase = c_curr
        if not np.isnan(d_curr) and d_curr > max_seen_sdev:
            max_seen_sdev = d_curr

    # Identify primary first deterioration event (if any occurred)
    first_event = actual_events[0] if len(actual_events) > 0 else None

    # Step 2: Generate point-in-time predictions for each monthly report
    first_alert = None

    for i in range(n_obs):
        row = p_df.iloc[i]
        m_ym = row["reporting_month"]

        # Point-in-time prediction using ONLY features available at or before index i
        pred_res = predict_point_in_time(row, engine=engine)

        rec = {
            "reporting_month": m_ym,
            "observation_number": int(row.get("observation_number", i + 1)),
            "C_base": float(row.get("C_base", 0) or 0),
            "expenditure": float(pd.to_numeric(row.get("expenditure", 0), errors="coerce") or 0),
            "financial_progress": float(pd.to_numeric(row.get("financial_progress", 0), errors="coerce") or 0),
            "schedule_deviation_months": float(row.get("schedule_deviation_months", np.nan)) if not pd.isna(row.get("schedule_deviation_months")) else None,
            "V_fin_1m": float(row.get("V_fin_1m", np.nan)) if not pd.isna(row.get("V_fin_1m")) else None,
            "V_fin_3m": float(row.get("V_fin_3m", np.nan)) if not pd.isna(row.get("V_fin_3m")) else None,
            "A_fin": float(row.get("A_fin", np.nan)) if not pd.isna(row.get("A_fin")) else None,
            "EWMA_V_fin": float(row.get("EWMA_V_fin", np.nan)) if not pd.isna(row.get("EWMA_V_fin")) else None,
            "Z_peer_V_fin": float(row.get("Z_peer_V_fin", np.nan)) if not pd.isna(row.get("Z_peer_V_fin")) else None,
            "trajectory_risk_score": float(row.get("trajectory_risk_score", np.nan)) if not pd.isna(row.get("trajectory_risk_score")) else None,
            "raw_prob": pred_res["raw_prob"],
            "pred_prob": pred_res["pred_prob"],
            "risk_tier": pred_res["risk_tier"],
            "alert": pred_res["alert"],
            "top_explanations": pred_res["top_explanations"],
            "actual_event": any(ev["event_month"] == m_ym for ev in actual_events),
            "lead_time_if_event": None
        }

        # Track alerts
        if rec["alert"]:
            alert_points.append({
                "reporting_month": m_ym,
                "observation_number": rec["observation_number"],
                "risk_tier": rec["risk_tier"],
                "pred_prob": rec["pred_prob"],
                "top_explanation": rec["top_explanations"][0]["explanation"] if rec["top_explanations"] else None
            })

            # Check if this alert precedes the first deterioration event
            if first_event is not None:
                m_int = ym_to_int(m_ym)
                ev_int = ym_to_int(first_event["event_month"])
                if m_int is not None and ev_int is not None and m_int < ev_int:
                    rec["lead_time_if_event"] = ev_int - m_int
                    if first_alert is None:
                        first_alert = {
                            "alert_month": m_ym,
                            "risk_tier": rec["risk_tier"],
                            "pred_prob": rec["pred_prob"],
                            "lead_time_months": ev_int - m_int,
                            "top_explanation": rec["top_explanations"][0]["explanation"] if rec["top_explanations"] else None
                        }

        timeline_records.append(rec)

    overall_lead_time = first_alert["lead_time_months"] if first_alert is not None else None

    return {
        "project_id": pid,
        "project_name": pname,
        "sector": sector,
        "ministry": ministry,
        "state": state,
        "approved_cost": approved_cost,
        "total_observations": n_obs,
        "start_month": months_series[0] if n_obs > 0 else None,
        "end_month": months_series[-1] if n_obs > 0 else None,
        "timeline": timeline_records,
        "alert_points": alert_points,
        "actual_deterioration_event": first_event,
        "all_deterioration_events": actual_events,
        "first_alert": first_alert,
        "lead_time": overall_lead_time
    }

def get_project_replay(
    project_id: str,
    dataset_path: str = "DATA/model_dataset.parquet",
    engine: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Retrieve and reconstruct historical point-in-time replay for a specific project_id.
    Fails cleanly with ValueError if project is unknown.
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset '{dataset_path}' not found.")

    # Read project observations
    p_df = pd.read_parquet(
        dataset_path,
        filters=[("project_id", "==", str(project_id))]
    )

    if p_df.empty:
        raise ValueError(f"Project ID '{project_id}' not found in longitudinal dataset.")

    return replay_project_from_dataframe(p_df, engine=engine)

def replay_project(
    project_id: str,
    dataset_path: str = "DATA/model_dataset.parquet",
    engine: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Alias for get_project_replay.
    """
    return get_project_replay(project_id, dataset_path=dataset_path, engine=engine)
