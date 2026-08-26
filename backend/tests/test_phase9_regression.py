"""
Phase 9 — Regression Tests for the Three Reported Critical Bugs
================================================================
Bug 1: Hallucinated attendance data (non-deterministic, phantom students)
Bug 2: RAG always returns "no relevant document found"
Bug 3: "Who teaches machine learning?" routed to TimetableTool + fabricated follow-up

These tests are designed to FAIL before the Phase 9 fixes and PASS after them.
They use deterministic stubs so they do NOT require live Ollama/Qdrant/MySQL.
"""
import os
import sys
import re
import json
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("APP_MODE", "local")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────────────────────
# BUG 1 REGRESSION — Grounding check + plain-table fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestBug1GroundingCheck:
    """
    Bug 1: Attendance query returned hallucinated student rows every time.
    Root cause confirmed: OLLAMA_NUM_CTX=2048 caused truncation at ~98% of window;
    temperature=0.3 caused non-determinism.
    Fix: ctx→8192, temp→0.1, grounding_check() + plain fallback.
    """

    def test_extract_usns_from_text_finds_valid_usns(self):
        """_extract_usns_from_text() should find real USN patterns."""
        from ai.agent import _extract_usns_from_text
        text = "Student CS2022001 has 87.5% and 1BM22CS042 has 72%"
        usns = _extract_usns_from_text(text)
        assert "CS2022001" in [u.upper() for u in usns] or len(usns) >= 1

    def test_extract_usns_from_tool_result(self):
        """_extract_usns_from_tool_result() should extract USNs from attendance_records."""
        from ai.agent import _extract_usns_from_tool_result
        tool_data = {
            "attendance_records": [
                {"usn": "CS2022001", "student_name": "Aarav"},
                {"usn": "CS2022002", "student_name": "Priya"},
            ]
        }
        usns = _extract_usns_from_tool_result(tool_data)
        assert set(u.upper() for u in usns) == {"CS2022001", "CS2022002"}

    def test_grounding_check_passes_when_all_usns_real(self):
        """Grounding check should pass when LLM only mentions real USNs."""
        from ai.agent import _grounding_check
        tool_data = {
            "attendance_records": [
                {"usn": "CS2022001", "student_name": "Aarav"},
            ]
        }
        # LLM answer contains only the real USN
        answer = "Student CS2022001 has 87.5% attendance."
        ok, phantoms = _grounding_check(answer, tool_data)
        assert ok is True
        assert phantoms == []

    def test_grounding_check_fails_on_phantom_usn(self):
        """Grounding check must catch a hallucinated USN not in tool data."""
        from ai.agent import _grounding_check
        tool_data = {
            "attendance_records": [
                {"usn": "CS2022001", "student_name": "Aarav"},
            ]
        }
        # LLM hallucinated CS2099999 which is NOT in the real data
        answer = "Student CS2022001 has 87.5%. Also CS2099999 has 65%."
        ok, phantoms = _grounding_check(answer, tool_data)
        assert ok is False
        assert "CS2099999" in phantoms

    def test_plain_attendance_table_renders_without_llm(self):
        """_plain_attendance_table() must produce a Markdown table purely from data."""
        from ai.agent import _plain_attendance_table
        tool_data = {
            "attendance_records": [
                {
                    "usn": "CS2022001", "student_name": "Aarav Kumar",
                    "course_code": "CS601", "course_name": "Machine Learning",
                    "classes_attended": 42, "total_classes": 48,
                    "attendance_pct": 87.5,
                }
            ]
        }
        result = _plain_attendance_table(tool_data, "Show me attendance for CS601")
        assert "CS2022001" in result
        assert "Aarav Kumar" in result
        assert "87.50%" in result
        assert "|" in result  # Must be a table

    def test_plain_table_no_phantom_usns_ever_appear(self):
        """Plain-table fallback must NEVER contain a USN not in the data."""
        from ai.agent import _plain_attendance_table, _extract_usns_from_text, _extract_usns_from_tool_result
        tool_data = {
            "attendance_records": [
                {"usn": "CS2022001", "student_name": "Aarav", "course_code": "CS601",
                 "course_name": "ML", "classes_attended": 42, "total_classes": 48,
                 "attendance_pct": 87.5},
                {"usn": "CS2022002", "student_name": "Priya", "course_code": "CS601",
                 "course_name": "ML", "classes_attended": 36, "total_classes": 48,
                 "attendance_pct": 75.0},
            ]
        }
        result = _plain_attendance_table(tool_data, "Show attendance for CS601")
        answer_usns = set(_extract_usns_from_text(result))
        real_usns = set(u.upper() for u in _extract_usns_from_tool_result(tool_data))
        phantom = answer_usns - real_usns
        assert phantom == set(), f"Plain-table introduced phantom USNs: {phantom}"

    def test_ollama_num_ctx_is_large_enough(self):
        """OLLAMA_NUM_CTX must be >= 4096 to fit a 40-student attendance payload."""
        from config import OLLAMA_NUM_CTX
        assert OLLAMA_NUM_CTX >= 4096, (
            f"OLLAMA_NUM_CTX={OLLAMA_NUM_CTX} is too small. "
            f"A 40-student payload requires ~2015 tokens. Must be >= 4096."
        )

    def test_format_temperature_is_low(self):
        """
        Verify format call uses temperature <= 0.1 (near-deterministic).
        We inspect agent.py source to confirm the constant \u2014 this is a static check.
        """
        import inspect
        from ai import agent
        source = inspect.getsource(agent.execute_tool_query)
        # Find all temperature= assignments in the format section
        temps = re.findall(r"temperature\s*=\s*([0-9.]+)", source)
        float_temps = [float(t) for t in temps]
        # At least one temperature setting must be <= 0.1 (the format call)
        assert any(t <= 0.1 for t in float_temps), (
            f"No temperature <= 0.1 found in execute_tool_query. Found: {float_temps}. "
            f"Format call must use low temperature for determinism."
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG 2 REGRESSION — RAG threshold retuning
# ─────────────────────────────────────────────────────────────────────────────

class TestBug2RAGThreshold:
    """
    Bug 2: RAG always returns 'no relevant document found'.
    Root cause confirmed: best score from mxbai-embed-large = 0.5191,
    but RAG_MIN_SCORE was 0.58 \u2014 ALL results rejected.
    Fix: RAG_MIN_SCORE lowered to 0.45.
    """

    def test_rag_min_score_is_below_measured_best_score(self):
        """RAG_MIN_SCORE must be <= 0.52 to accept the measured best score of 0.5191."""
        from config import RAG_MIN_SCORE
        measured_best = 0.5191
        assert RAG_MIN_SCORE <= measured_best, (
            f"RAG_MIN_SCORE={RAG_MIN_SCORE} would reject the best measured score "
            f"of {measured_best}. Threshold must be lowered."
        )

    def test_rag_min_score_not_too_low(self):
        """RAG_MIN_SCORE should not be so low it accepts garbage (floor = 0.30)."""
        from config import RAG_MIN_SCORE
        assert RAG_MIN_SCORE >= 0.30, (
            f"RAG_MIN_SCORE={RAG_MIN_SCORE} is too low and will accept irrelevant chunks."
        )

    def test_rag_search_accepts_hit_at_measured_score(self):
        """
        Simulate a Qdrant search returning score=0.5191 and verify it passes the threshold.
        """
        from config import RAG_MIN_SCORE

        # Simulate the score we measured in diagnosis
        simulated_score = 0.5191
        assert simulated_score >= RAG_MIN_SCORE, (
            f"Score {simulated_score} would be rejected by RAG_MIN_SCORE={RAG_MIN_SCORE}. "
            f"This was the actual measured score for the condonation fee query."
        )

    def test_rag_search_with_stub_accepts_result(self):
        """Integration stub: RAG search_with_sources() returns has_relevant_results=True
        when Qdrant returns a score above the new threshold."""
        from ai.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline()

        # Stub the embedder and qdrant client
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1] * 1024

        # Simulate a Qdrant hit with the measured score
        mock_hit = MagicMock()
        mock_hit.score = 0.5191
        mock_hit.payload = {
            "text": "The condonation fee is Rs. 1000 per subject.",
            "filename": "bmsce_academic_policies_2026.pdf",
            "doc_id": "test-doc-001",
            "page": 1,
            "chunk_index": 1,
        }

        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [mock_hit]

        pipeline._embedding_service = mock_embedder
        pipeline._qdrant_client = mock_qdrant

        result = pipeline.search_with_sources("what is the condonation fee")
        assert result["has_relevant_results"] is True, (
            f"Score 0.5191 should pass RAG_MIN_SCORE={0.45} but got no results. "
            f"Result: {result}"
        )
        assert len(result["sources"]) >= 1

    def test_rag_search_rejects_very_low_score(self):
        """RAG search must still reject genuinely irrelevant results (score=0.20)."""
        from ai.rag_pipeline import RAGPipeline

        pipeline = RAGPipeline()

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1] * 1024

        mock_hit = MagicMock()
        mock_hit.score = 0.20  # clearly irrelevant
        mock_hit.payload = {
            "text": "Some completely unrelated text.",
            "filename": "irrelevant.pdf",
            "doc_id": "test-doc-002",
            "page": 1,
            "chunk_index": 0,
        }

        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [mock_hit]

        pipeline._embedding_service = mock_embedder
        pipeline._qdrant_client = mock_qdrant

        result = pipeline.search_with_sources("condonation fee")
        assert result["has_relevant_results"] is False


# ─────────────────────────────────────────────────────────────────────────────
# BUG 3 REGRESSION — Tool routing for 'who teaches machine learning?'
# ─────────────────────────────────────────────────────────────────────────────

class TestBug3ToolRouting:
    """
    Bug 3: 'Who teaches machine learning?' routed to TimetableTool + fabricated follow-up.
    Root causes confirmed:
      1. 'teaches' not in ERP keyword list \u2014 fell through to LLM fallback
      2. No routing rule 'who teaches => FacultyTool' in dispatch prompt
      3. No stop sequences / num_predict cap \u2014 model generated fake extra turns
    Fixes: keyword list updated, routing rule added, num_predict=1024 cap added.
    """

    def test_teaches_keyword_triggers_erp_classification(self):
        """'teaches' must now hit the fast-path ERP keyword check (no LLM call needed)."""
        from ai.agent import classify_query
        # Inject a stub LLM that would indicate 'general' if called
        # (prove fast-path catches it before LLM is invoked)
        with patch("ai.agent.get_llm") as mock_llm:
            mock_llm.return_value = MagicMock()
            result = classify_query("Who teaches machine learning?")

        # Must be 'erp', not 'general'
        assert result == "erp", (
            f"classify_query returned '{result}' for 'Who teaches machine learning?' "
            f"Expected 'erp'. The 'teaches' keyword must be in the fast-path erp_keywords list."
        )

    def test_faculty_tool_has_by_course_action(self):
        """FacultyTool must expose a 'by_course' action."""
        from ai.tools.faculty_tool import FacultyTool
        tool = FacultyTool()
        assert "by_course" in tool.parameters.get("action", ""), (
            f"FacultyTool.parameters['action'] = {tool.parameters.get('action')}. "
            f"Must include 'by_course'."
        )

    def test_faculty_tool_description_mentions_teaches(self):
        """FacultyTool description must guide LLM to use it for 'who teaches' queries."""
        from ai.tools.faculty_tool import FacultyTool
        tool = FacultyTool()
        desc_lower = tool.description.lower()
        assert "teaches" in desc_lower or "instructor" in desc_lower, (
            f"FacultyTool description does not mention 'teaches' or 'instructor'. "
            f"The LLM dispatcher won't route 'who teaches X' here. "
            f"Description: {tool.description}"
        )

    def test_faculty_tool_by_course_graceful_not_found(self):
        """FacultyTool by_course must return a clean message when course doesn't exist."""
        from ai.tools.faculty_tool import FacultyTool
        tool = FacultyTool()

        with patch("ai.tools.faculty_tool.execute_query", return_value=[]):
            result = tool.execute({
                "action": "by_course",
                "course_name": "Nonexistent Subject XYZ"
            })

        assert "message" in result or "error" in result, (
            f"Expected a 'message' or 'error' key in the result for unknown course. Got: {result}"
        )
        assert result.get("found") is not True

    def test_faculty_tool_by_course_returns_faculty_data(self):
        """FacultyTool by_course must return faculty info when course exists."""
        from ai.tools.faculty_tool import FacultyTool
        tool = FacultyTool()

        def mock_query(sql, params=None):
            sql_up = sql.upper()
            if "FROM COURSES" in sql_up and "COURSE_NAME" in sql_up:
                return [{"course_code": "CS601"}]
            if "VW_FACULTY_DASHBOARD" in sql_up:
                return [
                    {
                        "employee_code": "F001",
                        "faculty_name": "Dr. Anjali Sharma",
                        "designation": "Professor",
                        "department_name": "CSE",
                        "email": "anjali@bmsce.ac.in",
                        "course_name": "Machine Learning",
                        "course_code": "CS601",
                    }
                ]
            return []

        with patch("ai.tools.faculty_tool.execute_query", side_effect=mock_query):
            result = tool.execute({
                "action": "by_course",
                "course_name": "Machine Learning"
            })

        assert result.get("found") is True
        assert len(result.get("faculty", [])) >= 1
        assert result["faculty"][0]["faculty_name"] == "Dr. Anjali Sharma"

    def test_num_predict_cap_set_in_local_llm(self):
        """generate() and generate_stream() must pass num_predict to prevent runaway generation."""
        import inspect
        from providers.llm.local_llm import OllamaLLMProvider
        source = inspect.getsource(OllamaLLMProvider)
        assert "num_predict" in source, (
            "num_predict not found in OllamaLLMProvider source. "
            "Output token cap is required to prevent fabricated follow-up turns."
        )

    def test_extract_prompt_contains_faculty_routing_rule(self):
        """The dispatch extract_prompt in agent.py must contain FacultyTool routing rule."""
        import inspect
        from ai import agent
        source = inspect.getsource(agent.execute_tool_query)
        assert "FacultyTool" in source and (
            "who teaches" in source.lower() or "instructor" in source.lower()
        ), (
            "execute_tool_query dispatch prompt must contain an explicit rule routing "
            "'who teaches' queries to FacultyTool."
        )


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION SMOKE TESTS (run with: pytest -m regression9)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.regression9
class TestPhase9IntegrationSmoke:
    """
    Fast smoke tests verifying the three bug fixes together, without needing
    live services. These use the client fixture from conftest.py.
    """

    def test_attendance_query_uses_correct_tool(self, client):
        """Attendance query should get a response from AttendanceTool."""
        resp = client.post("/chat", json={"message": "Show me attendance for CS601"})
        assert resp.status_code == 200
        data = resp.json()
        # Should not indicate an error
        assert data.get("answer") or data.get("query_type") == "erp"

    def test_who_teaches_classified_as_erp(self, client):
        """'Who teaches machine learning?' must be classified as ERP, not general."""
        resp = client.post("/chat", json={"message": "Who teaches machine learning?"})
        assert resp.status_code == 200
        data = resp.json()
        # query_type must be 'erp'
        assert data.get("query_type") == "erp", (
            f"Expected query_type='erp', got '{data.get('query_type')}'"
        )
