import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_inference.py

Unit tests for sanket.inference:
- Risk tier mapping matches validated operational thresholds.
- Point-in-time scoring determinism.
- Deterministic "WHY?" explanation generation using TreeSHAP values.
- Traceability of explanations to actual input values.
- Robust handling of missing / unobserved features.
"""

import pytest
import numpy as np
import pandas as pd

from sanket.inference import (
    load_inference_engine,
    get_risk_tier,
    generate_feature_explanation,
    explain_prediction,
    predict_point_in_time
)

def test_risk_tiers_exact_thresholds():
    """Verify risk tiers match validated operational thresholds: WATCH=0.40, REVIEW=0.45, ESCALATE=0.50."""
    assert get_risk_tier(0.10) == "NORMAL"
    assert get_risk_tier(0.3999) == "NORMAL"
    assert get_risk_tier(0.40) == "WATCH"
    assert get_risk_tier(0.4499) == "WATCH"
    assert get_risk_tier(0.45) == "REVIEW"
    assert get_risk_tier(0.4999) == "REVIEW"
    assert get_risk_tier(0.50) == "ESCALATE"
    assert get_risk_tier(0.85) == "ESCALATE"

def test_explanation_traceability():
    """Verify explanation strings contain actual numeric feature values."""
    exp_sdev = generate_feature_explanation("schedule_deviation_months", 14.5)
    assert "14.5 months" in exp_sdev

    exp_burn = generate_feature_explanation("expenditure_to_baseline", 0.925)
    assert "92.5%" in exp_burn

    exp_rev = generate_feature_explanation("cost_revision_ratio", 1.15)
    assert "+15.0%" in exp_rev

    exp_vfin = generate_feature_explanation("V_fin_1m", 0.75)
    assert "0.75%/month" in exp_vfin

def test_predict_point_in_time_and_explanations():
    """Verify predict_point_in_time produces calibrated probability, tier, and top explanations."""
    engine = load_inference_engine()

    sample_row = {
        "C_base": 5000.0,
        "expenditure_to_baseline": 0.85,
        "schedule_deviation_months": 12.0,
        "schedule_deviation_change": 2.0,
        "completion_date_drift": 6.0,
        "cost_revision_ratio": 1.10,
        "V_fin_1m": 0.5,
        "V_fin_3m": 0.8,
        "A_fin": -0.1,
        "EWMA_V_fin": 0.6,
        "V_exp_1m": 25.0,
        "V_exp_3m": 22.0,
        "A_exp": 1.5,
        "Z_peer_V_fin": -0.8,
        "trajectory_risk_score": 45.0,
        "financial_physical_gap": 15.0,
        "project_age_months": 36.0,
        "observation_number": 24,
        "months_since_previous_observation": 1.0,
        "reporting_gap_flag": 0,
        "scale_bucket": "MAJOR",
        "sector_clean": "Railways"
    }

    res = predict_point_in_time(sample_row, engine=engine)

    assert "pred_prob" in res
    assert "risk_tier" in res
    assert "alert" in res
    assert "top_explanations" in res

    assert 0.0 <= res["pred_prob"] <= 1.0
    assert res["risk_tier"] in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]
    assert len(res["top_explanations"]) >= 1
    assert len(res["top_explanations"]) <= 3

    # Check that each explanation has feature name, contribution, and value
    first_exp = res["top_explanations"][0]
    assert "feature" in first_exp
    assert "contribution" in first_exp
    assert "explanation" in first_exp
    assert first_exp["feature"] in engine["features"]

def test_inference_handles_missing_values():
    """Verify inference natively handles missing / unobserved features without error."""
    engine = load_inference_engine()
    sparse_row = {
        "C_base": 1000.0,
        "scale_bucket": "MAJOR",
        "sector_clean": "Power"
        # All other features missing / NaN
    }
    res = predict_point_in_time(sparse_row, engine=engine)
    assert 0.0 <= res["pred_prob"] <= 1.0
    assert res["risk_tier"] in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]
