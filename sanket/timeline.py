#!/usr/bin/env python3
"""
sanket/timeline.py

Phase 1: Production-quality timeline builder for VIGIL.
Constructs strictly chronological, longitudinal project timelines from canonical
project-month records.

Key Invariants:
1. Strict ordering: (project_id, reporting_month).
2. Zero forward-fill: Preserves real reporting gaps; never imputes missing financial values.
3. Pure point-in-time temporal metadata:
   - project_age_months: months elapsed since project's first observed reporting month
   - observation_number: 1-indexed cumulative observation counter
   - months_since_previous_observation: calendar month delta from t_{prev}
   - reporting_gap_flag: 1 if delta > 1 month, 0 if consecutive, 0 for first observation
4. Full provenance retention.
"""

import os
import sys
import argparse
from typing import Optional
import pandas as pd
import numpy as np

def ym_to_month_index(ym_series: pd.Series) -> pd.Series:
    """Convert YYYY-MM string series to integer month index: year * 12 + month."""
    parts = ym_series.astype(str).str.split("-", expand=True)
    years = pd.to_numeric(parts[0], errors="coerce")
    months = pd.to_numeric(parts[1], errors="coerce")
    return years * 12 + months

def build_project_timelines(
    input_path: str = "DATA/project_monthly.csv",
    output_path: Optional[str] = "DATA/project_timelines.parquet"
) -> pd.DataFrame:
    """
    Load canonical project monthly data, sort strictly, validate ordering,
    and attach point-in-time temporal tracking metadata.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file '{input_path}' does not exist.")

    print(f"Loading canonical dataset from {input_path}...")
    df = pd.read_csv(input_path, dtype=str)
    initial_count = len(df)
    print(f"Loaded {initial_count:,} raw canonical records.")

    # 1. Assert unique canonical grain
    is_dup = df.duplicated(subset=["project_id", "reporting_month"]).any()
    if is_dup:
        dup_count = df.duplicated(subset=["project_id", "reporting_month"]).sum()
        raise ValueError(
            f"Integrity violation: Found {dup_count} duplicate (project_id, reporting_month) pairs!"
        )

    # 2. Strict sorting by project_id and reporting_month
    print("Sorting strictly by (project_id, reporting_month)...")
    df["month_idx"] = ym_to_month_index(df["reporting_month"])
    if df["month_idx"].isna().any():
        raise ValueError("Encountered invalid reporting_month values that could not be parsed.")

    df = df.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

    # 3. Vectorized temporal metadata computation
    print("Computing point-in-time temporal timeline metadata...")
    grouped = df.groupby("project_id", sort=False)

    # observation_number: 1, 2, 3, ...
    df["observation_number"] = grouped.cumcount() + 1

    # previous month_idx
    df["prev_month_idx"] = grouped["month_idx"].shift(1)

    # months_since_previous_observation: delta in calendar months
    df["months_since_previous_observation"] = df["month_idx"] - df["prev_month_idx"]

    # Validate strict chronological ordering (delta must be > 0 for all subsequent rows)
    subsequent_rows = df[df["observation_number"] > 1]
    invalid_order = subsequent_rows[subsequent_rows["months_since_previous_observation"] <= 0]
    if len(invalid_order) > 0:
        bad_sample = invalid_order[["project_id", "reporting_month"]].head(5).to_dict(orient="records")
        raise ValueError(f"Chronological ordering violation found in {len(invalid_order)} rows: {bad_sample}")

    # reporting_gap_flag: 1 if months_since_previous_observation > 1, else 0
    df["reporting_gap_flag"] = np.where(
        df["months_since_previous_observation"].fillna(1) > 1, 1, 0
    ).astype(np.int32)

    # first_seen_month_idx per project
    first_month_idx = grouped["month_idx"].transform("first")
    df["project_age_months"] = (df["month_idx"] - first_month_idx).astype(np.int32)

    # Drop temporary helper column
    df.drop(columns=["month_idx", "prev_month_idx"], inplace=True)

    # Cast numeric and metadata types appropriately
    df["observation_number"] = df["observation_number"].astype(np.int32)
    df["months_since_previous_observation"] = df["months_since_previous_observation"].astype(np.float64)

    # Ensure financial & physical progress columns are numeric floats where non-empty, WITHOUT forward filling
    numeric_cols = [
        "physical_progress", "financial_progress", "expenditure",
        "approved_cost", "revised_cost", "schedule_deviation"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        print(f"Saving timelines to {output_path}...")
        df.to_parquet(output_path, index=False, engine="pyarrow")
        print(f"Successfully saved {len(df):,} records to {output_path}.")

    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build longitudinal project timelines.")
    parser.add_argument("--input", default="DATA/project_monthly.csv", help="Input canonical CSV path")
    parser.add_argument("--output", default="DATA/project_timelines.parquet", help="Output Parquet path")
    args = parser.parse_args()

    build_project_timelines(args.input, args.output)
