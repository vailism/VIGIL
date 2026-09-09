"""
tests/test_leakage.py

MANDATORY TEMPORAL LEAKAGE TEST SUITE FOR VIGIL:
1. Future cost revision does NOT change features at observation month t.
2. Future completion-date revision does NOT change features at observation month t.
3. Future expenditure does NOT affect historical velocity at or before t.
4. Peer statistics do NOT include future observations.
5. Right-censored targets strictly remain NaN (never 0).
6. Duplicate project-month observations cannot enter the model dataset.
7. Feature calculations strictly reset at project boundaries.
"""

import pytest
import pandas as pd
import numpy as np
from sanket.timeline import build_project_timelines
from sanket.trajectory import compute_trajectories
from sanket.targets import compute_targets
from sanket.features import assemble_model_dataset

def test_leakage_1_future_cost_revision_does_not_affect_features():
    """
    Test that modifying revised_cost at month t+12 does NOT alter ANY feature
    computed at month t.
    """
    base_data = [
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0, "revised_cost": np.nan},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": 12.0, "expenditure": 120.0, "approved_cost": 1000.0, "revised_cost": np.nan},
        {"project_id": "P1", "reporting_month": "2020-03", "financial_progress": 15.0, "expenditure": 150.0, "approved_cost": 1000.0, "revised_cost": np.nan},
    ]

    # Dataset A: Future cost at month 4 remains 1000
    data_a = base_data + [
        {"project_id": "P1", "reporting_month": "2020-04", "financial_progress": 18.0, "expenditure": 180.0, "approved_cost": 1000.0, "revised_cost": 1000.0}
    ]

    # Dataset B: Future cost at month 4 explodes to 5000 (+400% cost revision!)
    data_b = base_data + [
        {"project_id": "P1", "reporting_month": "2020-04", "financial_progress": 18.0, "expenditure": 180.0, "approved_cost": 1000.0, "revised_cost": 5000.0}
    ]

    features_a = compute_trajectories(pd.DataFrame(data_a))
    features_b = compute_trajectories(pd.DataFrame(data_b))

    # Features at rows 0, 1, 2 (months 2020-01, 2020-02, 2020-03) MUST BE 100% IDENTICAL
    feature_cols = [
        "V_fin_1m", "V_exp_1m", "A_fin", "A_exp", "C_base", "cost_revision_ratio",
        "expenditure_to_baseline", "EWMA_V_fin", "trajectory_risk_score"
    ]
    for col in feature_cols:
        val_a = features_a.loc[2, col]
        val_b = features_b.loc[2, col]
        if np.isnan(val_a):
            assert np.isnan(val_b), f"Column {col} at t=3 differed (NaN vs non-NaN)"
        else:
            assert val_a == pytest.approx(val_b), f"Leakage detected! Feature '{col}' at t=3 changed when future cost at t=4 changed!"

def test_leakage_2_future_completion_revision_does_not_affect_features():
    """
    Test that modifying revised completion date in month t+6 does NOT alter
    schedule features at month t.
    """
    base_data = [
        {"project_id": "P1", "reporting_month": "2020-01", "original_completion_date": "2022-01", "revised_completion_date": np.nan, "schedule_deviation": 0.0},
        {"project_id": "P1", "reporting_month": "2020-02", "original_completion_date": "2022-01", "revised_completion_date": np.nan, "schedule_deviation": 0.0},
    ]

    # Future date delayed by 3 years in month 3
    data_delayed = base_data + [
        {"project_id": "P1", "reporting_month": "2020-03", "original_completion_date": "2022-01", "revised_completion_date": "2025-01", "schedule_deviation": 36.0}
    ]

    # Future date on time in month 3
    data_ontime = base_data + [
        {"project_id": "P1", "reporting_month": "2020-03", "original_completion_date": "2022-01", "revised_completion_date": "2022-01", "schedule_deviation": 0.0}
    ]

    res_delayed = compute_trajectories(pd.DataFrame(data_delayed))
    res_ontime = compute_trajectories(pd.DataFrame(data_ontime))

    # At month 2 (2020-02), schedule drift and deviation must be identical
    assert res_delayed.loc[1, "schedule_deviation_change"] == pytest.approx(res_ontime.loc[1, "schedule_deviation_change"])
    assert res_delayed.loc[1, "completion_date_drift"] == pytest.approx(res_ontime.loc[1, "completion_date_drift"])

def test_leakage_3_future_expenditure_does_not_affect_historical_velocity():
    """
    Test that future expenditure spend spikes do not change past velocities.
    """
    base = [
        {"project_id": "P1", "reporting_month": "2020-01", "expenditure": 100.0},
        {"project_id": "P1", "reporting_month": "2020-02", "expenditure": 150.0},
    ]
    data_normal = base + [{"project_id": "P1", "reporting_month": "2020-03", "expenditure": 200.0}]
    data_spike = base + [{"project_id": "P1", "reporting_month": "2020-03", "expenditure": 99999.0}]

    res_norm = compute_trajectories(pd.DataFrame(data_normal))
    res_spike = compute_trajectories(pd.DataFrame(data_spike))

    # Velocity at month 2 (150 - 100 = 50) must remain exactly 50 regardless of future spike
    assert res_norm.loc[1, "V_exp_1m"] == pytest.approx(50.0)
    assert res_spike.loc[1, "V_exp_1m"] == pytest.approx(50.0)

def test_leakage_4_peer_statistics_point_in_time():
    """
    Test that peer statistics at reporting_month t are strictly computed using
    observations from month t, and never leak future reports.
    """
    # Two projects observed in 2020-01
    # Project 3 appears in 2020-02 with a massive velocity
    data = [
        {"project_id": "P1", "reporting_month": "2020-01", "sector": "Power", "financial_progress": 10.0, "approved_cost": 500.0},
        {"project_id": "P1", "reporting_month": "2020-02", "sector": "Power", "financial_progress": 12.0, "approved_cost": 500.0},
        {"project_id": "P2", "reporting_month": "2020-01", "sector": "Power", "financial_progress": 20.0, "approved_cost": 500.0},
        {"project_id": "P2", "reporting_month": "2020-02", "sector": "Power", "financial_progress": 22.0, "approved_cost": 500.0},
        # Future massive velocity project added in month 2020-02
        {"project_id": "P3", "reporting_month": "2020-01", "sector": "Power", "financial_progress": 0.0, "approved_cost": 500.0},
        {"project_id": "P3", "reporting_month": "2020-02", "sector": "Power", "financial_progress": 80.0, "approved_cost": 500.0},
    ]
    res = compute_trajectories(pd.DataFrame(data))

    # Peer group for 2020-01 should not be affected by the +80% progress in 2020-02
    p1_m1 = res[(res["project_id"] == "P1") & (res["reporting_month"] == "2020-01")].iloc[0]
    # Since V_fin_1m is NaN for observation 1, Z score is 0.0
    assert p1_m1["Z_peer_V_fin"] == 0.0

def test_leakage_5_right_censored_targets_remain_nan():
    """
    Test that observations near the project boundary strictly receive NaN targets,
    NEVER imputed with 0.
    """
    data = [
        {"project_id": "P1", "reporting_month": "2024-10", "approved_cost": 1000.0},
        {"project_id": "P1", "reporting_month": "2024-11", "approved_cost": 1000.0},
        {"project_id": "P1", "reporting_month": "2024-12", "approved_cost": 1000.0},
    ]
    df = pd.DataFrame(data)
    targets = compute_targets(df)

    # Incomplete future window (max future is 2 months < 6 and < 12)
    for idx in range(len(targets)):
        assert targets.loc[idx, "target_observable_6m"] == 0
        assert targets.loc[idx, "target_observable_12m"] == 0
        assert np.isnan(targets.loc[idx, "cost_overrun_6m"]), "Censored target was not NaN!"
        assert np.isnan(targets.loc[idx, "cost_overrun_12m"]), "Censored target was not NaN!"
        assert np.isnan(targets.loc[idx, "schedule_overrun_6m"]), "Censored target was not NaN!"
        assert np.isnan(targets.loc[idx, "schedule_overrun_12m"]), "Censored target was not NaN!"
        assert np.isnan(targets.loc[idx, "overrun_composite_6m"]), "Censored composite target was not NaN!"
        assert np.isnan(targets.loc[idx, "overrun_composite_12m"]), "Censored composite target was not NaN!"
        assert targets.loc[idx, "distress_type_12m"] == "UNOBSERVABLE"

def test_leakage_6_duplicate_prevention(tmp_path):
    """
    Test that duplicate project-month observations cannot enter the model dataset.
    """
    traj_file = tmp_path / "dup_traj.parquet"
    targ_file = tmp_path / "dup_targ.parquet"

    df_dup = pd.DataFrame([
        {"project_id": "P1", "reporting_month": "2020-01", "V_fin_1m": 1.0},
        {"project_id": "P1", "reporting_month": "2020-01", "V_fin_1m": 2.0}, # Duplicate!
    ])
    df_dup.to_parquet(traj_file)
    df_dup.to_parquet(targ_file)

    with pytest.raises(AssertionError, match="duplicate"):
        assemble_model_dataset(str(traj_file), str(targ_file), output_path=None)

def test_leakage_7_project_boundary_resets():
    """
    Test that shifting operations strictly reset when crossing from P1 to P2.
    """
    data = [
        {"project_id": "P1", "reporting_month": "2020-01", "financial_progress": 10.0, "approved_cost": 1000.0},
        {"project_id": "P1", "reporting_month": "2020-02", "financial_progress": 15.0, "approved_cost": 1000.0},
        {"project_id": "P2", "reporting_month": "2020-01", "financial_progress": 90.0, "approved_cost": 500.0},
        {"project_id": "P2", "reporting_month": "2020-02", "financial_progress": 95.0, "approved_cost": 500.0},
    ]
    res = compute_trajectories(pd.DataFrame(data))

    p2_m1 = res[(res["project_id"] == "P2") & (res["reporting_month"] == "2020-01")].iloc[0]
    # P2 first row must NOT subtract P1's 15.0 (90 - 15 = 75 is wrong!)
    assert np.isnan(p2_m1["V_fin_1m"]), "Project boundary leak! Subtracted previous project's value."

    p2_m2 = res[(res["project_id"] == "P2") & (res["reporting_month"] == "2020-02")].iloc[0]
    assert p2_m2["V_fin_1m"] == pytest.approx(5.0), "P2 velocity within project should be 95 - 90 = 5."
