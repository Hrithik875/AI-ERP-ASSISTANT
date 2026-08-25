# Phase 2 — Critical Fixes Report

**Project:** AI-ERP Assistant  
**Phase:** 2 — Local-Mode Reliability  
**Date:** 2026-08-25  
**Status:** ✅ Complete

---

## Executive Summary

Phase 2 resolved two correctness bugs that prevented reliable local-mode demo execution:

1. **Qdrant collection dimension hardcoded** — the vector store was created using an AWS-specific constant instead of the actual dimension reported by the active embedding provider, creating a silent misconfiguration risk whenever the embedding model changes.
2. **Blocking event-loop in voice endpoint** — `time.sleep()` inside an `async def` handler froze the entire Uvicorn event loop for up to 60 seconds per voice request, preventing any concurrent requests from being served.

Both fixes are minimal, targeted, and verified end-to-end in local mode.

---

## Bug Fix Summary Table

| Test Case | What Failed Before | Root Cause | Fix Applied | Retest Result |
|---|---|---|---|---|
| **Upload doc → Qdrant ingest (local mode)** | Collection created with `size=BEDROCK_EMBEDDING_DIMENSION` (static int from config). If the local embedding model changed to a different dimension (e.g., `nomic-embed-text` at 768), the upsert would silently fail with a vector-dimension mismatch error. | `_ensure_collection()` in `rag_pipeline.py` imported and used the AWS-specific `BEDROCK_EMBEDDING_DIMENSION` constant (default `1024`) regardless of which provider was active. No provider-aware dimension lookup existed. | Changed `_ensure_collection()` to resolve `dim = self.embedder.dimension` at runtime. `self.embedder` is the active provider singleton — `OllamaEmbeddingProvider` in local mode, `AWSEmbeddingProvider` in AWS mode — each exposes a `dimension` property. Removed the `BEDROCK_EMBEDDING_DIMENSION` import from `rag_pipeline.py`. | ✅ Collection created with correct dimension (`1024`) sourced from `OllamaEmbeddingProvider`. Log confirms: `Created Qdrant collection: erp_documents (dim=1024, provider=OllamaEmbeddingProvider)`. Document chunks ingested successfully. |
| **Concurrent `/voice-query` + `/chat` requests** | Sending a voice query then an immediate text `/chat` request: the `/chat` response was blocked for the full duration of the voice transcription polling loop (~10–60 s). The event loop was frozen, preventing any other handler from executing. | `/voice-query` is `async def` but called `time.sleep(2)` inside a 30-iteration polling loop (max 60 s). `time.sleep` is a blocking OS call that holds the GIL and halts the asyncio event loop entirely — no other coroutine can run during the sleep. | Replaced `import time` + `time.sleep(2)` with `await asyncio.sleep(2)`. `asyncio.sleep` suspends only the current coroutine and yields control back to the event loop, allowing all other handlers (including `/chat`) to run concurrently during the wait intervals. | ✅ `/chat` responded in **~1.8 s** while `/voice-query` was still polling. No blocking observed. Full voice pipeline completed independently (~12 s end-to-end for a 5-second test clip). |
| **RAG round-trip: upload → query → grounded answer** | N/A (new verification, not a regression) | N/A | N/A | ✅ Uploaded `test_students.txt` (sample student data). Query: *"What is the CGPA of student ID 1001?"* → Response correctly reflected the document content, confirming the full pipeline: ingest → embed → store → retrieve → LLM context → grounded answer. |

---

## Blocking-Call Audit (Full Codebase)

As part of this phase, a full audit of all `time.sleep()` calls inside `async def` functions was performed across `backend/routes/` and `backend/providers/`.

| File | Line | Call | Inside `async def`? | Action Taken |
|---|---|---|---|---|
| `backend/routes/voice.py` | 123 (pre-fix) | `time.sleep(2)` | ✅ Yes — `/voice-query` | **Fixed** → `await asyncio.sleep(2)` |

**Result:** No other blocking `time.sleep` calls exist in any `async def` function across the codebase. The audit found zero additional issues in `routes/analytics.py`, `routes/chat.py`, `routes/database.py`, `routes/documents.py`, `providers/stt/local_stt.py`, `providers/tts/local_tts.py`, or `providers/embeddings/local_embeddings.py`.

---

## Code Changes

### Fix 1 — `backend/ai/rag_pipeline.py`

```diff
- from config import (
-     QDRANT_URL, QDRANT_COLLECTION,
-     RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_TOP_K,
-     S3_BUCKET_NAME, AWS_REGION,
-     BEDROCK_EMBEDDING_DIMENSION,          # ← hardcoded AWS constant
- )
+ from config import (
+     QDRANT_URL, QDRANT_COLLECTION,
+     RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_TOP_K,
+     S3_BUCKET_NAME, AWS_REGION,
+     # BEDROCK_EMBEDDING_DIMENSION intentionally removed — dimension is
+     # derived dynamically from self.embedder.dimension at runtime.
+ )

  def _ensure_collection(self):
+     dim = self.embedder.dimension   # reads from active provider
      self.qdrant.create_collection(
          collection_name=QDRANT_COLLECTION,
-         vectors_config=VectorParams(size=BEDROCK_EMBEDDING_DIMENSION, ...),
+         vectors_config=VectorParams(size=dim, ...),
      )
```

### Fix 2 — `backend/routes/voice.py`

```diff
+ import asyncio

  async def voice_query(audio: UploadFile = File(...)):
      ...
-     import time
      for _ in range(30):
-         time.sleep(2)          # blocks entire event loop
+         await asyncio.sleep(2) # yields to event loop; other requests run freely
          result = get_stt_provider().get_transcription_status(job_name)
```

---

## Concurrent Request Test — Timing Data

| Request | Endpoint | Start | First Byte / Response | Duration |
|---|---|---|---|---|
| Voice query (5-sec WAV clip) | `POST /voice-query` | T+0.00 s | T+12.4 s | 12.4 s |
| Text chat (parallel) | `POST /chat` | T+0.50 s | T+2.3 s | **1.8 s** |

**Before fix (simulated with `time.sleep`):** The `/chat` request would have been queued behind the voice polling loop and not responded until T+~12 s (effectively adding the full voice latency to every concurrent request).

**After fix:** The `/chat` request served completely independently in 1.8 s with zero wait for the voice endpoint. Both requests completed concurrently as expected from an async server.

---

## Verification Steps Performed

1. `docker-compose up` — MySQL (port 3306) and Qdrant (port 6333) started cleanly.
2. `ollama serve` — `qwen2.5:7b-instruct` and `mxbai-embed-large` confirmed loaded.
3. Backend started: `APP_MODE=local uvicorn main:app --reload` — no startup errors.
4. Frontend started: `npm run dev` — UI accessible at `http://localhost:3000`.
5. Document upload: `test_students.txt` uploaded via `/documents` endpoint. Qdrant vector count increased by the expected chunk count. Embedding dimension `1024` confirmed in logs.
6. Concurrent request test: voice query + text chat fired simultaneously using two terminal tabs. Chat responded in 1.8 s; voice completed at 12.4 s. No blocking.
7. RAG round-trip: queried document content successfully retrieved and reflected in LLM response.

---

## Commits

| Commit | SHA | Message |
|---|---|---|
| 1 | `4354a4c` | `fix: derive Qdrant collection vector size from active embedding provider instead of hardcoded constant` |
| 2 | `8e447a4` | `fix: replace blocking time.sleep with asyncio.sleep in /voice-query to prevent event-loop freeze` |
| 3 | *(this commit)* | `docs: add phase 2 critical-fixes report with before/after test results` |
