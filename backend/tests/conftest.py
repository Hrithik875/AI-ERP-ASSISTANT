"""
AI ERP Assistant — Shared Test Fixtures (conftest.py)
=======================================================
Provides centralized fixtures for all test modules:
  - TestClient with APP_MODE=local set
  - Mock LLM provider (fast deterministic stub)
  - Mock embedding provider (returns fixed 1024-d vectors)
  - Mock STT/TTS providers
  - Mock DB execute_query / execute_write
  - Mock Qdrant search

Usage:
  pytest tests/ -v -m "not integration"        # fast unit tests only
  pytest tests/ -v -m integration               # full stack (requires running services)
"""

import os
import sys

# Ensure backend root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force local mode before any config import
os.environ.setdefault("APP_MODE", "local")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-123")

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Provider name maps (for mode-aware assertions) ───────────────────────────

APP_MODE = os.environ.get("APP_MODE", "local")

EXPECTED_LLM_PROVIDER = {
    "local": "OllamaLLMProvider",
    "aws": "AWSLLMProvider",
}.get(APP_MODE, "OllamaLLMProvider")

EXPECTED_EMBEDDING_PROVIDER = {
    "local": "OllamaEmbeddingProvider",
    "aws": "AWSEmbeddingProvider",
}.get(APP_MODE, "OllamaEmbeddingProvider")


# ── Stub classes ─────────────────────────────────────────────────────────────

class _StubLLM:
    """Deterministic LLM stub — returns fast canned responses without any network calls."""
    model_id = "stub-model"
    fast_model = "stub-fast-model"

    def generate(self, user_message="", context="", system_prompt="", temperature=0.3):
        # Classification stub: return 'erp' for attendance queries, etc.
        msg_lower = (user_message + " " + system_prompt).lower()
        if any(k in msg_lower for k in ["tool_name", "params", "json"]):
            return '{"tool_name": "AttendanceTool", "params": {"action": "student_summary", "usn": "CS2022001"}}'
        return "Stub LLM response: query processed successfully."

    def generate_fast(self, user_message="", system_prompt="", temperature=0.0):
        return self.generate(user_message=user_message, system_prompt=system_prompt, temperature=temperature)

    def generate_stream(self, user_message="", context="", system_prompt="", temperature=0.3):
        yield "Stub "
        yield "LLM "
        yield "response: query processed successfully."

    def prewarm(self):
        return {self.fast_model: 0, self.model_id: 0}

    def health_check(self):
        return {"status": "ok", "provider": "stub", "model": self.model_id, "fast_model": self.fast_model}


class _StubEmbeddingProvider:
    """Returns a fixed 1024-d embedding vector instantly."""
    model_id = "stub-embeddings"

    @property
    def dimension(self):
        return 1024

    def embed(self, text):
        return [0.1] * 1024

    def embed_batch(self, texts):
        return [[0.1] * 1024 for _ in texts]


class _StubSTTProvider:
    """Synchronous STT stub that immediately returns a canned transcript."""
    _jobs = {}

    def transcribe(self, audio_data, audio_format="webm"):
        return "Show me attendance for CS601"

    def transcribe_async(self, audio_data, audio_format="webm", job_name=None):
        job_name = job_name or "stub-job-001"
        self._jobs[job_name] = {"status": "COMPLETED", "transcript": "Show me attendance for CS601"}
        return {"job_name": job_name, "status": "IN_PROGRESS"}

    def get_transcription_status(self, job_name):
        if job_name in self._jobs:
            return self._jobs[job_name]
        return {"status": "FAILED", "reason": "Job not found"}


class _FailingSTTProvider(_StubSTTProvider):
    """STT stub that raises on transcribe (simulates faster-whisper crash)."""
    def transcribe(self, audio_data, audio_format="webm"):
        raise RuntimeError("Simulated faster-whisper transcription failure")

    def transcribe_async(self, audio_data, audio_format="webm", job_name=None):
        raise RuntimeError("Simulated faster-whisper transcription failure")


class _TimeoutSTTProvider(_StubSTTProvider):
    """STT stub that always returns IN_PROGRESS to simulate a timeout."""
    def get_transcription_status(self, job_name):
        return {"status": "IN_PROGRESS"}


class _StubTTSProvider:
    """TTS stub that returns a fake audio URL."""
    def synthesize(self, text):
        return {"audio_url": "http://localhost:8000/files/stub_audio.mp3", "duration_approx_s": 1.0}


class _StubStorageProvider:
    """No-op storage provider for tests."""
    _store = {}

    def upload_bytes(self, key, data, content_type="application/octet-stream"):
        self._store[key] = data
        return key

    def download_bytes(self, key):
        return self._store.get(key, b"")

    def get_url(self, key, expiration=3600):
        return f"http://localhost:8000/files/{key}"

    def delete(self, key):
        self._store.pop(key, None)

    def ensure_ready(self):
        pass


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def stub_llm():
    return _StubLLM()


@pytest.fixture(scope="session")
def stub_embedding():
    return _StubEmbeddingProvider()


@pytest.fixture(scope="session")
def stub_stt():
    return _StubSTTProvider()


@pytest.fixture(scope="session")
def stub_tts():
    return _StubTTSProvider()


@pytest.fixture(scope="session")
def stub_storage():
    return _StubStorageProvider()


@pytest.fixture(autouse=True)
def mock_all_providers():
    """Ensure mock providers are always active for all tests by default."""
    from providers import registry as reg
    stub_llm_inst = _StubLLM()
    stub_emb_inst = _StubEmbeddingProvider()
    stub_stt_inst = _StubSTTProvider()
    stub_tts_inst = _StubTTSProvider()
    stub_storage_inst = _StubStorageProvider()

    reg._llm_provider = stub_llm_inst
    reg._embedding_provider = stub_emb_inst
    reg._stt_provider = stub_stt_inst
    reg._tts_provider = stub_tts_inst
    reg._storage_provider = stub_storage_inst

    yield

    reg._llm_provider = stub_llm_inst
    reg._embedding_provider = stub_emb_inst
    reg._stt_provider = stub_stt_inst
    reg._tts_provider = stub_tts_inst
    reg._storage_provider = stub_storage_inst


@pytest.fixture(scope="session")
def client():
    """
    Session-scoped TestClient with full provider mocking.

    Patches:
      - providers.registry singletons → stub implementations
      - db.connection.execute_query → returns fixture data
      - db.connection.execute_write → returns 1 (affected rows)
    """
    from providers import registry as reg

    # Inject stub providers before app import
    stub_llm_inst = _StubLLM()
    stub_emb_inst = _StubEmbeddingProvider()
    stub_stt_inst = _StubSTTProvider()
    stub_tts_inst = _StubTTSProvider()
    stub_storage_inst = _StubStorageProvider()

    reg._llm_provider = stub_llm_inst
    reg._embedding_provider = stub_emb_inst
    reg._stt_provider = stub_stt_inst
    reg._tts_provider = stub_tts_inst
    reg._storage_provider = stub_storage_inst

    # Stub DB calls
    def _mock_execute_query(sql, params=None):
        sql_upper = sql.strip().upper()
        if params:
            for p in params:
                if str(p).startswith("NONEXISTENT") or str(p).startswith("ZZZZZZ"):
                    return []
        if "QUERY_LOGS" in sql_upper:
            return []
        if "INFORMATION_SCHEMA" in sql_upper:
            return [{"TABLE_NAME": "students"}, {"TABLE_NAME": "attendance"}]
        if "COUNT(*)" in sql_upper:
            return [{"total": 0, "cnt": 0}]
        if "GRADES" in sql_upper:
            return [
                {
                    "student_id": "CS2022001", "name": "Test Student",
                    "course_code": "CS601", "course_name": "Machine Learning",
                    "grade": "A", "grade_points": 9.0, "marks_obtained": 88,
                    "exam_type": "SEE", "semester": 6,
                }
            ]
        if "VW_ATTENDANCE_SUMMARY" in sql_upper or "ATTENDANCE" in sql_upper:
            return [
                {
                    "usn": "CS2022001", "student_name": "Test Student",
                    "course_code": "CS601", "course_name": "Machine Learning",
                    "classes_attended": 25, "total_classes": 30,
                    "attendance_pct": 83.33,
                    "present": 25, "absent": 5, "late": 0, "percentage": 83.3,
                }
            ]
        if "FACULTY" in sql_upper:
            return [
                {
                    "employee_id": "EMP001", "name": "Dr. Smith", "email": "smith@bmsce.ac.in",
                    "department": "CSE", "designation": "Professor", "phone": "9999999999",
                    "joined_at": "2020-01-01", "courses": [],
                }
            ]
        if "STUDENTS" in sql_upper or "STUDENT" in sql_upper:
            return [
                {
                    "student_id": "CS2022001", "usn": "CS2022001", "name": "Test Student",
                    "full_name": "Test Student", "email": "test@bmsce.ac.in",
                    "department": "Computer Science", "semester": 6, "section": "A",
                    "phone": "9999999999", "guardian_phone": "8888888888",
                    "enrolled_at": "2022-08-01", "is_active": 1,
                }
            ]
        return []

    def _mock_execute_write(sql, params=None):
        return 1

    with (
        patch("db.connection.execute_query", side_effect=_mock_execute_query),
        patch("db.connection.execute_write", side_effect=_mock_execute_write),
    ):
        from main import app
        with TestClient(app) as c:
            yield c

    # Reset singletons after session
    reg.reset_providers()


# ── Voice-specific fixtures (function-scoped for override) ────────────────────

@pytest.fixture()
def client_failing_stt():
    """TestClient where the STT provider raises on every transcription attempt."""
    from providers import registry as reg

    orig_stt = reg._stt_provider
    reg._stt_provider = _FailingSTTProvider()

    def _mock_execute_query(sql, params=None):
        return []

    def _mock_execute_write(sql, params=None):
        return 1

    with (
        patch("db.connection.execute_query", side_effect=_mock_execute_query),
        patch("db.connection.execute_write", side_effect=_mock_execute_write),
    ):
        from main import app
        with TestClient(app) as c:
            yield c

    reg._stt_provider = orig_stt


@pytest.fixture()
def client_timeout_stt():
    """TestClient where the STT provider always returns IN_PROGRESS (timeout scenario)."""
    from providers import registry as reg

    orig_stt = reg._stt_provider
    reg._stt_provider = _TimeoutSTTProvider()

    def _mock_execute_query(sql, params=None):
        return []

    def _mock_execute_write(sql, params=None):
        return 1

    with (
        patch("db.connection.execute_query", side_effect=_mock_execute_query),
        patch("db.connection.execute_write", side_effect=_mock_execute_write),
    ):
        from main import app
        with TestClient(app) as c:
            yield c

    reg._stt_provider = orig_stt


# ── Markers ───────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests that require a running local stack "
        "(MySQL + Qdrant + Ollama + backend). Skipped by default. Run with: pytest -m integration",
    )
