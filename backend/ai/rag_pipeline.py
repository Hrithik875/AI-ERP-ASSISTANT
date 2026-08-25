"""
AI ERP Assistant — RAG Pipeline
=================================
Complete Retrieval-Augmented Generation pipeline:
  1. Load documents from S3 / local storage
  2. Chunk documents into passages (with page-number tracking for PDFs/DOCX)
  3. Generate embeddings via the active provider (Bedrock Titan or local Ollama)
  4. Store in Qdrant vector database
  5. Query: embed → search → filter by confidence threshold → pass context to LLM
"""

import io
import logging
import uuid
from typing import List, Dict, Optional, Tuple

from config import (
    QDRANT_URL, QDRANT_COLLECTION,
    RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_TOP_K, RAG_MIN_SCORE,
    S3_BUCKET_NAME, AWS_REGION,
    # NOTE: BEDROCK_EMBEDDING_DIMENSION is intentionally NOT imported here.
    # The collection vector size is derived dynamically from self.embedder.dimension
    # so it is always correct regardless of which embedding provider is active.
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
        """
        Create the Qdrant collection if it doesn't exist.

        The vector size is read from self.embedder.dimension rather than a
        hardcoded constant so the collection is always sized correctly for
        whichever embedding provider is currently active (AWS Titan @ 1024,
        local mxbai-embed-large @ 1024, or any future model).
        """
        from qdrant_client.models import VectorParams, Distance

        # Resolve the real dimension from the active embedding provider.
        # self.embedder is a lazy property; accessing it here is safe because
        # self._qdrant_client is already set before _ensure_collection is called.
        dim = self.embedder.dimension

        collections = [c.name for c in self.qdrant.get_collections().collections]
        if QDRANT_COLLECTION not in collections:
            self.qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Created Qdrant collection: {QDRANT_COLLECTION} "
                f"(dim={dim}, provider={type(self.embedder).__name__})"
            )
        else:
            logger.info(
                f"Qdrant collection exists: {QDRANT_COLLECTION} "
                f"(active provider dim={dim})"
            )

    # ── Document Processing ─────────────────────────────────────────────

    def chunk_text(self, text: str, page_breaks: Optional[List[int]] = None) -> List[Dict]:
        """
        Split text into overlapping chunks and annotate each with a page number.

        Args:
            text: The full document text.
            page_breaks: Sorted list of character offsets where each new page starts.
                         e.g. [0, 1500, 3200] means page 1 starts at 0, page 2 at 1500, etc.
                         If None, all chunks are tagged as page 1.

        Returns:
            List of {"text": str, "page": int, "chunk_index": int}.
        """
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + RAG_CHUNK_SIZE
            chunk = text[start:end]
            if chunk.strip():
                # Determine which page this chunk mostly falls in.
                page = 1
                if page_breaks:
                    # Find the last page break <= start
                    for p_idx, offset in enumerate(page_breaks):
                        if offset <= start:
                            page = p_idx + 1
                        else:
                            break
                chunks.append({
                    "text": chunk.strip(),
                    "page": page,
                    "chunk_index": idx,
                })
                idx += 1
            start += RAG_CHUNK_SIZE - RAG_CHUNK_OVERLAP
        return chunks

    def extract_text_from_storage(self, storage_key: str) -> Tuple[str, Optional[List[int]]]:
        """
        Download a document from storage and extract text.

        Returns:
            (full_text, page_breaks) where page_breaks is a list of character
            offsets marking the start of each page (for PDFs/DOCX), or None if
            page tracking is not applicable (txt, csv, xlsx).
        """
        try:
            content = self.storage.download_bytes(storage_key)

            ext = storage_key.rsplit(".", 1)[-1].lower()

            if ext == "txt":
                return content.decode("utf-8", errors="ignore"), None

            elif ext == "csv":
                return content.decode("utf-8", errors="ignore"), None

            elif ext == "pdf":
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(io.BytesIO(content))
                    pages = []
                    page_breaks = []
                    offset = 0
                    for page in reader.pages:
                        page_breaks.append(offset)
                        text = page.extract_text()
                        if text:
                            pages.append(text)
                            offset += len(text) + 2  # +2 for the "\n\n" separator
                        # If no text on this page, offset stays the same
                    return "\n\n".join(pages), page_breaks if page_breaks else None
                except ImportError:
                    logger.warning("PyPDF2 not installed; cannot extract PDF text")
                    return f"[PDF document: {storage_key}]", None

            elif ext in ("doc", "docx"):
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(content))
                    # DOCX doesn't have clean page breaks in python-docx, but
                    # we can approximate by treating every ~3000 chars as a page
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    full_text = "\n".join(paragraphs)
                    # Approximate page breaks (~3000 chars per page)
                    page_breaks = list(range(0, len(full_text), 3000)) if full_text else None
                    return full_text, page_breaks
                except ImportError:
                    logger.warning("python-docx not installed; cannot extract DOCX text")
                    return f"[DOCX document: {storage_key}]", None

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
                    return "\n".join(rows), None
                except ImportError:
                    logger.warning("openpyxl not installed; cannot extract XLSX text")
                    return f"[XLSX document: {storage_key}]", None

            else:
                return content.decode("utf-8", errors="ignore"), None

        except Exception as e:
            logger.error(f"Failed to extract text from storage key={storage_key}: {e}")
            raise

    def ingest_document(self, storage_key: str, doc_id: str, filename: str) -> int:
        """
        Full ingestion pipeline:
          1. Download from storage
          2. Extract text (with page break tracking for PDFs/DOCX)
          3. Chunk (annotating each chunk with its page number)
          4. Embed via provider
          5. Store in Qdrant (with page metadata for citation support)
        Returns number of chunks stored.
        """
        logger.info(f"Ingesting document: {filename} (key={storage_key})")

        text, page_breaks = self.extract_text_from_storage(storage_key)
        if not text.strip():
            logger.warning(f"No text extracted from {storage_key}")
            return 0

        chunks = self.chunk_text(text, page_breaks)
        logger.info(f"Document chunked into {len(chunks)} passages")

        if not chunks:
            return 0

        chunk_texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed_batch(chunk_texts)

        from qdrant_client.models import PointStruct

        points = []
        for chunk_meta, embedding in zip(chunks, embeddings):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "doc_id": doc_id,
                        "filename": filename,
                        "storage_key": storage_key,
                        "chunk_index": chunk_meta["chunk_index"],
                        "page": chunk_meta["page"],
                        "text": chunk_meta["text"],
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
        Search for relevant document chunks, filtering by RAG_MIN_SCORE.

        Returns list of {text, filename, doc_id, page, score} for chunks
        that meet the minimum similarity threshold.  Returns an empty list
        if no chunk passes the filter.
        """
        k = top_k or RAG_TOP_K

        try:
            query_embedding = self.embedder.embed(query)

            results = self.qdrant.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_embedding,
                limit=k,
            )

            # Filter by confidence threshold
            hits = []
            dropped = 0
            for r in results:
                if r.score >= RAG_MIN_SCORE:
                    hits.append({
                        "text": r.payload.get("text", ""),
                        "filename": r.payload.get("filename", ""),
                        "doc_id": r.payload.get("doc_id", ""),
                        "page": r.payload.get("page"),
                        "chunk_index": r.payload.get("chunk_index"),
                        "score": round(r.score, 4),
                    })
                else:
                    dropped += 1

            logger.info(
                f"RAG search: {len(hits)} above threshold, {dropped} dropped "
                f"(min_score={RAG_MIN_SCORE}) for query: '{query[:60]}'"
            )
            return hits

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []

    def search_with_sources(self, query: str, top_k: int = None) -> Dict:
        """
        High-level RAG query that returns both the formatted context string
        and a structured sources list for API citation responses.

        Returns:
            {
                "context": str,              # formatted text for LLM prompt
                "sources": List[Dict],       # [{filename, page, score}]
                "has_relevant_results": bool, # False => no-match fallback
            }
        """
        hits = self.search(query, top_k)

        if not hits:
            return {
                "context": "",
                "sources": [],
                "has_relevant_results": False,
            }

        # Build context string for LLM
        context_parts = []
        sources = []
        for i, hit in enumerate(hits):
            context_parts.append(
                f"[Source {i+1}: {hit['filename']} "
                f"(page {hit.get('page', '?')}, relevance: {hit['score']:.2f})]\n{hit['text']}"
            )
            sources.append({
                "filename": hit["filename"],
                "page": hit.get("page"),
                "score": hit["score"],
            })

        return {
            "context": "\n\n---\n\n".join(context_parts),
            "sources": sources,
            "has_relevant_results": True,
        }

    def get_context(self, query: str, top_k: int = None) -> str:
        """Search and format results as context string for LLM (legacy)."""
        result = self.search_with_sources(query, top_k)
        return result["context"]

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
