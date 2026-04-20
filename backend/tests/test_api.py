"""
AI ERP Assistant — API Integration Tests
==========================================
Tests all REST endpoints for expected behavior.
Run with: pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient

# We need to be able to import from the backend root
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_required_fields(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["llm_provider"] == "amazon-bedrock"
        assert data["database"] == "aurora-mysql"
        assert data["vector_db"] == "qdrant"
        assert "region" in data
        assert "bucket" in data
        assert "timestamp" in data


class TestChatEndpoint:
    """Tests for POST /chat"""

    def test_chat_empty_message_returns_400(self, client):
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 400

    def test_chat_missing_message_returns_400(self, client):
        response = client.post("/chat", json={})
        assert response.status_code == 400

    def test_chat_valid_message_returns_response(self, client):
        response = client.post("/chat", json={"message": "What is my attendance?"})
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "id" in data
        assert data["role"] == "assistant"
        assert "query_type" in data

    def test_chat_returns_query_type(self, client):
        response = client.post("/chat", json={"message": "Show me grades"})
        data = response.json()
        assert data.get("query_type") in ["erp", "document", "general"]


class TestTextQueryEndpoint:
    """Tests for POST /text-query"""

    def test_text_query_returns_response(self, client):
        response = client.post("/text-query", json={"query": "List all students"})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "query_type" in data


class TestVoiceEndpoint:
    """Tests for POST /voice-input"""

    def test_voice_input_no_file_returns_422(self, client):
        response = client.post("/voice-input")
        assert response.status_code == 422


class TestAnalyticsEndpoint:
    """Tests for GET /analytics and GET /dashboard/stats"""

    def test_analytics_returns_200(self, client):
        response = client.get("/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "queriesPerDay" in data
        assert "usageStats" in data
        assert "responseTimes" in data

    def test_dashboard_stats_returns_200(self, client):
        response = client.get("/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "totalQueries" in data
        assert "avgResponse" in data
        assert "successRate" in data
        assert "recentQueries" in data


class TestDocumentsEndpoint:
    """Tests for /documents"""

    def test_list_documents_returns_200(self, client):
        response = client.get("/documents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestStudentsEndpoint:
    """Tests for /students and related"""

    def test_list_students_returns_200(self, client):
        response = client.get("/students")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_students_with_filters(self, client):
        response = client.get("/students?department=Computer Science&semester=6")
        assert response.status_code == 200

    def test_get_student_not_found(self, client):
        response = client.get("/student/NONEXISTENT")
        assert response.status_code == 404


class TestAttendanceEndpoint:
    """Tests for GET /attendance"""

    def test_attendance_returns_200(self, client):
        response = client.get("/attendance")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_attendance_with_student_filter(self, client):
        response = client.get("/attendance?student_id=CS2021001")
        assert response.status_code == 200


class TestGradesEndpoint:
    """Tests for GET /grades"""

    def test_grades_returns_200(self, client):
        response = client.get("/grades")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestFacultyEndpoint:
    """Tests for GET /faculty"""

    def test_faculty_returns_200(self, client):
        response = client.get("/faculty")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """
    Create a test client for the FastAPI app.
    Uses the real app with real Aurora MySQL connections.
    Requires a running Aurora MySQL instance.
    """
    from main import app
    with TestClient(app) as c:
        yield c
