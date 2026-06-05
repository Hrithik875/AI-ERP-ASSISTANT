"""
AI ERP Assistant — AWS Titan Embedding Provider
=================================================
Wrapper around the existing EmbeddingService.
"""

from typing import List
from providers.base import BaseEmbeddingProvider


class AWSEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        from ai.embeddings import EmbeddingService
        self._svc = EmbeddingService()

    @property
    def dimension(self) -> int:
        return self._svc.dimension

    def embed(self, text: str) -> List[float]:
        return self._svc.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self._svc.embed_batch(texts)
