# AI ERP Assistant

> Voice-powered, AI-driven ERP for academic institutions � built for B.M.S. College of Engineering (BMSCE).

Faculty members � Professors, HODs, and Deans � can query attendance, grades, schedules, student records, and documents using natural language (text or voice). No more navigating complex ERP menus.

---

## Architecture

The project supports two runtime modes, selectable via the `APP_MODE` environment variable.

### Local Mode (`APP_MODE=local`) � Fully Offline after First Run

| Layer | Technology |
|---|---|
| LLM | Ollama (`qwen2.5:7b-instruct`) |
| Embeddings | Ollama (`mxbai-embed-large`) |
| Speech-to-Text | faster-whisper (`small.en`) |
| Text-to-Speech | **Piper TTS** (`en_US-amy-medium`) � genuinely offline, no Microsoft/cloud dependency |
| Database | Local MySQL 8.0 |
| Vector DB | Qdrant (Docker) |
| Storage | Local Filesystem |
| Backend | FastAPI + Uvicorn |
| Frontend | Next.js 16 (dev server) |

> [!NOTE]
> Piper TTS downloads its voice model (~60 MB) from Hugging Face on the **first** synthesis call only. After that, all TTS is performed entirely on-device with zero network dependency � replacing the old edge-tts provider which required a live connection to Microsoft''s Azure TTS service.

### AWS Mode (`APP_MODE=aws`) � Cloud Production

| Layer | Technology |
|---|---|
| LLM | Amazon Bedrock (Claude 3 Sonnet) |
| Embeddings | Amazon Bedrock (Titan Embeddings V2) |
| Speech-to-Text | Amazon Transcribe |
| Text-to-Speech | Amazon Polly (Neural) |
| Database | Amazon Aurora MySQL |
| Vector DB | Qdrant (self-hosted) |
| Storage | Amazon S3 |
| Backend | AWS Lambda + API Gateway (via Mangum) |
| Frontend | Amazon CloudFront |

---

## Local Mode Setup

### Prerequisites

| Tool | Install |
|---|---|
| Docker Desktop | https://www.docker.com/products/docker-desktop |
| Python 3.10+ | https://www.python.org/downloads/ |
| Node.js 18+ | https://nodejs.org |
| Ollama | https://ollama.com |
| espeak-ng | `winget install espeak-ng` (Windows) or `sudo apt-get install espeak-ng` (Ubuntu) |

> [!IMPORTANT]
> **espeak-ng is required for Piper TTS** on all platforms. Install it before starting the backend.

---

### Step 1 � Start Docker Services

From the project root:

```bash
docker-compose up -d
```

This starts:
- **MySQL 8.0** on port `3306` (database: `erp_assistant`, root password: `root`)
- **Qdrant** on port `6333` (vector store for document RAG)

---

### Step 2 � Pull Ollama Models

```bash
ollama pull qwen2.5:7b-instruct
ollama pull mxbai-embed-large
```

> [!NOTE]
> If you previously ran this project with `nomic-embed-text` (768-dim embeddings), you need to delete the Qdrant collection and re-create it after switching to `mxbai-embed-large` (1024-dim). The two are not dimension-compatible.

---

### Step 3 � Configure and Start the Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
# or: source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt

# Copy the local environment file (APP_MODE=local is already set inside)
copy .env.local .env

uvicorn main:app --reload --port 8000
```

Environment variables are documented in [backend/.env.sample](backend/.env.sample).

On first startup, the backend automatically:
- Creates all MySQL tables (`db/models.py`)
- Seeds the database with sample BMSCE academic data (`db/seed.py`)

---

### Step 4 � Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

---

### Access Points

| Service | URL |
|---|---|
| Frontend UI | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |



---

### Admin Console Security

The raw-SQL database management console (\/db/*\ endpoints) is protected by a
shared-secret header check. Every request to those routes must include:

\X-Admin-Key: <value of ADMIN_API_KEY in your .env>
\
Requests without the correct header receive a **401 Unauthorized** response.

The regular assistant routes (\/chat\, \/voice-query\, \/documents\, \/students\, etc.)
are **not** gated by this key -- they are intentionally open for the student/faculty demo.
Role-based auth for Professor/HOD/Dean personas is deferred to a later phase.

CORS is restricted to the origins listed in \ALLOWED_ORIGINS\ (default: \http://localhost:3000\).
Set this env var to your CloudFront/production domain before any real deployment.

---

## AWS Mode Setup (Brief)

1. Set up an AWS account with access to Bedrock (Claude 3 Sonnet + Titan Embeddings), Aurora MySQL, S3, Transcribe, and Polly.
2. Copy `backend/.env.sample` to `backend/.env` and fill in all AWS values.
3. Set `APP_MODE=aws`.
4. Deploy the backend via `backend/deploy.ps1` (packages the Lambda zip and updates the function).
5. Host the `frontend/` build on CloudFront.

See [backend/README.md](backend/README.md) for full deployment details.

---

## Project Structure

```
AI-ERP-ASSISTANT/
+-- backend/                 # FastAPI backend
�   +-- ai/                  # LLM agent + tool dispatcher + embeddings
�   +-- db/                  # MySQL models, migrations, seed data
�   +-- providers/           # Pluggable providers (LLM, TTS, STT, embeddings, storage)
�   �   +-- llm/             # aws_llm.py + local_llm.py (Ollama)
�   �   +-- tts/             # aws_tts.py (Polly) + local_tts.py (Piper TTS)
�   �   +-- stt/             # aws_stt.py (Transcribe) + local_stt.py (faster-whisper)
�   �   +-- embeddings/      # aws_embeddings.py (Titan) + local_embeddings.py (Ollama)
�   �   +-- storage/         # aws_storage.py (S3) + local_storage.py (filesystem)
�   +-- routes/              # FastAPI route handlers
�   +-- piper_voices/        # Auto-downloaded Piper TTS models (git-ignored)
�   +-- main.py              # App entry point
+-- frontend/                # Next.js 16 frontend
+-- docs/
�   +-- phase-reports/       # Per-phase implementation reports
�   +-- diagrams/            # Architecture diagrams
�   +-- presentation/        # Slide content built up over phases
+-- docker-compose.yml       # MySQL + Qdrant for local dev
```

---

## Implementation Phases

| Phase | Focus | Status |
|---|---|---|
| 1 | Foundation & tech stack stabilization | ? Done |
| 2 | AI agent & tool refinement | ?? |
| 3 | Voice pipeline integration | ?? |
| 4 | RAG document pipeline | ?? |
| 5 | Analytics & dashboards | ?? |
| 6 | Security & auth | ?? |
| 7 | Testing & QA | ?? |
| 8 | Deployment & final demo prep | ?? |
