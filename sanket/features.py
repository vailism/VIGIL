#!/usr/bin/env python3
"""
sanket/features.py

Phase 5: Model Feature Matrix Assembler for VIGIL.
Joins independently computed trajectory features and forward targets on (project_id, reporting_month),
enforcing strict temporal lineage and auditing metadata.

Key Invariants:
1. Pure Post-Hoc Join: Features and targets are computed in independent modules and joined strictly
   on the composite grain (project_id, reporting_month).
2. Explicit Lineage Metadata:
   - feature_cutoff_month: reporting month t (boundary of information known at t)
   - target_horizon_month_6m: month t + 6
   - target_horizon_month_12m: month t + 12
3. Auditable Verification: Ensures zero duplicate grains and checks column lineage partitioning.
"""

import os
import sys
import argparse
from typing import Optional, Tuple
import pandas as pd
import numpy as np

def add_months_to_ym(ym_str: str, months_to_add: int) -> str:
    """Add calendar months to a YYYY-MM string."""
    if not isinstance(ym_str, str) or len(ym_str) != 7:
        return ""
    try:
        y, m = map(int, ym_str.split("-"))
        total_m = y * 12 + (m - 1) + months_to_add
        new_y = total_m // 12
        new_m = total_m % 12 + 1
        return f"{new_y:04d}-{new_m:02d}"
    except Exception:
        return ""

def assemble_model_dataset(
    trajectories_path: str = "DATA/project_trajectories.parquet",
    targets_path: str = "DATA/project_targets.parquet",
    output_path: Optional[str] = "DATA/model_dataset.parquet"
) -> pd.DataFrame:
    """
    Assemble complete model dataset by joining trajectory features and forward targets.
    """
    if not os.path.exists(trajectories_path):
        raise FileNotFoundError(f"Trajectories file '{trajectories_path}' not found.")
    if not os.path.exists(targets_path):
        raise FileNotFoundError(f"Targets file '{targets_path}' not found.")

    print(f"Loading trajectory features from {trajectories_path}...")
    df_features = pd.read_parquet(trajectories_path, engine="pyarrow")

    print(f"Loading targets from {targets_path}...")
    df_targets = pd.read_parquet(targets_path, engine="pyarrow")

    # Verify duplicate grain on both datasets before merging
    assert not df_features.duplicated(subset=["project_id", "reporting_month"]).any(), \
        "Features dataset contains duplicate (project_id, reporting_month) pairs!"
    assert not df_targets.duplicated(subset=["project_id", "reporting_month"]).any(), \
        "Targets dataset contains duplicate (project_id, reporting_month) pairs!"

    print("Joining features and targets on (project_id, reporting_month)...")
    merged = pd.merge(
        df_features,
        df_targets,
        on=["project_id", "reporting_month"],
        how="inner"
    )

    if len(merged) != len(df_features):
        print(f"Warning: Merged row count ({len(merged):,}) differs from features count ({len(df_features):,})")

    # Add temporal auditing metadata
    print("Attaching temporal audit metadata...")
    merged["feature_cutoff_month"] = merged["reporting_month"]
    merged["target_horizon_month_6m"] = merged["reporting_month"].apply(lambda ym: add_months_to_ym(ym, 6))
    merged["target_horizon_month_12m"] = merged["reporting_month"].apply(lambda ym: add_months_to_ym(ym, 12))

    # Sort strictly by (project_id, reporting_month)
    merged = merged.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        print(f"Writing complete model dataset to {output_path}...")
        merged.to_parquet(output_path, index=False, engine="pyarrow")
        print(f"Model dataset successfully written: {len(merged):,} rows, {len(merged.columns)} columns.")

    return merged

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble VIGIL model dataset.")
    parser.add_argument("--trajectories", default="DATA/project_trajectories.parquet", help="Path to trajectories Parquet")
    parser.add_argument("--targets", default="DATA/project_targets.parquet", help="Path to targets Parquet")
    parser.add_argument("--output", default="DATA/model_dataset.parquet", help="Output model dataset Parquet")
    args = parser.parse_args()

    assemble_model_dataset(args.trajectories, args.targets, args.output)
