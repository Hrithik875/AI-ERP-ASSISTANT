"""
AI ERP Assistant — Negative & Edge-Case Tests
===============================================
Tests that verify graceful failure handling for:
  - Invalid/nonexistent student USNs
  - Missing required tool parameters
  - Unknown tool names from classification
  - Malformed LLM JSON output
  - Admin console auth (missing/wrong/correct key)
  - Empty/malformed API inputs

Run with: pytest tests/test_negative.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_MODE", "local")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-123")

import pytest
from unittest.mock import patch, MagicMock
import io


_ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "test-admin-key-123")
_WRONG_KEY = "definitely-not-the-right-key"


# ══════════════════════════════════════════════════════════════════════════════
# Admin Console Authentication
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminConsoleAuth:
    """
    Phase 3 introduced ADMIN_API_KEY gate on all /db/* routes.
    These tests verify the gate is working correctly without hitting the DB.
    """

    def test_admin_route_missing_key_returns_401(self, client):
        """No X-Admin-Key header → 401 Unauthorized."""
        response = client.get("/db/tables")
        assert response.status_code == 401, (
            f"Expected 401 for missing X-Admin-Key, got {response.status_code}"
        )

    def test_admin_route_wrong_key_returns_401(self, client):
        """Wrong X-Admin-Key value → 401 Unauthorized."""
        response = client.get("/db/tables", headers={"X-Admin-Key": _WRONG_KEY})
        assert response.status_code == 401, (
            f"Expected 401 for wrong X-Admin-Key, got {response.status_code}"
        )

    def test_admin_route_correct_key_not_401(self, client):
        """Correct X-Admin-Key should NOT return 401. May return 200 or 500 (DB error is ok)."""
        response = client.get("/db/tables", headers={"X-Admin-Key": _ADMIN_KEY})
        assert response.status_code != 401, (
            f"Expected non-401 for correct X-Admin-Key, got {response.status_code}"
        )

    def test_admin_query_missing_key_returns_401(self, client):
        """POST /db/query without key → 401."""
        response = client.post("/db/query", json={"sql": "SELECT 1"})
        assert response.status_code == 401

    def test_admin_query_wrong_key_returns_401(self, client):
        """POST /db/query with wrong key → 401."""
        response = client.post(
            "/db/query",
            json={"sql": "SELECT 1"},
            headers={"X-Admin-Key": _WRONG_KEY},
        )
        assert response.status_code == 401

    def test_admin_error_response_has_detail(self, client):
        """401 response must have a 'detail' field explaining the error."""
        response = client.get("/db/tables")
        assert "detail" in response.json()


# ══════════════════════════════════════════════════════════════════════════════
# Invalid Student USN
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidStudentUSN:
    """Tests for graceful handling of nonexistent/invalid student identifiers."""

    def test_get_nonexistent_student_returns_404(self, client):
        """GET /student/<usn> with a nonexistent USN must return 404."""
        response = client.get("/student/ZZZZZZ999999")
        assert response.status_code == 404

    def test_chat_nonexistent_usn_returns_200_graceful(self, client):
        """
        Asking the AI about a completely made-up USN should return 200 with
        a graceful 'not found' message, not a 500 crash.
        """
        response = client.post("/chat", json={
            "message": "Show attendance for student NONEXISTENT_USN_ABCDEF"
        })
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert isinstance(data["content"], str)
        assert len(data["content"]) > 0  # Should have a graceful message, not empty


# ══════════════════════════════════════════════════════════════════════════════
# Missing Required Tool Parameters
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingToolParameters:
    """Tests that tools return errors for missing/invalid params without crashing."""

    def test_attendance_tool_missing_action_returns_error(self):
        """AttendanceTool with no action should return a dict with 'error' key."""
        from ai.tools.attendance_tool import AttendanceTool
        tool = AttendanceTool()
        with patch("db.connection.execute_query", return_value=[]):
            result = tool.execute({})
        assert isinstance(result, dict)
        assert "error" in result, f"Expected 'error' key, got: {result}"

    def test_attendance_tool_unknown_action_returns_error(self):
        """AttendanceTool with completely unknown action should return error dict."""
        from ai.tools.attendance_tool import AttendanceTool
        tool = AttendanceTool()
        with patch("db.connection.execute_query", return_value=[]):
            result = tool.execute({"action": "nonexistent_action_xyz"})
        assert isinstance(result, dict)
        assert "error" in result

    def test_timetable_tool_missing_day_returns_error(self):
        """TimetableTool day_schedule without 'day' parameter should return error."""
        from ai.tools.timetable_tool import TimetableTool
        tool = TimetableTool()
        with patch("db.connection.execute_query", return_value=[]):
            result = tool.execute({"action": "day_schedule"})  # no 'day' param
        assert isinstance(result, dict)
        assert "error" in result

    def test_timetable_tool_faculty_missing_employee_code_returns_error(self):
        """faculty_schedule without employee_code should return error."""
        from ai.tools.timetable_tool import TimetableTool
        tool = TimetableTool()
        with patch("db.connection.execute_query", return_value=[]):
            result = tool.execute({"action": "faculty_schedule"})
        assert isinstance(result, dict)
        assert "error" in result

    def test_grades_tool_missing_action_returns_error(self):
        """GradesTool with no action should return error dict."""
        from ai.tools.grades_tool import GradesTool
        tool = GradesTool()
        with patch("db.connection.execute_query", return_value=[]):
            result = tool.execute({})
        assert isinstance(result, dict)
        assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# Unknown Tool Name from Classification
# ══════════════════════════════════════════════════════════════════════════════

class TestUnknownToolName:
    """
    When the LLM returns a tool_name that doesn't exist in REGISTERED_TOOLS,
    execute_tool_query should handle it gracefully (no crash, graceful message).
    """

    def test_unknown_tool_name_returns_graceful_string(self):
        """Simulate LLM returning a completely unknown tool name."""
        from ai.agent import execute_tool_query

        fake_json = '{"tool_name": "UnknownTool_XYZ_9999", "params": {"action": "do_something"}}'
        with patch("ai.llm_service.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = fake_json
            mock_get_llm.return_value = mock_llm
            with patch("db.connection.execute_query", return_value=[]):
                answer, source, sources, tool_used = execute_tool_query("what is this?")

        assert isinstance(answer, str)
        assert len(answer) > 0
        # Should not crash — the function returns a graceful message
        assert "error" not in answer.lower() or "could not" in answer.lower() or "encountered" in answer.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Malformed LLM JSON Output
# ══════════════════════════════════════════════════════════════════════════════

class TestMalformedLLMJSON:
    """
    When the LLM returns non-JSON garbage (e.g. "Sorry, I cannot help with that."),
    the agent should catch the JSONDecodeError and return a graceful error response
    rather than propagating an uncaught exception.
    """

    def test_malformed_json_does_not_crash(self):
        """Simulate LLM returning non-JSON; verify no exception is raised."""
        from ai.agent import execute_tool_query

        bad_outputs = [
            "THIS IS NOT JSON AT ALL",
            "Sorry I cannot help with that.",
            "```\nInvalid response\n```",
            "",
            "{broken json: true,,}",
        ]

        for bad_output in bad_outputs:
            with patch("ai.llm_service.get_llm") as mock_get_llm:
                mock_llm = MagicMock()
                mock_llm.generate.return_value = bad_output
                mock_get_llm.return_value = mock_llm
                with patch("db.connection.execute_query", return_value=[]):
                    try:
                        answer, source, sources, tool_used = execute_tool_query(
                            "What is my attendance?",
                            history=[]
                        )
                    except Exception as exc:
                        pytest.fail(
                            f"execute_tool_query raised {type(exc).__name__} for bad LLM output "
                            f"{bad_output!r}: {exc}"
                        )
                    # Must return a graceful response string
                    assert isinstance(answer, str), f"Expected str answer for bad output {bad_output!r}"
                    assert len(answer) > 0

    def test_malformed_json_returns_graceful_answer_via_api(self, client):
        """
        End-to-end: even if the tool-extraction LLM returns garbage,
        the /chat endpoint should return HTTP 200 with a polite message.
        """
        # Patch the LLM used in execute_tool_query to return bad JSON
        with patch("ai.agent.execute_tool_query") as mock_etq:
            mock_etq.return_value = (
                "I encountered an error understanding your request.",
                "JSON Decode Error",
                [],
                "Error",
            )
            response = client.post("/chat", json={"message": "Show attendance for CS601"})

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert isinstance(data["content"], str)


# ══════════════════════════════════════════════════════════════════════════════
# API Input Validation
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIInputValidation:
    """Tests for API-level input validation on all major endpoints."""

    def test_chat_empty_message_400(self, client):
        assert client.post("/chat", json={"message": ""}).status_code == 400

    def test_chat_whitespace_only_400(self, client):
        assert client.post("/chat", json={"message": "   "}).status_code == 400

    def test_chat_missing_key_400(self, client):
        assert client.post("/chat", json={}).status_code == 400

    def test_text_query_empty_400(self, client):
        assert client.post("/text-query", json={"query": ""}).status_code == 400

    def test_text_query_missing_key_400(self, client):
        assert client.post("/text-query", json={}).status_code == 400

    def test_voice_input_no_file_422(self, client):
        assert client.post("/voice-input").status_code == 422
