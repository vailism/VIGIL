"""
tests/test_demo_scenarios.py

Deterministic tests for VIGIL Demo Scenarios:
1. Scenario 1: Contractor Recovery Workflow (5 Months)
2. Scenario 2: Authority Escalation Workflow (7 Months)
3. Reproducibility, idempotency, and REST API seeding endpoints.
"""

import os
import pytest
from fastapi.testclient import TestClient

from sanket import monitoring, demo_scenarios
from sanket.api import app


@pytest.fixture
def temp_demo_db(tmp_path):
    """Provide an isolated test database for demo scenario testing."""
    db_file = str(tmp_path / "test_demo_scenarios.db")
    monitoring.init_db(db_file)
    return db_file


def test_scenario_1_recovery_workflow_deterministic_execution(temp_demo_db):
    """
    Test Scenario 1 (5 Months: Healthy -> Deterioration -> Warning -> Response -> Recovered).
    Verifies every monthly step, risk tier, governance transition, and recovery.
    """
    res = demo_scenarios.execute_scenario_1(db_path=temp_demo_db, reset=True)

    assert res["scenario_id"] == "SCENARIO_1_RECOVERY"
    assert res["total_months"] == 5
    assert res["project_id"] == "PRJ-DEMO-RECOVERY-01"

    history = res["history"]
    assert len(history) == 5

    # Month 1: Project appears healthy, sufficient baseline info
    m1 = history[0]
    assert m1["month"] == 1
    assert m1["reporting_month"] == "2024-01"
    assert m1["calibrated_prob"] < 0.50
    assert m1["risk_tier"] == "WATCH"
    assert m1["governance_action"] == "NONE"

    # Month 2: Small deterioration begins
    m2 = history[1]
    assert m2["month"] == 2
    assert m2["reporting_month"] == "2024-02"
    assert m2["calibrated_prob"] < 0.50
    assert m2["risk_tier"] == "WATCH"
    assert m2["governance_action"] == "NONE"

    # Month 3: Trajectory deterioration becomes significant -> CONTRACTOR_WARNING
    m3 = history[2]
    assert m3["month"] == 3
    assert m3["reporting_month"] == "2024-03"
    assert m3["calibrated_prob"] >= 0.50
    assert m3["risk_tier"] == "ESCALATE"
    assert m3["governance_action"] == "CONTRACTOR_WARNING_ISSUED"

    # Check warning issuance in DB
    warnings = monitoring.get_project_warnings(res["project_id"], db_path=temp_demo_db)
    assert len(warnings) == 1
    w3 = warnings[0]
    assert w3["status"] in ["RECOVERED", "RESPONSE_SUBMITTED", "ACTIVE", "PERSISTENT_DETERIORATION"]

    # Month 4: Contractor submits corrective action; measurable recovery evidence appears
    m4 = history[3]
    assert m4["month"] == 4
    assert m4["reporting_month"] == "2024-04"
    assert m4["calibrated_prob"] >= 0.50
    assert m4["governance_action"] == "NONE"
    assert m4["recovery_status"] == "PERSISTENT_DETERIORATION"

    # Month 5: Trajectory improves -> Project becomes RECOVERED
    m5 = history[4]
    assert m5["month"] == 5
    assert m5["reporting_month"] == "2024-05"
    assert m5["calibrated_prob"] < 0.50
    assert m5["risk_tier"] == "WATCH"
    assert m5["governance_action"] == "PROJECT_RECOVERED"
    assert m5["recovery_status"] == "RECOVERED"

    # Verify final project and warning status
    final_status = monitoring.get_project_status(res["project_id"], db_path=temp_demo_db)
    assert final_status["governance_state"] == "RECOVERED"
    assert final_status["active_warning"]["status"] == "RECOVERED"

    updated_warnings = monitoring.get_project_warnings(res["project_id"], db_path=temp_demo_db)
    assert updated_warnings[0]["status"] == "RECOVERED"

    # Verify audit events ledger recorded the lifecycle
    audit = monitoring.get_audit_trail(res["project_id"], db_path=temp_demo_db)
    event_types = [a["event_type"] for a in audit]
    assert "PROJECT_REGISTERED" in event_types
    assert "CONTRACTOR_WARNING_ISSUED" in event_types
    assert "CONTRACTOR_RESPONSE_RECEIVED" in event_types
    assert "RECOVERY_DETECTED" in event_types


def test_scenario_2_escalation_workflow_deterministic_execution(temp_demo_db):
    """
    Test Scenario 2 (7 Months: Deterioration -> Warning -> Response -> Persistent -> Escalation).
    Verifies every monthly step, persistence window, and government escalation.
    """
    res = demo_scenarios.execute_scenario_2(db_path=temp_demo_db, reset=True)

    assert res["scenario_id"] == "SCENARIO_2_ESCALATION"
    assert res["total_months"] == 7
    assert res["project_id"] == "PRJ-DEMO-ESCALATE-02"

    history = res["history"]
    assert len(history) == 7

    # Month 1-3: Deterioration develops across cycles, still below ESCALATE
    for idx in range(3):
        m = history[idx]
        assert m["calibrated_prob"] < 0.50
        assert m["risk_tier"] in ["NORMAL", "WATCH", "REVIEW"]
        assert m["governance_action"] == "NONE"

    # Month 4: CONTRACTOR_WARNING
    m4 = history[3]
    assert m4["month"] == 4
    assert m4["reporting_month"] == "2025-01"
    assert m4["calibrated_prob"] >= 0.50
    assert m4["risk_tier"] == "ESCALATE"
    assert m4["governance_action"] == "CONTRACTOR_WARNING_ISSUED"

    # Month 5: Contractor response exists but no measurable recovery
    m5 = history[4]
    assert m5["month"] == 5
    assert m5["reporting_month"] == "2025-02"
    assert m5["calibrated_prob"] >= 0.50
    assert m5["governance_action"] == "NONE"
    assert m5["recovery_status"] == "PERSISTENT_DETERIORATION"

    # Month 6: Deterioration persists
    m6 = history[5]
    assert m6["month"] == 6
    assert m6["reporting_month"] == "2025-03"
    assert m6["calibrated_prob"] >= 0.50
    assert m6["governance_action"] == "NONE"
    assert m6["recovery_status"] == "PERSISTENT_DETERIORATION"

    # Month 7: Unresponsive recovery -> AUTHORITY_ESCALATION
    m7 = history[6]
    assert m7["month"] == 7
    assert m7["reporting_month"] == "2025-04"
    assert m7["calibrated_prob"] >= 0.50
    assert m7["governance_action"] == "AUTHORITY_ESCALATION_ISSUED"
    assert m7["recovery_status"] == "PERSISTENT_DETERIORATION"

    # Verify final project state and escalation record
    final_status = monitoring.get_project_status(res["project_id"], db_path=temp_demo_db)
    assert final_status["governance_state"] == "ESCALATED"

    escalations = monitoring.get_authority_escalations(db_path=temp_demo_db)
    assert len(escalations) == 1
    esc = escalations[0]
    assert esc["project_id"] == "PRJ-DEMO-ESCALATE-02"
    assert esc["persistence_duration_months"] >= 4
    assert "contractor_response" in esc
    assert esc["response_status"] == "RESPONSE_SUBMITTED"

    # Verify audit trail contains full escalation sequence
    audit = monitoring.get_audit_trail(res["project_id"], db_path=temp_demo_db)
    event_types = [a["event_type"] for a in audit]
    assert "CONTRACTOR_WARNING_ISSUED" in event_types
    assert "CONTRACTOR_RESPONSE_RECEIVED" in event_types
    assert "PERSISTENT_DETERIORATION_DETECTED" in event_types
    assert "AUTHORITY_ESCALATION_ISSUED" in event_types


def test_demo_scenarios_idempotency(temp_demo_db):
    """
    Test that running demo scenario generators repeatedly is safe and idempotent.
    """
    r1_first = demo_scenarios.execute_scenario_1(db_path=temp_demo_db, reset=True)
    r1_second = demo_scenarios.execute_scenario_1(db_path=temp_demo_db, reset=True)

    assert r1_first["total_months"] == r1_second["total_months"] == 5
    assert r1_first["final_status"]["governance_state"] == r1_second["final_status"]["governance_state"] == "RECOVERED"

    r2_first = demo_scenarios.execute_scenario_2(db_path=temp_demo_db, reset=True)
    r2_second = demo_scenarios.execute_scenario_2(db_path=temp_demo_db, reset=True)

    assert r2_first["total_months"] == r2_second["total_months"] == 7
    assert r2_first["final_status"]["governance_state"] == r2_second["final_status"]["governance_state"] == "ESCALATED"


def test_api_demo_seed_endpoint(monkeypatch, temp_demo_db):
    """
    Test the FastAPI endpoint POST /api/monitor/demo/seed.
    """
    monkeypatch.setattr(monitoring, "DEFAULT_DB_PATH", temp_demo_db)

    client = TestClient(app)

    # Seed scenario 1
    resp1 = client.post("/api/monitor/demo/seed?scenario=1")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "SUCCESS"
    assert data1["scenario_1"]["project_id"] == "PRJ-DEMO-RECOVERY-01"

    # Verify via public GET API
    p_resp = client.get("/api/monitor/projects/PRJ-DEMO-RECOVERY-01/status")
    assert p_resp.status_code == 200
    assert p_resp.json()["governance_state"] == "RECOVERED"

    # Seed scenario 2
    resp2 = client.post("/api/monitor/demo/seed?scenario=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "SUCCESS"
    assert data2["scenario_2"]["project_id"] == "PRJ-DEMO-ESCALATE-02"

    # Verify escalations endpoint
    esc_resp = client.get("/api/monitor/escalations")
    assert esc_resp.status_code == 200
    assert esc_resp.json()["total"] == 1
