import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_replay.py

Comprehensive tests for sanket.replay:
1. Replay never uses future rows.
2. Prediction at t is unchanged if future rows are removed (temporal invariance).
3. First alert occurs strictly before event.
4. Repeated alerts collapse correctly into single first-alert event lead time.
5. Risk tiers correspond exactly to validated operational thresholds.
6. Explanation values correspond to actual feature values.
7. Unknown project_id fails cleanly with ValueError.
8. Replay works cleanly on projects with sparse observations.
"""

import pytest
import numpy as np
import pandas as pd

from sanket.replay import (
    get_project_replay,
    replay_project,
    replay_project_from_dataframe
)
from sanket.inference import load_inference_engine

@pytest.fixture(scope="module")
def engine():
    return load_inference_engine()

def create_synthetic_project(n_obs=10):
    """Create a synthetic longitudinal project history."""
    dates = [f"2020-{m:02d}" for m in range(1, n_obs + 1)]
    records = []
    for i, dt in enumerate(dates):
        records.append({
            "project_id": "SYNTH_001",
            "project_name": "Synthetic Fast Transit Project",
            "sector_clean": "Railways",
            "scale_bucket": "MAJOR",
            "reporting_month": dt,
            "observation_number": i + 1,
            "project_age_months": 12 + i,
            "months_since_previous_observation": 1.0,
            "reporting_gap_flag": 0,
            "approved_cost": 5000.0,
            "C_base": 5000.0 if i < 6 else 6000.0, # Cost escalation at month 7 (2020-07)
            "expenditure": 1000.0 + i * 250.0,
            "expenditure_to_baseline": (1000.0 + i * 250.0) / 5000.0,
            "financial_progress": 20.0 + i * 5.0,
            "schedule_deviation_months": 0.0 if i < 4 else (i - 3) * 2.0, # Delay starts month 5
            "schedule_deviation_change": 0.0 if i < 4 else 2.0,
            "completion_date_drift": 0.0 if i < 5 else 6.0,
            "cost_revision_ratio": 1.0 if i < 6 else 1.20,
            "V_fin_1m": 5.0 if i < 4 else 1.0, # Velocity slows
            "V_fin_3m": 5.0 if i < 4 else 2.0,
            "A_fin": 0.0 if i < 4 else -2.0,
            "EWMA_V_fin": 4.5 if i < 4 else 1.5,
            "V_exp_1m": 250.0,
            "V_exp_3m": 250.0,
            "A_exp": 0.0,
            "Z_peer_V_fin": 0.0 if i < 4 else -1.5,
            "trajectory_risk_score": 10.0 if i < 4 else 65.0,
            "financial_physical_gap": 0.0,
            "V_phys_1m": np.nan,
            "V_phys_3m": np.nan,
            "A_phys": np.nan
        })
    return pd.DataFrame(records)

def test_replay_temporal_invariance_future_rows_removed(engine):
    """
    Test that prediction at month t is strictly identical whether future rows exist or are removed.
    This guarantees zero forward leakage.
    """
    df_full = create_synthetic_project(n_obs=10)
    df_truncated = df_full.iloc[:5].copy() # Cut off at month 5

    res_full = replay_project_from_dataframe(df_full, engine=engine)
    res_trunc = replay_project_from_dataframe(df_truncated, engine=engine)

    # Predictions for the first 5 months must match exactly
    for i in range(5):
        full_rec = res_full["timeline"][i]
        trunc_rec = res_trunc["timeline"][i]

        assert full_rec["reporting_month"] == trunc_rec["reporting_month"]
        assert full_rec["pred_prob"] == pytest.approx(trunc_rec["pred_prob"], abs=1e-5)
        assert full_rec["risk_tier"] == trunc_rec["risk_tier"]
        assert full_rec["alert"] == trunc_rec["alert"]

def test_first_alert_strictly_precedes_event(engine):
    """Test that first alert lead time is strictly positive and precedes deterioration."""
    df_project = create_synthetic_project(n_obs=10)
    res = replay_project_from_dataframe(df_project, engine=engine)

    assert res["actual_deterioration_event"] is not None
    assert res["actual_deterioration_event"]["event_month"] == "2020-07"

    if res["first_alert"] is not None:
        alert_m = res["first_alert"]["alert_month"]
        event_m = res["actual_deterioration_event"]["event_month"]
        assert alert_m < event_m
        assert res["lead_time"] > 0
        assert res["first_alert"]["lead_time_months"] == res["lead_time"]

def test_repeated_alerts_collapse_correctly(engine):
    """
    Test that multiple consecutive monthly alerts do NOT count as multiple events.
    They must collapse into a single first_alert with a single lead_time.
    """
    df_project = create_synthetic_project(n_obs=10)
    res = replay_project_from_dataframe(df_project, engine=engine)

    # In synthetic project, alerts trigger at months 5 and 6 before the month 7 deterioration
    alert_count = len(res["alert_points"])
    assert alert_count >= 1

    # But overall lead_time is a single scalar integer representing time from first alert
    assert isinstance(res["lead_time"], int)
    assert res["first_alert"]["alert_month"] == res["alert_points"][0]["reporting_month"]

def test_risk_tiers_correspond_to_validated_thresholds(engine):
    """Verify that every timeline record's tier maps precisely to the threshold rules."""
    df_project = create_synthetic_project(n_obs=10)
    res = replay_project_from_dataframe(df_project, engine=engine)

    for rec in res["timeline"]:
        p = rec["pred_prob"]
        tier = rec["risk_tier"]
        if p >= 0.50:
            assert tier == "ESCALATE"
            assert rec["alert"] is True
        elif p >= 0.45:
            assert tier == "REVIEW"
            assert rec["alert"] is True
        elif p >= 0.40:
            assert tier == "WATCH"
            assert rec["alert"] is True
        else:
            assert tier == "NORMAL"
            assert rec["alert"] is False

def test_explanation_values_traceable_to_actual_features(engine):
    """Verify that explanation outputs trace directly to actual numeric inputs."""
    df_project = create_synthetic_project(n_obs=10)
    res = replay_project_from_dataframe(df_project, engine=engine)

    alert_rec = [r for r in res["timeline"] if r["alert"]][0]
    explanations = alert_rec["top_explanations"]

    assert len(explanations) > 0
    for exp in explanations:
        feat = exp["feature"]
        val = exp["value"]
        assert feat in engine["features"]
        # Value must match what is in the synthetic record
        expected_val = df_project.loc[df_project["reporting_month"] == alert_rec["reporting_month"], feat].values[0]
        if not pd.isna(expected_val) and isinstance(expected_val, (int, float)):
            assert val == pytest.approx(float(expected_val), abs=1e-4)

def test_unknown_project_fails_cleanly():
    """Verify that querying a nonexistent project_id raises ValueError cleanly."""
    with pytest.raises(ValueError, match="not found in longitudinal dataset"):
        get_project_replay("NONEXISTENT_PROJECT_99999")

def test_sparse_project_observations(engine):
    """Verify that replay works without crashing on a project with only 1 observation."""
    sparse_df = pd.DataFrame([{
        "project_id": "SPARSE_001",
        "project_name": "Sparse Asset",
        "sector_clean": "Power",
        "scale_bucket": "SMALL",
        "reporting_month": "2021-01",
        "observation_number": 1,
        "project_age_months": 2.0,
        "C_base": 80.0,
        "expenditure": 10.0,
        "financial_progress": 12.5
    }])

    res = replay_project_from_dataframe(sparse_df, engine=engine)
    assert res["total_observations"] == 1
    assert len(res["timeline"]) == 1
    assert res["actual_deterioration_event"] is None
    assert res["lead_time"] is None

def test_future_cost_revision_cannot_alter_cbase_or_features_before_revision_month(engine):
    """
    REGRESSION TEST:
    Verify that introducing a massive future cost revision at month t+1 (e.g. +500% revision)
    cannot alter C_base, any model feature, pred_prob, risk_tier, or explanations at month t.
    """
    # Project with 3 baseline months
    base_rows = [
        {
            "project_id": "REGR_001",
            "project_name": "Hydroelectric Complex",
            "sector_clean": "Power",
            "scale_bucket": "MAJOR",
            "reporting_month": "2021-01",
            "observation_number": 1,
            "project_age_months": 1,
            "months_since_previous_observation": 1.0,
            "reporting_gap_flag": 0,
            "approved_cost": 3000.0,
            "C_base": 3000.0,
            "expenditure": 500.0,
            "expenditure_to_baseline": 500.0 / 3000.0,
            "financial_progress": 16.67,
            "schedule_deviation_months": 0.0,
            "V_fin_1m": np.nan,
            "V_fin_3m": np.nan,
            "A_fin": np.nan,
            "EWMA_V_fin": np.nan,
            "V_exp_1m": np.nan,
            "V_exp_3m": np.nan,
            "A_exp": np.nan,
            "cost_revision_ratio": np.nan,
            "Z_peer_V_fin": 0.0,
            "trajectory_risk_score": 15.0
        },
        {
            "project_id": "REGR_001",
            "project_name": "Hydroelectric Complex",
            "sector_clean": "Power",
            "scale_bucket": "MAJOR",
            "reporting_month": "2021-02",
            "observation_number": 2,
            "project_age_months": 2,
            "months_since_previous_observation": 1.0,
            "reporting_gap_flag": 0,
            "approved_cost": 3000.0,
            "C_base": 3000.0,
            "expenditure": 600.0,
            "expenditure_to_baseline": 600.0 / 3000.0,
            "financial_progress": 20.0,
            "schedule_deviation_months": 0.0,
            "V_fin_1m": 3.33,
            "V_fin_3m": np.nan,
            "A_fin": np.nan,
            "EWMA_V_fin": 3.33,
            "V_exp_1m": 100.0,
            "V_exp_3m": np.nan,
            "A_exp": np.nan,
            "cost_revision_ratio": np.nan,
            "Z_peer_V_fin": 0.1,
            "trajectory_risk_score": 18.0
        }
    ]

    # Scenario A: Observation 3 continues normally with C_base = 3000.0
    row_3_normal = {
        "project_id": "REGR_001",
        "project_name": "Hydroelectric Complex",
        "sector_clean": "Power",
        "scale_bucket": "MAJOR",
        "reporting_month": "2021-03",
        "observation_number": 3,
        "project_age_months": 3,
        "months_since_previous_observation": 1.0,
        "reporting_gap_flag": 0,
        "approved_cost": 3000.0,
        "C_base": 3000.0,
        "expenditure": 700.0,
        "expenditure_to_baseline": 700.0 / 3000.0,
        "financial_progress": 23.33,
        "schedule_deviation_months": 0.0,
        "V_fin_1m": 3.33,
        "V_fin_3m": np.nan,
        "A_fin": 0.0,
        "EWMA_V_fin": 3.33,
        "V_exp_1m": 100.0,
        "V_exp_3m": np.nan,
        "A_exp": 0.0,
        "cost_revision_ratio": np.nan,
        "Z_peer_V_fin": 0.1,
        "trajectory_risk_score": 18.0
    }

    # Scenario B: Observation 3 undergoes a catastrophic cost revision to 12,000.0 Cr (+300%)
    row_3_escalated = row_3_normal.copy()
    row_3_escalated.update({
        "approved_cost": 12000.0,
        "C_base": 12000.0,
        "cost_revision_ratio": 4.0,
        "scale_bucket": "MEGA",
        "expenditure_to_baseline": 700.0 / 12000.0
    })

    df_truncated = pd.DataFrame(base_rows)
    df_normal = pd.DataFrame(base_rows + [row_3_normal])
    df_escalated = pd.DataFrame(base_rows + [row_3_escalated])

    res_trunc = replay_project_from_dataframe(df_truncated, engine=engine)
    res_normal = replay_project_from_dataframe(df_normal, engine=engine)
    res_escalated = replay_project_from_dataframe(df_escalated, engine=engine)

    # Verify at months 1 and 2 (indices 0 and 1):
    for m_idx in range(2):
        rec_t = res_trunc["timeline"][m_idx]
        rec_n = res_normal["timeline"][m_idx]
        rec_e = res_escalated["timeline"][m_idx]

        # C_base must be strictly unaffected
        assert rec_t["C_base"] == 3000.0
        assert rec_n["C_base"] == 3000.0
        assert rec_e["C_base"] == 3000.0

        # Model probabilities must be strictly identical
        assert rec_t["pred_prob"] == pytest.approx(rec_n["pred_prob"], abs=1e-6)
        assert rec_t["pred_prob"] == pytest.approx(rec_e["pred_prob"], abs=1e-6)

        # Risk tier must be identical
        assert rec_t["risk_tier"] == rec_n["risk_tier"]
        assert rec_t["risk_tier"] == rec_e["risk_tier"]

        # Explanations must be identical
        assert rec_t["top_explanations"] == rec_n["top_explanations"]
        assert rec_t["top_explanations"] == rec_e["top_explanations"]

def test_replay_cost_restoration_not_false_deterioration(engine):
    """
    REGRESSION TEST:
    Verify that if reported cost temporarily drops (e.g. reporting anomaly) and returns to
    its established historical baseline, it is NOT flagged as a false cost deterioration event.
    """
    dip_rows = [
        {"project_id": "DIP_001", "reporting_month": "2020-01", "C_base": 5000.0, "expenditure": 1000.0, "financial_progress": 20.0, "sector_clean": "Power", "scale_bucket": "MAJOR", "observation_number": 1, "project_age_months": 1},
        {"project_id": "DIP_001", "reporting_month": "2020-02", "C_base": 5000.0, "expenditure": 1100.0, "financial_progress": 22.0, "sector_clean": "Power", "scale_bucket": "MAJOR", "observation_number": 2, "project_age_months": 2},
        # Month 3 temporarily dips to 3000
        {"project_id": "DIP_001", "reporting_month": "2020-03", "C_base": 3000.0, "expenditure": 1200.0, "financial_progress": 40.0, "sector_clean": "Power", "scale_bucket": "MAJOR", "observation_number": 3, "project_age_months": 3},
        # Month 4 restores to 5000 (established baseline)
        {"project_id": "DIP_001", "reporting_month": "2020-04", "C_base": 5000.0, "expenditure": 1300.0, "financial_progress": 26.0, "sector_clean": "Power", "scale_bucket": "MAJOR", "observation_number": 4, "project_age_months": 4},
    ]
    df_dip = pd.DataFrame(dip_rows)
    res = replay_project_from_dataframe(df_dip, engine=engine)

    # Restoring to 5000 must NOT be classified as an actual deterioration event
    assert res["actual_deterioration_event"] is None
    assert len(res["all_deterioration_events"]) == 0
