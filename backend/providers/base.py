"""
AI ERP Assistant — Provider Base Classes
==========================================
Abstract base classes defining the interface contract for each
infrastructure service. Both AWS and Local providers implement these.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Generate a text response from the LLM."""
        ...

    @abstractmethod
    def health_check(self) -> Dict:
        """Check if the LLM service is available."""
        ...


class BaseEmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        ...


class BaseStorageProvider(ABC):
    """Abstract file storage provider interface."""

    @abstractmethod
    def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload bytes. Returns the storage key."""
        ...

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """Download file bytes."""
        ...

    @abstractmethod
    def get_url(self, key: str, expiration: int = 3600) -> str:
        """Get a URL to access the stored file."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a stored file."""
        ...

    @abstractmethod
    def ensure_ready(self) -> None:
        """Ensure the storage backend is ready (create bucket/directory etc)."""
        ...


class BaseTTSProvider(ABC):
    """Abstract text-to-speech provider interface."""

    @abstractmethod
    def synthesize(self, text: str) -> Dict:
        """
        Convert text to speech audio.
        Returns: {audio_url: str, duration_approx_s: float, error?: str}
        """
        ...


class BaseSTTProvider(ABC):
    """Abstract speech-to-text provider interface."""

    @abstractmethod
    def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> str:
        """
        Transcribe audio bytes to text.
        Returns the transcript string.
        """
        ...

    @abstractmethod
    def transcribe_async(self, audio_data: bytes, audio_format: str = "webm", job_name: str = None) -> Dict:
        """
        Start an async transcription (for AWS Transcribe compatibility).
        Returns: {job_name: str, status: str} or {status: str, transcript: str}
        For local providers, this may complete synchronously.
        """
        ...

    @abstractmethod
    def get_transcription_status(self, job_name: str) -> Dict:
        """
        Check status of an async transcription job.
        Returns: {status: 'IN_PROGRESS'|'COMPLETED'|'FAILED', transcript?: str}
        """
        ...
