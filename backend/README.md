# AI ERP Assistant � Backend

FastAPI backend for the AI ERP Assistant. Supports two runtime modes:
- `APP_MODE=local` � fully offline, Ollama + Piper TTS + faster-whisper + local MySQL + Qdrant
- `APP_MODE=aws` � AWS production stack (Bedrock + Polly + Transcribe + Aurora + S3 + Lambda)

---

## Directory Structure

```
backend/
+-- ai/
�   +-- agent.py            # Main orchestrator: classify ? tool dispatch ? format
�   +-- llm_service.py      # Thin wrapper around the provider registry
�   +-- embeddings.py       # AWS Bedrock embedding service
�   +-- tools/              # One tool class per ERP domain
�       +-- attendance_tool.py
�       +-- grades_tool.py
�       +-- student_tool.py
�       +-- faculty_tool.py
�       +-- course_tool.py
�       +-- timetable_tool.py
�       +-- analytics_tool.py
�       +-- document_tool.py
+-- db/
�   +-- connection.py       # MySQL connection pool helpers
�   +-- models.py           # SQLAlchemy table definitions (10 tables)
�   +-- seed.py             # Sample BMSCE academic data
�   +-- migrate.py          # Schema migration utilities
+-- providers/
�   +-- base.py             # Abstract base classes (BaseLLMProvider, BaseTTSProvider, �)
�   +-- registry.py         # Factory: returns local or AWS provider based on APP_MODE
�   +-- llm/
�   �   +-- aws_llm.py      # Bedrock (Claude 3 Sonnet)
�   �   +-- local_llm.py    # Ollama (qwen2.5:7b-instruct)
�   +-- tts/
�   �   +-- aws_tts.py      # Amazon Polly
�   �   +-- local_tts.py    # Piper TTS (offline, en_US-amy-medium)
�   +-- stt/
�   �   +-- aws_stt.py      # Amazon Transcribe
�   �   +-- local_stt.py    # faster-whisper (small.en)
�   +-- embeddings/
�   �   +-- aws_embeddings.py   # Bedrock Titan Embeddings V2
�   �   +-- local_embeddings.py # Ollama (mxbai-embed-large)
�   +-- storage/
�       +-- aws_storage.py  # Amazon S3
�       +-- local_storage.py# Local filesystem (serves via /files/ static mount)
+-- routes/
�   +-- health.py           # GET /health
�   +-- chat.py             # POST /chat (text query)
�   +-- voice.py            # POST /voice/transcribe, /voice/synthesize, /voice/chat
�   +-- analytics.py        # GET /analytics/*
�   +-- documents.py        # POST /documents/upload, GET /documents/search
�   +-- students.py         # GET /students/*
�   +-- database.py         # GET /database/* (raw table queries)
+-- piper_voices/           # Auto-downloaded Piper TTS models (git-ignored)
+-- local_storage/          # TTS audio, uploaded docs (git-ignored)
+-- config.py               # All environment variable bindings
+-- main.py                 # FastAPI app, CORS, route registration, Mangum adapter
+-- requirements.txt        # Python dependencies
+-- .env.local              # Local mode config (APP_MODE=local, Ollama, local MySQL)
+-- .env.sample             # Template for both local and AWS mode
```

---

## Environment Variables

Copy `.env.local` for local mode or `.env.sample` for AWS mode, then rename to `.env`.

### Key Variables

| Variable | Default (local) | Description |
|---|---|---|
| `APP_MODE` | `local` | Runtime mode: `local` or `aws` |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Ollama LLM model |
| `OLLAMA_EMBEDDING_MODEL` | `mxbai-embed-large` | Ollama embedding model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `WHISPER_MODEL` | `small.en` | faster-whisper model size |
| `PIPER_VOICE` | `en_US-amy-medium` | Piper TTS voice name |
| `AURORA_HOST` | `localhost` | MySQL host |
| `AURORA_PORT` | `3306` | MySQL port |
| `AURORA_USER` | `root` | MySQL user |
| `AURORA_PASSWORD` | `root` | MySQL password |
| `AURORA_DATABASE` | `erp_assistant` | MySQL database name |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB URL |
| `QDRANT_COLLECTION` | `erp_documents` | Qdrant collection name |
| `LOCAL_STORAGE_DIR` | `./local_storage` | Directory for TTS audio and docs |

---

## Local Development

### Prerequisites

```bash
# 1. Docker (for MySQL + Qdrant)
docker-compose up -d

# 2. Ollama models
ollama pull qwen2.5:7b-instruct
ollama pull mxbai-embed-large

# 3. espeak-ng (required by Piper TTS)
# Windows:  winget install espeak-ng
# Ubuntu:   sudo apt-get install espeak-ng
# macOS:    brew install espeak-ng
```

### Start Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows

pip install -r requirements.txt
copy .env.local .env

uvicorn main:app --reload --port 8000
```

### Verify

```bash
# Health check
curl http://localhost:8000/health

# Mode check
curl http://localhost:8000/mode
# Expected: {"mode":"local"}

# Swagger UI
# Open http://localhost:8000/docs in browser
```

---

## Provider System

The backend uses a provider registry pattern. `providers/registry.py` reads `APP_MODE` at startup and returns the correct implementation:

```python
from providers.registry import get_tts_provider, get_llm_provider

tts = get_tts_provider()   # ? LocalTTSProvider (local) or AWSTTSProvider (aws)
llm = get_llm_provider()   # ? OllamaLLMProvider (local) or AWSLLMProvider (aws)
```

All providers implement abstract base classes from `providers/base.py`. Routes import only the registry � never a concrete provider directly � so swapping mode requires only changing `APP_MODE`.

---

## AI Agent Architecture

Queries flow through `ai/agent.py` in three steps:

1. **Intent Classification** � LLM classifies the query as `erp`, `document`, or `general`
2. **Tool Dispatch** � For `erp` queries, the LLM picks a tool and extracts parameters (no SQL generation ever happens � only parameterized tool calls). For `document` queries, the DocumentTool performs RAG over Qdrant. For `general`, the LLM answers directly.
3. **Response Formatting** � The tool''s structured result is passed back to the LLM for natural-language formatting with Markdown tables where appropriate.

Available tools: `AttendanceTool`, `GradesTool`, `StudentTool`, `FacultyTool`, `CourseTool`, `TimetableTool`, `AnalyticsTool`, `DocumentTool`.

---

## Piper TTS Notes

On first TTS call, `local_tts.py` will download:
- `piper_voices/en_US-amy-medium.onnx` (~60 MB)
- `piper_voices/en_US-amy-medium.onnx.json` (~3 KB)

These files are git-ignored and cached permanently after first download. All subsequent TTS calls are fully offline.

To pre-download manually:
```bash
python -c "from providers.tts.local_tts import _ensure_voice_model; _ensure_voice_model()"
```

---

## AWS Deployment

```bash
# Package and deploy to Lambda
.\deploy.ps1

# The Lambda handler entrypoint is: main.handler
# (Mangum wraps FastAPI as an ASGI-compatible Lambda handler)
```

See `.env.sample` for all required AWS environment variables.

---

## Admin Console Security

The \/db/*\ routes (database management console) require an \X-Admin-Key\ header
matching the \ADMIN_API_KEY\ value in your \.env\ file.  Missing or incorrect keys
return **401 Unauthorized**.

This key gates ONLY the admin console -- the assistant's \/chat\, \/voice-query\,
\/documents\, and tool-based query routes are not affected.

Set \ALLOWED_ORIGINS\ in your \.env\ to the comma-separated list of front-end
origins that the backend will accept CORS requests from (default: \http://localhost:3000\).

