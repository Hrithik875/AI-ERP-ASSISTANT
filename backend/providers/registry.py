"""
AI ERP Assistant — Provider Registry
=======================================
Central factory that returns the correct provider implementation
based on APP_MODE configuration.

Usage:
    from providers.registry import get_llm_provider, get_storage_provider
    llm = get_llm_provider()
    storage = get_storage_provider()
"""

import logging
from typing import Optional

from config import APP_MODE
from providers.base import (
    BaseLLMProvider,
    BaseEmbeddingProvider,
    BaseStorageProvider,
    BaseTTSProvider,
    BaseSTTProvider,
)

logger = logging.getLogger("erp-assistant")

# ── Singletons ─────────────────────────────────────────────────────────────
_llm_provider: Optional[BaseLLMProvider] = None
_embedding_provider: Optional[BaseEmbeddingProvider] = None
_storage_provider: Optional[BaseStorageProvider] = None
_tts_provider: Optional[BaseTTSProvider] = None
_stt_provider: Optional[BaseSTTProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    """Return the LLM provider for the current APP_MODE."""
    global _llm_provider
    if _llm_provider is None:
        if APP_MODE == "local":
            from providers.llm.local_llm import OllamaLLMProvider
            _llm_provider = OllamaLLMProvider()
        else:
            from providers.llm.aws_llm import AWSLLMProvider
            _llm_provider = AWSLLMProvider()
        logger.info(f"LLM provider initialized: {type(_llm_provider).__name__} (mode={APP_MODE})")
    return _llm_provider


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Return the embedding provider for the current APP_MODE."""
    global _embedding_provider
    if _embedding_provider is None:
        if APP_MODE == "local":
            from providers.embeddings.local_embeddings import OllamaEmbeddingProvider
            _embedding_provider = OllamaEmbeddingProvider()
        else:
            from providers.embeddings.aws_embeddings import AWSEmbeddingProvider
            _embedding_provider = AWSEmbeddingProvider()
        logger.info(f"Embedding provider initialized: {type(_embedding_provider).__name__} (mode={APP_MODE})")
    return _embedding_provider


def get_storage_provider() -> BaseStorageProvider:
    """Return the storage provider for the current APP_MODE."""
    global _storage_provider
    if _storage_provider is None:
        if APP_MODE == "local":
            from providers.storage.local_storage import LocalStorageProvider
            _storage_provider = LocalStorageProvider()
        else:
            from providers.storage.aws_storage import AWSStorageProvider
            _storage_provider = AWSStorageProvider()
        logger.info(f"Storage provider initialized: {type(_storage_provider).__name__} (mode={APP_MODE})")
    return _storage_provider


def get_tts_provider() -> BaseTTSProvider:
    """Return the TTS provider for the current APP_MODE."""
    global _tts_provider
    if _tts_provider is None:
        if APP_MODE == "local":
            from providers.tts.local_tts import LocalTTSProvider
            _tts_provider = LocalTTSProvider()
        else:
            from providers.tts.aws_tts import AWSTTSProvider
            _tts_provider = AWSTTSProvider()
        logger.info(f"TTS provider initialized: {type(_tts_provider).__name__} (mode={APP_MODE})")
    return _tts_provider


def get_stt_provider() -> BaseSTTProvider:
    """Return the STT provider for the current APP_MODE."""
    global _stt_provider
    if _stt_provider is None:
        if APP_MODE == "local":
            from providers.stt.local_stt import LocalSTTProvider
            _stt_provider = LocalSTTProvider()
        else:
            from providers.stt.aws_stt import AWSSTTProvider
            _stt_provider = AWSSTTProvider()
        logger.info(f"STT provider initialized: {type(_stt_provider).__name__} (mode={APP_MODE})")
    return _stt_provider


def get_current_mode() -> str:
    """Return the current runtime mode."""
    return APP_MODE


def reset_providers():
    """Reset all cached provider singletons (useful for testing)."""
    global _llm_provider, _embedding_provider, _storage_provider, _tts_provider, _stt_provider
    _llm_provider = None
    _embedding_provider = None
    _storage_provider = None
    _tts_provider = None
    _stt_provider = None
    logger.info("All provider singletons reset")
