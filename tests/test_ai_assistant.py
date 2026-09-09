import pytest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from sanket.api import app

client = TestClient(app)

@pytest.fixture
def mock_gemini_client():
    with patch("sanket.api.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_models = MagicMock()
        
        # Create a fake response that matches the AIFindingsResponse schema
        fake_response_text = json.dumps({
            "summary": "This is a mock summary.",
            "key_findings": ["Finding 1"],
            "evidence": ["Evidence 1"],
            "governance_status": "Watch",
            "recommended_review": "Review contractor reports."
        })
        
        mock_response = MagicMock()
        mock_response.text = fake_response_text
        mock_models.generate_content.return_value = mock_response
        
        mock_client.models = mock_models
        mock_client_cls.return_value = mock_client
        yield mock_client_cls


def test_ai_endpoint_validates_project_id():
    """Test that the endpoint returns 422 if payload is missing project_id."""
    response = client.post("/api/ai/project-brief", json={})
    assert response.status_code == 422

def test_ai_endpoint_404_for_invalid_project():
    """Test that the endpoint returns 404 for unknown project."""
    response = client.post("/api/ai/project-brief", json={"project_id": "INVALID-123"})
    assert response.status_code == 404

def test_ai_endpoint_success_with_demo_recovery(mock_gemini_client):
    """Test that the AI endpoint successfully processes a demo project."""
    # Ensure demo project is seeded
    client.post("/api/monitor/demo/seed?scenario=1")
    
    # Needs GEMINI_API_KEY to not immediately 503
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
        response = client.post("/api/ai/project-brief", json={"project_id": "PRJ-DEMO-RECOVERY-01"})
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "key_findings" in data
        assert data["summary"] == "This is a mock summary."

def test_ai_endpoint_success_with_demo_escalate(mock_gemini_client):
    """Test that the AI endpoint successfully processes the escalation demo project."""
    client.post("/api/monitor/demo/seed?scenario=2")
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
        response = client.post("/api/ai/project-brief", json={"project_id": "PRJ-DEMO-ESCALATE-02"})
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data

def test_ai_endpoint_fails_gracefully_without_api_key():
    """Test that the endpoint returns 503 if API key is missing."""
    client.post("/api/monitor/demo/seed?scenario=1")
    
    with patch.dict(os.environ, clear=True):
        response = client.post("/api/ai/project-brief", json={"project_id": "PRJ-DEMO-RECOVERY-01"})
        
        assert response.status_code == 503
        assert "missing configuration" in response.json()["detail"]

def test_ai_endpoint_fails_gracefully_on_gemini_error(mock_gemini_client):
    """Test that the endpoint returns 503 if Gemini throws an error."""
    client.post("/api/monitor/demo/seed?scenario=1")
    
    # Make the mock raise an exception
    mock_instance = mock_gemini_client.return_value
    mock_instance.models.generate_content.side_effect = Exception("Gemini Quota Exceeded")
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
        response = client.post("/api/ai/project-brief", json={"project_id": "PRJ-DEMO-RECOVERY-01"})
        
        assert response.status_code == 503
        assert "Gemini Quota Exceeded" in response.json()["detail"]

def test_ai_endpoint_does_not_modify_backend_state(mock_gemini_client):
    """Test that calling the AI endpoint does not alter the underlying model state."""
    client.post("/api/monitor/demo/seed?scenario=1")
    
    # Check original state
    orig_res = client.get("/api/monitor/projects/PRJ-DEMO-RECOVERY-01/status")
    orig_status = orig_res.json().get("current_status")
    
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
        # Call AI endpoint
        client.post("/api/ai/project-brief", json={"project_id": "PRJ-DEMO-RECOVERY-01"})
        
    # Check new state
    new_res = client.get("/api/monitor/projects/PRJ-DEMO-RECOVERY-01/status")
    new_status = new_res.json().get("current_status")
    
    assert orig_status == new_status
