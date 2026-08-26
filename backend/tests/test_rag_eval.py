"""
AI ERP Assistant — RAG Evaluation Regression Tests
====================================================
Codifies the 4 Phase 4 manual eval cases + 1 new case as automated pytest tests.
These tests mock Qdrant so they run fast without any vector DB or embedding calls.

If RAG_MIN_SCORE is accidentally lowered or the filtering logic is broken,
these tests will catch the regression automatically.

Run with: pytest tests/test_rag_eval.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_MODE", "local")

import pytest
from unittest.mock import patch, MagicMock


# ── Fixture: Simulated Qdrant search results ─────────────────────────────────

def _make_hit(score: float, filename: str, page: int, text: str) -> MagicMock:
    """Build a mock Qdrant ScoredPoint with the given score and payload."""
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "text": text,
        "filename": filename,
        "doc_id": "test-doc-001",
        "page": page,
        "chunk_index": 0,
    }
    return hit


# ══════════════════════════════════════════════════════════════════════════════
# Case 1 — Relevant document (Attendance Policy, Page 1)
# Scores: 0.6755, 0.6693  → both above RAG_MIN_SCORE=0.58 → should pass
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEvalCase1RelevantDoc:
    """Case 1: Query directly answered by Page 1 of the academic policies PDF."""

    def test_relevant_query_returns_results(self):
        """
        Simulated scores [0.6755, 0.6693] both exceed the 0.58 threshold.
        RAG search should return 2 chunks with has_relevant_results=True.
        """
        from ai.rag_pipeline import RAGPipeline

        mock_hits = [
            _make_hit(0.6755, "bmsce_academic_policies_2026.pdf", 1,
                      "Students must maintain a minimum of 85% attendance. "
                      "A condonation fee of INR 1000 per course is applicable."),
            _make_hit(0.6693, "bmsce_academic_policies_2026.pdf", 1,
                      "Attendance below 75% will result in academic detention."),
        ]

        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources("What is the minimum attendance required?")

        assert result["has_relevant_results"] is True
        assert len(result["sources"]) == 2
        assert result["sources"][0]["score"] == pytest.approx(0.6755, rel=1e-3)
        assert result["sources"][0]["page"] == 1
        assert result["sources"][0]["filename"] == "bmsce_academic_policies_2026.pdf"
        assert "context" in result
        assert len(result["context"]) > 0

    def test_relevant_query_sources_include_page_numbers(self):
        """Source citations must include page numbers for the UI to display them."""
        from ai.rag_pipeline import RAGPipeline

        mock_hits = [
            _make_hit(0.6755, "bmsce_academic_policies_2026.pdf", 1, "Attendance policy text."),
        ]
        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources("minimum attendance required")

        for source in result["sources"]:
            assert "page" in source
            assert "filename" in source
            assert "score" in source


# ══════════════════════════════════════════════════════════════════════════════
# Case 2 — Relevant document (Fast Track Credits, Page 2)
# Scores: 0.7830, 0.6908 → both above 0.58 → should pass
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEvalCase2FastTrack:
    """Case 2: Query about fast-track semester credits answered from Page 2."""

    def test_fast_track_query_returns_results(self):
        from ai.rag_pipeline import RAGPipeline

        mock_hits = [
            _make_hit(0.7830, "bmsce_academic_policies_2026.pdf", 2,
                      "A student may register for a maximum of 16 credits in the "
                      "fast-track semester during summer vacation."),
            _make_hit(0.6908, "bmsce_academic_policies_2026.pdf", 2,
                      "Fast-track semesters run from June to July and are intended "
                      "for backlog clearance and CGPA improvement."),
        ]

        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources("maximum credits in fast track semester")

        assert result["has_relevant_results"] is True
        assert len(result["sources"]) == 2
        # The highest score should be ~0.7830
        assert result["sources"][0]["score"] == pytest.approx(0.7830, rel=1e-3)
        assert result["sources"][0]["page"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# Case 3 — Out-of-domain query (zero relevant results)
# Scores: 0.4010, 0.3800 → both below 0.58 → should trigger fallback
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEvalCase3OutOfDomain:
    """Case 3: Completely unrelated query should trigger no-match fallback."""

    def test_out_of_domain_query_returns_no_results(self):
        from ai.rag_pipeline import RAGPipeline

        # Both scores below RAG_MIN_SCORE=0.58 → should be dropped
        mock_hits = [
            _make_hit(0.4010, "bmsce_academic_policies_2026.pdf", 1,
                      "Astronaut warp drive certification requires 85% training attendance."),
            _make_hit(0.3800, "bmsce_academic_policies_2026.pdf", 2,
                      "Students must submit warp drive application forms by deadline."),
        ]

        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources(
                "What is the policy for astronaut warp drive spaceflight certification?"
            )

        assert result["has_relevant_results"] is False
        assert result["sources"] == []
        assert result["context"] == ""

    def test_document_tool_no_match_returns_fallback_message(self):
        """DocumentTool should return a structured no-match dict with has_relevant_results=False."""
        from ai.tools.document_tool import DocumentTool

        tool = DocumentTool()
        with patch("ai.rag_pipeline.get_rag") as mock_get_rag:
            mock_rag = MagicMock()
            mock_rag.search_with_sources.return_value = {
                "has_relevant_results": False,
                "context": "",
                "sources": [],
            }
            mock_get_rag.return_value = mock_rag

            result = tool.execute({"query": "astronaut warp drive certification"})

        assert result.get("has_relevant_results") is False
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Case 4 — Borderline / weak match (superficial keyword overlap)
# Scores: 0.4200, 0.3800 → all below 0.45 → should be suppressed
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEvalCase4BorderlineMatch:
    """Case 4: Borderline weak match should be suppressed, no hallucination."""

    def test_borderline_query_suppressed(self):
        from ai.rag_pipeline import RAGPipeline

        mock_hits = [
            _make_hit(0.4200, "bmsce_academic_policies_2026.pdf", 3,
                      "BMSCE facilities include gymnasium and sports complex."),
            _make_hit(0.3800, "bmsce_academic_policies_2026.pdf", 1,
                      "BMSCE Section 4 covers student recreational facilities."),
        ]

        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources("campus swimming pool and gymnasium rules and timings")

        assert result["has_relevant_results"] is False
        assert result["sources"] == []


# ══════════════════════════════════════════════════════════════════════════════
# Case 5 — Partial match (one chunk above threshold, others below)
# Scores: 0.6322, 0.3900 → only 0.6322 passes (>= 0.45) → exactly 1 source returned
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEvalCase5PartialMatch:
    """Case 5: Only some chunks pass the threshold — verify filtering is per-chunk."""

    def test_partial_match_returns_only_above_threshold_chunks(self):
        from ai.rag_pipeline import RAGPipeline

        mock_hits = [
            _make_hit(0.6322, "bmsce_academic_policies_2026.pdf", 1,
                      "Condonation fee for attendance between 75% and 84% is INR 1000 per course."),
            _make_hit(0.3900, "bmsce_academic_policies_2026.pdf", 2,
                      "Students below 75% will not be eligible to sit for examinations."),
        ]

        rag = RAGPipeline()
        with patch.object(rag, "_qdrant_client") as mock_client, \
             patch.object(rag, "_embedding_service") as mock_emb:
            mock_emb.embed.return_value = [0.1] * 1024
            mock_emb.dimension = 1024
            mock_client.search.return_value = mock_hits
            rag._qdrant_client = mock_client

            result = rag.search_with_sources("condonation fee for low attendance")

        assert result["has_relevant_results"] is True
        # Only 1 source should remain (score 0.6322 >= 0.45, score 0.3900 < 0.45)
        assert len(result["sources"]) == 1
        assert result["sources"][0]["score"] == pytest.approx(0.6322, rel=1e-3)
        assert result["sources"][0]["page"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# RAG Min Score Threshold Sanity Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGMinScoreConfig:
    """Verify that RAG_MIN_SCORE config is loaded correctly and within sane bounds."""

    def test_rag_min_score_is_between_0_and_1(self):
        from config import RAG_MIN_SCORE
        assert 0.0 < RAG_MIN_SCORE < 1.0, (
            f"RAG_MIN_SCORE={RAG_MIN_SCORE} is outside the valid (0, 1) range"
        )

    def test_rag_min_score_default_is_sensible(self):
        """Default threshold should be at least 0.4 to avoid weak matches."""
        from config import RAG_MIN_SCORE
        assert RAG_MIN_SCORE >= 0.4, (
            f"RAG_MIN_SCORE={RAG_MIN_SCORE} is dangerously low — "
            "will allow weak matches through and risk hallucination."
        )

    def test_rag_top_k_is_positive(self):
        from config import RAG_TOP_K
        assert RAG_TOP_K > 0

    def test_chunk_size_is_reasonable(self):
        from config import RAG_CHUNK_SIZE
        assert 128 <= RAG_CHUNK_SIZE <= 4096
