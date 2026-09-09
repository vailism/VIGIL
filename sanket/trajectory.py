#!/usr/bin/env python3
"""
sanket/trajectory.py

Phase 2 & Phase 3: Trajectory Engine & Interpretable Risk Scoring for VIGIL.
Calculates strictly point-in-time temporal velocities, accelerations, EWMA trends,
peer-normalized benchmarks, and transparent component-level risk scores.

Key Invariants:
1. Zero Future Leakage: Features at observation month t use ONLY data available at or before t.
2. Strict Reset at Project Boundaries: Shifting operations group by project_id.
3. Transparent Interpretable Risk Score: Driven by configs/trajectory.yaml, preserving
   all 7 component sub-scores independently.
"""

import os
import sys
import argparse
import yaml
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

def load_config(config_path: str = "configs/trajectory.yaml") -> Dict[str, Any]:
    """Load trajectory configuration from YAML."""
    if not os.path.exists(config_path):
        # Fallback default configuration
        return {
            "ewma_alpha": 0.30,
            "risk_score_weights": {
                "stalled_velocity": 0.25,
                "deceleration": 0.15,
                "burn_rate_anomaly": 0.15,
                "cost_revision_drift": 0.15,
                "schedule_deterioration": 0.15,
                "peer_underperformance": 0.15,
            },
            "physical_progress_weight": 0.10
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ym_to_month_number(ym_str: Any) -> Optional[int]:
    """Convert YYYY-MM to integer month number."""
    if not isinstance(ym_str, str) or not ym_str or ym_str == "nan":
        return None
    parts = ym_str.strip().split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        y, m = int(parts[0]), int(parts[1])
        if 1 <= m <= 12:
            return y * 12 + m
    return None

def compute_trajectories(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    peer_stats: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Compute point-in-time trajectory features and component risk scores.
    Expects DataFrame sorted by (project_id, reporting_month).
    """
    if config is None:
        config = load_config()

    df = df.copy().reset_index(drop=True)

    # Ensure expected input columns exist (handling minimal test DataFrames safely)
    expected_optional_cols = [
        "financial_progress", "expenditure", "approved_cost", "revised_cost",
        "schedule_deviation", "original_completion_date", "revised_completion_date",
        "physical_progress", "sector"
    ]
    for col in expected_optional_cols:
        if col not in df.columns:
            df[col] = np.nan

    # Ensure strictly sorted
    df = df.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

    grouped = df.groupby("project_id", sort=False)

    # -------------------------------------------------------------
    # 1. CORE FINANCIAL TRAJECTORY
    # -------------------------------------------------------------
    fin_prog = pd.to_numeric(df["financial_progress"], errors="coerce")
    
    # Financial progress velocity (1-month delta)
    prev_fin = grouped["financial_progress"].shift(1)
    df["V_fin_1m"] = fin_prog - prev_fin

    # Financial progress velocity (3-month / 3-observation delta)
    prev_fin_3m = grouped["financial_progress"].shift(3)
    df["V_fin_3m"] = fin_prog - prev_fin_3m

    # Financial progress acceleration: change in velocity
    prev_v_fin = grouped["V_fin_1m"].shift(1)
    df["A_fin"] = df["V_fin_1m"] - prev_v_fin

    # -------------------------------------------------------------
    # 2. EXPENDITURE TRAJECTORY
    # -------------------------------------------------------------
    exp = pd.to_numeric(df["expenditure"], errors="coerce")
    # Clean negative expenditure (audit artifact) point-in-time
    exp_clean = np.where(exp < 0, np.nan, exp)
    df["expenditure_clean"] = exp_clean

    prev_exp = grouped["expenditure_clean"].shift(1)
    df["V_exp_1m"] = df["expenditure_clean"] - prev_exp

    prev_exp_3m = grouped["expenditure_clean"].shift(3)
    df["V_exp_3m"] = df["expenditure_clean"] - prev_exp_3m

    prev_v_exp = grouped["V_exp_1m"].shift(1)
    df["A_exp"] = df["V_exp_1m"] - prev_v_exp

    # -------------------------------------------------------------
    # 3. COST BASELINE & DRIFT
    # -------------------------------------------------------------
    app_cost = pd.to_numeric(df["approved_cost"], errors="coerce")
    app_cost_clean = np.where(app_cost <= 0, np.nan, app_cost)

    rev_cost = pd.to_numeric(df["revised_cost"], errors="coerce")
    rev_cost_clean = np.where(rev_cost <= 0, np.nan, rev_cost)

    # Point-in-time C_base(t): revised_cost if valid & positive, else approved_cost
    df["C_base"] = np.where(~np.isnan(rev_cost_clean), rev_cost_clean, app_cost_clean)

    # Cost revision ratio: (revised - approved) / approved
    df["cost_revision_ratio"] = np.where(
        app_cost_clean > 0,
        (rev_cost_clean - app_cost_clean) / app_cost_clean,
        np.nan
    )

    # Expenditure to baseline ratio
    df["expenditure_to_baseline"] = np.where(
        df["C_base"] > 0,
        df["expenditure_clean"] / df["C_base"],
        np.nan
    )

    # -------------------------------------------------------------
    # 4. SCHEDULE TRAJECTORY (Point-in-Time Only)
    # -------------------------------------------------------------
    sch_dev = pd.to_numeric(df["schedule_deviation"], errors="coerce")
    df["schedule_deviation_months"] = sch_dev

    prev_sch_dev = grouped["schedule_deviation_months"].shift(1)
    df["schedule_deviation_change"] = df["schedule_deviation_months"] - prev_sch_dev

    # Target completion date point-in-time: revised if non-null, else original
    def resolve_target_date(r):
        rev = str(r.get("revised_completion_date", "") or "").strip()
        if rev and rev != "nan" and ym_to_month_number(rev) is not None:
            return ym_to_month_number(rev)
        orig = str(r.get("original_completion_date", "") or "").strip()
        if orig and orig != "nan" and ym_to_month_number(orig) is not None:
            return ym_to_month_number(orig)
        return np.nan

    df["target_completion_month_num"] = df.apply(resolve_target_date, axis=1)
    prev_target_month = grouped["target_completion_month_num"].shift(1)
    df["completion_date_drift"] = df["target_completion_month_num"] - prev_target_month

    # -------------------------------------------------------------
    # 5. EWMA FOR FINANCIAL VELOCITY
    # -------------------------------------------------------------
    ewma_alpha = float(config.get("ewma_alpha", 0.30))
    print(f"Calculating recursive chronological EWMA (alpha={ewma_alpha})...")
    # Vectorized group transform using pandas ewm (strictly chronological within group)
    df["EWMA_V_fin"] = grouped["V_fin_1m"].transform(
        lambda s: s.ewm(alpha=ewma_alpha, adjust=False).mean()
    )

    # -------------------------------------------------------------
    # 6. PHYSICAL PROGRESS TRAJECTORY (No Imputation)
    # -------------------------------------------------------------
    phys = pd.to_numeric(df["physical_progress"], errors="coerce")
    df["physical_progress_clean"] = np.where((phys < 0) | (phys > 100), np.nan, phys)

    prev_phys = grouped["physical_progress_clean"].shift(1)
    df["V_phys_1m"] = df["physical_progress_clean"] - prev_phys

    prev_phys_3m = grouped["physical_progress_clean"].shift(3)
    df["V_phys_3m"] = df["physical_progress_clean"] - prev_phys_3m

    prev_v_phys = grouped["V_phys_1m"].shift(1)
    df["A_phys"] = df["V_phys_1m"] - prev_v_phys

    # Decoupling gap: financial_progress - physical_progress
    df["financial_physical_gap"] = fin_prog - df["physical_progress_clean"]

    # -------------------------------------------------------------
    # 7. POINT-IN-TIME PEER NORMALIZATION
    # -------------------------------------------------------------
    print("Computing point-in-time sector peer benchmarks...")
    # Clean sector string
    df["sector_clean"] = df["sector"].fillna("UNKNOWN").astype(str).str.strip()
    df["sector_clean"] = np.where(df["sector_clean"].isin(["", "nan", "UNKNOWN"]), "OTHER", df["sector_clean"])

    # Scale bucket
    conditions_scale = [
        df["C_base"] < 150.0,
        (df["C_base"] >= 150.0) & (df["C_base"] < 1000.0),
        df["C_base"] >= 1000.0
    ]
    choices_scale = ["SMALL", "MAJOR", "MEGA"]
    df["scale_bucket"] = np.select(conditions_scale, choices_scale, default="UNKNOWN")

    # Group strictly by reporting_month and sector_clean to prevent future leakage
    peer_group_cols = ["reporting_month", "sector_clean", "scale_bucket"]
    
    if peer_stats is None:
        # Calculate peer velocity statistics within current reporting month
        peer_stats = df.groupby(peer_group_cols, observed=False)["V_fin_1m"].agg(
            peer_v_mean="mean",
            peer_v_std="std",
            peer_count="count"
        ).reset_index()

    df = df.merge(peer_stats, on=peer_group_cols, how="left")

    # Vectorized z-score calculation (minimum 5 peers required, std clamped to 0.01)
    valid_peer_mask = (df["peer_count"] >= 5) & (df["peer_v_std"].fillna(0) > 0.01)
    df["Z_peer_V_fin"] = np.where(
        valid_peer_mask,
        (df["V_fin_1m"] - df["peer_v_mean"]) / df["peer_v_std"],
        0.0
    )

    # -------------------------------------------------------------
    # 8. PHASE 3: INTERPRETABLE COMPONENT RISK SCORES
    # -------------------------------------------------------------
    print("Computing transparent trajectory risk score components...")
    weights = config.get("risk_score_weights", {})
    w_stall = weights.get("stalled_velocity", 0.25)
    w_decel = weights.get("deceleration", 0.15)
    w_burn = weights.get("burn_rate_anomaly", 0.15)
    w_cost = weights.get("cost_revision_drift", 0.15)
    w_sch = weights.get("schedule_deterioration", 0.15)
    w_peer = weights.get("peer_underperformance", 0.15)
    w_phys = config.get("physical_progress_weight", 0.10)

    # Component 1: Stalled or Negative Velocity (V <= 0 -> 1.0, V >= 3% -> 0.0)
    df["score_stalled_velocity"] = np.where(
        df["V_fin_1m"].isna(),
        np.nan,
        np.clip(1.0 - (df["V_fin_1m"] / 3.0), 0.0, 1.0)
    )

    # Component 2: Negative Acceleration (Deceleration: A <= -2.0% -> 1.0, A >= 0 -> 0.0)
    df["score_deceleration"] = np.where(
        df["A_fin"].isna(),
        np.nan,
        np.clip(-df["A_fin"] / 2.0, 0.0, 1.0)
    )

    # Component 3: Burn-Rate Anomaly (expenditure ratio high relative to progress)
    cur_fin_prog = pd.to_numeric(df["financial_progress"], errors="coerce")
    burn_ratio = np.where(
        (cur_fin_prog > 0) & (df["expenditure_to_baseline"] > 0),
        df["expenditure_to_baseline"] / (cur_fin_prog / 100.0),
        np.nan
    )
    df["score_burn_anomaly"] = np.where(
        np.isnan(burn_ratio),
        np.nan,
        np.clip((burn_ratio - 1.0) / 0.5, 0.0, 1.0)
    )

    # Component 4: Existing Cost Revision Drift
    df["score_cost_revision"] = np.where(
        df["cost_revision_ratio"].isna(),
        0.0,
        np.clip(df["cost_revision_ratio"] / 0.25, 0.0, 1.0)
    )

    # Component 5: Schedule Deterioration (Drift or deviation increase >= 6 mos -> 1.0)
    sch_deterioration_months = np.maximum(
        df["completion_date_drift"].fillna(0),
        df["schedule_deviation_change"].fillna(0)
    )
    df["score_schedule_deterioration"] = np.where(
        df["completion_date_drift"].isna() & df["schedule_deviation_change"].isna(),
        np.nan,
        np.clip(sch_deterioration_months / 6.0, 0.0, 1.0)
    )

    # Component 6: Peer Underperformance (Z <= -2.0 -> 1.0, Z >= 0 -> 0.0)
    df["score_peer_underperformance"] = np.where(
        df["V_fin_1m"].isna(),
        np.nan,
        np.clip(-df["Z_peer_V_fin"] / 2.0, 0.0, 1.0)
    )

    # Component 7: Physical-Financial Decoupling (where physical progress exists)
    # Spending 20 percentage points ahead of physical build -> 1.0
    df["score_physical_decoupling"] = np.where(
        df["financial_physical_gap"].isna(),
        np.nan,
        np.clip(df["financial_physical_gap"] / 20.0, 0.0, 1.0)
    )

    # Composite Weighted Trajectory Score (0 to 100)
    comp_map = [
        ("score_stalled_velocity", w_stall),
        ("score_deceleration", w_decel),
        ("score_burn_anomaly", w_burn),
        ("score_cost_revision", w_cost),
        ("score_schedule_deterioration", w_sch),
        ("score_peer_underperformance", w_peer)
    ]

    total_weighted_score = np.zeros(len(df), dtype=np.float64)
    total_valid_weight = np.zeros(len(df), dtype=np.float64)
    valid_component_count = np.zeros(len(df), dtype=np.int32)

    for col, weight in comp_map:
        val = df[col].values
        valid_mask = ~np.isnan(val)
        total_weighted_score += np.where(valid_mask, val * weight, 0.0)
        total_valid_weight += np.where(valid_mask, weight, 0.0)
        valid_component_count += valid_mask.astype(np.int32)

    # Add physical decoupling if present
    phys_mask = ~df["score_physical_decoupling"].isna()
    total_weighted_score += np.where(phys_mask, df["score_physical_decoupling"].values * w_phys, 0.0)
    total_valid_weight += np.where(phys_mask, w_phys, 0.0)
    valid_component_count += phys_mask.astype(np.int32)

    # Require at least 2 valid components to produce an aggregate score
    df["trajectory_risk_score"] = np.where(
        (valid_component_count >= 2) & (total_valid_weight > 0),
        np.round((total_weighted_score / total_valid_weight) * 100.0, 2),
        np.nan
    )

    # Drop temporary calculation columns
    drop_temp = ["target_completion_month_num", "peer_v_mean", "peer_v_std", "peer_count"]
    df.drop(columns=[c for c in drop_temp if c in df.columns], inplace=True)

    return df

def run_trajectory_pipeline(
    input_path: str = "DATA/project_timelines.parquet",
    output_path: str = "DATA/project_trajectories.parquet",
    config_path: str = "configs/trajectory.yaml"
) -> pd.DataFrame:
    """Run trajectory pipeline end-to-end from Parquet timeline input."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Timelines file '{input_path}' not found. Run sanket.timeline first.")

    print(f"Loading timelines from {input_path}...")
    df_timelines = pd.read_parquet(input_path, engine="pyarrow")
    config = load_config(config_path)

    df_traj = compute_trajectories(df_timelines, config)

    print(f"Saving trajectory feature dataset to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_traj.to_parquet(output_path, index=False, engine="pyarrow")
    print(f"Successfully generated trajectory dataset with {len(df_traj):,} rows and {len(df_traj.columns)} columns.")
    return df_traj

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute VIGIL project trajectory features.")
    parser.add_argument("--input", default="DATA/project_timelines.parquet", help="Input timeline Parquet")
    parser.add_argument("--output", default="DATA/project_trajectories.parquet", help="Output trajectory Parquet")
    parser.add_argument("--config", default="configs/trajectory.yaml", help="Path to trajectory YAML config")
    args = parser.parse_args()

    run_trajectory_pipeline(args.input, args.output, args.config)


def compute_canonical_features_for_project(
    observations: Any,
    project_start_date: Optional[str] = None,
    peer_benchmarks: Optional[pd.DataFrame] = None,
    config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Canonical feature-building function shared between historical inference and operational monitoring.
    Given chronological observations for a single project through month t:
    1. Sorts strictly by reporting_month ascending.
    2. Computes pure timeline features:
       - observation_number: 1-indexed sequential count (1, 2, 3...)
       - months_since_previous_observation: calendar delta from t_{prev}
       - reporting_gap_flag: 1 if delta > 1 month, 0 otherwise
       - project_age_months: reporting_month - project_start_date (np.nan if start_date missing)
    3. Computes point-in-time trajectory features via compute_trajectories.
    4. Guarantees strict type casting and feature presence matching production model expectations.
    """
    if isinstance(observations, list):
        df = pd.DataFrame(observations)
    else:
        df = observations.copy()

    if df.empty:
        return df

    # Standardize column types
    df = df.reset_index(drop=True)
    df["reporting_month"] = df["reporting_month"].astype(str).str.strip()
    df = df.sort_values(by="reporting_month", ascending=True).reset_index(drop=True)

    n_obs = len(df)
    month_indices = [ym_to_month_number(m) for m in df["reporting_month"]]

    # Timeline features
    df["observation_number"] = np.arange(1, n_obs + 1, dtype=np.int32)

    months_since_prev = [np.nan]
    for i in range(1, n_obs):
        m_curr = month_indices[i]
        m_prev = month_indices[i - 1]
        if m_curr is not None and m_prev is not None:
            months_since_prev.append(float(m_curr - m_prev))
        else:
            months_since_prev.append(np.nan)
    df["months_since_previous_observation"] = pd.to_numeric(months_since_prev, errors="coerce")

    df["reporting_gap_flag"] = np.where(
        df["months_since_previous_observation"].fillna(1) > 1, 1, 0
    ).astype(np.int32)

    # Project age semantics: reporting_month - actual project_start_date
    start_m_idx = ym_to_month_number(project_start_date) if project_start_date else None
    if start_m_idx is not None:
        age_list = []
        for m_idx in month_indices:
            if m_idx is not None:
                age_list.append(float(m_idx - start_m_idx))
            else:
                age_list.append(np.nan)
        df["project_age_months"] = pd.to_numeric(age_list, errors="coerce")
    elif "project_age_months" in df.columns and df["project_age_months"].notna().any():
        # Preserve if explicitly supplied in historical replay/record
        df["project_age_months"] = pd.to_numeric(df["project_age_months"], errors="coerce")
    else:
        df["project_age_months"] = np.nan

    # Compute trajectories using canonical engine
    df = compute_trajectories(df, config=config, peer_stats=peer_benchmarks)

    # Ensure all 25 model features are present and cast to proper types
    numeric_model_features = [
        'V_fin_1m', 'V_fin_3m', 'A_fin', 'EWMA_V_fin', 'V_exp_1m', 'V_exp_3m', 'A_exp',
        'cost_revision_ratio', 'expenditure_to_baseline', 'schedule_deviation_months',
        'schedule_deviation_change', 'completion_date_drift', 'Z_peer_V_fin',
        'trajectory_risk_score', 'V_phys_1m', 'V_phys_3m', 'A_phys',
        'financial_physical_gap', 'project_age_months', 'observation_number',
        'months_since_previous_observation', 'reporting_gap_flag', 'C_base'
    ]
    for feat in numeric_model_features:
        if feat not in df.columns:
            df[feat] = np.nan
        else:
            df[feat] = pd.to_numeric(df[feat], errors="coerce").astype(np.float64)

    cat_model_features = ['sector_clean', 'scale_bucket']
    for cat in cat_model_features:
        if cat not in df.columns:
            df[cat] = "UNKNOWN"
        else:
            df[cat] = df[cat].fillna("UNKNOWN").astype(str)

    return df

