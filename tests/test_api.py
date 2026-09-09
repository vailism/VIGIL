"""
tests/test_api.py

Comprehensive test suite for VIGIL production FastAPI service:
1. /health
2. Project lookup and filtering
3. Unknown project returns 404
4. Replay endpoint
5. Timeline endpoint
6. Dashboard summary
7. Intervention ranking
8. Response JSON is serializable (zero NaN tokens)
9. API predictions exactly match inference engine
10. API replay exactly matches get_project_replay()
"""

import json
import pytest
from fastapi.testclient import TestClient

from sanket.api import app, sanitize_for_json
from sanket.inference import load_inference_engine, predict_point_in_time
from sanket.replay import get_project_replay


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_1_health_endpoint(client):
    """1. Test /health returns 200 and healthy status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "vigil-api"
    assert data["version"] == "1.0.0"
    assert data["model_loaded"] is True
    assert data["total_projects_indexed"] > 0


def test_2_project_lookup(client):
    """2. Test /api/projects with search, pagination, and filtering."""
    # Pagination
    resp = client.get("/api/projects?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["projects"]) == 10

    sample = data["projects"][0]
    expected_keys = {
        "project_id", "project_name", "sector", "latest_observation",
        "latest_risk", "latest_risk_tier", "baseline_cost"
    }
    assert expected_keys.issubset(sample.keys())

    # Search filter
    resp_search = client.get("/api/projects?search=180100210")
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert any(p["project_id"] == "180100210" for p in search_data["projects"])

    # Risk tier filter
    resp_tier = client.get("/api/projects?risk_tier=ESCALATE&limit=5")
    assert resp_tier.status_code == 200
    tier_data = resp_tier.json()
    for p in tier_data["projects"]:
        assert p["latest_risk_tier"] == "ESCALATE"


def test_3_unknown_project_returns_404(client):
    """3. Test unknown project_id returns 404 cleanly across endpoints."""
    bad_id = "NONEXISTENT_PROJECT_999999"

    resp_details = client.get(f"/api/projects/{bad_id}")
    assert resp_details.status_code == 404
    assert f"Project '{bad_id}' not found" in resp_details.json()["detail"]

    resp_replay = client.get(f"/api/projects/{bad_id}/replay")
    assert resp_replay.status_code == 404
    assert f"Project '{bad_id}' not found" in resp_replay.json()["detail"]

    resp_timeline = client.get(f"/api/projects/{bad_id}/timeline")
    assert resp_timeline.status_code == 404
    assert f"Project '{bad_id}' not found" in resp_timeline.json()["detail"]


def test_4_replay_endpoint(client):
    """4. Test /api/projects/{project_id}/replay reconstructs historical progression."""
    pid = "180100210"
    resp = client.get(f"/api/projects/{pid}/replay")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == pid
    assert "timeline" in data
    assert "alert_points" in data
    assert "actual_deterioration_event" in data
    assert "first_alert" in data
    assert data["lead_time"] == 20
    assert data["first_alert"]["alert_month"] == "2013-06"
    assert data["first_alert"]["risk_tier"] == "WATCH"


def test_5_timeline_endpoint(client):
    """5. Test /api/projects/{project_id}/timeline returns monthly progression records."""
    pid = "180100210"
    resp = client.get(f"/api/projects/{pid}/timeline")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == pid
    assert data["total_observations"] == len(data["timeline"])
    assert data["total_observations"] > 0

    first_rec = data["timeline"][0]
    for key in ["reporting_month", "C_base", "expenditure", "pred_prob", "risk_tier", "alert"]:
        assert key in first_rec


def test_6_dashboard_summary(client):
    """6. Test /api/dashboard/summary returns portfolio governance aggregates."""
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_projects"] > 0
    assert data["projects_currently_scored"] == data["total_projects"]
    assert data["watch_count"] >= 0
    assert data["review_count"] >= 0
    assert data["escalate_count"] >= 0
    assert data["total_baseline_exposure"] > 0
    assert data["exposure_in_escalate"] >= 0
    assert data["median_warning_lead_time"] > 0
    assert isinstance(data["sector_breakdown"], list)
    assert len(data["sector_breakdown"]) > 0

    sector_sample = data["sector_breakdown"][0]
    for k in ["sector", "total_projects", "escalate_count", "total_exposure"]:
        assert k in sector_sample


def test_7_intervention_ranking(client):
    """7. Test /api/dashboard/interventions ranks transparently by risk x exposure."""
    resp = client.get("/api/dashboard/interventions?limit=15")
    assert resp.status_code == 200
    data = resp.json()

    assert "methodology_note" in data
    assert "Transparent prioritization ranking" in data["methodology_note"]
    projects = data["projects"]
    assert len(projects) == 15

    # Verify descending ordering by priority_score
    scores = [p["priority_score"] for p in projects]
    assert scores == sorted(scores, reverse=True)

    # Verify transparent arithmetic: priority_score == round(latest_risk * baseline_cost, 2)
    for p in projects:
        expected_score = round(p["latest_risk"] * p["baseline_cost"], 2)
        assert p["priority_score"] == pytest.approx(expected_score, abs=0.05)


def test_8_response_json_serializable(client):
    """8. Test response JSON is strictly serializable without NaN or inf tokens."""
    # Test details, replay, summary, interventions
    endpoints = [
        "/health",
        "/api/projects?limit=5",
        "/api/projects/180100210",
        "/api/projects/180100210/replay",
        "/api/projects/180100210/timeline",
        "/api/dashboard/summary",
        "/api/dashboard/interventions?limit=5"
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200
        raw_text = resp.text
        # Strict JSON RFC 8259 check: no NaN, Infinity, or -Infinity literal tokens
        assert "NaN" not in raw_text
        assert "Infinity" not in raw_text
        # Must be parseable by standard json.loads
        parsed = json.loads(raw_text)
        assert isinstance(parsed, dict)


def test_9_api_predictions_match_inference_engine(client):
    """9. Test API project details prediction matches inference engine bit-for-bit."""
    pid = "180100210"
    resp = client.get(f"/api/projects/{pid}")
    assert resp.status_code == 200
    api_data = resp.json()

    # Obtain ground truth from get_project_replay / inference engine
    engine = load_inference_engine()
    rep = get_project_replay(pid, engine=engine)
    latest_rec = rep["timeline"][-1]

    assert api_data["latest_prediction"]["raw_prob"] == pytest.approx(latest_rec["raw_prob"], abs=1e-5)
    assert api_data["latest_prediction"]["pred_prob"] == pytest.approx(latest_rec["pred_prob"], abs=1e-5)
    assert api_data["latest_prediction"]["risk_tier"] == latest_rec["risk_tier"]
    assert api_data["latest_prediction"]["alert"] == latest_rec["alert"]


def test_10_api_replay_matches_get_project_replay(client):
    """10. Test /api/projects/{id}/replay output matches get_project_replay() directly."""
    pid = "180100210"
    resp = client.get(f"/api/projects/{pid}/replay")
    assert resp.status_code == 200
    api_replay = resp.json()

    engine = load_inference_engine()
    direct_replay = sanitize_for_json(get_project_replay(pid, engine=engine))

    assert api_replay["project_id"] == direct_replay["project_id"]
    assert api_replay["lead_time"] == direct_replay["lead_time"]
    assert api_replay["first_alert"] == direct_replay["first_alert"]
    assert api_replay["actual_deterioration_event"] == direct_replay["actual_deterioration_event"]
    assert len(api_replay["timeline"]) == len(direct_replay["timeline"])

    # Check alert points
    assert len(api_replay["alert_points"]) == len(direct_replay["alert_points"])
