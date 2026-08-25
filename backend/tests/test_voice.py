"""
AI ERP Assistant — Voice Pipeline Failure Tests
================================================
Tests for graceful failure handling across all voice pipeline scenarios:
  - Unsupported audio format → 400
  - Empty/silent audio → 400
  - Transcription failure (faster-whisper raises) → 500
  - Polling timeout (voice-query never completes) → 504
  - Transcript job not found → 404

All tests use provider mocking from conftest.py.

Run with: pytest tests/test_voice.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_MODE", "local")

import pytest
import io
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_audio_upload(content: bytes = b"\x00" * 1024, content_type: str = "audio/webm"):
    """Build a multipart file upload dict for the TestClient."""
    return {
        "audio": (
            "test_audio.webm",
            io.BytesIO(content),
            content_type,
        )
    }


# ══════════════════════════════════════════════════════════════════════════════
# Unsupported Audio Format
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceUnsupportedFormat:
    """Verify that unsupported MIME types are rejected immediately with 400."""

    UNSUPPORTED_TYPES = [
        "application/pdf",
        "image/jpeg",
        "text/plain",
        "audio/wma",
        "video/mp4",        # video/mp4 is not in ALLOWED_AUDIO_TYPES
        "application/octet-stream",
    ]

    @pytest.mark.parametrize("content_type", UNSUPPORTED_TYPES)
    def test_unsupported_format_returns_400(self, client, content_type):
        """All non-audio MIME types should be rejected with HTTP 400."""
        response = client.post(
            "/voice-input",
            files={
                "audio": ("test.bin", io.BytesIO(b"\x00" * 512), content_type)
            },
        )
        assert response.status_code == 400, (
            f"Expected 400 for content_type={content_type!r}, got {response.status_code}"
        )

    def test_unsupported_format_error_message_is_descriptive(self, client):
        """400 error must include a human-readable detail field."""
        response = client.post(
            "/voice-input",
            files={"audio": ("test.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert len(data["detail"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Empty/Silent Audio
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceEmptyAudio:
    """Verify that zero-byte audio uploads are rejected with 400."""

    def test_empty_audio_returns_400(self, client):
        """0-byte file body should return 400 (empty audio check in voice.py)."""
        response = client.post(
            "/voice-input",
            files={"audio": ("silent.webm", io.BytesIO(b""), "audio/webm")},
        )
        assert response.status_code == 400

    def test_empty_audio_detail_mentions_empty(self, client):
        """Error detail should mention 'empty' to help the user understand why."""
        response = client.post(
            "/voice-input",
            files={"audio": ("silent.wav", io.BytesIO(b""), "audio/wav")},
        )
        data = response.json()
        assert "detail" in data
        assert "empty" in data["detail"].lower(), (
            f"Expected 'empty' in error detail, got: {data['detail']!r}"
        )

    def test_empty_voice_query_returns_400(self, client):
        """0-byte file to /voice-query should also return 400."""
        response = client.post(
            "/voice-query",
            files={"audio": ("silent.webm", io.BytesIO(b""), "audio/webm")},
        )
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Transcription Failure (faster-whisper raises)
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceTranscriptionFailure:
    """
    When faster-whisper (or AWS Transcribe) raises an exception,
    the endpoint should return 500 gracefully rather than propagating the crash.
    """

    def test_transcription_failure_returns_500(self, client_failing_stt):
        """
        The client_failing_stt fixture injects a provider that raises
        RuntimeError on every transcribe call.
        """
        response = client_failing_stt.post(
            "/voice-input",
            files={"audio": ("test.webm", io.BytesIO(b"\x00" * 1024), "audio/webm")},
        )
        assert response.status_code == 500, (
            f"Expected 500 for transcription failure, got {response.status_code}"
        )

    def test_transcription_failure_returns_json_detail(self, client_failing_stt):
        """500 response should be JSON with a 'detail' field, not an HTML error page."""
        response = client_failing_stt.post(
            "/voice-input",
            files={"audio": ("test.webm", io.BytesIO(b"\x00" * 1024), "audio/webm")},
        )
        # Should be JSON
        assert response.headers.get("content-type", "").startswith("application/json"), (
            "Error response should be JSON, not HTML"
        )
        data = response.json()
        assert "detail" in data


# ══════════════════════════════════════════════════════════════════════════════
# Polling Timeout (voice-query never completes)
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceQueryTimeout:
    """
    When the STT provider always returns IN_PROGRESS (e.g. a hung Transcribe job),
    /voice-query should time out and return HTTP 504 after its poll loop.

    NOTE: The real voice.py polls 30 times with 2s sleep between each.
    For test speed, we mock asyncio.sleep to be instant.
    """

    def test_voice_query_timeout_returns_504(self, client_timeout_stt):
        """
        client_timeout_stt injects a provider that always returns IN_PROGRESS.
        asyncio.sleep is mocked to avoid 60s real wait.
        """
        with patch("routes.voice.asyncio.sleep", return_value=None):
            response = client_timeout_stt.post(
                "/voice-query",
                files={"audio": ("test.webm", io.BytesIO(b"\x00" * 1024), "audio/webm")},
            )
        assert response.status_code == 504, (
            f"Expected 504 Transcription timed out, got {response.status_code}"
        )

    def test_voice_query_timeout_detail_mentions_timeout(self, client_timeout_stt):
        """504 response detail should mention 'timed out' or 'timeout'."""
        with patch("routes.voice.asyncio.sleep", return_value=None):
            response = client_timeout_stt.post(
                "/voice-query",
                files={"audio": ("test.webm", io.BytesIO(b"\x00" * 1024), "audio/webm")},
            )
        data = response.json()
        assert "detail" in data
        detail_lower = data["detail"].lower()
        assert "timed out" in detail_lower or "timeout" in detail_lower, (
            f"Expected timeout message in detail, got: {data['detail']!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Transcript Job Not Found
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceTranscriptNotFound:
    """Tests for /get-transcript/{job_name} with invalid/nonexistent job names."""

    def test_get_transcript_unknown_job_returns_404(self, client):
        """Polling for a nonexistent job name should return 404."""
        response = client.get("/get-transcript/nonexistent-job-xyz-12345")
        assert response.status_code == 404

    def test_get_transcript_empty_job_name_returns_4xx(self, client):
        """Polling with just a space/empty segment is a bad route."""
        response = client.get("/get-transcript/ ")
        # FastAPI may return 404 or 422; either is acceptable (not 200 or 500)
        assert response.status_code in (404, 422)


# ══════════════════════════════════════════════════════════════════════════════
# Happy Path (sanity check with stub STT)
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceHappyPath:
    """Basic sanity checks for the working voice pipeline using stub STT/TTS."""

    def test_voice_input_valid_audio_returns_200(self, client):
        """Valid webm audio with correct content type should return 200 with job_name."""
        response = client.post(
            "/voice-input",
            files={"audio": ("test.webm", io.BytesIO(b"\x00" * 2048), "audio/webm")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_name" in data
        assert "status" in data

    def test_voice_input_wav_returns_200(self, client):
        """WAV format should also be accepted."""
        response = client.post(
            "/voice-input",
            files={"audio": ("test.wav", io.BytesIO(b"\x00" * 2048), "audio/wav")},
        )
        assert response.status_code == 200

    def test_voice_input_returns_file_id(self, client):
        """Response should include file_id for subsequent operations."""
        response = client.post(
            "/voice-input",
            files={"audio": ("test.webm", io.BytesIO(b"\x00" * 1024), "audio/webm")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert len(data["file_id"]) > 0
