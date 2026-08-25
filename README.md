# AI ERP Assistant

> **A conversational AI layer for academic ERP systems** — natural-language queries
> across attendance, grades, timetables, and institutional documents, with full
> local (Ollama) and AWS (Bedrock) deployment modes.

[![Tests](https://img.shields.io/badge/tests-107%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![Next.js](https://img.shields.io/badge/next.js-14-black)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Local Setup (APP\_MODE=local)](#local-setup-app_modelocal)
5. [AWS Setup (APP\_MODE=aws)](#aws-setup-app_modeaws)
6. [Environment Variables](#environment-variables)
7. [Running Tests](#running-tests)
8. [API Reference](#api-reference)
9. [Project Structure](#project-structure)
10. [Known Limitations](#known-limitations)
11. [Documentation](#documentation)

---

## Features

| Feature | Details |
|---|---|
| **Conversational ERP queries** | Attendance, grades, timetable, courses, analytics — natural language |
| **Multi-turn context** | Last 8 turns sent per request; agent resolves referential follow-ups |
| **Compound reasoning** | "How many more classes does he need to reach 75%?" computed, not guessed |
| **RAG document answers** | Upload PDFs/DOCX; MMR-reranked chunked retrieval with source citations |
| **Voice interface** | Record → transcribe → query → spoken response |
| **SSE streaming** | First token delivered in ~3 s; no frozen UI |
| **Tool transparency** | Every answer carries a `tool_used` badge |
| **Dual-mode deployment** | `APP_MODE=local` (Ollama) or `APP_MODE=aws` (Bedrock) — same codebase |
| **Full test suite** | 107 tests, 100% pass, all external calls mocked |
| **Observability** | `GET /system-status`, correlation IDs, per-step timing logs |

---

## Architecture

```
Browser (Next.js 14)
  │  EventSource / fetch
  ▼
FastAPI  ←  RequestID Middleware
  │
  ▼
AI Agent (agent.py)
  ├─ classify_query()    →  fast LLM  (qwen2.5:3b / Bedrock)
  ├─ execute_tool_query()→  fast LLM  (tool JSON extraction)
  └─ format answer       →  full LLM  (qwen2.5:7b / Bedrock)
       │
       ├─ AttendanceTool / GradesTool / TimetableTool
       │   CourseTool / AnalyticsTool  →  MySQL (parameterized)
       └─ DocumentTool  →  RAG Pipeline  →  Qdrant
```

Five detailed Mermaid architecture diagrams are in [`docs/diagrams/`](docs/diagrams/):

| File | Describes |
|---|---|
| `01-overall-architecture.mmd` | Full system component map |
| `02-dual-mode-architecture.mmd` | Local vs. AWS provider abstraction |
| `03-agent-flow.mmd` | Request sequence through classify → dispatch → stream |
| `04-rag-pipeline.mmd` | Document ingestion + query-time retrieval |
| `05-voice-pipeline.mmd` | Voice record → transcribe → respond → speak |

---

## Prerequisites

### Common (both modes)

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.12 | Backend runtime |
| Node.js | ≥ 18 | Frontend build |
| MySQL | 8.0 | ERP database |
| Git | any | Cloning |

### Local mode only

| Tool | Install | Purpose |
|---|---|---|
| [Ollama](https://ollama.com) | `winget install Ollama.Ollama` | Local LLM + embeddings |
| [Qdrant](https://qdrant.tech/documentation/quick-start/) | Docker or binary | Local vector store |

### AWS mode only

- AWS account with Bedrock model access (Claude 3 Haiku + Titan Embeddings G1 enabled in your region).
- IAM role/user with: `bedrock:InvokeModel`, `s3:*`, `polly:SynthesizeSpeech`, `transcribe:StartTranscriptionJob`, `rds-data:*`.
- Aurora MySQL cluster (or RDS MySQL 8.0).

---

## Local Setup (APP\_MODE=local)

### 1. Clone and install

```bash
git clone https://github.com/your-org/AI-ERP-ASSISTANT.git
cd AI-ERP-ASSISTANT
```

### 2. Pull Ollama models

```bash
ollama pull qwen2.5:7b-instruct    # full-quality answer model  (~5 GB)
ollama pull qwen2.5:3b-instruct    # fast dispatch/classify model (~2 GB)
ollama pull mxbai-embed-large      # embeddings
ollama serve                        # keep running in a separate terminal
```

### 3. Start Qdrant

```bash
# Docker (recommended)
docker run -p 6333:6333 qdrant/qdrant

# Or download binary from https://github.com/qdrant/qdrant/releases
```

### 4. Create and seed the MySQL database

```bash
mysql -u root -p < backend/scripts/schema.sql
mysql -u root -p erp_db < backend/scripts/seed_data.sql
```

### 5. Configure environment

```bash
cp backend/.env.sample backend/.env.local
```

Edit `backend/.env.local`:

```env
APP_MODE=local

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=erp_db

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_FAST_MODEL=qwen2.5:3b-instruct
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Auth
JWT_SECRET=change-me-in-production
```

### 6. Start the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
$env:PYTHONPATH="backend"
python -m uvicorn main:app --port 8000 --log-level info
```

On startup you will see:

```
[INFO] Pre-warming Ollama models: qwen2.5:3b-instruct, qwen2.5:7b-instruct
[INFO] LLM provider initialized: OllamaLLMProvider (mode=local)
[INFO] Application startup complete.
```

### 7. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**.

---

## AWS Setup (APP\_MODE=aws)

### 1. Enable Bedrock models

In the AWS Console → Bedrock → Model access, enable:
- `anthropic.claude-3-haiku-20240307-v1:0`
- `amazon.titan-embed-text-v1`

### 2. Configure environment

```bash
cp backend/.env.sample backend/.env
```

Edit `backend/.env`:

```env
APP_MODE=aws

# AWS credentials (or use IAM role / env vars)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v1

# Aurora MySQL
DB_HOST=<cluster-endpoint>
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=...
DB_NAME=erp_db

# S3
S3_BUCKET_NAME=your-erp-docs-bucket

# Qdrant (hosted or self-managed)
QDRANT_HOST=your-qdrant-host
QDRANT_PORT=6333

# Auth
JWT_SECRET=change-me-in-production
```

### 3. Deploy backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Or deploy to Lambda using backend/deploy.ps1
```

---

## Environment Variables

Full reference — all keys accepted by `backend/config.py`:

| Variable | Default | Description |
|---|---|---|
| `APP_MODE` | `aws` | `local` or `aws` |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | — | MySQL user |
| `DB_PASSWORD` | — | MySQL password |
| `DB_NAME` | `erp_db` | MySQL database name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Full-quality LLM |
| `OLLAMA_FAST_MODEL` | `qwen2.5:3b-instruct` | Fast dispatch LLM |
| `OLLAMA_EMBEDDING_MODEL` | `mxbai-embed-large` | Embedding model |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `LLM_TIMEOUT_SECONDS` | `60` | Hard timeout per LLM call |
| `DB_QUERY_TIMEOUT_SECONDS` | `10` | Hard timeout per MySQL query |
| `QDRANT_TIMEOUT_SECONDS` | `10` | Hard timeout per Qdrant call |
| `JWT_SECRET` | — | Secret for JWT signing |
| `AWS_REGION` | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | — | Bedrock LLM model ID |
| `BEDROCK_EMBEDDING_MODEL_ID` | — | Bedrock embedding model ID |
| `S3_BUCKET_NAME` | — | S3 bucket for documents (AWS mode) |

---

## Running Tests

All external calls (LLM, DB, Qdrant) are mocked. Tests run offline in ~6 s.

```bash
cd backend
$env:PYTHONPATH="backend"
pytest tests/ -v
```

Expected output:

```
107 passed in 5.9s
```

To run a specific category:

```bash
pytest tests/test_api.py -v          # route + auth tests
pytest tests/test_ai.py -v           # agent + tool tests (mocked)
pytest tests/test_voice.py -v        # voice pipeline tests
pytest tests/test_security.py -v     # security tests
pytest tests/test_context.py -v      # multi-turn context tests
```

---

## API Reference

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Non-streaming chat (JSON response) |
| `POST` | `/chat/stream` | SSE streaming chat — recommended |

**Request body:**
```json
{
  "message": "How many more classes does Aarav M need to reach 75%?",
  "history": [
    {"role": "user", "content": "What is Aarav M's attendance?"},
    {"role": "assistant", "content": "Aarav M has attended 28/40 classes (70.0%)..."}
  ]
}
```

**SSE event format:**
```
data: {"token": "Aarav"}
data: {"token": " needs"}
...
data: {"done": true, "tool_used": "Reasoning (AttendanceTool)", "sources": []}
```

### Voice

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/voice/transcribe` | Upload audio → transcript + answer + audio |
| `POST` | `/voice/speak` | Text → synthesized audio |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/documents/upload` | Upload PDF/DOCX/TXT for RAG ingestion |
| `GET` | `/documents` | List ingested documents |
| `DELETE` | `/documents/{id}` | Remove a document |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic liveness probe |
| `GET` | `/system-status` | Deep health: DB, Qdrant, Ollama, model list |

### ERP Data (read-only, JWT required)

`GET /attendance/{usn}` · `GET /grades/{usn}` · `GET /timetable/{usn}`
`GET /students` · `GET /courses` · `GET /analytics`

---

## Project Structure

```
AI-ERP-ASSISTANT/
├── backend/
│   ├── ai/
│   │   ├── agent.py          # Orchestrator: classify → dispatch → format
│   │   ├── rag_pipeline.py   # Chunk, embed, retrieve, rerank
│   │   ├── tools/            # AttendanceTool, GradesTool, …
│   │   └── llm_service.py    # LLM façade used by agent
│   ├── providers/
│   │   ├── base.py           # Abstract interfaces for all providers
│   │   ├── registry.py       # Factory: APP_MODE → concrete provider
│   │   ├── llm/              # OllamaLLMProvider, AWSLLMProvider
│   │   ├── embeddings/       # OllamaEmbeddingProvider, AWSEmbeddingProvider
│   │   ├── storage/          # LocalStorageProvider, AWSStorageProvider
│   │   ├── tts/              # LocalTTSProvider, AWSTTSProvider
│   │   └── stt/              # LocalSTTProvider, AWSSTTProvider
│   ├── routes/
│   │   ├── chat.py           # /chat, /chat/stream
│   │   ├── voice.py          # /voice/transcribe, /voice/speak
│   │   ├── documents.py      # /documents
│   │   ├── database.py       # /attendance, /grades, /timetable, /students
│   │   ├── analytics.py      # /analytics
│   │   ├── students.py       # /students admin
│   │   └── health.py         # /health, /system-status
│   ├── middleware/
│   │   └── request_id.py     # X-Request-ID correlation
│   ├── db/
│   │   └── connection.py     # MySQL pool (parameterized only)
│   ├── tests/                # 107 tests (pytest)
│   ├── config.py             # All env vars in one place
│   ├── main.py               # FastAPI app + lifespan pre-warming
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatUI.tsx        # Main chat: SSE, history, tool badge
│   │   │   ├── VoicePipeline.tsx # Mic record, WAV, playback
│   │   │   └── StatusPanel.tsx   # System health overlay
│   │   └── lib/
│   │       └── api.ts            # streamChatMessage, fetchStatus
│   └── package.json
└── docs/
    ├── diagrams/             # 5 Mermaid architecture diagrams
    ├── phase-reports/        # Phase 1–7 detailed reports
    └── presentation/
        └── presentation-content.md   # Aug 28 review content
```

---

## Known Limitations

| Issue | Details | Workaround |
|---|---|---|
| **CPU-only latency** | ~25 s ERP, ~8 s RAG on CPU without GPU | SSE streaming delivers first token in ~3 s; pre-warming eliminates cold start |
| **faster-whisper Error 1094995529** | Intermittent on Windows CPU for some audio lengths | Retry; AWS Transcribe (APP_MODE=aws) does not have this issue |
| **No persistent server-side session** | History is client-side only | Frontend localStorage survives page reloads; server restart clears nothing that matters |
| **Qdrant in-memory on local** | Vectors lost on restart without configured persistence | Set `QDRANT_STORAGE_PATH` in qdrant config or use Docker volume |
| **Voice TTS quality (pyttsx3)** | Robotic voice on local | AWS Polly (APP_MODE=aws) is neural and natural |

---

## Documentation

| Document | Location |
|---|---|
| Overall architecture diagram | [`docs/diagrams/01-overall-architecture.mmd`](docs/diagrams/01-overall-architecture.mmd) |
| Dual-mode provider diagram | [`docs/diagrams/02-dual-mode-architecture.mmd`](docs/diagrams/02-dual-mode-architecture.mmd) |
| Agent request flow | [`docs/diagrams/03-agent-flow.mmd`](docs/diagrams/03-agent-flow.mmd) |
| RAG pipeline diagram | [`docs/diagrams/04-rag-pipeline.mmd`](docs/diagrams/04-rag-pipeline.mmd) |
| Voice pipeline diagram | [`docs/diagrams/05-voice-pipeline.mmd`](docs/diagrams/05-voice-pipeline.mmd) |
| Presentation content | [`docs/presentation/presentation-content.md`](docs/presentation/presentation-content.md) |
| Phase reports (1–7) | [`docs/phase-reports/`](docs/phase-reports/) |

---

*Built as part of a cloud computing academic project. Phase 8 of 8 — documentation complete.*
