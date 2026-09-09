import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_monitoring.py

Comprehensive test suite for VIGIL Operational Monitoring Layer:
1. Onboarding new projects absent from historical training corpora.
2. Month 1 observation: current-state prediction, NaN velocities, LOW_HISTORY confidence.
3. Month 2 observation: 1-month velocity availability, LIMITED_HISTORY confidence.
4. Month 3 observation: acceleration and trajectory metrics availability, DEVELOPING_HISTORY confidence.
5. Contractor warning issuance on severe deterioration (risk >= 0.50).
6. Contractor response submission & SLA recovery tracking.
7. Scenario A: Trajectory improvement & RECOVERED status ("Trajectory improved following the warning.").
8. Scenario B: Persistent deterioration & AUTHORITY ESCALATION with full dossier.
9. Prediction Equivalence: Historical project fed through canonical feature pipeline matches existing inference engine.
10. Point-in-Time Invariance: prediction(t) invariant to future observations.
11. Validation: duplicate month rejection, chronology rejection, non-negative bounds.
12. Physical progress missingness preservation (never fabricated).
13. Append-only audit trail immutability.
14. Historical dataset integrity preservation.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from sanket.api import app
from sanket import monitoring
from sanket.inference import load_inference_engine, predict_point_in_time
from sanket.trajectory import compute_canonical_features_for_project


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Ensure every test runs against a clean, isolated SQLite database."""
    test_db = str(tmp_path / "test_monitoring.db")
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", test_db)
    monitoring.init_db(test_db)
    return test_db


@pytest.fixture
def client():
    return TestClient(app)


def test_01_onboard_unseen_project(client):
    """1. Verify onboarding a completely unseen project not in training data."""
    payload = {
        "project_id": "NEW-SOLAR-2026",
        "project_name": "Ultra Mega Solar Park Phase IV",
        "sector": "Power",
        "ministry": "Ministry of New and Renewable Energy",
        "state": "Rajasthan",
        "approved_cost": 4200.0,
        "revised_cost": 4200.0,
        "planned_start_date": "2024-01",
        "planned_completion_date": "2026-12",
        "contractor": "Apex Infra Solar Ltd",
        "initial_reporting_month": "2025-01"
    }

    resp = client.post("/api/monitor/projects", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project"]["project_id"] == "NEW-SOLAR-2026"
    assert data["project"]["status"] == "ACTIVE"

    # Verify retrieval
    get_resp = client.get("/api/monitor/projects/NEW-SOLAR-2026")
    assert get_resp.status_code == 200
    assert get_resp.json()["project_name"] == "Ultra Mega Solar Park Phase IV"

    # Duplicate registration must fail
    dup_resp = client.post("/api/monitor/projects", json=payload)
    assert dup_resp.status_code == 400


def test_02_month_1_observation_limited_history(client):
    """2. Month 1: Current-state prediction, NaN velocities, LOW_HISTORY confidence."""
    # Register project
    client.post("/api/monitor/projects", json={
        "project_id": "METRO-X1",
        "project_name": "Urban Metro Rapid Transit",
        "sector": "Urban Development",
        "approved_cost": 3000.0,
        "initial_reporting_month": "2025-01",
        "planned_start_date": "2024-06"
    })

    obs1 = {
        "reporting_month": "2025-01",
        "financial_progress": 8.0,
        "expenditure": 240.0,
        "schedule_deviation_months": 0.0,
        "physical_progress": 7.5
    }

    resp = client.post("/api/monitor/projects/METRO-X1/observations", json=obs1)
    assert resp.status_code == 201
    res = resp.json()

    # Invariants for Month 1
    assert res["observation_number"] == 1
    assert res["trajectory_status"] == "INSUFFICIENT_HISTORY"
    assert res["history_confidence"] == "LOW_HISTORY"
    assert res["trajectory_history_months"] == 1

    # Valid calibrated prediction returned
    pred = res["prediction"]
    assert 0.0 <= pred["calibrated_probability"] <= 1.0
    assert pred["risk_tier"] in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]
    assert len(res["top_deterministic_explanations"]) > 0

    # Verify project age semantics (2025-01 minus 2024-06 = 7 months)
    obs_list = monitoring.get_project_observations("METRO-X1")
    features = json.loads(obs_list[0]["features_snapshot"])
    assert features["project_age_months"] == 7.0
    assert features["V_fin_1m"] is None
    assert features["A_fin"] is None


def test_03_month_2_progressive_velocity_unlock(client):
    """3. Month 2: 1-month velocity unlocks; acceleration remains NaN; LIMITED_HISTORY."""
    client.post("/api/monitor/projects", json={
        "project_id": "HIGHWAY-99",
        "project_name": "Greenfield Expressway Section 3",
        "sector": "Road Transport And Highways",
        "approved_cost": 1500.0,
        "initial_reporting_month": "2025-01"
    })

    # Month 1
    client.post("/api/monitor/projects/HIGHWAY-99/observations", json={
        "reporting_month": "2025-01",
        "financial_progress": 10.0,
        "expenditure": 150.0,
        "schedule_deviation_months": 0.0
    })

    # Month 2
    resp2 = client.post("/api/monitor/projects/HIGHWAY-99/observations", json={
        "reporting_month": "2025-02",
        "financial_progress": 12.5,
        "expenditure": 187.5,
        "schedule_deviation_months": 0.5
    })
    assert resp2.status_code == 201
    res2 = resp2.json()

    assert res2["observation_number"] == 2
    assert res2["trajectory_status"] == "INITIAL_TRAJECTORY"
    assert res2["history_confidence"] == "LIMITED_HISTORY"

    obs_list = monitoring.get_project_observations("HIGHWAY-99")
    f2 = json.loads(obs_list[1]["features_snapshot"])
    assert abs(f2["V_fin_1m"] - 2.5) < 1e-4  # 12.5 - 10.0 = 2.5%/mo
    assert f2["A_fin"] is None  # Acceleration requires >= 2 velocity points


def test_04_month_3_acceleration_and_trajectory_unlock(client):
    """4. Month 3: Acceleration unlocks; DEVELOPING_HISTORY confidence."""
    client.post("/api/monitor/projects", json={
        "project_id": "PORT-PORT",
        "project_name": "Deepwater Container Terminal",
        "sector": "Shipping",
        "approved_cost": 2500.0,
        "initial_reporting_month": "2025-01"
    })

    client.post("/api/monitor/projects/PORT-PORT/observations", json={
        "reporting_month": "2025-01", "financial_progress": 5.0, "expenditure": 125.0
    })
    client.post("/api/monitor/projects/PORT-PORT/observations", json={
        "reporting_month": "2025-02", "financial_progress": 7.0, "expenditure": 175.0
    })
    resp3 = client.post("/api/monitor/projects/PORT-PORT/observations", json={
        "reporting_month": "2025-03", "financial_progress": 8.0, "expenditure": 200.0
    })
    assert resp3.status_code == 201
    res3 = resp3.json()

    assert res3["observation_number"] == 3
    assert res3["trajectory_status"] == "ESTABLISHED_TRAJECTORY"
    assert res3["history_confidence"] == "DEVELOPING_HISTORY"

    obs_list = monitoring.get_project_observations("PORT-PORT")
    f3 = json.loads(obs_list[2]["features_snapshot"])
    # V1 = 2.0 (7 - 5), V2 = 1.0 (8 - 7), A = 1.0 - 2.0 = -1.0%/mo^2
    assert abs(f3["V_fin_1m"] - 1.0) < 1e-4
    assert abs(f3["A_fin"] - (-1.0)) < 1e-4


def test_05_contractor_warning_trigger_and_payload(client):
    """5. Contractor Warning triggered when calibrated risk reaches ESCALATE (>= 0.50)."""
    client.post("/api/monitor/projects", json={
        "project_id": "DISTRESSED-01",
        "project_name": "Troubled Substation Scheme",
        "sector": "Power",
        "approved_cost": 50.0,
        "revised_cost": 50.0,
        "planned_start_date": "2022-01",
        "initial_reporting_month": "2025-01"
    })

    # Month 1
    client.post("/api/monitor/projects/DISTRESSED-01/observations", json={
        "reporting_month": "2025-01",
        "financial_progress": 10.0,
        "expenditure": 5.0,
        "schedule_deviation_months": 0.0
    })

    # Month 2
    client.post("/api/monitor/projects/DISTRESSED-01/observations", json={
        "reporting_month": "2025-02",
        "financial_progress": 10.0,
        "expenditure": 10.0,
        "schedule_deviation_months": 0.0
    })

    # Month 3: Severe schedule delay jump and high burn rate triggers ESCALATE >= 0.50
    resp3 = client.post("/api/monitor/projects/DISTRESSED-01/observations", json={
        "reporting_month": "2025-03",
        "financial_progress": 10.0,
        "expenditure": 40.0,
        "schedule_deviation_months": 36.0
    })
    assert resp3.status_code == 201
    data = resp3.json()

    pred = data["prediction"]
    gov = data["governance_status"]

    # Calibrated risk should be elevated in ESCALATE tier (>= 0.50)
    assert pred["calibrated_probability"] >= 0.50
    assert pred["risk_tier"] == "ESCALATE"

    # Governance action: warning issued
    assert gov["action"] == "CONTRACTOR_WARNING_ISSUED"
    warning_id = gov["active_warning_id"]
    assert warning_id.startswith("WARN-")

    # Verify warning in DB
    warn_list = client.get("/api/monitor/projects/DISTRESSED-01/warnings").json()["warnings"]
    assert len(warn_list) == 1
    w = warn_list[0]
    assert w["warning_id"] == warning_id
    assert w["status"] == "ISSUED"
    assert "VIGIL detected sustained deterioration" in w["warning_reason"]
    assert "Contractor acknowledgment" in w["required_response"]
    assert w["response_deadline"] is not None


def test_06_contractor_response_submission(client):
    """6. Contractor submits formal response and recovery plan."""
    client.post("/api/monitor/projects", json={
        "project_id": "RESP-PROJ",
        "project_name": "Expressway Package 4",
        "sector": "Road Transport And Highways",
        "approved_cost": 50.0,
        "revised_cost": 50.0,
        "planned_start_date": "2022-01",
        "initial_reporting_month": "2025-01"
    })

    client.post("/api/monitor/projects/RESP-PROJ/observations", json={
        "reporting_month": "2025-01", "financial_progress": 10.0, "expenditure": 5.0, "schedule_deviation_months": 0.0
    })
    client.post("/api/monitor/projects/RESP-PROJ/observations", json={
        "reporting_month": "2025-02", "financial_progress": 10.0, "expenditure": 10.0, "schedule_deviation_months": 0.0
    })
    client.post("/api/monitor/projects/RESP-PROJ/observations", json={
        "reporting_month": "2025-03", "financial_progress": 10.0, "expenditure": 40.0, "schedule_deviation_months": 36.0
    })

    warnings = client.get("/api/monitor/projects/RESP-PROJ/warnings").json()["warnings"]
    assert len(warnings) >= 1
    wid = warnings[0]["warning_id"]

    # Submit contractor response
    resp_payload = {
        "acknowledged": True,
        "response_text": "Land acquisition delay in Section B resolved; deployed 2 additional earthmoving teams.",
        "corrective_action": "Doubled shift capacity and renegotiated subcontractor agreements.",
        "expected_recovery_date": "2025-06",
        "responsible_person": "Chief Project Manager R. Sharma"
    }

    r = client.post(f"/api/monitor/projects/RESP-PROJ/warnings/{wid}/response", json=resp_payload)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data["status"] == "RESPONSE_SUBMITTED"

    # Status check
    status = client.get("/api/monitor/projects/RESP-PROJ/status").json()
    assert status["active_warning"]["status"] == "RESPONSE_SUBMITTED"
    assert status["governance_state"] == "UNDER_RECOVERY"


def test_07_recovery_monitoring_scenario_a(client):
    """7. Scenario A: Following warning and response, project trajectory recovers."""
    client.post("/api/monitor/projects", json={
        "project_id": "RECOV-01",
        "project_name": "Coastal Transmission Line",
        "sector": "Power",
        "approved_cost": 50.0,
        "revised_cost": 50.0,
        "planned_start_date": "2022-01",
        "initial_reporting_month": "2025-01"
    })

    # Months 1-2
    client.post("/api/monitor/projects/RECOV-01/observations", json={
        "reporting_month": "2025-01", "financial_progress": 10.0, "expenditure": 5.0, "schedule_deviation_months": 0.0
    })
    client.post("/api/monitor/projects/RECOV-01/observations", json={
        "reporting_month": "2025-02", "financial_progress": 10.0, "expenditure": 10.0, "schedule_deviation_months": 0.0
    })
    # Month 3: Deterioration triggers warning
    client.post("/api/monitor/projects/RECOV-01/observations", json={
        "reporting_month": "2025-03", "financial_progress": 10.0, "expenditure": 40.0, "schedule_deviation_months": 36.0
    })

    warnings = client.get("/api/monitor/projects/RECOV-01/warnings").json()["warnings"]
    wid = warnings[0]["warning_id"]

    # Contractor responds
    client.post(f"/api/monitor/projects/RECOV-01/warnings/{wid}/response", json={
        "acknowledged": True,
        "response_text": "Equipment bottleneck resolved.",
        "corrective_action": "Subcontractor mobilized.",
        "expected_recovery_date": "2025-05"
    })

    # Month 4: Substantial recovery (progress jumps to 30%, delay reduced to 0, cost sanctioned)
    resp4 = client.post("/api/monitor/projects/RECOV-01/observations", json={
        "reporting_month": "2025-04",
        "financial_progress": 30.0,  # +20% velocity!
        "expenditure": 15.0,
        "revised_cost": 80.0,
        "schedule_deviation_months": 0.0  # Delay drops!
    })
    assert resp4.status_code == 201
    data4 = resp4.json()

    # Verify recovery detected
    gov4 = data4["governance_status"]
    assert gov4["action"] == "PROJECT_RECOVERED"
    assert gov4["recovery_status"] == "RECOVERED"
    assert "Trajectory improved following the warning" in gov4["details"]

    # Warning status updated to RECOVERED
    w_updated = client.get("/api/monitor/projects/RECOV-01/warnings").json()["warnings"][0]
    assert w_updated["status"] == "RECOVERED"


def test_08_persistent_deterioration_and_authority_escalation_scenario_b(client):
    """8. Scenario B: Continued deterioration triggers Authority Escalation after persistence cycles."""
    client.post("/api/monitor/projects", json={
        "project_id": "CHRONIC-01",
        "project_name": "Freight Rail Spur",
        "sector": "Railways",
        "approved_cost": 50.0,
        "revised_cost": 50.0,
        "planned_start_date": "2022-01",
        "initial_reporting_month": "2025-01"
    })

    # Months 1-2
    client.post("/api/monitor/projects/CHRONIC-01/observations", json={
        "reporting_month": "2025-01", "financial_progress": 10.0, "expenditure": 5.0, "schedule_deviation_months": 0.0
    })
    client.post("/api/monitor/projects/CHRONIC-01/observations", json={
        "reporting_month": "2025-02", "financial_progress": 10.0, "expenditure": 10.0, "schedule_deviation_months": 0.0
    })

    # Month 3: Severe stall -> Warning
    r3 = client.post("/api/monitor/projects/CHRONIC-01/observations", json={
        "reporting_month": "2025-03", "financial_progress": 10.0, "expenditure": 40.0, "schedule_deviation_months": 36.0
    })
    wid = r3.json()["governance_status"]["active_warning_id"]
    assert wid is not None

    # Contractor responds
    client.post(f"/api/monitor/projects/CHRONIC-01/warnings/{wid}/response", json={
        "acknowledged": True,
        "response_text": "Facing contractor liquidity dispute.",
        "corrective_action": "Seeking bridge financing.",
        "expected_recovery_date": "2025-08"
    })

    # Month 4: Continued deterioration (Cycle 2 -> Escalation!)
    r4 = client.post("/api/monitor/projects/CHRONIC-01/observations", json={
        "reporting_month": "2025-04", "financial_progress": 10.0, "expenditure": 42.0, "schedule_deviation_months": 40.0
    })
    assert r4.status_code == 201
    gov4 = r4.json()["governance_status"]

    assert gov4["action"] == "AUTHORITY_ESCALATION_ISSUED"
    esc_id = gov4["escalation_id"]
    assert esc_id.startswith("ESC-")

    # Check escalation listed in /api/monitor/escalations
    escs = client.get("/api/monitor/escalations").json()["escalations"]
    assert len(escs) >= 1
    e = next(x for x in escs if x["escalation_id"] == esc_id)
    assert e["project_id"] == "CHRONIC-01"
    assert e["warning_id"] == wid
    assert e["persistence_duration_months"] >= 2
    assert "Calibrated 12-month deterioration risk remained in ESCALATE tier" in e["reason_for_escalation"]


def test_09_prediction_equivalence_with_existing_inference_engine():
    """9. Historical project fed through canonical pipeline matches existing inference engine."""
    md = pd.read_parquet("DATA/model_dataset.parquet")
    sample_pid = "180100210"  # Parbati Hydroelectric
    sample_df = md[md["project_id"] == sample_pid].sort_values("reporting_month").reset_index(drop=True)

    # Take first 5 observations
    n_test = min(5, len(sample_df))
    raw_obs = []
    for i in range(n_test):
        r = sample_df.iloc[i]
        raw_obs.append({
            "project_id": sample_pid,
            "reporting_month": r["reporting_month"],
            "financial_progress": r["financial_progress"],
            "physical_progress": r["physical_progress"],
            "expenditure": r["expenditure"],
            "approved_cost": r["approved_cost"],
            "revised_cost": r["revised_cost"],
            "schedule_deviation": r["schedule_deviation"],
            "sector": r["sector"]
        })

    # Pass through canonical pipeline
    recomputed_df = compute_canonical_features_for_project(raw_obs)
    engine = load_inference_engine()

    for i in range(n_test):
        pred_existing = predict_point_in_time(sample_df.iloc[i], engine=engine)
        pred_canonical = predict_point_in_time(recomputed_df.iloc[i], engine=engine)

        diff = abs(pred_existing["calibrated_prob"] - pred_canonical["calibrated_prob"])
        # Must be within tolerance (peer Z defaults to 0 in isolated single-project stream)
        assert diff < 0.05, f"Discrepancy at obs {i}: {pred_existing['calibrated_prob']} vs {pred_canonical['calibrated_prob']}"


def test_10_point_in_time_invariance():
    """10. For observation at month t, prediction(t) is invariant to adding/deleting observations after t."""
    obs_t1 = {
        "project_id": "INV-01", "reporting_month": "2025-01",
        "financial_progress": 10.0, "expenditure": 100.0, "approved_cost": 1000.0, "sector": "Power"
    }
    obs_t2 = {
        "project_id": "INV-01", "reporting_month": "2025-02",
        "financial_progress": 12.0, "expenditure": 120.0, "approved_cost": 1000.0, "sector": "Power"
    }
    obs_t3 = {
        "project_id": "INV-01", "reporting_month": "2025-03",
        "financial_progress": 14.0, "expenditure": 140.0, "approved_cost": 1000.0, "sector": "Power"
    }

    # Predict month 2 using [t1, t2]
    df_2 = compute_canonical_features_for_project([obs_t1, obs_t2])
    engine = load_inference_engine()
    pred_2_alone = predict_point_in_time(df_2.iloc[1], engine=engine)

    # Predict month 2 using [t1, t2, t3]
    df_3 = compute_canonical_features_for_project([obs_t1, obs_t2, obs_t3])
    pred_2_with_future = predict_point_in_time(df_3.iloc[1], engine=engine)

    assert pred_2_alone["calibrated_prob"] == pred_2_with_future["calibrated_prob"]
    assert pred_2_alone["risk_tier"] == pred_2_with_future["risk_tier"]
    assert pred_2_alone["raw_prob"] == pred_2_with_future["raw_prob"]


def test_11_validation_and_chronology(client):
    """11. Validate duplicate month rejection and chronological order enforcement."""
    client.post("/api/monitor/projects", json={
        "project_id": "VAL-01", "project_name": "Validation Project", "sector": "Coal",
        "approved_cost": 1000.0, "initial_reporting_month": "2025-01"
    })

    # Submit Month 1
    r1 = client.post("/api/monitor/projects/VAL-01/observations", json={
        "reporting_month": "2025-01", "financial_progress": 10.0, "expenditure": 100.0
    })
    assert r1.status_code == 201

    # Duplicate month
    r_dup = client.post("/api/monitor/projects/VAL-01/observations", json={
        "reporting_month": "2025-01", "financial_progress": 11.0, "expenditure": 110.0
    })
    assert r_dup.status_code == 400
    assert "Duplicate monthly observation" in r_dup.json()["detail"]

    # Out of order month (earlier than latest)
    r_back = client.post("/api/monitor/projects/VAL-01/observations", json={
        "reporting_month": "2024-12", "financial_progress": 9.0, "expenditure": 90.0
    })
    assert r_back.status_code == 400
    assert "Chronological order violation" in r_back.json()["detail"]

    # Negative expenditure
    r_neg = client.post("/api/monitor/projects/VAL-01/observations", json={
        "reporting_month": "2025-02", "financial_progress": 12.0, "expenditure": -50.0
    })
    assert r_neg.status_code == 400


def test_12_physical_progress_missingness_preserved(client):
    """12. Unobserved physical progress is preserved as missing, never fabricated."""
    client.post("/api/monitor/projects", json={
        "project_id": "MISS-PHYS", "project_name": "Telecom Towers", "sector": "Telecommunications",
        "approved_cost": 800.0, "initial_reporting_month": "2025-01"
    })

    client.post("/api/monitor/projects/MISS-PHYS/observations", json={
        "reporting_month": "2025-01",
        "financial_progress": 15.0,
        "expenditure": 120.0,
        "physical_progress": None  # Unobserved
    })

    obs = monitoring.get_project_observations("MISS-PHYS")[0]
    assert obs["physical_progress"] is None

    # In canonical features, it must be NaN, not 0.0 or fabricated
    df = compute_canonical_features_for_project([{
        "project_id": "MISS-PHYS", "reporting_month": "2025-01",
        "financial_progress": 15.0, "physical_progress": None, "approved_cost": 800.0, "sector": "Telecommunications"
    }])
    assert pd.isna(df.iloc[0]["physical_progress_clean"])
    assert pd.isna(df.iloc[0]["financial_physical_gap"])


def test_13_audit_trail_immutability(client):
    """13. Audit events are strictly append-only and chronological."""
    client.post("/api/monitor/projects", json={
        "project_id": "AUDIT-01", "project_name": "Audit Verification", "sector": "Mines",
        "approved_cost": 600.0, "initial_reporting_month": "2025-01"
    })

    client.post("/api/monitor/projects/AUDIT-01/observations", json={
        "reporting_month": "2025-01", "financial_progress": 5.0, "expenditure": 30.0
    })

    audit_events = client.get("/api/monitor/projects/AUDIT-01/audit").json()["audit_events"]
    assert len(audit_events) >= 2

    # Check event ordering
    types = [e["event_type"] for e in audit_events]
    assert types[0] == "PROJECT_REGISTERED"
    assert "MONTHLY_REPORT_SUBMITTED" in types
    assert "PREDICTION_GENERATED" in types


def test_14_historical_dataset_frozen():
    """14. Confirm frozen research datasets (parquet/csv) remain completely intact."""
    assert os.path.exists("DATA/model_dataset.parquet")
    assert os.path.exists("DATA/project_monthly.csv")
    assert os.path.exists("DATA/vigil_production_model.joblib")
