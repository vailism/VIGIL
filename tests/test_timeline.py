"""
tests/test_timeline.py

Unit tests for sanket.timeline:
- Duplicate project/month detection
- Strict chronological ordering
- Observation gap calculations
- Preservation of missing values (zero forward-fill)
- Project boundary separation
"""

import pytest
import pandas as pd
import numpy as np
from sanket.timeline import build_project_timelines, ym_to_month_index

def test_ym_to_month_index():
    s = pd.Series(["2020-01", "2020-12", "2021-01"])
    idx = ym_to_month_index(s)
    assert idx.tolist() == [2020 * 12 + 1, 2020 * 12 + 12, 2021 * 12 + 1]
    assert idx.iloc[2] - idx.iloc[1] == 1
    assert idx.iloc[1] - idx.iloc[0] == 11

def test_timeline_builder_basic(tmp_path):
    csv_file = tmp_path / "test_monthly.csv"
    data = [
        # Project 1: strictly sequential
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": "10.0", "expenditure": "100"},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": "12.0", "expenditure": "120"},
        {"project_id": "P1", "reporting_month": "2020-04", "financial_progress": np.nan, "expenditure": "140"}, # 2-month gap, missing progress
        # Project 2: interleaved in raw data to test sorting
        {"project_id": "P2", "reporting_month": "2019-06", "financial_progress": "50.0", "expenditure": "500"},
        {"project_id": "P2", "reporting_month": "2019-05", "financial_progress": "45.0", "expenditure": "450"},
    ]
    pd.DataFrame(data).to_csv(csv_file, index=False)

    df_out = build_project_timelines(str(csv_file), output_path=None)

    # Check length
    assert len(df_out) == 5

    # Check P1 rows
    p1 = df_out[df_out["project_id"] == "P1"].reset_index(drop=True)
    assert p1["reporting_month"].tolist() == ["2020-01", "2020-02", "2020-04"]
    assert p1["observation_number"].tolist() == [1, 2, 3]
    assert p1["project_age_months"].tolist() == [0, 1, 3]
    assert np.isnan(p1["months_since_previous_observation"].iloc[0])
    assert p1["months_since_previous_observation"].iloc[1] == 1.0
    assert p1["months_since_previous_observation"].iloc[2] == 2.0
    assert p1["reporting_gap_flag"].tolist() == [0, 0, 1]

    # Verify zero forward fill: 3rd row financial_progress must remain NaN
    assert np.isnan(p1["financial_progress"].iloc[2])

    # Check P2 rows: must be sorted 2019-05 then 2019-06
    p2 = df_out[df_out["project_id"] == "P2"].reset_index(drop=True)
    assert p2["reporting_month"].tolist() == ["2019-05", "2019-06"]
    assert p2["observation_number"].tolist() == [1, 2]
    assert p2["project_age_months"].tolist() == [0, 1]
    assert p2["months_since_previous_observation"].iloc[1] == 1.0
    assert p2["reporting_gap_flag"].tolist() == [0, 0]

def test_timeline_duplicate_rejection(tmp_path):
    csv_file = tmp_path / "test_dup.csv"
    data = [
        {"project_id": "P1", "reporting_month": "2020-01"},
        {"project_id": "P1", "reporting_month": "2020-01"}, # Duplicate!
    ]
    pd.DataFrame(data).to_csv(csv_file, index=False)
    with pytest.raises(ValueError, match="duplicate"):
        build_project_timelines(str(csv_file), output_path=None)

def test_timeline_project_boundaries(tmp_path):
    csv_file = tmp_path / "test_bounds.csv"
    data = [
        {"project_id": "P1", "reporting_month": "2020-05"},
        {"project_id": "P2", "reporting_month": "2020-06"},
    ]
    pd.DataFrame(data).to_csv(csv_file, index=False)
    df_out = build_project_timelines(str(csv_file), output_path=None)

    # For P2, months_since_previous_observation must be NaN (boundary reset)
    p2 = df_out[df_out["project_id"] == "P2"].iloc[0]
    assert np.isnan(p2["months_since_previous_observation"])
    assert p2["observation_number"] == 1
    assert p2["project_age_months"] == 0
