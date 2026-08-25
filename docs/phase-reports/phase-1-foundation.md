# Phase 1 — Foundation & Tech Stack Decisions

**Project:** AI ERP Assistant — BMSCE  
**Phase:** 1 of 8  
**Date:** August 25, 2026  
**Author:** Hrithik M  
**Status:** ? Complete

---

## 1. Introduction

This report documents the technology decisions made in Phase 1 of the AI ERP Assistant project. It is written for the "Implementation Methodology" and "Introduction" sections of the final presentation. Each decision reflects a deliberate choice driven by reliability, offline capability, and the practical constraints of a college demo environment.

---

## 2. Technology Comparison Table

### 2.1 LLM Model (Local Mode)

| Aspect | Previous | New |
|---|---|---|
| Model | `llama3.2` (Ollama) | `qwen2.5:7b-instruct` (Ollama) |
| Parameters | 3B | 7B |
| Instruction tuning | General | Instruction-tuned, strong structured output |

**Justification:** The core ERP query pipeline requires the LLM to output a precisely-formatted JSON object identifying a tool name and its parameters (e.g., `{"tool_name": "AttendanceTool", "params": {"action": "student_summary", "usn": "1BM21CS001"}}`). Llama 3.2 3B frequently produced malformed JSON or hallucinated tool names, breaking the tool dispatcher. Qwen 2.5 7B Instruct is trained with a stronger emphasis on structured output and function-calling patterns, which directly matches this application''s requirement. The 7B size remains practical for a laptop-class demo machine with 16 GB RAM.

---

### 2.2 Embedding Model (Local Mode)

| Aspect | Previous | New |
|---|---|---|
| Model | `nomic-embed-text` (Ollama) | `mxbai-embed-large` (Ollama) |
| Embedding dimension | 768 | 1024 |
| MTEB benchmark (retrieval avg) | ~45 | ~54.39 |

**Justification:** The document retrieval (RAG) pipeline retrieves policy documents, circulars, and syllabi from Qdrant using cosine similarity over embedding vectors. `mxbai-embed-large` consistently outperforms `nomic-embed-text` on the MTEB retrieval benchmarks by a significant margin (~9 points average), which translates to more relevant document chunks being returned for faculty queries like "What is the attendance policy?" or "Summarize the syllabus for Data Structures." The dimension change from 768 to 1024 requires re-indexing any existing Qdrant collection, but yields materially better retrieval precision — a worthwhile trade-off before the first public demo.

---

### 2.3 Speech-to-Text Model (Local Mode)

| Aspect | Previous | New |
|---|---|---|
| Backend | faster-whisper | faster-whisper (unchanged) |
| Model size | `tiny.en` (~39 MB, ~10x realtime) | `small.en` (~244 MB, ~4x realtime) |
| Word Error Rate (clean speech) | ~15% | ~5-8% |

**Justification:** The `tiny.en` model, while extremely fast, produced a noticeable number of transcription errors during testing with academic terminology ("USN", "CGPA", "HOD", course codes like "18CS501"). These errors cascaded directly into incorrect LLM intent classification, causing the agent to pick the wrong tool or parameters. The `small.en` model is still fast enough for near-real-time transcription on a CPU (4× real-time on int8), cuts word error rate by roughly half on clear speech, and fits comfortably in memory alongside the Ollama LLM. The speed trade-off is not perceptible in a conversational interface where the user pauses naturally between queries.

---

### 2.4 Text-to-Speech (Local Mode)

| Aspect | Previous | New |
|---|---|---|
| Library | `edge-tts` | `piper-tts` |
| Offline operation | ? No — requires live connection to Microsoft Azure TTS | ? Yes — fully on-device after first model download |
| Voice quality | Neural (Azure AriaNeural) | Neural ONNX (en_US-amy-medium) |
| Network dependency at demo | Azure TTS API | None after initial ~60 MB download |

**Justification:** This is the most significant architectural improvement in Phase 1. `edge-tts` works by relaying text to Microsoft''s Azure Cognitive Services TTS endpoint over HTTPS. This means any demo environment without reliable internet (college auditorium WiFi, laptop hotspot) would cause TTS to silently fail or timeout. `piper-tts` uses an ONNX-format neural voice model running entirely via ONNX Runtime on the local CPU. After downloading the voice model file (~60 MB) on the first run, all subsequent synthesis is performed in-process with zero network calls — making the local mode stack genuinely and provably offline. The voice quality of the `en_US-amy-medium` Piper model is comparable to neural cloud voices for the short, informational sentences this assistant produces.

---

## 3. Why Tool-Based Dispatch (Not LLM-Generated SQL)

### 3.1 The Problem with LLM-Generated SQL

A naive implementation of a natural-language ERP interface would ask the LLM: *"Write a SQL query to answer: What is Aarav''s attendance?"* and execute the result directly against the database. This approach is fragile for several reasons: LLMs hallucinate table names and column names, produce syntactically invalid SQL, are susceptible to prompt injection attacks that could result in destructive queries, and produce non-deterministic output that is difficult to test or audit.

### 3.2 The Tool-Based Architecture

The AI ERP Assistant uses a structured **tool dispatch** pattern. This is implemented across three files:

**`ai/agent.py` — The Orchestrator**

The agent''s `process_query()` function runs three LLM calls, none of which generate SQL:

1. **Intent classification** (`classify_query`): The LLM is given a closed-form prompt and asked to output exactly one of three words: `erp`, `document`, or `general`. This routes the query to the right handler with zero ambiguity.

2. **Tool + parameter extraction** (`execute_tool_query`): For `erp` queries, the LLM is shown the list of available tools with their names, descriptions, and parameter schemas. It is instructed to output a single JSON object of the form `{"tool_name": "...", "params": {...}}`. The agent then looks up the named tool in the `REGISTERED_TOOLS` list and calls `tool.execute(params)` — a Python method, not a database query.

3. **Response formatting**: The tool''s structured result (a Python dict of records) is passed back to the LLM for natural-language formatting, including Markdown tables.

**`ai/tools/base.py` — The Tool Contract**

Each tool extends `BaseTool` and exposes three attributes:
- `name`: the string the LLM must emit to select this tool
- `description`: a plain-English summary shown to the LLM in the dispatch prompt
- `parameters`: a dict defining accepted parameter names and their meanings

**`ai/tools/*.py` — Domain-Specific Tools**

Each tool''s `execute(params)` method contains hard-coded, parameterized SQL queries. For example, `AttendanceTool` has an `action="student_summary"` path that runs:

```sql
SELECT usn, student_name, course_code, course_name,
       total_classes, classes_attended, attendance_pct
FROM vw_attendance_summary
WHERE usn = %s  -- parameter bound by PyMySQL driver, not string-formatted
```

The entity values (USN, name, course code) come from the LLM''s JSON extraction — but they are bound as parameterized query placeholders, not interpolated into the SQL string. This makes injection attacks structurally impossible at the database layer, while still allowing the LLM to extract the *values* from natural language.

### 3.3 Why This Approach Was Chosen

| Concern | LLM-Generated SQL | Tool Dispatch |
|---|---|---|
| SQL injection risk | High — LLM output is unpredictable | None — parameters bound by PyMySQL |
| Schema knowledge required by LLM | Full table/column names | Only tool names and parameter keys |
| Testability | Low — non-deterministic | High — each tool''s SQL is fixed and unit-testable |
| Error handling | Hard — malformed SQL crashes | Easy — tool returns `{"error": "..."}` dicts |
| LLM prompt complexity | High | Low — closed-form classification + JSON extraction |
| Auditability | Hard | Easy — all queries are in `ai/tools/*.py` |

The tool dispatch pattern also enables a clean extension path: adding a new ERP domain (e.g., fee records, library loans) means adding one new `Tool` class with its own SQL, not modifying any prompt or the agent logic.

---

## 4. Summary of Changes Made

| File | Change |
|---|---|
| `backend/config.py` | OLLAMA_MODEL ? `qwen2.5:7b-instruct`; OLLAMA_EMBEDDING_MODEL ? `mxbai-embed-large`; docstring updated |
| `backend/providers/stt/local_stt.py` | WHISPER_MODEL default ? `small.en` |
| `backend/providers/tts/local_tts.py` | Full rewrite: edge-tts removed, Piper TTS (PiperVoice API) implemented with auto-download |
| `backend/providers/embeddings/local_embeddings.py` | Fallback dimension comment updated (768?1024) |
| `backend/requirements.txt` | `edge-tts` ? `piper-tts` |
| `backend/main.py` | Startup log updated to reference Piper TTS |
| `.gitignore` | Added `backend/piper_voices/` |
| `docs/` | Created `/phase-reports/`, `/diagrams/`, `/presentation/` |
| `README.md` (root) | Created — full dual-mode setup guide |
| `backend/README.md` | Created — backend-specific dev guide |

---

## 5. Environment Reproduction Commands

To reproduce this environment from scratch on a new machine:

```bash
# 1. Clone the repo and start Docker services
git clone https://github.com/Hrithik875/AI-ERP-ASSISTANT
cd AI-ERP-ASSISTANT
docker-compose up -d

# 2. Pull required Ollama models
ollama pull qwen2.5:7b-instruct
ollama pull mxbai-embed-large

# 3. Install espeak-ng (required by Piper TTS)
# Windows:
winget install espeak-ng
# Ubuntu:
# sudo apt-get install espeak-ng

# 4. Backend setup
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
copy .env.local .env
uvicorn main:app --reload --port 8000

# 5. Frontend setup (separate terminal)
cd ../frontend
npm install
npm run dev
```

First TTS call will auto-download `piper_voices/en_US-amy-medium.onnx` (~60 MB) from Hugging Face. All subsequent operation is fully offline.
