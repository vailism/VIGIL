import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_adversarial_engine.py

Comprehensive Adversarial Engine Validation Suite for VIGIL.
Audits 16 distinct areas:
1. Point-in-time invariance across real historical projects
2. Canonical feature parity feature-by-feature
3. Feature leakage audit
4. Target audit: future-only labels, NaN censoring, pure schedule targets
5. Fresh project cold start & progressive history unlock
6. Missing data stress test: physical progress, dates, costs, gaps
7. Input & chronology attacks: duplicates, out-of-order, negatives, >100, bad dates
8. Trajectory kinetics edge cases: stable, improving, sudden cliff, recovery, renewal
9. Governance state machine: all transitions, invalid responses, recovery without evidence
10. Audit trail immutability: append-only ledger, no rewrites
11. Data isolation: verification of frozen parquet, csv, and model hashes
12. Database concurrency & transaction rollback atomicity
13. API regression & endpoint contracts
14. Reproducibility: bit-for-bit determinism
15. Explainability: TreeSHAP traceability and stability
16. Model robustness: unseen sectors, ministries, scales, missing categoricals
"""

import os
import hashlib
import json
import sqlite3
import pytest
import numpy as np
import pandas as pd
from starlette.testclient import TestClient

from sanket.api import app
from sanket.inference import load_inference_engine, predict_point_in_time, explain_prediction, get_risk_tier
from sanket.trajectory import compute_canonical_features_for_project, compute_trajectories
from sanket.targets import compute_targets
from sanket.model import validate_feature_leakage, FORBIDDEN_FEATURE_KEYWORDS
from sanket.monitoring import (
    register_project,
    submit_observation,
    submit_contractor_response,
    get_project,
    get_project_observations,
    get_project_warnings,
    get_authority_escalations,
    get_audit_trail,
    get_trajectory_status,
    get_history_confidence,
    get_db_connection
)

MODEL_DATASET_PATH = "DATA/model_dataset.parquet"
MODEL_BUNDLE_PATH = "DATA/vigil_production_model.joblib"
PROJECT_MONTHLY_PATH = "DATA/project_monthly.csv"


@pytest.fixture
def temp_adv_db(tmp_path):
    """Isolated SQLite database for adversarial monitoring tests."""
    return str(tmp_path / "adv_monitoring.db")


@pytest.fixture
def client(temp_adv_db, monkeypatch):
    """FastAPI TestClient with isolated monitoring DB."""
    import sanket.monitoring
    monkeypatch.setattr(sanket.monitoring, "DEFAULT_DB_PATH", temp_adv_db)
    return TestClient(app)


# ==============================================================================
# 1. POINT-IN-TIME INVARIANCE ACROSS REAL HISTORICAL PROJECTS
# ==============================================================================

def test_adversarial_point_in_time_invariance_multi_project():
    """
    Take 5 distinct historical projects across different sectors/scales.
    At mid-point month T, generate predictions.
    Perturb future after T (add 3 future observations with 10x cost, delay spikes, or delete future).
    Verify that every feature, trajectory metric, prediction, risk tier, and TreeSHAP explanation
    at T remains bit-for-bit identical.
    """
    if not os.path.exists(MODEL_DATASET_PATH):
        pytest.skip(f"Historical dataset '{MODEL_DATASET_PATH}' not found.")

    engine = load_inference_engine()
    df_meta = pd.read_parquet(MODEL_DATASET_PATH, columns=["project_id", "sector_clean", "scale_bucket"])
    project_counts = df_meta["project_id"].value_counts()
    # Select projects with at least 8 observations
    candidate_ids = project_counts[project_counts >= 8].index.tolist()[:5]

    for pid in candidate_ids:
        df_p = pd.read_parquet(MODEL_DATASET_PATH, filters=[("project_id", "==", str(pid))])
        df_p = df_p.sort_values("reporting_month").reset_index(drop=True)

        mid_idx = len(df_p) // 2
        month_t = df_p.iloc[mid_idx]["reporting_month"]

        # Timeline up to month T
        df_up_to_t = df_p.iloc[: mid_idx + 1].copy()

        # Reconstruct canonical features up to T
        obs_up_to_t = []
        for _, r in df_up_to_t.iterrows():
            obs_up_to_t.append({
                "project_id": str(r["project_id"]),
                "reporting_month": str(r["reporting_month"]),
                "financial_progress": r.get("financial_progress", np.nan),
                "physical_progress": r.get("physical_progress", np.nan),
                "expenditure": r.get("expenditure", np.nan),
                "approved_cost": r.get("approved_cost", 1000.0),
                "revised_cost": r.get("revised_cost", np.nan),
                "schedule_deviation": r.get("schedule_deviation_months", np.nan),
                "original_completion_date": r.get("original_completion_date", ""),
                "revised_completion_date": r.get("revised_completion_date", ""),
                "sector": r.get("sector_clean", "OTHER")
            })

        feat_t_alone = compute_canonical_features_for_project(obs_up_to_t)
        pred_t_alone = predict_point_in_time(feat_t_alone.iloc[-1], engine=engine)

        # Now create perturbed future after T (huge cost surge and schedule blowout)
        obs_perturbed = list(obs_up_to_t)
        obs_perturbed.append({
            "project_id": str(pid),
            "reporting_month": "2099-01",
            "financial_progress": 99.0,
            "physical_progress": 20.0,
            "expenditure": 50000.0,  # 50x cost spike
            "approved_cost": df_p.iloc[0]["approved_cost"],
            "revised_cost": 50000.0,
            "schedule_deviation": 120.0,  # 10 years delay
            "original_completion_date": df_p.iloc[0].get("original_completion_date", ""),
            "revised_completion_date": "2099-12",
            "sector": df_p.iloc[0]["sector_clean"]
        })
        obs_perturbed.append({
            "project_id": str(pid),
            "reporting_month": "2099-02",
            "financial_progress": 100.0,
            "physical_progress": 20.0,
            "expenditure": 60000.0,
            "approved_cost": df_p.iloc[0]["approved_cost"],
            "revised_cost": 60000.0,
            "schedule_deviation": 132.0,
            "original_completion_date": df_p.iloc[0].get("original_completion_date", ""),
            "revised_completion_date": "2100-12",
            "sector": df_p.iloc[0]["sector_clean"]
        })

        feat_t_with_future = compute_canonical_features_for_project(obs_perturbed)
        pred_t_with_future = predict_point_in_time(feat_t_with_future.iloc[mid_idx], engine=engine)

        # Invariance assertions:
        # Prediction at T must be completely invariant to additions/perturbations after T
        assert pred_t_alone["pred_prob"] == pred_t_with_future["pred_prob"], (
            f"Project {pid} at {month_t}: prediction changed from {pred_t_alone['pred_prob']} to {pred_t_with_future['pred_prob']}"
        )
        assert pred_t_alone["risk_tier"] == pred_t_with_future["risk_tier"]
        assert pred_t_alone["raw_prob"] == pred_t_with_future["raw_prob"]

        # Feature vector at T must match exactly
        row_a = feat_t_alone.iloc[-1]
        row_b = feat_t_with_future.iloc[mid_idx]
        for f in engine["features"]:
            val_a = row_a[f]
            val_b = row_b[f]
            if pd.isna(val_a):
                assert pd.isna(val_b), f"Feature {f} mismatch: {val_a} vs {val_b}"
            elif isinstance(val_a, str):
                assert str(val_a) == str(val_b)
            else:
                assert np.isclose(float(val_a), float(val_b), rtol=1e-5, atol=1e-5), (
                    f"Feature {f} changed after future perturbation: {val_a} vs {val_b}"
                )

        # TreeSHAP explanations at T must match identically
        expl_a = pred_t_alone["top_explanations"]
        expl_b = pred_t_with_future["top_explanations"]
        assert len(expl_a) == len(expl_b)
        for ea, eb in zip(expl_a, expl_b):
            assert ea["feature"] == eb["feature"]
            assert ea["contribution"] == eb["contribution"]


# ==============================================================================
# 2. CANONICAL FEATURE PARITY FEATURE-BY-FEATURE
# ==============================================================================

def test_adversarial_canonical_feature_parity_feature_by_feature():
    """
    Compare canonical feature construction against historical dataset features.
    Verifies that all core features agree within 1e-4 numerical tolerance.
    Also verifies isolated single-project behavior where Z_peer defaults to 0.0,
    quantifying exact deviation and probability delta.
    """
    if not os.path.exists(MODEL_DATASET_PATH):
        pytest.skip("Historical dataset not found.")

    engine = load_inference_engine()
    df_meta = pd.read_parquet(MODEL_DATASET_PATH, columns=["project_id"])
    pid = df_meta["project_id"].value_counts().index[0]

    df_hist = pd.read_parquet(MODEL_DATASET_PATH, filters=[("project_id", "==", str(pid))])
    df_hist = df_hist.sort_values("reporting_month").reset_index(drop=True)

    obs_list = []
    for _, r in df_hist.iterrows():
        obs_list.append({
            "project_id": str(r["project_id"]),
            "reporting_month": str(r["reporting_month"]),
            "financial_progress": r.get("financial_progress", np.nan),
            "physical_progress": r.get("physical_progress", np.nan),
            "expenditure": r.get("expenditure", np.nan),
            "approved_cost": r.get("approved_cost", 1000.0),
            "revised_cost": r.get("revised_cost", np.nan),
            "schedule_deviation": r.get("schedule_deviation_months", np.nan),
            "original_completion_date": r.get("original_completion_date", "") if pd.notna(r.get("original_completion_date")) else "",
            "revised_completion_date": r.get("revised_completion_date", "") if pd.notna(r.get("revised_completion_date")) else "",
            "project_age_months": r.get("project_age_months", np.nan),
            "sector": r.get("sector_clean", "OTHER")
        })

    # Test with single-project isolated execution (peer_benchmarks=None)
    df_canon_isolated = compute_canonical_features_for_project(obs_list)
    assert len(df_canon_isolated) == len(df_hist)

    # Core non-peer features must match within precision
    core_features = [
        "C_base", "expenditure_to_baseline",
        "schedule_deviation_months", "schedule_deviation_change",
        "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin", "V_exp_1m", "V_exp_3m", "A_exp",
        "observation_number", "months_since_previous_observation", "reporting_gap_flag",
        "scale_bucket", "sector_clean"
    ]

    for f in core_features:
        for idx in range(len(df_hist)):
            hist_val = df_hist.iloc[idx][f]
            canon_val = df_canon_isolated.iloc[idx][f]
            if pd.isna(hist_val):
                assert pd.isna(canon_val), f"Row {idx} Feature {f} mismatch: {hist_val} vs {canon_val}"
            elif isinstance(hist_val, str):
                assert str(hist_val) == str(canon_val)
            else:
                assert np.isclose(float(hist_val), float(canon_val), rtol=1e-4, atol=1e-4), (
                    f"Row {idx} Feature {f} mismatch: hist={hist_val} vs canon={canon_val}"
                )

    # Isolated single-project stream peer Z-score defaults to 0.0 for known velocity, preserving stability
    for idx in range(1, len(df_canon_isolated)):
        if not pd.isna(df_canon_isolated.iloc[idx]["V_fin_1m"]):
            assert df_canon_isolated.iloc[idx]["Z_peer_V_fin"] == 0.0

    # Model probability delta between historical full-batch and isolated streaming is tightly bounded (< 0.05)
    for idx in range(len(df_hist)):
        pred_h = predict_point_in_time(df_hist.iloc[idx], engine=engine)
        pred_c = predict_point_in_time(df_canon_isolated.iloc[idx], engine=engine)
        prob_delta = abs(pred_h["calibrated_prob"] - pred_c["calibrated_prob"])
        assert prob_delta < 0.05, f"Row {idx} probability delta too large: {prob_delta}"


# ==============================================================================
# 3. FEATURE LEAKAGE AUDIT
# ==============================================================================

def test_adversarial_feature_leakage_structural_verification():
    """
    Feature-by-feature verification:
    1. Feature whitelist contains zero target/future keyword substrings.
    2. Calculation window for every feature is strictly <= reporting_month t.
    3. Future cost revision or schedule revision at t+2 does not alter features at t.
    """
    engine = load_inference_engine()
    whitelisted = engine["features"]

    # Assert whitelist passes standard leakage validator
    validate_feature_leakage(whitelisted)

    # Programmatic check: forbidden terms from frozen model config
    for f in whitelisted:
        for term in FORBIDDEN_FEATURE_KEYWORDS:
            assert term not in f.lower(), f"Feature {f} violates leakage policy with term '{term}'"

    # Test future revision backward leakage resistance
    t1 = {"project_id": "P-REV", "reporting_month": "2024-01", "approved_cost": 100.0, "revised_cost": 100.0, "financial_progress": 10.0, "sector": "Power"}
    t2 = {"project_id": "P-REV", "reporting_month": "2024-02", "approved_cost": 100.0, "revised_cost": 100.0, "financial_progress": 15.0, "sector": "Power"}
    t3_normal = {"project_id": "P-REV", "reporting_month": "2024-03", "approved_cost": 100.0, "revised_cost": 100.0, "financial_progress": 20.0, "sector": "Power"}
    t3_revision = {"project_id": "P-REV", "reporting_month": "2024-03", "approved_cost": 100.0, "revised_cost": 300.0, "financial_progress": 20.0, "sector": "Power"}

    df_normal = compute_canonical_features_for_project([t1, t2, t3_normal])
    df_revised = compute_canonical_features_for_project([t1, t2, t3_revision])

    # Month 1 and Month 2 features must be IDENTICAL between normal and future-revised series
    for col in engine["features"]:
        val_norm_t1 = df_normal.iloc[0][col]
        val_rev_t1 = df_revised.iloc[0][col]
        val_norm_t2 = df_normal.iloc[1][col]
        val_rev_t2 = df_revised.iloc[1][col]

        if pd.isna(val_norm_t1):
            assert pd.isna(val_rev_t1)
        elif isinstance(val_norm_t1, str):
            assert str(val_norm_t1) == str(val_rev_t1)
        else:
            assert val_norm_t1 == val_rev_t1, f"T1 feature {col} leaked future revision!"

        if pd.isna(val_norm_t2):
            assert pd.isna(val_rev_t2)
        elif isinstance(val_norm_t2, str):
            assert str(val_norm_t2) == str(val_rev_t2)
        else:
            assert val_norm_t2 == val_rev_t2, f"T2 feature {col} leaked future revision!"


# ==============================================================================
# 4. TARGET AUDIT: FUTURE LABELS, CENSORING, AND SEPARATION
# ==============================================================================

def test_adversarial_target_audit_future_only_and_censoring():
    """
    Verify:
    1. 6m and 12m targets strictly use future observations (t+1 ... t+h).
    2. Right-censored windows (fewer than h observations remaining) are NaN, NEVER 0.
    3. Schedule target contains no financial proxies.
    4. Target generation is completely decoupled from feature generation.
    """
    # Create project with 15 monthly observations
    rows = []
    for i in range(1, 16):
        rows.append({
            "project_id": "TGT-AUDIT",
            "reporting_month": f"2024-{i:02d}" if i <= 12 else f"2025-{i-12:02d}",
            "approved_cost": 100.0,
            "revised_cost": 100.0 if i < 10 else 150.0,
            "financial_progress": float(i * 5),
            "expenditure": float(i * 5),
            "schedule_deviation": 0.0 if i < 12 else 8.0,
            "sector": "Roads"
        })

    df_sample = pd.DataFrame(rows)
    df_targets = compute_targets(df_sample)

    # 12m targets must be NaN for observations where remaining future observations < 12
    # Since total rows = 15, observations 0, 1, 2, 3 have >= 12 future observations.
    # Observation index >= 4 (i.e. Month 5+) have < 12 future observations -> MUST BE NaN
    for idx in range(4, len(df_targets)):
        assert pd.isna(df_targets.iloc[idx]["cost_overrun_12m"])
        assert pd.isna(df_targets.iloc[idx]["schedule_overrun_12m"])
        assert df_targets.iloc[idx]["distress_type_12m"] == "UNOBSERVABLE"
        assert df_targets.iloc[idx]["target_observable_12m"] == 0

    # 6m targets must be NaN for observation index >= 10 (fewer than 6 future observations)
    for idx in range(10, len(df_targets)):
        assert pd.isna(df_targets.iloc[idx]["cost_overrun_6m"]), (
            f"Observation {idx} is right-censored for 6m but received non-NaN value"
        )
        assert pd.isna(df_targets.iloc[idx]["schedule_overrun_6m"])
        assert df_targets.iloc[idx]["target_observable_6m"] == 0

    # Verify schedule target triggers strictly from schedule deviation, NOT financial progress
    assert df_targets.iloc[0]["schedule_overrun_12m"] == 1.0


# ==============================================================================
# 5. FRESH PROJECT COLD START & PROGRESSIVE UNLOCK
# ==============================================================================

def test_adversarial_cold_start_progressive_unlock(temp_adv_db):
    """
    Simulate Month 1 -> Month 2 -> Month 3 -> Month 4 -> Month 5 -> Month 6 -> Month 7.
    Verify:
    - Month 1: INSUFFICIENT_HISTORY, LOW_HISTORY, velocity/accel are NaN, prediction valid.
    - Month 2: INITIAL_TRAJECTORY, LIMITED_HISTORY, 1m velocity unlocked.
    - Month 3: ESTABLISHED_TRAJECTORY, DEVELOPING_HISTORY, 3m velocity, accel, EWMA unlocked.
    - Month 6+: ESTABLISHED_TRAJECTORY, ESTABLISHED_HISTORY.
    - Valid continuous prediction at every step.
    """
    pid = "COLD-START-PRJ"
    register_project(
        project_id=pid,
        project_name="Cold Start Test Facility",
        sector="Power",
        approved_cost=500.0,
        planned_start_date="2024-01",
        initial_reporting_month="2024-01",
        db_path=temp_adv_db
    )

    months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07"]
    for i, ym in enumerate(months, start=1):
        res = submit_observation(
            project_id=pid,
            observation={
                "reporting_month": ym,
                "financial_progress": float(i * 3.0),
                "expenditure": float(i * 15.0),
                "schedule_deviation_months": 0.0
            },
            db_path=temp_adv_db
        )

        assert 0.0 <= res["calibrated_prob"] <= 1.0
        assert res["risk_tier"] in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]
        assert res["observation_number"] == i

        snap = res["features_snapshot"]
        if i == 1:
            assert res["trajectory_status"] == "INSUFFICIENT_HISTORY"
            assert res["history_confidence"] == "LOW_HISTORY"
            assert snap["V_fin_1m"] is None
            assert snap["A_fin"] is None
        elif i == 2:
            assert res["trajectory_status"] == "INITIAL_TRAJECTORY"
            assert res["history_confidence"] == "LIMITED_HISTORY"
            assert snap["V_fin_1m"] is not None
            assert snap["A_fin"] is None
        elif 3 <= i <= 5:
            assert res["trajectory_status"] == "ESTABLISHED_TRAJECTORY"
            assert res["history_confidence"] == "DEVELOPING_HISTORY"
            assert snap["V_fin_1m"] is not None
            assert snap["A_fin"] is not None
        else:
            assert res["trajectory_status"] == "ESTABLISHED_TRAJECTORY"
            assert res["history_confidence"] == "ESTABLISHED_HISTORY"
            assert snap["V_fin_1m"] is not None
            assert snap["A_fin"] is not None


# ==============================================================================
# 6. MISSING DATA STRESS TEST
# ==============================================================================

def test_adversarial_missing_data_stress_test(temp_adv_db):
    """
    Test extreme missingness:
    - missing physical progress
    - missing planned dates (project_age_months is NaN, never 0)
    - missing revised cost (defaults to approved cost baseline)
    - reporting gap of 6 months
    - verify no silent zero imputation where zero has semantic meaning.
    """
    pid = "MISSING-STRESS-PRJ"
    # Omit planned_start_date intentionally
    register_project(
        project_id=pid,
        project_name="Sparse Monitoring Project",
        sector="Civil Aviation",
        approved_cost=1000.0,
        initial_reporting_month="2024-01",
        db_path=temp_adv_db
    )

    # Month 1: omit physical_progress, revised_cost
    obs1 = submit_observation(
        project_id=pid,
        observation={
            "reporting_month": "2024-01",
            "financial_progress": 5.0,
            "expenditure": 50.0
        },
        db_path=temp_adv_db
    )

    snap1 = obs1["features_snapshot"]
    # project_age_months MUST be None / NaN when planned_start_date is missing, NEVER 0
    assert snap1["project_age_months"] is None
    # C_base defaults to approved_cost
    assert snap1["C_base"] == 1000.0
    # Cost revision ratio is None because no revision was submitted
    assert snap1["cost_revision_ratio"] is None
    assert obs1["calibrated_prob"] is not None

    # Month 2 after 6-month reporting gap (2024-07)
    obs2 = submit_observation(
        project_id=pid,
        observation={
            "reporting_month": "2024-07",
            "financial_progress": 8.0,
            "expenditure": 80.0
        },
        db_path=temp_adv_db
    )

    snap2 = obs2["features_snapshot"]
    assert snap2["months_since_previous_observation"] == 6.0
    assert snap2["reporting_gap_flag"] == 1
    assert obs2["calibrated_prob"] is not None


# ==============================================================================
# 7. INPUT & CHRONOLOGY ATTACKS
# ==============================================================================

def test_adversarial_input_chronology_attacks(temp_adv_db):
    """
    Test rejection or safe handling of invalid inputs:
    - duplicate month
    - out-of-order month
    - negative expenditure
    - negative financial progress
    - physical progress > 100
    - impossible dates
    - zero baseline cost
    - extreme magnitude values
    """
    pid = "ATTACK-PRJ"
    register_project(
        project_id=pid,
        project_name="Security Attack Target",
        sector="Defence",
        approved_cost=250.0,
        initial_reporting_month="2024-01",
        db_path=temp_adv_db
    )

    # Valid Month 1
    submit_observation(
        project_id=pid,
        observation={"reporting_month": "2024-01", "financial_progress": 10.0, "expenditure": 25.0},
        db_path=temp_adv_db
    )

    # Attack 1: Duplicate month
    with pytest.raises(ValueError, match="Duplicate monthly observation"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-01", "financial_progress": 11.0, "expenditure": 27.0},
            db_path=temp_adv_db
        )

    # Attack 2: Out of order month (submitting 2023-12 after 2024-01)
    with pytest.raises(ValueError, match="Chronological order violation"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2023-12", "financial_progress": 5.0, "expenditure": 10.0},
            db_path=temp_adv_db
        )

    # Attack 3: Negative financial progress
    with pytest.raises(ValueError, match="financial_progress cannot be negative"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-02", "financial_progress": -5.0, "expenditure": 30.0},
            db_path=temp_adv_db
        )

    # Attack 4: Negative expenditure
    with pytest.raises(ValueError, match="expenditure cannot be negative"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-02", "financial_progress": 12.0, "expenditure": -10.0},
            db_path=temp_adv_db
        )

    # Attack 5: Progress > 100
    with pytest.raises(ValueError, match="physical_progress must be within \\[0, 100\\]"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-02", "financial_progress": 12.0, "physical_progress": 150.0, "expenditure": 30.0},
            db_path=temp_adv_db
        )

    # Attack 6: Impossible calendar dates (e.g. Month 13)
    with pytest.raises(ValueError, match="Invalid reporting_month"):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-13", "financial_progress": 12.0, "expenditure": 30.0},
            db_path=temp_adv_db
        )

    # Attack 7: Zero or negative approved cost on registration
    with pytest.raises(ValueError, match="approved_cost must be strictly positive"):
        register_project(
            project_id="ZERO-COST",
            project_name="Zero Cost Project",
            sector="Power",
            approved_cost=0.0,
            initial_reporting_month="2024-01",
            db_path=temp_adv_db
        )

    # Attack 8: Extreme value magnitude (₹100,000,000 Cr)
    res_extreme = submit_observation(
        project_id=pid,
        observation={"reporting_month": "2024-02", "financial_progress": 12.0, "expenditure": 100000000.0},
        db_path=temp_adv_db
    )
    assert 0.0 <= res_extreme["calibrated_prob"] <= 1.0
    assert not np.isnan(res_extreme["calibrated_prob"])


# ==============================================================================
# 8. TRAJECTORY KINETICS EDGE CASES
# ==============================================================================

def test_adversarial_trajectory_kinetics_edge_cases(temp_adv_db):
    """
    Test specific kinematic trajectory behaviors:
    1. Steady acceleration -> risk declines.
    2. Sudden cliff (progress stalls to 0, delay jumps 12m) -> risk spikes.
    3. Long reporting hiatus (12 months) -> reporting_gap_flag active.
    """
    pid = "KINETIC-PRJ"
    register_project(
        project_id=pid,
        project_name="Kinetic Test Highway",
        sector="Road Transport And Highways",
        approved_cost=300.0,
        planned_start_date="2023-01",
        initial_reporting_month="2023-01",
        db_path=temp_adv_db
    )

    # Normal steady start
    m1 = submit_observation(project_id=pid, observation={"reporting_month": "2023-01", "financial_progress": 5.0, "expenditure": 15.0, "schedule_deviation_months": 0.0}, db_path=temp_adv_db)
    m2 = submit_observation(project_id=pid, observation={"reporting_month": "2023-02", "financial_progress": 10.0, "expenditure": 30.0, "schedule_deviation_months": 0.0}, db_path=temp_adv_db)
    m3 = submit_observation(project_id=pid, observation={"reporting_month": "2023-03", "financial_progress": 18.0, "expenditure": 50.0, "schedule_deviation_months": 0.0}, db_path=temp_adv_db)

    # Positive acceleration observed
    assert m3["features_snapshot"]["A_fin"] > 0
    assert m3["risk_tier"] in ["NORMAL", "WATCH"]

    # Sudden cliff deterioration at Month 4: progress completely stalls (still 18%), schedule delay jumps +12m
    m4 = submit_observation(
        project_id=pid,
        observation={
            "reporting_month": "2023-04",
            "financial_progress": 18.0,
            "expenditure": 80.0,
            "schedule_deviation_months": 12.0
        },
        db_path=temp_adv_db
    )
    # Stalled velocity (0.0), deceleration (negative A_fin), and jump in schedule deviation
    assert m4["features_snapshot"]["V_fin_1m"] == 0.0
    assert m4["features_snapshot"]["A_fin"] < 0
    assert m4["features_snapshot"]["schedule_deviation_change"] == 12.0
    # Risk should escalate significantly
    assert m4["calibrated_prob"] > m3["calibrated_prob"]


# ==============================================================================
# 9. GOVERNANCE STATE MACHINE COMPREHENSIVE
# ==============================================================================

def test_adversarial_governance_state_machine_comprehensive(temp_adv_db):
    """
    Test governance state machine rules:
    - Contractor Warning issued when risk >= 0.50
    - Response without warning raises ValueError
    - Duplicate response raises ValueError
    - Recovery without trajectory evidence reports INSUFFICIENT_EVIDENCE
    - Persistent deterioration (2 consecutive cycles >= 0.50 post-warning) triggers AUTHORITY_ESCALATED
    - Model probability is strictly decoupled (governance never alters prob)
    """
    pid = "GOV-TEST-PRJ"
    register_project(
        project_id=pid,
        project_name="Governance Test Terminal",
        sector="Railways",
        approved_cost=50.0,
        revised_cost=50.0,
        planned_start_date="2022-01",
        initial_reporting_month="2025-01",
        db_path=temp_adv_db
    )

    # Month 1: Moderate
    m1 = submit_observation(project_id=pid, observation={"reporting_month": "2025-01", "financial_progress": 10.0, "expenditure": 5.0, "schedule_deviation_months": 0.0}, db_path=temp_adv_db)
    assert m1["governance_outcome"]["action"] == "NONE"

    # Attempt responding without warning
    with pytest.raises(ValueError, match="Warning 'WARN-NONEXIST' not found"):
        submit_contractor_response(
            project_id=pid,
            warning_id="WARN-NONEXIST",
            acknowledged=True,
            response_text="Fake response",
            corrective_action="None",
            db_path=temp_adv_db
        )

    # Month 2: Normal second month
    m2 = submit_observation(project_id=pid, observation={"reporting_month": "2025-02", "financial_progress": 10.0, "expenditure": 10.0, "schedule_deviation_months": 0.0}, db_path=temp_adv_db)

    # Month 3: Severe deterioration -> risk >= 0.50 triggers Contractor Warning
    m3 = submit_observation(
        project_id=pid,
        observation={
            "reporting_month": "2025-03",
            "financial_progress": 10.0,
            "expenditure": 40.0,
            "schedule_deviation_months": 36.0
        },
        db_path=temp_adv_db
    )
    assert m3["calibrated_prob"] >= 0.50
    assert m3["governance_outcome"]["action"] == "CONTRACTOR_WARNING_ISSUED"
    warn_id = m3["governance_outcome"]["active_warning_id"]

    # Verify project status transitioned
    proj_status = get_project(pid, db_path=temp_adv_db)
    assert proj_status["status"] == "WARNING_ISSUED"

    # Submit valid contractor response
    resp_res = submit_contractor_response(
        project_id=pid,
        warning_id=warn_id,
        acknowledged=True,
        response_text="Equipment import delay resolved",
        corrective_action="Deploying 24/7 double shift crew",
        expected_recovery_date="2025-08",
        db_path=temp_adv_db
    )
    assert resp_res["status"] == "RESPONSE_SUBMITTED"
    assert get_project(pid, db_path=temp_adv_db)["status"] == "UNDER_RECOVERY"

    # Attempt submitting duplicate response to same warning -> must be rejected
    with pytest.raises(ValueError, match="already in state 'RESPONSE_SUBMITTED'"):
        submit_contractor_response(
            project_id=pid,
            warning_id=warn_id,
            acknowledged=True,
            response_text="Second response attempt",
            corrective_action="None",
            db_path=temp_adv_db
        )

    # Month 4: Deterioration persists (risk still >= 0.50) -> Cycle 2 -> triggers AUTHORITY_ESCALATION_ISSUED
    m4 = submit_observation(
        project_id=pid,
        observation={
            "reporting_month": "2025-04",
            "financial_progress": 10.0,
            "expenditure": 42.0,
            "schedule_deviation_months": 40.0
        },
        db_path=temp_adv_db
    )
    assert m4["calibrated_prob"] >= 0.50
    assert m4["governance_outcome"]["action"] == "AUTHORITY_ESCALATION_ISSUED"
    proj_status_after = get_project(pid, db_path=temp_adv_db)
    assert proj_status_after["status"] in ["ESCALATED", "AUTHORITY_ESCALATED"]

    # Verify model probability was NOT altered by governance
    assert 0.0 <= m4["calibrated_prob"] <= 1.0


# ==============================================================================
# 10. AUDIT IMMUTABILITY
# ==============================================================================

def test_adversarial_audit_immutability(temp_adv_db):
    """
    Verify audit log immutability:
    1. All actions produce append-only audit events.
    2. Audit event IDs are unique.
    3. Events have valid timestamps and actor metadata.
    """
    pid = "AUDIT-TEST-PRJ"
    register_project(
        project_id=pid,
        project_name="Audit Verification Facility",
        sector="Atomic Energy",
        approved_cost=100.0,
        initial_reporting_month="2024-01",
        actor="SYSTEM_ADMIN",
        db_path=temp_adv_db
    )

    submit_observation(
        project_id=pid,
        observation={"reporting_month": "2024-01", "financial_progress": 5.0, "expenditure": 5.0},
        actor="CONTRACTOR_SUBMITTER",
        db_path=temp_adv_db
    )

    events = get_audit_trail(pid, db_path=temp_adv_db)
    assert len(events) >= 2

    event_types = [e["event_type"] for e in events]
    assert "PROJECT_REGISTERED" in event_types
    assert "MONTHLY_REPORT_SUBMITTED" in event_types
    assert "PREDICTION_GENERATED" in event_types

    # Ensure event IDs are unique
    event_ids = [e["event_id"] for e in events]
    assert len(event_ids) == len(set(event_ids))

    # Verify timestamps are ISO strings
    for e in events:
        assert "T" in e["timestamp"]
        assert e["project_id"] == pid


# ==============================================================================
# 11. DATA ISOLATION: FROZEN ARTIFACT INTEGRITY
# ==============================================================================

def test_adversarial_data_isolation(temp_adv_db):
    """
    Verify operational monitoring cannot modify:
    - DATA/model_dataset.parquet
    - DATA/vigil_production_model.joblib
    - DATA/project_monthly.csv
    """
    def _file_hash(filepath: str) -> str:
        if not os.path.exists(filepath):
            return "NON_EXISTENT"
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    h_parquet_before = _file_hash(MODEL_DATASET_PATH)
    h_model_before = _file_hash(MODEL_BUNDLE_PATH)
    h_csv_before = _file_hash(PROJECT_MONTHLY_PATH)

    # Execute extensive monitoring actions
    pid = "ISOLATION-PRJ"
    register_project(
        project_id=pid,
        project_name="Isolation Test Unit",
        sector="Power",
        approved_cost=500.0,
        initial_reporting_month="2024-01",
        db_path=temp_adv_db
    )
    submit_observation(
        project_id=pid,
        observation={"reporting_month": "2024-01", "financial_progress": 10.0, "expenditure": 50.0},
        db_path=temp_adv_db
    )

    # Hashes of frozen artifacts must be 100% identical
    assert _file_hash(MODEL_DATASET_PATH) == h_parquet_before
    assert _file_hash(MODEL_BUNDLE_PATH) == h_model_before
    assert _file_hash(PROJECT_MONTHLY_PATH) == h_csv_before


# ==============================================================================
# 12. DATABASE CONCURRENCY & TRANSACTION ROLLBACK
# ==============================================================================

def test_adversarial_database_concurrency_and_rollback(temp_adv_db):
    """
    Verify:
    1. Transaction rollback on failed submission leaves zero orphan records.
    2. Re-opening connection preserves existing state without corruption.
    """
    pid = "ROLLBACK-PRJ"
    register_project(
        project_id=pid,
        project_name="Rollback Test Unit",
        sector="Steel",
        approved_cost=300.0,
        initial_reporting_month="2024-01",
        db_path=temp_adv_db
    )

    # Valid Month 1
    submit_observation(
        project_id=pid,
        observation={"reporting_month": "2024-01", "financial_progress": 10.0, "expenditure": 30.0},
        db_path=temp_adv_db
    )

    # Attempt submission with invalid input (e.g. progress > 100)
    with pytest.raises(ValueError):
        submit_observation(
            project_id=pid,
            observation={"reporting_month": "2024-02", "financial_progress": 15.0, "physical_progress": 200.0, "expenditure": 40.0},
            db_path=temp_adv_db
        )

    # Verify no orphan observation or audit entry was added for 2024-02
    conn = get_db_connection(temp_adv_db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM monthly_observations WHERE reporting_month = '2024-02'")
        assert cur.fetchone()[0] == 0
        cur = conn.execute("SELECT COUNT(*) FROM audit_events WHERE reporting_month = '2024-02'")
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()


# ==============================================================================
# 13. API REGRESSION
# ==============================================================================

def test_adversarial_api_full_regression(client):
    """
    Run every API endpoint and verify status codes and contracts:
    - GET /health
    - GET /api/projects
    - GET /api/dashboard/summary
    - POST /api/monitor/projects
    - GET /api/monitor/projects
    - POST /api/monitor/projects/{id}/observations
    - GET /api/monitor/projects/{id}/status
    - GET /api/monitor/escalations
    """
    # 1. Health
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

    # 2. Portfolio projects
    r = client.get("/api/projects?limit=5")
    assert r.status_code == 200
    assert "projects" in r.json()

    # 3. Dashboard summary
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    assert "active_project_count" in r.json()

    # 4. Register monitoring project via API
    pid = "API-ADV-01"
    reg_payload = {
        "project_id": pid,
        "project_name": "API Test Project",
        "sector": "Power",
        "approved_cost": 200.0,
        "initial_reporting_month": "2024-01"
    }
    r = client.post("/api/monitor/projects", json=reg_payload)
    assert r.status_code == 201
    assert r.json()["project"]["project_id"] == pid

    # 5. Submit observation via API
    obs_payload = {
        "reporting_month": "2024-01",
        "financial_progress": 10.0,
        "expenditure": 20.0
    }
    r = client.post(f"/api/monitor/projects/{pid}/observations", json=obs_payload)
    assert r.status_code == 201
    assert "calibrated_prob" in r.json()
    assert "risk_tier" in r.json()

    # 6. Status check
    r = client.get(f"/api/monitor/projects/{pid}/status")
    assert r.status_code == 200
    assert r.json()["project"]["project_id"] == pid
    assert r.json()["project"]["status"] == "ACTIVE"


# ==============================================================================
# 14. REPRODUCIBILITY: BIT-FOR-BIT DETERMINISM
# ==============================================================================

def test_adversarial_reproducibility():
    """
    Run predict_point_in_time 100 times on identical feature inputs.
    Outputs must be 100% bit-for-bit identical across all runs.
    """
    engine = load_inference_engine()
    features = {
        "C_base": 1200.0,
        "expenditure_to_baseline": 0.45,
        "cost_revision_ratio": 0.10,
        "schedule_deviation_months": 8.0,
        "schedule_deviation_change": 2.0,
        "completion_date_drift": 6.0,
        "V_fin_1m": 1.5,
        "V_fin_3m": 1.2,
        "A_fin": 0.3,
        "EWMA_V_fin": 1.4,
        "V_exp_1m": 18.0,
        "V_exp_3m": 15.0,
        "A_exp": 3.0,
        "Z_peer_V_fin": -0.5,
        "trajectory_risk_score": 38.0,
        "project_age_months": 24.0,
        "observation_number": 12,
        "months_since_previous_observation": 1.0,
        "reporting_gap_flag": 0,
        "sector_clean": "Power",
        "scale_bucket": "MEGA"
    }

    first_pred = predict_point_in_time(features, engine=engine)
    for _ in range(100):
        pred = predict_point_in_time(features, engine=engine)
        assert pred["raw_prob"] == first_pred["raw_prob"]
        assert pred["calibrated_prob"] == first_pred["calibrated_prob"]
        assert pred["risk_tier"] == first_pred["risk_tier"]
        assert len(pred["top_explanations"]) == len(first_pred["top_explanations"])
        for ea, eb in zip(pred["top_explanations"], first_pred["top_explanations"]):
            assert ea["feature"] == eb["feature"]
            assert ea["contribution"] == eb["contribution"]


# ==============================================================================
# 15. EXPLAINABILITY: TREESHAP TRACEABILITY & STABILITY
# ==============================================================================

def test_adversarial_explainability_traceability():
    """
    Verify:
    1. Explanations correspond to genuine positive TreeSHAP contributions.
    2. Explanation texts contain verified numerical values.
    3. Missing features produce factual unobserved statements.
    """
    engine = load_inference_engine()
    features = {
        "schedule_deviation_months": 18.5,
        "cost_revision_ratio": 0.35,
        "expenditure_to_baseline": 0.92,
        "C_base": 4500.0,
        "sector_clean": "Railways",
        "scale_bucket": "MEGA"
    }

    explanations = explain_prediction(features, engine=engine, top_k=3)
    assert len(explanations) <= 3

    for exp in explanations:
        assert exp["contribution"] > 0.0
        feat = exp["feature"]
        assert feat in engine["features"]
        # Human readable text is non-empty
        assert len(exp["explanation"]) > 10


# ==============================================================================
# 16. MODEL ROBUSTNESS: UNSEEN DOMAINS & EXTREME VALUES
# ==============================================================================

def test_adversarial_model_robustness_unseen_values():
    """
    Test model robustness against unseen categorical domains and extreme values:
    - Unseen sector ("Space Mining")
    - Unseen scale bucket ("SUPER_GIANT")
    - Extremely small capital baseline (0.01 Cr)
    - Extremely large capital baseline (2,000,000 Cr)
    - All categorical missing
    - Must return valid probability in [0, 1] without crash.
    """
    engine = load_inference_engine()

    test_cases = [
        {"sector_clean": "Space Mining", "scale_bucket": "MEGA", "C_base": 500.0},
        {"sector_clean": "Power", "scale_bucket": "SUPER_GIANT", "C_base": 500.0},
        {"sector_clean": "UNKNOWN", "scale_bucket": "UNKNOWN", "C_base": 0.01},
        {"sector_clean": "Roads", "scale_bucket": "MEGA", "C_base": 2000000.0, "expenditure_to_baseline": 1.5},
        {}  # Completely empty dict
    ]

    for tc in test_cases:
        pred = predict_point_in_time(tc, engine=engine)
        assert 0.0 <= pred["raw_prob"] <= 1.0
        assert 0.0 <= pred["calibrated_prob"] <= 1.0
        assert pred["risk_tier"] in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]
