#!/usr/bin/env python3
"""
sanket/targets.py

Phase 4: Leakage-Safe Target Generator for VIGIL.
Implements the formal methodology defined in TARGET_DEFINITION.md.

Produces:
- Independent binary targets: cost_overrun_6m, cost_overrun_12m, schedule_overrun_6m, schedule_overrun_12m
- Continuous change metrics: cost_escalation_pct_6m, cost_escalation_pct_12m, schedule_drift_months_6m, schedule_drift_months_12m
- Derived governance distress: overrun_composite_6m, overrun_composite_12m
- Explanatory cause categorization: distress_type_6m, distress_type_12m
- Dual eligibility flags: eligible_features, target_observable_6m, target_observable_12m

Key Invariants:
1. Pure Forward Window: Targets at observation month t inspect ONLY reports dated s in (t, t+H].
2. Strict Right-Censoring: If future window is incomplete, target fields MUST be NaN (never 0).
3. Independent Generation: Target module operates independently from the feature engine.
"""

import os
import sys
import argparse
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np

def ym_to_month_int(ym_val: Any) -> Optional[int]:
    """Convert YYYY-MM string to integer month index: year * 12 + month."""
    if not isinstance(ym_val, str) or not ym_val or ym_val == "nan":
        return None
    parts = ym_val.strip().split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]) * 12 + int(parts[1])
    return None

def compute_targets(
    df: pd.DataFrame,
    cost_threshold_6m: float = 0.05,
    cost_threshold_12m: float = 0.05,
    delay_threshold_6m: float = 3.0,
    delay_threshold_12m: float = 6.0
) -> pd.DataFrame:
    """
    Generate leakage-safe targets for every project-month observation.
    Expects DataFrame sorted by (project_id, reporting_month).
    """
    df = df.copy()

    # Ensure required columns exist
    req_cols = [
        "project_id", "reporting_month", "approved_cost", "revised_cost",
        "original_completion_date", "revised_completion_date", "schedule_deviation"
    ]
    for col in req_cols:
        if col not in df.columns:
            df[col] = np.nan

    if not df["project_id"].is_monotonic_increasing:
        df = df.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

    # Convert reporting month to integer month index
    df["report_month_int"] = df["reporting_month"].apply(ym_to_month_int)

    # Point-in-time cost baseline C_base(t)
    app_cost = pd.to_numeric(df["approved_cost"], errors="coerce")
    app_cost_clean = np.where(app_cost <= 0, np.nan, app_cost)

    rev_cost = pd.to_numeric(df["revised_cost"], errors="coerce")
    rev_cost_clean = np.where(rev_cost <= 0, np.nan, rev_cost)

    df["C_base"] = np.where(~np.isnan(rev_cost_clean), rev_cost_clean, app_cost_clean)

    # Point-in-time target completion date in integer months
    def get_target_comp(r):
        rev = str(r.get("revised_completion_date", "") or "").strip()
        if rev and rev != "nan" and ym_to_month_int(rev) is not None:
            return ym_to_month_int(rev)
        orig = str(r.get("original_completion_date", "") or "").strip()
        if orig and orig != "nan" and ym_to_month_int(orig) is not None:
            return ym_to_month_int(orig)
        return np.nan

    df["target_comp_int"] = df.apply(get_target_comp, axis=1)
    df["sch_dev_clean"] = pd.to_numeric(df["schedule_deviation"], errors="coerce")

    # Fast iteration by project to compute forward windows and historical eligibility
    grouped_indices = df.groupby("project_id", sort=False).indices

    n = len(df)
    cost_overrun_6m = np.full(n, np.nan, dtype=np.float64)
    cost_overrun_12m = np.full(n, np.nan, dtype=np.float64)
    sch_overrun_6m = np.full(n, np.nan, dtype=np.float64)
    sch_overrun_12m = np.full(n, np.nan, dtype=np.float64)

    cost_esc_6m = np.full(n, np.nan, dtype=np.float64)
    cost_esc_12m = np.full(n, np.nan, dtype=np.float64)
    sch_drift_6m = np.full(n, np.nan, dtype=np.float64)
    sch_drift_12m = np.full(n, np.nan, dtype=np.float64)

    target_obs_6m = np.zeros(n, dtype=np.int32)
    target_obs_12m = np.zeros(n, dtype=np.int32)
    eligible_features = np.zeros(n, dtype=np.int32)

    report_m_arr = df["report_month_int"].values
    c_base_arr = df["C_base"].values
    target_comp_arr = df["target_comp_int"].values
    sch_dev_arr = df["sch_dev_clean"].values

    for pid, idxs in grouped_indices.items():
        m_len = len(idxs)
        if m_len == 0:
            continue

        p_months = report_m_arr[idxs]
        p_cbase = c_base_arr[idxs]
        p_tcomp = target_comp_arr[idxs]
        p_sdev = sch_dev_arr[idxs]
        last_m = p_months[-1]

        for i_pos in range(m_len):
            row_idx = idxs[i_pos]
            t_month = p_months[i_pos]
            t_cbase = p_cbase[i_pos]
            t_comp = p_tcomp[i_pos]
            t_dev = p_sdev[i_pos]

            # 1. Feature Eligibility: at least 3 prior historical observations + valid positive C_base
            if i_pos >= 3 and not np.isnan(t_cbase) and t_cbase > 0:
                eligible_features[row_idx] = 1

            # 2. Target Forward Windows
            # 6-Month Horizon (H = 6)
            if (last_m - t_month) >= 6:
                # Find all future rows in (t_month, t_month + 6]
                fwd_mask_6m = (p_months > t_month) & (p_months <= t_month + 6)
                if np.any(fwd_mask_6m):
                    target_obs_6m[row_idx] = 1
                    fwd_cbase = p_cbase[fwd_mask_6m]
                    fwd_tcomp = p_tcomp[fwd_mask_6m]
                    fwd_sdev = p_sdev[fwd_mask_6m]

                    # Cost escalation 6m
                    if not np.isnan(t_cbase) and t_cbase > 0 and not np.all(np.isnan(fwd_cbase)):
                        max_fwd_c = np.nanmax(fwd_cbase)
                        c_esc = (max_fwd_c - t_cbase) / t_cbase
                        cost_esc_6m[row_idx] = c_esc
                        cost_overrun_6m[row_idx] = 1.0 if c_esc >= cost_threshold_6m else 0.0

                    # Schedule deterioration 6m
                    max_drift = np.nan
                    if not np.isnan(t_comp) and not np.all(np.isnan(fwd_tcomp)):
                        max_drift = np.nanmax(fwd_tcomp) - t_comp

                    max_dev_inc = np.nan
                    if not np.isnan(t_dev) and not np.all(np.isnan(fwd_sdev)):
                        max_dev_inc = np.nanmax(fwd_sdev) - t_dev

                    drift_cand = [v for v in [max_drift, max_dev_inc] if not np.isnan(v)]
                    if drift_cand:
                        eff_drift = max(drift_cand)
                        sch_drift_6m[row_idx] = eff_drift
                        sch_overrun_6m[row_idx] = 1.0 if eff_drift >= delay_threshold_6m else 0.0

            # 12-Month Horizon (H = 12)
            if (last_m - t_month) >= 12:
                # Find all future rows in (t_month, t_month + 12]
                fwd_mask_12m = (p_months > t_month) & (p_months <= t_month + 12)
                if np.any(fwd_mask_12m):
                    target_obs_12m[row_idx] = 1
                    fwd_cbase_12 = p_cbase[fwd_mask_12m]
                    fwd_tcomp_12 = p_tcomp[fwd_mask_12m]
                    fwd_sdev_12 = p_sdev[fwd_mask_12m]

                    # Cost escalation 12m
                    if not np.isnan(t_cbase) and t_cbase > 0 and not np.all(np.isnan(fwd_cbase_12)):
                        max_fwd_c12 = np.nanmax(fwd_cbase_12)
                        c_esc12 = (max_fwd_c12 - t_cbase) / t_cbase
                        cost_esc_12m[row_idx] = c_esc12
                        cost_overrun_12m[row_idx] = 1.0 if c_esc12 >= cost_threshold_12m else 0.0

                    # Schedule deterioration 12m
                    max_drift12 = np.nan
                    if not np.isnan(t_comp) and not np.all(np.isnan(fwd_tcomp_12)):
                        max_drift12 = np.nanmax(fwd_tcomp_12) - t_comp

                    max_dev_inc12 = np.nan
                    if not np.isnan(t_dev) and not np.all(np.isnan(fwd_sdev_12)):
                        max_dev_inc12 = np.nanmax(fwd_sdev_12) - t_dev

                    drift_cand12 = [v for v in [max_drift12, max_dev_inc12] if not np.isnan(v)]
                    if drift_cand12:
                        eff_drift12 = max(drift_cand12)
                        sch_drift_12m[row_idx] = eff_drift12
                        sch_overrun_12m[row_idx] = 1.0 if eff_drift12 >= delay_threshold_12m else 0.0

    df["cost_overrun_6m"] = cost_overrun_6m
    df["cost_overrun_12m"] = cost_overrun_12m
    df["schedule_overrun_6m"] = sch_overrun_6m
    df["schedule_overrun_12m"] = sch_overrun_12m

    df["cost_escalation_pct_6m"] = cost_esc_6m
    df["cost_escalation_pct_12m"] = cost_esc_12m
    df["schedule_drift_months_6m"] = sch_drift_6m
    df["schedule_drift_months_12m"] = sch_drift_12m

    df["target_observable_6m"] = target_obs_6m
    df["target_observable_12m"] = target_obs_12m
    df["eligible_features"] = eligible_features

    # 3. Derived Composite Overrun Targets (Y_cost OR Y_sch)
    def compute_composite(cost_s, sch_s, obs_s):
        comp = np.full(len(cost_s), np.nan, dtype=np.float64)
        c_val = cost_s.values
        s_val = sch_s.values
        obs_val = obs_s.values

        for k in range(len(comp)):
            if obs_val[k] == 0:
                continue
            c = c_val[k]
            s = s_val[k]
            if c == 1.0 or s == 1.0:
                comp[k] = 1.0
            elif c == 0.0 and s == 0.0:
                comp[k] = 0.0
            elif c == 0.0 and np.isnan(s):
                comp[k] = 0.0 # Cost confirmed no overrun, schedule unobserved
            elif np.isnan(c) and s == 0.0:
                comp[k] = 0.0
        return comp

    df["overrun_composite_6m"] = compute_composite(df["cost_overrun_6m"], df["schedule_overrun_6m"], df["target_observable_6m"])
    df["overrun_composite_12m"] = compute_composite(df["cost_overrun_12m"], df["schedule_overrun_12m"], df["target_observable_12m"])

    # 4. Explanatory Distress Type Categorization
    def categorize_distress(cost_s, sch_s, obs_s):
        dist_type = np.full(len(cost_s), "UNOBSERVABLE", dtype=object)
        c_val = cost_s.values
        s_val = sch_s.values
        obs_val = obs_s.values

        for k in range(len(dist_type)):
            if obs_val[k] == 0:
                dist_type[k] = "UNOBSERVABLE"
            else:
                c = c_val[k]
                s = s_val[k]
                if c == 1.0 and s == 1.0:
                    dist_type[k] = "BOTH"
                elif c == 1.0 and (s == 0.0 or np.isnan(s)):
                    dist_type[k] = "COST"
                elif (c == 0.0 or np.isnan(c)) and s == 1.0:
                    dist_type[k] = "SCHEDULE"
                elif (c == 0.0 or np.isnan(c)) and (s == 0.0 or np.isnan(s)):
                    dist_type[k] = "NONE"
        return dist_type

    df["distress_type_6m"] = categorize_distress(df["cost_overrun_6m"], df["schedule_overrun_6m"], df["target_observable_6m"])
    df["distress_type_12m"] = categorize_distress(df["cost_overrun_12m"], df["schedule_overrun_12m"], df["target_observable_12m"])

    # Drop temporary helper columns
    drop_helpers = ["report_month_int", "C_base", "target_comp_int", "sch_dev_clean"]
    df.drop(columns=[c for c in drop_helpers if c in df.columns], inplace=True)

    # Select target dataset columns
    target_columns = [
        "project_id", "reporting_month",
        "cost_overrun_6m", "cost_overrun_12m",
        "schedule_overrun_6m", "schedule_overrun_12m",
        "overrun_composite_6m", "overrun_composite_12m",
        "distress_type_6m", "distress_type_12m",
        "cost_escalation_pct_6m", "cost_escalation_pct_12m",
        "schedule_drift_months_6m", "schedule_drift_months_12m",
        "eligible_features", "target_observable_6m", "target_observable_12m"
    ]

    return df[target_columns]

def run_targets_pipeline(
    input_path: str = "DATA/project_timelines.parquet",
    output_path: str = "DATA/project_targets.parquet"
) -> pd.DataFrame:
    """Run target generator pipeline from timeline Parquet input."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file '{input_path}' not found.")

    print(f"Loading input data from {input_path}...")
    if input_path.endswith(".parquet"):
        df_in = pd.read_parquet(input_path, engine="pyarrow")
    else:
        df_in = pd.read_csv(input_path, dtype=str)

    print(f"Generating targets for {len(df_in):,} project-month records...")
    df_targets = compute_targets(df_in)

    print(f"Saving targets dataset to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_targets.to_parquet(output_path, index=False, engine="pyarrow")
    print(f"Target generator complete: {len(df_targets):,} records saved to {output_path}.")
    return df_targets

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate leakage-safe VIGIL project targets.")
    parser.add_argument("--input", default="DATA/project_timelines.parquet", help="Input timeline path")
    parser.add_argument("--output", default="DATA/project_targets.parquet", help="Output targets path")
    args = parser.parse_args()

    run_targets_pipeline(args.input, args.output)
