"""
AI ERP Assistant — Embeddings Service (Amazon Bedrock Titan)
==============================================================
Generate embeddings using Amazon Bedrock Titan Embeddings V2.
"""

import json
import logging
from typing import List, Optional

import boto3

from config import (
    BEDROCK_EMBEDDING_REGION, BEDROCK_EMBEDDING_MODEL_ID, BEDROCK_EMBEDDING_DIMENSION,
)

logger = logging.getLogger("erp-assistant")


class EmbeddingService:
    """Generate text embeddings via Amazon Bedrock Titan Embeddings."""

    def __init__(self):
        self.model_id = BEDROCK_EMBEDDING_MODEL_ID
        self.dimension = BEDROCK_EMBEDDING_DIMENSION
        self._client = None
        logger.info(
            f"Embedding service: provider=bedrock-titan, "
            f"model={self.model_id}, dim={self.dimension}"
        )

    @property
    def client(self):
        """Lazy-init Bedrock runtime client."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=BEDROCK_EMBEDDING_REGION,
            )
        return self._client

    def embed(self, text: str) -> List[float]:
        """Embed a single text string via Bedrock Titan."""
        try:
            return self._embed_titan(text)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts (Titan doesn't support native batch, so we loop)."""
        return [self._embed_titan(t) for t in texts]

    def _embed_titan(self, text: str) -> List[float]:
        """Generate embedding via Amazon Bedrock Titan Embeddings V2."""
        body = json.dumps({
            "inputText": text,
            "dimensions": self.dimension,
            "normalize": True,
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        embedding = response_body.get("embedding", [])

        if not embedding:
            raise ValueError(f"Titan returned empty embedding for text: '{text[:50]}...'")

        return embedding


# ── Singleton ───────────────────────────────────────────────────────────────
_embedding_instance = None


def get_embedding_service():
    """
    Returns the singleton embedding provider instance from the registry.
    This maintains compatibility with existing code while supporting dual-mode.
    """
    global _embedding_instance
    if _embedding_instance is None:
        from providers.registry import get_embedding_provider
        _embedding_instance = get_embedding_provider()
    return _embedding_instance
