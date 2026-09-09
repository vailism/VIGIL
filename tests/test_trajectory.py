import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_trajectory.py

Unit tests for sanket.trajectory:
- Mathematical accuracy of velocity (1m, 3m) and acceleration
- Expenditure burn rate and baseline ratio
- Schedule drift and deviation change
- Recursive EWMA computation
- Clean boundary separation between projects
- Trajectory risk score bounds [0, 100] and component separation
"""

import pytest
import pandas as pd
import numpy as np
from sanket.trajectory import compute_trajectories

def test_trajectory_financial_and_expenditure():
    data = [
        # Project 1: smooth progress
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0, "revised_cost": np.nan, "original_completion_date": "2022-01", "revised_completion_date": np.nan, "schedule_deviation": 0.0},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": 12.0, "expenditure": 120.0, "approved_cost": 1000.0, "revised_cost": np.nan, "original_completion_date": "2022-01", "revised_completion_date": np.nan, "schedule_deviation": 0.0},
        {"project_id": "P1", "reporting_month": "2020-03", "financial_progress": 15.0, "expenditure": 150.0, "approved_cost": 1000.0, "revised_cost": np.nan, "original_completion_date": "2022-01", "revised_completion_date": np.nan, "schedule_deviation": 0.0},
        {"project_id": "P1", "reporting_month": "2020-04", "financial_progress": 17.0, "expenditure": 170.0, "approved_cost": 1000.0, "revised_cost": 1200.0, "original_completion_date": "2022-01", "revised_completion_date": "2022-04", "schedule_deviation": 3.0}, # Drift +3m, revised cost +20%
    ]
    df = pd.DataFrame(data)
    res = compute_trajectories(df)

    p1 = res[res["project_id"] == "P1"].reset_index(drop=True)

    # 1. Financial Velocity 1m
    assert np.isnan(p1["V_fin_1m"].iloc[0])
    assert p1["V_fin_1m"].iloc[1] == pytest.approx(2.0)
    assert p1["V_fin_1m"].iloc[2] == pytest.approx(3.0)
    assert p1["V_fin_1m"].iloc[3] == pytest.approx(2.0)

    # 2. Financial Velocity 3m
    assert np.isnan(p1["V_fin_3m"].iloc[0])
    assert np.isnan(p1["V_fin_3m"].iloc[1])
    assert np.isnan(p1["V_fin_3m"].iloc[2])
    assert p1["V_fin_3m"].iloc[3] == pytest.approx(7.0) # 17.0 - 10.0

    # 3. Acceleration
    assert np.isnan(p1["A_fin"].iloc[0])
    assert np.isnan(p1["A_fin"].iloc[1])
    assert p1["A_fin"].iloc[2] == pytest.approx(1.0) # 3.0 - 2.0
    assert p1["A_fin"].iloc[3] == pytest.approx(-1.0) # 2.0 - 3.0 (deceleration!)

    # 4. Expenditure Velocity & Baseline
    assert p1["V_exp_1m"].iloc[1] == pytest.approx(20.0)
    assert p1["V_exp_3m"].iloc[3] == pytest.approx(70.0)
    assert p1["C_base"].iloc[0] == pytest.approx(1000.0)
    assert p1["C_base"].iloc[3] == pytest.approx(1200.0)
    assert p1["cost_revision_ratio"].iloc[3] == pytest.approx(0.20) # (1200-1000)/1000

    # 5. Schedule Drift & Deviation change
    assert p1["completion_date_drift"].iloc[3] == pytest.approx(3.0) # 2022-04 vs 2022-01
    assert p1["schedule_deviation_change"].iloc[3] == pytest.approx(3.0)

def test_ewma_calculation():
    data = [
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 0.0},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": 2.0},
        {"project_id": "P1", "reporting_month": "2020-03", "financial_progress": 4.0},
        {"project_id": "P1", "reporting_month": "2020-04", "financial_progress": 6.0},
    ]
    df = pd.DataFrame(data)
    res = compute_trajectories(df, config={"ewma_alpha": 0.30})
    p1 = res[res["project_id"] == "P1"].reset_index(drop=True)

    # V_fin_1m are [NaN, 2.0, 2.0, 2.0]
    # EWMA with constant input 2.0 must converge to 2.0
    assert np.isnan(p1["EWMA_V_fin"].iloc[0])
    assert p1["EWMA_V_fin"].iloc[1] == pytest.approx(2.0)
    assert p1["EWMA_V_fin"].iloc[2] == pytest.approx(2.0)
    assert p1["EWMA_V_fin"].iloc[3] == pytest.approx(2.0)

def test_project_boundary_isolation():
    data = [
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 10.0, "expenditure": 100.0},
        {"project_id": "P2", "reporting_month": "2020-02", "financial_progress": 50.0, "expenditure": 500.0},
    ]
    df = pd.DataFrame(data)
    res = compute_trajectories(df)
    p2 = res[res["project_id"] == "P2"].iloc[0]

    # For P2 first row, velocity must be NaN (must not subtract P1!)
    assert np.isnan(p2["V_fin_1m"])
    assert np.isnan(p2["V_exp_1m"])

def test_risk_score_bounds():
    data = [
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0}, # Zero velocity (stalled)
        {"project_id": "P1", "reporting_month": "2020-03", "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0},
    ]
    df = pd.DataFrame(data)
    res = compute_trajectories(df)
    scores = res["trajectory_risk_score"].dropna()
    assert len(scores) > 0
    assert (scores >= 0.0).all()
    assert (scores <= 100.0).all()
    # Row 2 & 3 have stalled velocity, score must be elevated (> 50)
    assert res["score_stalled_velocity"].iloc[1] == 1.0
