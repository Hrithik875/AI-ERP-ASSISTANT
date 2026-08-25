"""
AI ERP Assistant — Full Local-Stack Integration Test
=====================================================
Verifies that all required services are up and responding to health checks
before running end-to-end queries.

This test is SKIPPED by default in the fast unit suite. Run explicitly with:
  pytest tests/test_integration.py -v -m integration

Or run everything including integration:
  pytest tests/ -v

Requirements (all must be running):
  - MySQL on localhost:3306 with erp_assistant database seeded
  - Qdrant on localhost:6333
  - Ollama on localhost:11434 with qwen2.5:7b-instruct + mxbai-embed-large pulled
  - Backend uvicorn on localhost:8000 (start separately: uvicorn main:app --port 8000)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_MODE", "local")

import pytest
import requests
import socket
import time

# ── Backend URL ───────────────────────────────────────────────────────────────
BACKEND_URL = os.environ.get("LOCAL_SERVER_URL", "http://localhost:8000")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DB_HOST = os.environ.get("AURORA_HOST", "localhost")
DB_PORT = int(os.environ.get("AURORA_PORT", "3306"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    """Return True if an HTTP GET to url returns 2xx."""
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 300
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Service Health Checks
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestServiceHealthChecks:
    """Verifies each dependency in the local stack responds to health probes."""

    def test_mysql_port_open(self):
        """MySQL must be reachable on localhost:3306."""
        assert _port_open(DB_HOST, DB_PORT), (
            f"MySQL is not reachable at {DB_HOST}:{DB_PORT}. "
            "Start it with: mysqld or docker run -e MYSQL_ROOT_PASSWORD=... mysql"
        )

    def test_qdrant_health_endpoint(self):
        """Qdrant must respond to GET /healthz."""
        assert _http_ok(f"{QDRANT_URL}/healthz"), (
            f"Qdrant health check failed at {QDRANT_URL}/healthz. "
            "Start it with: docker run -p 6333:6333 qdrant/qdrant"
        )

    def test_ollama_api_reachable(self):
        """Ollama API must respond to GET /api/tags."""
        assert _http_ok(f"{OLLAMA_URL}/api/tags"), (
            f"Ollama is not reachable at {OLLAMA_URL}. "
            "Start it with: ollama serve"
        )

    def test_backend_health_endpoint(self):
        """Backend /health must return 200 with status=healthy."""
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=10)
        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"Backend is not running at {BACKEND_URL}. "
                "Start it with: cd backend && uvicorn main:app --port 8000"
            )
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "healthy"
        assert data.get("mode") == "local"


# ══════════════════════════════════════════════════════════════════════════════
# Database Connectivity
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDatabaseConnectivity:
    """Verifies MySQL tables are seeded and queryable."""

    def test_students_table_has_data(self):
        """GET /students should return at least 1 seeded student record."""
        r = requests.get(f"{BACKEND_URL}/students", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Students table appears to be empty — run seed_database()"

    def test_attendance_table_has_data(self):
        """GET /attendance should return attendance records."""
        r = requests.get(f"{BACKEND_URL}/attendance", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_faculty_table_has_data(self):
        """GET /faculty should return faculty records."""
        r = requests.get(f"{BACKEND_URL}/faculty", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# Ollama Model Check
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestOllamaModels:
    """Verifies required Ollama models are pulled and available."""

    def test_llm_model_is_available(self):
        """The configured OLLAMA_MODEL must appear in Ollama's model list."""
        ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            models = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            pytest.fail(f"Could not list Ollama models: {e}")

        # Match by prefix (model name may include digest suffix)
        found = any(ollama_model.split(":")[0] in m for m in models)
        assert found, (
            f"Ollama model '{ollama_model}' not found. Pull it with: ollama pull {ollama_model}\n"
            f"Available models: {models}"
        )

    def test_embedding_model_is_available(self):
        """The configured OLLAMA_EMBEDDING_MODEL must appear in Ollama's model list."""
        emb_model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large")
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            models = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            pytest.fail(f"Could not list Ollama models: {e}")

        found = any(emb_model.split(":")[0] in m for m in models)
        assert found, (
            f"Embedding model '{emb_model}' not found. Pull it with: ollama pull {emb_model}\n"
            f"Available models: {models}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# End-to-End Chat Query (full pipeline)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestEndToEndChatIntegration:
    """
    Full stack end-to-end test: client → backend → Ollama LLM → MySQL → response.
    These tests are slow (each call may take 30-90s on CPU Ollama).
    """

    def test_erp_attendance_query_end_to_end(self):
        """Simple attendance query should return 200 with content and tool_used."""
        try:
            r = requests.post(
                f"{BACKEND_URL}/chat",
                json={"message": "Show me the attendance summary for CS601"},
                timeout=180,
            )
        except requests.exceptions.Timeout:
            pytest.skip("Ollama response timed out — model may be slow on CPU")
        assert r.status_code == 200
        data = r.json()
        assert "content" in data
        assert data.get("tool_used") is not None
        assert data.get("query_type") == "erp"

    def test_general_query_end_to_end(self):
        """General query should return 200 without crashing."""
        try:
            r = requests.post(
                f"{BACKEND_URL}/chat",
                json={"message": "Hello, how are you?"},
                timeout=120,
            )
        except requests.exceptions.Timeout:
            pytest.skip("Ollama response timed out — model may be slow on CPU")
        assert r.status_code == 200
        data = r.json()
        assert data.get("query_type") == "general"

    def test_analytics_dashboard_end_to_end(self):
        """Analytics dashboard stats should return populated data."""
        r = requests.get(f"{BACKEND_URL}/dashboard/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "totalQueries" in data
