"""
AI ERP Assistant — API Integration Tests (Mode-Aware)
======================================================
Tests all REST endpoints for expected behavior.

All assertions are mode-aware: values are derived from APP_MODE (local or aws)
rather than hardcoded to AWS-specific strings.

Run with: pytest tests/test_api.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ── Mode-aware expected values ───────────────────────────────────────────────

_APP_MODE = os.environ.get("APP_MODE", "local")

_EXPECTED_LLM_PROVIDER = {
    "local": "OllamaLLMProvider",
    "aws": "AWSLLMProvider",
}.get(_APP_MODE, "OllamaLLMProvider")

_EXPECTED_EMBEDDING_PROVIDER = {
    "local": "OllamaEmbeddingProvider",
    "aws": "AWSEmbeddingProvider",
}.get(_APP_MODE, "OllamaEmbeddingProvider")


# ══════════════════════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_required_fields(self, client):
        """
        Mode-aware assertions: llm_provider is the class name returned by
        type(provider).__name__, which differs between local and AWS modes.
        The 'region' and 'bucket' fields are NOT in the health response schema
        (they were AWS-only fields that were removed). The 'mode' field IS present.
        """
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        # Mode-aware: OllamaLLMProvider (local), AWSLLMProvider (aws), or _StubLLM (mocked)
        assert data["llm_provider"] in (_EXPECTED_LLM_PROVIDER, "_StubLLM"), (
            f"Expected llm_provider in ({_EXPECTED_LLM_PROVIDER!r}, '_StubLLM'), "
            f"got {data.get('llm_provider')!r}"
        )
        assert data["database"] == "aurora-mysql"
        assert data["vector_db"] == "qdrant"
        assert "mode" in data, "Health response must include 'mode' field"
        assert "timestamp" in data

    def test_health_mode_matches_env(self, client):
        """Health endpoint should report the actual APP_MODE from environment."""
        response = client.get("/health")
        data = response.json()
        assert data["mode"] == _APP_MODE


# ══════════════════════════════════════════════════════════════════════════════
# Chat
# ══════════════════════════════════════════════════════════════════════════════

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
        assert response.status_code == 200
        data = response.json()
        assert data.get("query_type") in ["erp", "document", "general"]

    def test_chat_returns_tool_used(self, client):
        """tool_used field should be present in every chat response (added in Phase 5)."""
        response = client.post("/chat", json={"message": "Show me attendance for CS601"})
        assert response.status_code == 200
        data = response.json()
        assert "tool_used" in data, "tool_used field must be present in chat response"

    def test_chat_returns_sources(self, client):
        """sources field should always be present (may be empty list for ERP queries)."""
        response = client.post("/chat", json={"message": "What is my attendance?"})
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_chat_accepts_history(self, client):
        """Bounded history should be accepted without error."""
        history = [
            {"role": "user", "content": "Show attendance for CS601"},
            {"role": "assistant", "content": "Average attendance for CS601 is 87.58%."},
        ]
        response = client.post("/chat", json={
            "message": "Which student has the lowest attendance?",
            "history": history,
        })
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Text Query
# ══════════════════════════════════════════════════════════════════════════════

class TestTextQueryEndpoint:
    """Tests for POST /text-query"""

    def test_text_query_returns_response(self, client):
        response = client.post("/text-query", json={"query": "List all students"})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "query_type" in data

    def test_text_query_returns_tool_used(self, client):
        response = client.post("/text-query", json={"query": "Show attendance"})
        assert response.status_code == 200
        assert "tool_used" in response.json()

    def test_text_query_empty_returns_400(self, client):
        response = client.post("/text-query", json={"query": ""})
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Voice
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceEndpoint:
    """Tests for POST /voice-input"""

    def test_voice_input_no_file_returns_422(self, client):
        response = client.post("/voice-input")
        assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# Analytics
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Documents
# ══════════════════════════════════════════════════════════════════════════════

class TestDocumentsEndpoint:
    """Tests for /documents"""

    def test_list_documents_returns_200(self, client):
        response = client.get("/documents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# Students
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Attendance
# ══════════════════════════════════════════════════════════════════════════════

class TestAttendanceEndpoint:
    """Tests for GET /attendance"""

    def test_attendance_returns_200(self, client):
        response = client.get("/attendance")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_attendance_with_student_filter(self, client):
        response = client.get("/attendance?student_id=CS2021001")
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Grades
# ══════════════════════════════════════════════════════════════════════════════

class TestGradesEndpoint:
    """Tests for GET /grades"""

    def test_grades_returns_200(self, client):
        response = client.get("/grades")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# Faculty
# ══════════════════════════════════════════════════════════════════════════════

class TestFacultyEndpoint:
    """Tests for GET /faculty"""

    def test_faculty_returns_200(self, client):
        response = client.get("/faculty")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
