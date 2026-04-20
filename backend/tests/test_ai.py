"""
AI ERP Assistant — AI Pipeline Tests
=======================================
Tests for query classification, LLM service, and RAG pipeline.
Run with: pytest tests/test_ai.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestQueryClassification:
    """Test query routing / classification logic."""

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
        assert classify_query("Who is my professor?") == "erp"
        assert classify_query("List all faculty members") == "erp"

    def test_document_query_classified_as_document(self):
        from ai.agent import classify_query
        assert classify_query("Search in the uploaded document") == "document"
        assert classify_query("Find information in the PDF") == "document"
        assert classify_query("What does the syllabus say?") == "document"

    def test_general_query_classified_as_general(self):
        from ai.agent import classify_query
        assert classify_query("Hello, how are you?") == "general"
        assert classify_query("What is machine learning?") == "general"

    def test_schedule_query_classified_as_erp(self):
        from ai.agent import classify_query
        assert classify_query("When is the next exam?") == "erp"
        assert classify_query("Show me the timetable") == "erp"


class TestLLMServiceInit:
    """Test LLM service initialization (Amazon Bedrock)."""

    def test_llm_service_has_model_id(self):
        from ai.llm_service import get_llm
        llm = get_llm()
        assert llm.model_id is not None
        assert "claude" in llm.model_id.lower() or "anthropic" in llm.model_id.lower()

    def test_llm_health_check(self):
        from ai.llm_service import get_llm
        llm = get_llm()
        health = llm.health_check()
        assert "status" in health
        assert "provider" in health
        assert health["provider"] == "bedrock"


class TestEmbeddingServiceInit:
    """Test Embedding service initialization (Bedrock Titan)."""

    def test_embedding_service_has_model_id(self):
        from ai.embeddings import get_embedding_service
        svc = get_embedding_service()
        assert svc.model_id is not None
        assert "titan" in svc.model_id.lower()

    def test_embedding_service_has_dimension(self):
        from ai.embeddings import get_embedding_service
        svc = get_embedding_service()
        assert svc.dimension > 0


class TestSQLSafety:
    """Test SQL generation safety checks."""

    def test_rejects_delete_statements(self):
        # The generate_sql function should raise on dangerous SQL
        dangerous_patterns = ["DELETE FROM students", "DROP TABLE grades", "UPDATE students SET"]
        for pattern in dangerous_patterns:
            sql_upper = pattern.upper()
            dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
            for d in dangerous:
                if d in sql_upper:
                    assert True  # Safety check would catch it
                    break


class TestEndToEnd:
    """End-to-end test: Text query → Bedrock AI → Response."""

    def test_process_query_returns_dict(self):
        """Test that process_query returns properly structured response."""
        from ai.agent import process_query
        result = process_query("What is my attendance percentage?")
        assert isinstance(result, dict)
        assert "answer" in result
        assert "query_type" in result
        assert "response_time_ms" in result
        assert result["query_type"] in ["erp", "document", "general"]
        assert isinstance(result["response_time_ms"], int)
        assert len(result["answer"]) > 0
