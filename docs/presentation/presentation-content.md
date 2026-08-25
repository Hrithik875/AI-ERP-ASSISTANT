# AI-ERP-ASSISTANT — Presentation Content
*Compiled from Phase 1–7 deliverables for the Aug 28 review*

---

## 1. Problem Statement & Motivation

### The Gap in Academic ERP Systems

Modern universities manage mountains of data — attendance records, grade sheets, timetables, HR documents, policies — spread across siloed databases and PDF repositories. Staff and students currently must:

- Log into separate portals for attendance vs. grades vs. documents.
- Formulate precise queries in rigid search forms.
- Cross-reference data manually (e.g., "which students are at-risk AND enrolled in CS601?").

**This project addresses that gap** by placing a conversational AI layer directly in front of the ERP, allowing natural-language queries that span databases and documents simultaneously.

### Why Existing Chatbots Fall Short

| Limitation | Typical Chatbot | This System |
|---|---|---|
| SQL hallucination | LLM writes SQL → injections / wrong answers | Parameterized tools only — no LLM SQL |
| No document grounding | Answers from model weights | RAG against institutional documents |
| Stateless conversations | Forgets prior turn immediately | 8-turn bounded conversation context |
| Vendor lock-in | Single provider | Dual-mode: local Ollama or AWS Bedrock |
| Opaque answers | No source attribution | Tool badge + source citations on every reply |

---

## 2. System Architecture Overview

### High-Level Stack

```
User
 │
 ▼
Next.js 14 (TypeScript)          ← Frontend: ChatUI, VoicePipeline, StatusPanel
 │  EventSource (SSE)
 ▼
FastAPI (Python 3.12)            ← Backend: routes + middleware
 │  RequestID Middleware
 ▼
AI Agent (agent.py)              ← Orchestrator
 ├─ classify_query()  → fast LLM (3b)
 ├─ execute_tool_query() → fast LLM (3b) dispatch
 └─ format answer → full LLM (7b)
      │
      ├─ ERP Tools → MySQL (parameterized SQL)
      └─ DocumentTool → RAG Pipeline → Qdrant
```

### Provider Abstraction (dual-mode)

All AI components are behind an abstract interface in `providers/base.py`. A single `APP_MODE` env var switches the entire stack:

| Component | Local (APP_MODE=local) | AWS (APP_MODE=aws) |
|---|---|---|
| LLM | Ollama qwen2.5:7b + 3b | Bedrock Claude 3 Haiku |
| Embeddings | nomic-embed-text | Titan Embeddings G1 |
| Storage | Local filesystem | Amazon S3 |
| TTS | pyttsx3 | Amazon Polly |
| STT | faster-whisper tiny.en | Amazon Transcribe |
| Database | MySQL 8.0 local | Aurora MySQL |
| Vectors | Qdrant local | Qdrant hosted |

**Architecture diagrams**: see `docs/diagrams/` (5 Mermaid files covering overall, dual-mode, agent flow, RAG pipeline, voice pipeline).

---

## 3. Key Features (Phase-by-Phase)

### Phase 1 — Foundation

- Next.js 14 + FastAPI scaffold with end-to-end `/chat` call.
- Ollama local LLM integration (qwen2.5:7b-instruct).
- MySQL schema: students, attendance_records, grades, courses, timetable.
- Basic voice pipeline: record → transcribe → speak.
- Document upload + Qdrant vector ingestion.

### Phase 2 — Critical Fixes

- Voice recording fixed (WAV blob, correct MIME type).
- `/chat` JSON parse errors resolved.
- Attendance schema mismatch patched.
- ERP tool `course_code` parameter handling corrected.

### Phase 3 — Security Hardening

- JWT-based auth with role-based access control (admin / staff / student).
- CORS policy tightened to explicit allowed origins.
- All parameterized queries audited; SQL injection surface eliminated.
- Structured error responses (no stack traces to client).
- Rate limiting middleware on chat and voice endpoints.

### Phase 4 — RAG Improvements

- Chunking upgraded: 500-token chunks / 50-token overlap, paragraph-boundary aware.
- MMR (Maximal Marginal Relevance) reranker for chunk diversity.
- Similarity threshold gating: below threshold → "no relevant documents found" (prevents hallucination).
- Source attribution: every document answer carries `{source_name, chunk_index, score}`.

### Phase 5 — Conversation Context & ERP Reasoning

- Frontend: history[] accumulated in React state, last 8 turns sent with every `/chat` request.
- Backend: `_format_history_context()` injects last 4 turns into classify + dispatch prompts.
- Referential resolution: "which one has the lowest attendance?" now resolves correctly.
- Compound reasoning tools:
  - `AttendanceTool action=calculate_classes_needed` → "needs N more classes to reach 75%"
  - `AttendanceTool action=calculate_classes_can_miss` → "can miss N more safely"
- Tool transparency: every chat response carries a `tool_used` badge visible in the UI.
- Explainability: format prompt instructs LLM to show current %, threshold, gap, and count.

### Phase 6 — Testing Overhaul

- Mode-aware test assertions: `test_api.py` reads actual APP_MODE, no hardcoded provider strings.
- All external calls mocked: `_StubLLM`, `_StubEmbedding`, mock MySQL via `unittest.mock`.
- Negative tests: invalid auth, malformed voice upload, missing document, oversized payload.
- RAG regression tests: known-good document + known query → expected passage appears in answer.
- Conversation context tests: multi-turn scenarios verify history forwarding.
- Voice failure tests: bad audio format returns 422, corrupted audio returns graceful error.
- **Result: 107 tests, 100% pass rate** (run: `pytest tests/ -v`).

### Phase 7 — Performance & Observability

- **Latency instrumentation**: per-step timings logged — classify / dispatch / tool / format.
- **Dual-model tiering**: 3b model for classify + dispatch (fast, cheap); 7b model for final answer (quality).
- **SSE streaming**: `POST /chat/stream` — first token delivered before full response is ready; perceived latency ↓ dramatically.
- **Model pre-warming**: lifespan startup event fires a throwaway prompt to both Ollama models, eliminating cold-start delays.
- **Correlation IDs**: every request gets `X-Request-ID`, threaded through all agent logs.
- **`GET /system-status`**: deep health check (DB ping, Qdrant ping, Ollama reachability, model list).
- **StatusPanel** in frontend: shows live latency, mode, provider health.
- **Measured baseline** (CPU-only, no GPU):
  - ERP query median: ~25 s wall-clock (SSE streams first tokens in ~3 s).
  - RAG warm cache: ~8 s.
  - General LLM: ~6 s.

---

## 4. Technical Challenges & Solutions

| Challenge | Root Cause | Solution |
|---|---|---|
| LLM writes wrong SQL | Non-deterministic generation | Tool-based architecture: LLM selects tool + params, SQL is parameterized and hardcoded in Python |
| Voice transcription Error 1094995529 | faster-whisper I/O race on Windows CPU | Documented limitation; retry on client side; AWS Transcribe is the robust alternative |
| Cold-start Ollama latency (~20 s first query) | Model not loaded into VRAM/RAM | Lifespan pre-warming sends dummy prompt on FastAPI startup |
| Follow-up questions fail ("which one is lowest?") | Stateless `/chat` — no prior context | Bounded history: frontend sends last 8 turns; agent injects last 4 into every LLM prompt |
| RAG hallucination on irrelevant queries | Low-score chunks still used | Similarity threshold gate: below threshold returns explicit "no relevant documents" |
| Test flakiness (live LLM calls) | Network + model variability | All providers mocked in tests via `_StubLLM` / `_StubEmbedding` |
| AWS vs. local assertion mismatches in tests | Hardcoded provider strings | Mode-aware parametrize: tests read APP_MODE from config |

---

## 5. Test Coverage Summary

### Test Suite Stats (Phase 6 baseline)

| File | Tests | Category |
|---|---|---|
| `test_api.py` | 28 | API routes, auth, mode-aware assertions |
| `test_ai.py` | 31 | Agent logic, tool dispatch, RAG, all mocked |
| `test_voice.py` | 18 | Voice transcription + TTS, failure paths |
| `test_security.py` | 16 | JWT, CORS, rate limiting, SQL injection probes |
| `test_context.py` | 14 | Multi-turn conversation context, referential resolution |
| **Total** | **107** | **100% pass, ~6 s runtime** |

### Test Methodology

- **Unit**: each tool, LLM call, and embedding call tested in isolation with stubs.
- **Integration**: full request path through FastAPI → agent → mock DB → response.
- **Negative**: invalid inputs, missing fields, oversized payloads, bad auth.
- **Regression**: RAG pipeline evaluated against a seeded document corpus with known expected passages.

---

## 6. Demo Walkthrough Script

*All queries validated on local hardware (i7-12th gen, 16 GB RAM, no GPU, APP_MODE=local).*

### Prerequisites
1. `ollama serve` running; `qwen2.5:7b-instruct` and `qwen2.5:3b-instruct` pulled.
2. MySQL running; `erp_db` seeded.
3. Qdrant running on port 6333.
4. Backend: `cd backend && python -m uvicorn main:app --port 8000`.
5. Frontend: `cd frontend && npm run dev`.

### Demo Sequence

| # | Query | Expected Behaviour | Tool Used |
|---|---|---|---|
| 1 | "What is the attendance of Aarav M?" | Returns attended/total, percentage, risk flag | AttendanceTool |
| 2 | "How many more classes does he need to reach 75%?" | References prior turn; calculates needed classes | Reasoning (AttendanceTool) |
| 3 | "Show all at-risk students in CS601" | Markdown table, shortage gap highlighted | AttendanceTool |
| 4 | "Which one has the lowest attendance?" | Resolves "which one" from prior CS601 result | AttendanceTool |
| 5 | "What does the college policy say about attendance?" | Retrieves from uploaded circular; shows source | DocumentTool |
| 6 | "What are the grades for CS601?" | Markdown grade table | GradesTool |
| 7 | (Voice) "What is my timetable for Monday?" | Mic → transcript → timetable → spoken response | TimetableTool |

### What to Show in UI
- **Tool badge** on each bubble (e.g., "AttendanceTool", "Reasoning (AttendanceTool)").
- **Source citation** on document answers (file name, chunk index).
- **StatusPanel** (bottom of chat): provider mode, DB/Qdrant health, last latency.
- **Streaming** — answer builds token-by-token; no frozen UI waiting for full response.

---

## 7. Known Limitations & Future Work

### Current Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| CPU-only inference (no GPU) | ~25 s ERP, ~8 s RAG wall-clock | SSE streaming hides latency; pre-warming eliminates cold start |
| faster-whisper Error 1094995529 | Intermittent voice failures on Windows | Retry on client; AWS Transcribe has no this issue |
| No persistent server-side session store | History lost on backend restart | Frontend localStorage preserves display history across page reloads |
| Qdrant runs in-memory on local | Vectors lost on restart if no snapshot | Documented; `qdrant_storage/` path configured for persistence |
| No multi-user auth in demo | Single JWT token for demo | Full RBAC implemented; token-per-user flow works |

### Recommended Next Steps

1. **GPU deployment**: Move Ollama to a machine with an NVIDIA GPU — expected 5–8× latency reduction.
2. **Fine-tuned intent classifier**: Replace LLM fallback in `classify_query()` with a small fine-tuned BERT-class model; reduces fast-model dependency for classification.
3. **Persistent session store (Redis)**: Move conversation history server-side; enables multi-device continuity.
4. **Evaluation harness**: Automate the RAG regression tests against a larger golden document set.
5. **AWS production deployment**: Swap `APP_MODE=aws`; provision RDS Aurora + Bedrock; deploy backend on ECS/Lambda.

---

## 8. Phase Completion Matrix

| Phase | Scope | Status | Key Deliverable |
|---|---|---|---|
| 1 — Foundation | Scaffold, MySQL, Ollama, basic chat/voice/RAG | ✅ Complete | Working end-to-end demo |
| 2 — Critical Fixes | Voice, JSON parse, attendance schema, tools | ✅ Complete | Bug-free baseline |
| 3 — Security | JWT auth, CORS, rate limiting, parameterized SQL | ✅ Complete | RBAC + security audit |
| 4 — RAG | Chunking, MMR reranker, threshold gating, citations | ✅ Complete | Grounded document answers |
| 5 — Reasoning/Context | Multi-turn history, compound ERP calc, tool transparency | ✅ Complete | Referential follow-ups work |
| 6 — Testing | 107 tests, mocked, mode-aware, negative, RAG regression | ✅ Complete | 100% pass rate, ~6 s |
| 7 — Performance | Timing, dual-model, SSE stream, pre-warm, /system-status | ✅ Complete | Sub-5 s first-token on ERP |
| 8 — Documentation | Architecture diagrams, README, this document | ✅ Complete | Presentation ready |
