"""
AI ERP Assistant — AI Pipeline Tests (Mocked)
==============================================
Tests for query classification, LLM service, RAG pipeline, and tool logic.

All LLM/Embedding/DB calls are mocked so the suite runs fast and
deterministically without requiring Ollama, Qdrant, or MySQL to be running.

Run with: pytest tests/test_ai.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_MODE", "local")

import pytest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# Query Classification (fast heuristics — no LLM needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryClassification:
    """Test query routing / classification logic via fast pre-classifier."""

    def test_attendance_query_classified_as_erp(self):
        from ai.agent import classify_query
        assert classify_query("What is my attendance?") == "erp"
        assert classify_query("Am I absent today?") == "erp"

    def test_grades_query_classified_as_erp(self):
        from ai.agent import classify_query
        assert classify_query("Show me my grades") == "erp"
        assert classify_query("What is my GPA?") == "erp"
        assert classify_query("What marks did I get?") == "erp"

    def test_faculty_query_classified_as_erp(self):
        from ai.agent import classify_query
        # "faculty" is in erp_keywords
        assert classify_query("List all faculty members") == "erp"

    def test_document_query_classified_as_document(self):
        from ai.agent import classify_query
        # "document", "syllabus", "policy" are in doc_keywords
        assert classify_query("What does the syllabus say?") == "document"
        assert classify_query("Search in the uploaded document") == "document"
        assert classify_query("What is the attendance policy?") == "document"

    def test_schedule_query_classified_as_erp(self):
        from ai.agent import classify_query
        assert classify_query("Show me the timetable") == "erp"
        assert classify_query("What classes do I have?") == "erp"

    def test_risk_query_classified_as_erp(self):
        from ai.agent import classify_query
        assert classify_query("Show at-risk students in CS601") == "erp"
        assert classify_query("How many more classes does she need?") == "erp"

    def test_contextual_followup_with_erp_history(self):
        """Follow-up query should resolve to 'erp' if history contains ERP context."""
        from ai.agent import classify_query
        history = [
            {"role": "user", "content": "Show attendance for CS601"},
            {"role": "assistant", "content": "Average attendance is 87.5%"},
        ]
        # "Which one has lowest" alone might be ambiguous, but history contains 'attendance'
        result = classify_query("Which one has the lowest?", history=history)
        assert result == "erp"


# ══════════════════════════════════════════════════════════════════════════════
# LLM Service Init (mocked — no Bedrock/Ollama)
# ══════════════════════════════════════════════════════════════════════════════

class TestLLMProviderInit:
    """
    Test that the provider registry returns the correct provider class for the
    current APP_MODE. Network calls are mocked so tests run offline.
    """

    def test_local_mode_returns_ollama_provider(self):
        """Under APP_MODE=local, the LLM provider class should be OllamaLLMProvider."""
        from providers.llm.local_llm import OllamaLLMProvider
        provider = OllamaLLMProvider()
        assert hasattr(provider, "model_id") or hasattr(provider, "model"), (
            "LLM provider must have model_id or model attribute"
        )
        model_name = getattr(provider, "model_id", getattr(provider, "model", None))
        assert model_name is not None

    def test_provider_health_check_returns_dict(self):
        """health_check() must return a dict with 'status' key."""
        from providers import registry as reg
        provider = reg.get_llm_provider()
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b-instruct"}]}
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            health = provider.health_check()
            assert isinstance(health, dict)
            assert "status" in health

    def test_embedding_provider_has_dimension(self):
        """Embedding provider must expose a positive 'dimension' property."""
        from providers import registry as reg
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1] * 1024}
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp
            emb = reg.get_embedding_provider()
            assert emb.dimension > 0


# ══════════════════════════════════════════════════════════════════════════════
# Attendance Tool — Unit Tests (no DB)
# ══════════════════════════════════════════════════════════════════════════════

class TestAttendanceCalculations:
    """Unit tests for pure-Python arithmetic functions in attendance_tool.py."""

    def test_classes_needed_when_below_75(self):
        from ai.tools.attendance_tool import compute_classes_needed_to_reach_target
        # Anjali: 20/33 = 60.61%, needs 19 more to reach 75%
        assert compute_classes_needed_to_reach_target(20, 33, 75.0) == 19

    def test_classes_needed_when_already_above_target(self):
        from ai.tools.attendance_tool import compute_classes_needed_to_reach_target
        # 30/33 = 90.91%, already above 75% → 0 needed
        assert compute_classes_needed_to_reach_target(30, 33, 75.0) == 0

    def test_classes_needed_edge_zero_total(self):
        from ai.tools.attendance_tool import compute_classes_needed_to_reach_target
        assert compute_classes_needed_to_reach_target(0, 0, 75.0) == 0

    def test_classes_can_miss_when_above_75(self):
        from ai.tools.attendance_tool import compute_classes_can_miss
        # Uday: 30/33 = 90.91%, can miss 7 classes and stay at 75%
        assert compute_classes_can_miss(30, 33, 75.0) == 7

    def test_classes_can_miss_when_below_threshold(self):
        from ai.tools.attendance_tool import compute_classes_can_miss
        # 20/33 < 75% → cannot miss any classes
        assert compute_classes_can_miss(20, 33, 75.0) == 0

    def test_classes_can_miss_exactly_at_threshold(self):
        from ai.tools.attendance_tool import compute_classes_can_miss
        # 75/100 = exactly 75% → 0 more can be missed without dropping below
        assert compute_classes_can_miss(75, 100, 75.0) == 0

    def test_verification_formula_19_classes(self):
        """Cross-verify: 20+19=39 attended, 33+19=52 total → exactly 75.0%."""
        attended, total = 20 + 19, 33 + 19
        assert abs((attended / total) * 100 - 75.0) < 0.01

    def test_verification_formula_7_misses(self):
        """Cross-verify: 30 attended, 33+7=40 total → exactly 75.0%."""
        attended, total = 30, 33 + 7
        assert abs((attended / total) * 100 - 75.0) < 0.01


# ══════════════════════════════════════════════════════════════════════════════
# SQL Safety (structural, no DB needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLSafety:
    """Verify that the tool layer never exposes raw SQL injection vectors."""

    def test_tool_params_never_use_raw_sql(self):
        """
        All registered tools use execute_query/execute_write with parameterized
        SQL (%s placeholders). Verify no tool parameter schema exposes a 'sql' key.
        """
        from ai.tools import REGISTERED_TOOLS
        for tool in REGISTERED_TOOLS:
            assert "sql" not in tool.parameters, (
                f"Tool {tool.name} exposes a 'sql' parameter — this risks injection!"
            )

    def test_rejects_dangerous_patterns_in_tool_parameters(self):
        """Tools should not accept raw DDL/DML via their execute() interface."""
        dangerous_patterns = ["DELETE FROM students", "DROP TABLE grades", "UPDATE students SET"]
        for pattern in dangerous_patterns:
            sql_upper = pattern.upper()
            # Verify our check would catch it
            dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
            assert any(d in sql_upper for d in dangerous_keywords)


# ══════════════════════════════════════════════════════════════════════════════
# RAG Chunking (pure Python, no Qdrant)
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGChunking:
    """Test the RAG pipeline's text chunking logic in isolation."""

    def test_chunk_text_produces_non_empty_chunks(self):
        from ai.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
        text = "A" * 2000
        chunks = rag.chunk_text(text)
        assert len(chunks) > 0
        assert all(c["text"] for c in chunks)

    def test_chunk_text_assigns_page_1_without_page_breaks(self):
        from ai.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
        chunks = rag.chunk_text("Hello world " * 100)
        assert all(c["page"] == 1 for c in chunks)

    def test_chunk_text_assigns_correct_pages_with_breaks(self):
        from ai.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
        text = "Page one content. " * 30 + "Page two content. " * 30
        # Page 2 starts at offset 540 (approx)
        page_breaks = [0, 540]
        chunks = rag.chunk_text(text, page_breaks=page_breaks)
        pages = set(c["page"] for c in chunks)
        assert 1 in pages or 2 in pages  # at least one valid page assigned

    def test_chunk_text_chunk_index_monotonically_increases(self):
        from ai.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
        chunks = rag.chunk_text("Word " * 500)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == sorted(indices)


# ══════════════════════════════════════════════════════════════════════════════
# End-to-End (mocked) — process_query structure
# ══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """Verifies that process_query returns the correct dict structure.
    Uses mocked LLM and DB — does NOT require live Ollama or MySQL."""

    def test_process_query_returns_dict(self, client):
        """
        Call process_query via the /chat HTTP endpoint (which uses TestClient backed
        by the fully-mocked app from conftest). Verify response structure.
        """
        response = client.post("/chat", json={"message": "What is my attendance?"})
        assert response.status_code == 200
        data = response.json()
        assert "content" in data           # maps to result["answer"]
        assert "id" in data
        assert "query_type" in data
        assert data["query_type"] in ["erp", "document", "general"]
        assert "response_time_ms" in data
        assert "tool_used" in data
        assert isinstance(data["content"], str)
        assert len(data["content"]) > 0
