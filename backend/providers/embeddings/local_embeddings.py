"""
AI ERP Assistant — Local Ollama Embedding Provider
====================================================
Uses local Ollama instance for embeddings via HTTP API.
"""

import logging
import requests
from typing import List

from config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL
from providers.base import BaseEmbeddingProvider

logger = logging.getLogger("erp-assistant")


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        self.model = OLLAMA_EMBEDDING_MODEL
        self._dimension = None
        logger.info(f"Ollama Embedding Provider initialized (url={self.base_url}, model={self.model})")

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # Get dimension by embedding a test string
            try:
                emb = self.embed("test")
                self._dimension = len(emb)
                logger.info(f"Detected Ollama embedding dimension: {self._dimension}")
            except Exception as e:
                logger.error(f"Failed to detect embedding dimension: {e}")
                self._dimension = 1024  # fallback default for mxbai-embed-large
        return self._dimension

    def embed(self, text: str) -> List[float]:
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            embedding = result.get("embedding", [])
            
            if not embedding:
                raise ValueError(f"Ollama returned empty embedding for text: '{text[:50]}...'")
                
            return embedding
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Ollama doesn't have a native batch embed endpoint yet, so we loop
        return [self.embed(t) for t in texts]
