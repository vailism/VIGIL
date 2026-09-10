#!/usr/bin/env python3
"""
Precomputes the Sanctioned Portfolio into compact artifacts to avoid
dynamic memory OOM crashes in the production container (Render 512MB limit).
Includes validation hashes and artifact metadata.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
import pandas as pd
import numpy as np

def get_file_hash(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def precompute_and_save():
    from sanket.inference import load_inference_engine, get_risk_tier
    from sanket.portfolio import is_genuine_project

    print("Precomputing static portfolio with canonical chronological inference...")
    dataset_path = "DATA/model_dataset.parquet"
    dataset_hash = get_file_hash(dataset_path)

    engine = load_inference_engine()
    features = engine["features"]
    cat_features = engine["categorical_features"]

    cols = list(set(features + [
        "project_id", "project_name", "sector", "sector_clean",
        "ministry", "state", "reporting_month", "approved_cost",
        "revised_cost", "C_base", "expenditure", "financial_progress",
        "observation_number", "schedule_deviation_months", "trajectory_risk_score",
        "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin", "Z_peer_V_fin"
    ]))

    import pyarrow.parquet as pq
    schema = pq.read_schema(dataset_path)
    actual_cols = [c for c in cols if c in schema.names]

    df_full = pd.read_parquet(dataset_path, columns=actual_cols)

    df_sorted = df_full.sort_values("reporting_month")

    # CANONICAL EXTRACTION: Use tail(1) to avoid forward-filling NaNs (unlike .last())
    latest_all = df_sorted.groupby("project_id").tail(1).reset_index(drop=True)

    # Calculate start_month
    first_all = df_sorted.groupby("project_id").first().reset_index()
    start_months = dict(zip(first_all["project_id"], first_all["reporting_month"]))
    latest_all["start_month"] = latest_all["project_id"].map(start_months)

    genuine_flags = [
        is_genuine_project(pid, name)
        for pid, name in zip(latest_all["project_id"], latest_all["project_name"])
    ]
    latest_all["is_genuine"] = genuine_flags

    genuine_df = latest_all[latest_all["is_genuine"]].copy()

    active_mask = genuine_df["reporting_month"] >= "2024-01"
    active_projects_df = genuine_df[active_mask].copy().reset_index(drop=True)
    historical_projects_df = genuine_df[~active_mask].copy().reset_index(drop=True)

    # Score active portfolio using frozen inference engine
    X_active = pd.DataFrame(index=active_projects_df.index)
    for f in features:
        if f in active_projects_df.columns:
            X_active[f] = active_projects_df[f]
        else:
            X_active[f] = np.nan

    for cat in cat_features:
        if cat in X_active.columns:
            X_active[cat] = X_active[cat].astype("category")

    raw_probs = engine["model"].predict_proba(X_active)[:, 1]
    cal_probs = engine["calibrator"].predict(raw_probs)
    risk_tiers = [get_risk_tier(p) for p in cal_probs]

    active_projects_df["latest_risk"] = np.round(cal_probs, 4)
    active_projects_df["risk_tier"] = risk_tiers
    active_projects_df["latest_risk_tier"] = risk_tiers

    cbase_vals = pd.to_numeric(active_projects_df["C_base"], errors="coerce").fillna(0).values
    active_projects_df["baseline_cost"] = np.round(cbase_vals, 2)
    active_projects_df["priority_score"] = np.round(
        active_projects_df["latest_risk"] * active_projects_df["baseline_cost"], 2
    )
    active_projects_df["risk_weighted_exposure"] = active_projects_df["priority_score"]

    active_projects_df["sector_display"] = (
        active_projects_df["sector_clean"]
        .fillna(active_projects_df["sector"])
        .fillna("Unknown")
        .astype(str)
    )

    risk_weighted_exposure = active_projects_df["risk_weighted_exposure"].sum()
    tier_counts = active_projects_df["risk_tier"].value_counts().to_dict()

    # Additional aggregations
    active_baseline_exposure = active_projects_df["baseline_cost"].sum()
    exposure_in_escalate = active_projects_df[active_projects_df["risk_tier"] == "ESCALATE"]["baseline_cost"].sum()

    # Sector breakdown
    sector_breakdown = []
    for s_name, s_df in active_projects_df.groupby("sector_display"):
        sector_breakdown.append({
            "sector": str(s_name),
            "total_projects": int(len(s_df)),
            "escalate_count": int((s_df["risk_tier"] == "ESCALATE").sum()),
            "review_count": int((s_df["risk_tier"] == "REVIEW").sum()),
            "watch_count": int((s_df["risk_tier"] == "WATCH").sum()),
            "total_exposure": float(s_df["baseline_cost"].sum())
        })
    sector_breakdown.sort(key=lambda x: x["total_exposure"], reverse=True)

    print("Saving DataFrames...")
    active_projects_df.to_parquet("DATA/portfolio_active.parquet", index=False)
    historical_projects_df.to_parquet("DATA/portfolio_historical.parquet", index=False)
    genuine_df.to_parquet("DATA/portfolio_genuine.parquet", index=False)

    metadata = {
        "_metadata": {
            "schema_version": "1.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_dataset_path": "DATA/model_dataset.parquet",
            "source_dataset_hash": dataset_hash,
            "active_window_start": "2024-01"
        },
        "metrics": {
            "active_project_count": int(len(active_projects_df)),
            "historical_project_count": int(len(historical_projects_df)),
            "genuine_project_count": int(len(genuine_df)),
            "total_archive_entities": int(df_full["project_id"].nunique()),
            "archive_start": str(df_full["reporting_month"].min()),
            "archive_end": str(df_full["reporting_month"].max()),
            "latest_data_month": str(df_full["reporting_month"].max()),
            "active_baseline_exposure": float(active_baseline_exposure),
            "exposure_in_escalate": float(exposure_in_escalate),
            "risk_weighted_exposure": float(risk_weighted_exposure),
            "watch_count": int(tier_counts.get("WATCH", 0)),
            "review_count": int(tier_counts.get("REVIEW", 0)),
            "escalate_count": int(tier_counts.get("ESCALATE", 0)),
            "normal_count": int(tier_counts.get("NORMAL", 0)),
            "historical_median_warning_lead": 6.5,
            "sector_breakdown": sector_breakdown
        }
    }

    with open("DATA/portfolio_metrics.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("Static artifacts successfully precomputed and saved.")

if __name__ == "__main__":
    precompute_and_save()
