import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_model.py

Unit tests for sanket.model:
- Feature leakage detection assertion
- Baseline A and Baseline B prediction accuracy
- LightGBM training with missing and categorical features
- Metric calculation accuracy (PR-AUC, ROC-AUC, Brier score)
- Early-warning lead time calculation
"""

import pytest
import numpy as np
import pandas as pd
from sanket.model import (
    validate_feature_leakage,
    predict_baseline_a,
    predict_baseline_b,
    train_lgbm_model,
    predict_lgbm_probs,
    evaluate_predictions,
    compute_early_warning_lead_times
)

def test_leakage_assertion_raises_on_forbidden_words():
    bad_features = ["V_fin_1m", "cost_overrun_12m", "expenditure"]
    with pytest.raises(AssertionError, match="forbidden keyword 'overrun'"):
        validate_feature_leakage(bad_features)

def test_leakage_assertion_passes_on_valid_whitelist():
    good_features = [
        "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin", "V_exp_1m",
        "cost_revision_ratio", "expenditure_to_baseline", "schedule_deviation_months"
    ]
    # Must not raise
    validate_feature_leakage(good_features)

def test_baseline_a_logic():
    df = pd.DataFrame({
        "expenditure_to_baseline": [0.5, 0.95, 0.80, 0.10],
        "schedule_deviation_months": [0.0, 0.0, 15.0, 0.0]
    })
    preds = predict_baseline_a(df, exp_ratio_thresh=0.90, sch_dev_thresh=12.0)
    assert preds.tolist() == [0, 1, 1, 0]

def test_baseline_b_logic():
    df = pd.DataFrame({
        "V_fin_1m": [2.0, 0.1, 3.0],        # Row 1 has stalled velocity
        "EWMA_V_fin": [2.0, 0.2, 3.0],
        "Z_peer_V_fin": [0.0, 0.0, -1.5],     # Row 2 has negative peer Z
        "trajectory_risk_score": [10.0, 50.0, 10.0] # Row 1 has high risk score
    })
    preds = predict_baseline_b(df, v_fin_thresh=0.5, ewma_thresh=0.5, z_peer_thresh=-1.0, risk_score_thresh=40.0)
    assert preds.tolist() == [0, 1, 1]

def test_lgbm_training_and_metrics():
    np.random.seed(42)
    n = 200
    X = pd.DataFrame({
        "V_fin": np.random.randn(n),
        "A_fin": np.random.randn(n),
        "cat": ["A" if i % 2 == 0 else "B" for i in range(n)]
    })
    # Target correlated with V_fin
    y = (X["V_fin"] < -0.5).astype(float).values

    model = train_lgbm_model(
        X.iloc[:150], y[:150],
        X.iloc[150:], y[150:],
        categorical_features=["cat"]
    )
    probs = predict_lgbm_probs(model, X.iloc[150:], categorical_features=["cat"])
    metrics = evaluate_predictions(y[150:], probs, threshold=0.50)

    assert metrics["roc_auc"] > 0.60
    assert 0.0 <= metrics["brier_score"] <= 1.0
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0

def test_lead_time_calculation():
    # Synthetic test set with true positive alert at 2020-01
    df_test = pd.DataFrame([{
        "project_id": "P1",
        "reporting_month": "2020-01",
        "pred_prob": 0.85,
        "target": 1.0,
        "C_base": 1000.0,
        "schedule_deviation_months": 0.0
    }])

    # Timeline showing cost escalation at 2020-07 (+6 months later)
    df_timelines = pd.DataFrame([
        {"project_id": "P1", "reporting_month": "2020-01", "C_base": 1000.0, "schedule_deviation_months": 0.0},
        {"project_id": "P1", "reporting_month": "2020-07", "C_base": 1200.0, "schedule_deviation_months": 0.0}, # Overrun!
    ])

    lead_stats = compute_early_warning_lead_times(
        df_test, df_timelines, threshold=0.50, cost_threshold=0.05
    )

    assert lead_stats["evaluated_alerts"] == 1
    assert lead_stats["median_lead_time_months"] == 6.0
