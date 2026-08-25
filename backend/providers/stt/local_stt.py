"""
AI ERP Assistant — Local faster-whisper STT Provider
======================================================
Uses faster-whisper for fast, local, offline speech recognition.
"""

import io
import logging
import os
import uuid
import tempfile
from typing import Dict
from providers.base import BaseSTTProvider

logger = logging.getLogger("erp-assistant")


class LocalSTTProvider(BaseSTTProvider):
    def __init__(self):
        self._model = None
        self.model_size = os.environ.get("WHISPER_MODEL", "small.en")
        logger.info(f"Local STT Provider initialized (faster-whisper, model={self.model_size})")
        # In-memory store for async jobs simulation
        self._jobs = {}

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading faster-whisper model '{self.model_size}'...")
            try:
                from faster_whisper import WhisperModel
                # Use CPU for maximum compatibility across devices, int8 for speed
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Faster-whisper model loaded successfully.")
            except ImportError:
                logger.error("faster-whisper is not installed. Run: pip install faster-whisper")
                raise
        return self._model

    def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> str:
        """Synchronously transcribe audio data."""
        try:
            # faster-whisper needs a file path or a file-like object
            # We'll write to a temp file because sometimes memory buffers confuse ffmpeg
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
                
            try:
                segments, info = self.model.transcribe(tmp_path, beam_size=5, language="en")
                text = " ".join([segment.text for segment in segments])
                text = text.strip()
                if not text:
                    text = "(No speech detected)"
                logger.info(f"Local transcription successful: '{text[:50]}...'")
                return text
            finally:
                os.remove(tmp_path)
                
        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            raise

    def transcribe_async(self, audio_data: bytes, audio_format: str = "webm", job_name: str = None) -> Dict:
        """
        Simulate an async transcription job by doing it synchronously
        and storing the result.
        """
        if not job_name:
            file_id = str(uuid.uuid4())
            job_name = f"erp-voice-{file_id}"
        else:
            file_id = job_name.replace("erp-voice-", "")
        
        # Save to storage for consistency with AWS flow
        from providers.registry import get_storage_provider
        storage = get_storage_provider()
        s3_key = f"audio/{file_id}.{audio_format}"
        storage.upload_bytes(s3_key, audio_data, f"audio/{audio_format}")
        
        import threading
        def _run_transcription():
            try:
                text = self.transcribe(audio_data, audio_format)
                self._jobs[job_name] = {
                    "status": "COMPLETED",
                    "transcript": text
                }
            except Exception as e:
                self._jobs[job_name] = {
                    "status": "FAILED",
                    "reason": str(e)
                }

        self._jobs[job_name] = {"status": "IN_PROGRESS"}
        threading.Thread(target=_run_transcription, daemon=True).start()
            
        return {
            "job_name": job_name,
            "status": "IN_PROGRESS",  # Return IN_PROGRESS so frontend polling works exactly the same
            "file_id": file_id,
            "s3_key": s3_key,
        }

    def get_transcription_status(self, job_name: str) -> Dict:
        """Return the pre-computed status."""
        if job_name in self._jobs:
            return self._jobs[job_name]
        return {"status": "FAILED", "reason": "Job not found"}
