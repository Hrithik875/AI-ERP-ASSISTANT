"""
AI ERP Assistant — RAG Pipeline
=================================
Complete Retrieval-Augmented Generation pipeline:
  1. Load documents from S3
  2. Chunk documents into passages
  3. Generate embeddings (Amazon Bedrock Titan Embeddings V2)
  4. Store in Qdrant vector database
  5. Query: embed → search → retrieve → pass context to LLM
"""

import io
import logging
import uuid
from typing import List, Dict, Optional

from config import (
    QDRANT_URL, QDRANT_COLLECTION,
    RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_TOP_K,
    S3_BUCKET_NAME, AWS_REGION,
    BEDROCK_EMBEDDING_DIMENSION,
)

logger = logging.getLogger("erp-assistant")


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline backed by Qdrant."""

    def __init__(self):
        self._qdrant_client = None
        self._embedding_service = None
        self._storage_provider = None
        logger.info("RAGPipeline initialized")

    @property
    def qdrant(self):
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient
            self._qdrant_client = QdrantClient(url=QDRANT_URL)
            self._ensure_collection()
        return self._qdrant_client

    @property
    def embedder(self):
        if self._embedding_service is None:
            from ai.embeddings import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def storage(self):
        if self._storage_provider is None:
            from providers.registry import get_storage_provider
            self._storage_provider = get_storage_provider()
        return self._storage_provider

    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        from qdrant_client.models import VectorParams, Distance

        collections = [c.name for c in self.qdrant.get_collections().collections]
        if QDRANT_COLLECTION not in collections:
            self.qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=BEDROCK_EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION} (dim={BEDROCK_EMBEDDING_DIMENSION})")
        else:
            logger.info(f"Qdrant collection exists: {QDRANT_COLLECTION}")

    # ── Document Processing ─────────────────────────────────────────────

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + RAG_CHUNK_SIZE
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start += RAG_CHUNK_SIZE - RAG_CHUNK_OVERLAP
        return chunks

    def extract_text_from_storage(self, storage_key: str) -> str:
        """Download a document from storage and extract text."""
        try:
            content = self.storage.download_bytes(storage_key)

            ext = storage_key.rsplit(".", 1)[-1].lower()

            if ext == "txt":
                return content.decode("utf-8", errors="ignore")

            elif ext == "csv":
                return content.decode("utf-8", errors="ignore")

            elif ext == "pdf":
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(io.BytesIO(content))
                    pages = []
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            pages.append(text)
                    return "\n\n".join(pages)
                except ImportError:
                    logger.warning("PyPDF2 not installed; cannot extract PDF text")
                    return f"[PDF document: {storage_key}]"

            elif ext in ("doc", "docx"):
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(content))
                    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                except ImportError:
                    logger.warning("python-docx not installed; cannot extract DOCX text")
                    return f"[DOCX document: {storage_key}]"

            elif ext == "xlsx":
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
                    rows = []
                    for sheet in wb.worksheets:
                        for row in sheet.iter_rows(values_only=True):
                            row_text = " | ".join(str(c) if c is not None else "" for c in row)
                            if row_text.strip():
                                rows.append(row_text)
                    return "\n".join(rows)
                except ImportError:
                    logger.warning("openpyxl not installed; cannot extract XLSX text")
                    return f"[XLSX document: {storage_key}]"

            else:
                return content.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Failed to extract text from storage key={storage_key}: {e}")
            raise

    def ingest_document(self, storage_key: str, doc_id: str, filename: str) -> int:
        """
        Full ingestion pipeline:
          1. Download from storage
          2. Extract text
          3. Chunk
          4. Embed via provider
          5. Store in Qdrant
        Returns number of chunks stored.
        """
        logger.info(f"Ingesting document: {filename} (key={storage_key})")

        text = self.extract_text_from_storage(storage_key)
        if not text.strip():
            logger.warning(f"No text extracted from {storage_key}")
            return 0

        chunks = self.chunk_text(text)
        logger.info(f"Document chunked into {len(chunks)} passages")

        if not chunks:
            return 0

        embeddings = self.embedder.embed_batch(chunks)

        from qdrant_client.models import PointStruct

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "doc_id": doc_id,
                        "filename": filename,
                        "storage_key": storage_key,
                        "chunk_index": i,
                        "text": chunk,
                    },
                )
            )

        self.qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points,
        )

        logger.info(f"Stored {len(points)} vectors in Qdrant for doc {doc_id}")
        return len(points)

    # ── Query Pipeline ──────────────────────────────────────────────────

    def search(self, query: str, top_k: int = None) -> List[Dict]:
        """
        Search for relevant document chunks.
        Returns list of {text, filename, score}.
        """
        k = top_k or RAG_TOP_K

        try:
            query_embedding = self.embedder.embed(query)

            results = self.qdrant.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_embedding,
                limit=k,
            )

            hits = []
            for r in results:
                hits.append({
                    "text": r.payload.get("text", ""),
                    "filename": r.payload.get("filename", ""),
                    "doc_id": r.payload.get("doc_id", ""),
                    "score": r.score,
                })

            logger.info(f"RAG search returned {len(hits)} results for query: '{query[:60]}'")
            return hits

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []

    def get_context(self, query: str, top_k: int = None) -> str:
        """Search and format results as context string for LLM."""
        hits = self.search(query, top_k)
        if not hits:
            return ""

        context_parts = []
        for i, hit in enumerate(hits):
            context_parts.append(
                f"[Source {i+1}: {hit['filename']} (relevance: {hit['score']:.2f})]\n{hit['text']}"
            )

        return "\n\n---\n\n".join(context_parts)

    def document_count(self) -> int:
        """Return total number of vectors in the collection."""
        try:
            info = self.qdrant.get_collection(QDRANT_COLLECTION)
            return info.points_count
        except Exception:
            return 0


# ── Singleton ───────────────────────────────────────────────────────────────
_rag_instance: Optional[RAGPipeline] = None


def get_rag() -> RAGPipeline:
    """Return singleton RAG pipeline."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGPipeline()
    return _rag_instance
