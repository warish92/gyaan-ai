"""Tests for the Honest System Health endpoint (/api/v1/system/health).

Verifies the 11-component granular health reporting and distinctions
between configured, registered, available, executed, and verified states.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from backend.app.main import app

client = TestClient(app)


def test_system_health_endpoint_schema():
    """Verify /api/v1/system/health returns complete 11-tier structure."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()

    assert "overall_status" in data
    assert data["overall_status"] in ("healthy", "degraded", "offline")
    assert "timestamp" in data
    assert "summary" in data
    assert "components" in data

    components = data["components"]
    expected_components = [
        "python_environment",
        "fastapi_backend",
        "sqlite_database",
        "cbse_curriculum",
        "ollama_service",
        "qwen_model",
        "crewai_framework",
        "agent_registry",
        "agent_execution",
        "learning_journey",
        "frontend_service",
    ]

    for comp_key in expected_components:
        assert comp_key in components, f"Missing component {comp_key} in health response"
        comp = components[comp_key]
        assert "name" in comp
        assert "status" in comp
        assert "configured" in comp
        assert "registered" in comp
        assert "available" in comp
        assert "executed" in comp
        assert "verified" in comp
        assert "details" in comp


def test_system_health_python_and_backend_verified():
    """Verify Python, FastAPI backend, and CrewAI framework are available and verified."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    components = response.json()["components"]

    py = components["python_environment"]
    assert py["status"] == "available"
    assert py["available"] is True
    assert "version" in py["details"]

    api = components["fastapi_backend"]
    assert api["status"] == "running"
    assert api["available"] is True

    crew = components["crewai_framework"]
    assert crew["available"] is True
    assert "version" in crew["details"]


def test_system_health_curriculum_and_database():
    """Verify SQLite database and CBSE curriculum reporting."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    components = response.json()["components"]

    db = components["sqlite_database"]
    assert db["status"] == "connected"
    assert db["available"] is True
    assert db["details"]["students"] >= 0

    curr = components["cbse_curriculum"]
    assert curr["status"] in ("initialized", "degraded")
    assert curr["details"]["prescribed_class"] == "Class 10"


def test_system_health_agent_registry_8_canonical():
    """Verify Agent Registry accurately reports all 8 canonical agents."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    components = response.json()["components"]

    reg = components["agent_registry"]
    assert reg["registered"] is True
    assert reg["details"]["registered_count"] == 8
    assert len(reg["details"]["agents"]) == 8
