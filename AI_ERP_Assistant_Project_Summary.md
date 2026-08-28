# AI ERP Assistant — Complete Project Summary

**Project Name:** AI ERP Assistant  
**Author:** Hrithik M  
**Date Generated:** June 5, 2026  
**Version:** 3.0.0  

---

## 1. Project Overview

The **AI ERP Assistant** is a full-stack, voice-powered Enterprise Resource Planning (ERP) system built for **B.M.S. College of Engineering (BMSCE)**. It enables faculty members — Professors, HODs, and Deans — to interact with academic data through **natural language** (text or voice), eliminating the need to navigate complex ERP menus.

The system combines an **AI agent** powered by large language models with a **structured relational database**, a **vector database** for document search (RAG), and **speech services** for a fully voice-enabled experience.

### Key Value Proposition
> "Stop digging through endless menus to find attendance, grades, or schedules. Just ask exactly what you need, and get the answer instantly."

---

## 2. Architecture

The project follows a **dual-mode architecture** supporting both AWS production deployment and fully offline local development.

### 2.1 AWS Production Stack
| Service | Technology | Purpose |
|---|---|---|
| AI / LLM | Amazon Bedrock (Claude 3 Sonnet) | Natural language understanding & response generation |
| Embeddings | Amazon Bedrock (Titan Embeddings V2) | Document vector embeddings for RAG |
| Database | Amazon Aurora MySQL 8.0+ | Primary ERP data store |
| Vector DB | Qdrant | Document semantic search |
| Speech-to-Text | Amazon Transcribe | Voice input transcription |
| Text-to-Speech | Amazon Polly (Neural) | Voice response generation |
| Storage | Amazon S3 | Audio files, documents, transcripts |
| Backend | AWS Lambda + API Gateway (via Mangum) | Serverless backend hosting |
| CDN | Amazon CloudFront | Frontend static hosting |
| Monitoring | Amazon CloudWatch | Lambda logs & metrics |

### 2.2 Local Development Stack
| Service | Technology | Purpose |
|---|---|---|
| AI / LLM | Ollama (Llama 3.2) | Local LLM inference |
| Embeddings | Ollama (nomic-embed-text) | Local embedding generation |
| Database | Local MySQL 8.0 | Same driver as Aurora |
| Vector DB | Qdrant (Docker) | Same as production |
| Speech-to-Text | faster-whisper (tiny.en) | Fast, offline speech recognition |
| Text-to-Speech | edge-tts (AriaNeural) | Microsoft Edge neural TTS |
| Storage | Local Filesystem | File storage |
| Backend | Uvicorn | Local FastAPI dev server |

### 2.3 Frontend Stack
| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.2.3 | React framework with SSR/App Router |
| React | 19.2.4 | UI component library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 4.x | Utility-first CSS framework |
| Framer Motion | 12.38.0 | Animation library |
| Recharts | 3.8.1 | Data visualization/charts |
| Radix UI | Various | Accessible UI primitives |
| Spline 3D | 4.1.0 | Interactive 3D scenes |
| Lucide React | 1.8.0 | Icon library |
| React Markdown | 10.1.0 | Markdown rendering for AI responses |

---

## 3. Backend Architecture — Detailed Module Breakdown

### 3.1 Application Entry Point (`main.py` — 142 lines)
- **FastAPI v3.0.0** application with ASGI support
- Lifespan management (startup/shutdown) with logging
- CORS middleware for frontend cross-origin access
- 7 route routers registered (health, voice, chat, analytics, documents, students, database)
- Auto-migration and database seeding on cold start
- **Mangum** adapter for AWS Lambda compatibility
- Local static file serving for `APP_MODE=local`
- Runtime mode endpoint (`GET /mode`)

### 3.2 Configuration Module (`config.py` — 103 lines)
- Centralized environment-based configuration
- Dual-mode support (`APP_MODE=aws` vs `APP_MODE=local`)
- 25+ configurable environment variables covering:
  - AWS region, S3 bucket, Bedrock models
  - Aurora MySQL connection (host, port, user, password, database)
  - Qdrant vector DB (URL, collection, RAG parameters)
  - Ollama local settings (base URL, model names)
  - TTS/STT settings (Polly voice, engine)
- Connection pooling configuration (pool size, recycle time)
- RAG chunking parameters (chunk size: 512, overlap: 64, top-k: 5)

---

## 4. Database Layer

### 4.1 Schema Design (`db/models.py` — 540 lines)

**10 Tables** with full referential integrity:

| Table | Purpose | Key Columns |
|---|---|---|
| `departments` | Academic departments | `department_code`, `department_name`, `hod_fk` |
| `faculty` | Faculty members | `employee_code`, `name`, `email`, `designation`, `status` |
| `students` | Student records | `usn`, `name`, `email`, `semester`, `section`, `cgpa` |
| `courses` | Course catalog | `course_code`, `course_name`, `credits`, `semester` |
| `faculty_courses` | Faculty-course mapping (M:N) | `faculty_fk`, `course_fk`, `academic_year` |
| `attendance` | Daily attendance records | `student_fk`, `course_fk`, `attendance_date`, `status` |
| `grades` | Student grades (IA1, IA2, IA3, Final) | `student_fk`, `course_fk`, `ia1/ia2/ia3_marks`, `final_grade` |
| `timetable` | Weekly class schedule | `faculty_fk`, `course_fk`, `day_of_week`, `start_time`, `room` |
| `announcements` | Faculty announcements | `faculty_fk`, `title`, `content`, `priority` |
| `documents` | Uploaded documents metadata | `doc_uuid`, `filename`, `storage_path`, `embedding_status` |
| `query_logs` | AI query audit trail | `query_text`, `query_type`, `response_time_ms`, `source` |

**21 Indexes** for performance optimization across all queryable columns.

**9 Reporting Views:**

| View | Purpose |
|---|---|
| `vw_student_profile` | Student details with department name |
| `vw_attendance_summary` | Per-student, per-course attendance % |
| `vw_grade_summary` | Grades with student/course/faculty joins |
| `vw_faculty_workload` | Courses assigned, weekly slots, students taught |
| `vw_course_statistics` | Enrollment, avg attendance %, avg marks, fail count |
| `vw_student_risk` | Students with attendance < 75% (warning/critical) |
| `vw_department_performance` | Per-department student/faculty/course/attendance stats |
| `vw_timetable_summary` | Human-readable timetable with names |
| `vw_faculty_dashboard` | Faculty quick-stats dashboard data |

### 4.2 Connection Management (`db/connection.py` — 168 lines)
- PyMySQL connection pooling with **Lambda warm-start reuse**
- Auto-create database if not found (error 1049 handling)
- Auto-schema migration + seeding on first connection
- Fast-fail mechanism (30s cooldown after connection failure)
- Context-managed cursor with auto-commit/rollback
- 4 query helpers: `execute_query`, `execute_write`, `execute_insert_returning`, `close_pool`
- Disabled `ONLY_FULL_GROUP_BY` SQL mode for LLM compatibility

### 4.3 Data Seeder (`db/seed.py` — 567 lines)

**Enterprise-scale realistic demo data:**

| Entity | Count | Details |
|---|---|---|
| Departments | 5 | CS, IS, EC, ME, CV |
| Faculty | 50 | 10 per department (named individuals with designations) |
| Students | 1,000 | 200 per department, semesters 3–8, 3 sections (A/B/C) |
| Courses | 40 | 8 per department (realistic names & credit hours) |
| Faculty-Course Mappings | ~60 | 1-2 courses per faculty |
| Attendance Records | ~300,000+ | 45 weekdays × all eligible students × all courses |
| Grade Records | ~10,000+ | IA1, IA2, IA3, final exam for each student-course |
| Timetable Entries | 150 | 3 classes/week per faculty-course pair |
| Announcements | 20 | Realistic academic announcements |
| Sample Query Logs | 8 | Pre-seeded for analytics demo |

- Grade distribution follows a **Gaussian model** (μ=65, σ=15)
- Attendance follows realistic probabilities: 82% present, 10% absent, 5% late, 3% excused
- All FK relationships guaranteed valid
- HODs set as first professor in each department
- Student names drawn from a pool of 120+ Indian first names and 44 last names

---

## 5. AI Pipeline

### 5.1 AI Agent / Orchestrator (`ai/agent.py` — 226 lines)

The AI agent implements a **3-stage pipeline**:

```
User Query → [1] Classify Intent → [2] Route to Tool → [3] Format Response
```

**Stage 1 — Query Classification:**
- Uses LLM to classify queries into: `erp`, `document`, or `general`
- Zero-temperature inference for deterministic classification

**Stage 2 — Tool-Based Dispatch (No Raw SQL Generation):**
- LLM extracts `tool_name` + `params` as structured JSON
- Dispatches to the appropriate registered tool
- **Security:** No LLM-generated SQL — only parameterized tool execution

**Stage 3 — Response Formatting:**
- LLM formats raw JSON data into human-readable Markdown tables
- Professional, faculty-friendly language
- Query logging to `query_logs` table with response time

### 5.2 AI Tools System (`ai/tools/` — 8 tools, 10 files)

| Tool | Actions | Description |
|---|---|---|
| `AttendanceTool` | `student_summary`, `course_summary`, `risk_list` | Per-student and per-course attendance with risk detection |
| `GradesTool` | `student_grades`, `course_grades`, `top_performers`, `failing_students` | Grade queries, performance rankings, failure tracking |
| `StudentTool` | `profile`, `search` | Student profile lookup & directory search |
| `FacultyTool` | `profile`, `workload`, `search` | Faculty profiles, workload analysis, directory |
| `CourseTool` | `search`, `details`, `statistics` | Course catalog, stats, enrollment data |
| `TimetableTool` | `faculty_schedule`, `course_schedule`, `day_schedule` | Weekly schedules by faculty/course/day |
| `AnalyticsTool` | `department_performance`, `overall_stats` | Department metrics, institutional analytics |
| `DocumentTool` | `query` (RAG search) | Semantic search over uploaded documents |

All tools extend `BaseTool` and use **parameterized SQL only** — no LLM-generated queries hit the database.

### 5.3 LLM Service (`ai/llm_service.py` — 166 lines)
- Unified wrapper for Amazon Bedrock (Claude 3 Sonnet)
- Support for both Claude (Messages API) and Titan (Text) model formats
- Lazy-initialized Bedrock runtime client (reused across warm Lambda starts)
- Configurable max tokens (default: 1024), temperature
- Comprehensive system prompt for faculty-facing ERP assistance
- Health check endpoint for service monitoring
- Singleton pattern via provider registry

### 5.4 Embeddings Service (`ai/embeddings.py` — 92 lines)
- Amazon Bedrock Titan Embeddings V2
- 1024-dimensional normalized vectors
- Single and batch embedding generation
- Singleton pattern via provider registry

### 5.5 RAG Pipeline (`ai/rag_pipeline.py` — 265 lines)

**Full Retrieval-Augmented Generation pipeline:**

1. **Document Loading** — Downloads from S3/local storage
2. **Text Extraction** — Supports PDF (PyPDF2), DOCX (python-docx), XLSX (openpyxl), CSV, TXT
3. **Chunking** — Overlapping text chunks (512 chars, 64 overlap)
4. **Embedding** — Via Bedrock Titan / Ollama
5. **Vector Storage** — Qdrant collection with COSINE distance
6. **Semantic Search** — Query embedding → top-k nearest neighbors
7. **Context Assembly** — Formatted context with source attribution and relevance scores

---

## 6. Provider System (Abstraction Layer)

### 6.1 Design Pattern
The system uses an **abstract base class + registry** pattern for all infrastructure services, enabling seamless switching between AWS and local providers.

### 6.2 Base Interfaces (`providers/base.py` — 120 lines)

| Interface | Methods |
|---|---|
| `BaseLLMProvider` | `generate()`, `health_check()` |
| `BaseEmbeddingProvider` | `embed()`, `embed_batch()`, `dimension` |
| `BaseStorageProvider` | `upload_bytes()`, `download_bytes()`, `get_url()`, `delete()`, `ensure_ready()` |
| `BaseTTSProvider` | `synthesize()` |
| `BaseSTTProvider` | `transcribe()`, `transcribe_async()`, `get_transcription_status()` |

### 6.3 Provider Registry (`providers/registry.py` — 119 lines)
- Central factory returning correct implementation based on `APP_MODE`
- 5 singleton provider getters: `get_llm_provider`, `get_embedding_provider`, `get_storage_provider`, `get_tts_provider`, `get_stt_provider`
- `reset_providers()` for testing
- Lazy initialization with logging

### 6.4 Provider Implementations (10 files)

| Category | AWS Provider | Local Provider |
|---|---|---|
| LLM | `AWSLLMProvider` (Bedrock Claude) | `OllamaLLMProvider` (Llama 3.2) |
| Embeddings | `AWSEmbeddingProvider` (Titan V2) | `OllamaEmbeddingProvider` (nomic-embed-text) |
| Storage | `AWSStorageProvider` (S3) | `LocalStorageProvider` (filesystem) |
| TTS | `AWSTTSProvider` (Polly) | `LocalTTSProvider` (edge-tts) |
| STT | `AWSSTTProvider` (Transcribe) | `LocalSTTProvider` (faster-whisper) |

---

## 7. API Routes

### 7.1 Route Summary — 7 Routers, 20+ Endpoints

| Router | Tag | Endpoints | Lines |
|---|---|---|---|
| `health.py` | health | `GET /health` | 46 |
| `chat.py` | chat | `POST /chat`, `POST /text-query` | 87 |
| `voice.py` | voice | `POST /voice-input`, `GET /get-transcript/{job}`, `POST /voice-query` | 148 |
| `analytics.py` | analytics | `GET /analytics`, `GET /dashboard/stats` | 173 |
| `documents.py` | documents | `POST /documents`, `GET /documents` | 131 |
| `students.py` | erp-data | `GET /students`, `GET /student/{id}`, `GET /attendance`, `GET /grades`, `GET /faculty` | 281 |
| `database.py` | database-console | 9 endpoints (list, CRUD, query, export, import) | 455 |

### 7.2 Database Management Console (`routes/database.py` — 455 lines)
A fully-featured database administration panel:
- `GET /db/tables` — List all tables with row counts & column schemas
- `GET /db/tables/{name}` — Paginated data with sorting, search, and filtering
- `POST /db/tables/{name}` — Insert new rows
- `PUT /db/tables/{name}/{id}` — Update rows by primary key
- `DELETE /db/tables/{name}/{id}` — Delete rows by primary key
- `POST /db/query` — Execute raw SQL (SELECT/INSERT/UPDATE/DELETE)
- `GET /db/export/{name}` — Export table data as CSV or JSON
- `POST /db/import/{name}` — Import data from CSV or JSON files
- SQL injection prevention via INFORMATION_SCHEMA validation
- Custom JSON serializer for MySQL types (datetime, Decimal, timedelta, bytes)

### 7.3 Voice Pipeline (`routes/voice.py` — 148 lines)
Complete voice flow:
```
Audio Upload → S3 Storage → STT Transcription → AI Agent → TTS Synthesis → Response
```
- Supports 10+ audio formats (webm, wav, mp3, mp4, ogg, flac)
- Async transcription with polling endpoint
- Synchronous voice-query convenience endpoint (max 60s timeout)

---

## 8. Frontend Application

### 8.1 Application Structure
Built with **Next.js 16 App Router** using the `(dashboard)` route group pattern for a layout with persistent sidebar navigation.

### 8.2 Pages (6 pages + landing)

| Page | File | Size | Description |
|---|---|---|---|
| Landing Page | `src/app/page.tsx` | 9.3 KB | Hero with 3D Spline scene, Bento grid features, animated CTA |
| Dashboard | `(dashboard)/dashboard/page.tsx` | 7.7 KB | Live stats, recent queries, system health metrics |
| Voice Interface | `(dashboard)/voice/page.tsx` | 4.1 KB | Voice recording UI with real-time transcription |
| Analytics | `(dashboard)/analytics/page.tsx` | 11.1 KB | Charts: queries/day, usage by category, response times, dept stats |
| Documents | `(dashboard)/documents/page.tsx` | 8.5 KB | Document upload, listing, RAG status tracking |
| Database Console | `(dashboard)/database/page.tsx` | 33.0 KB | Full CRUD table browser, SQL editor, data export/import |
| Settings | `(dashboard)/settings/page.tsx` | 7.3 KB | System configuration and preferences |

### 8.3 Components (8 components + 3 UI primitives)

| Component | Size | Description |
|---|---|---|
| `BentoGrid.tsx` | 19.1 KB | Animated feature showcase with interactive cards |
| `ChatUI.tsx` | 12.1 KB | Real-time chat interface with Markdown rendering |
| `Navbar.tsx` | 11.8 KB | Top navigation with responsive mobile support |
| `VoiceRecorder.tsx` | 9.4 KB | Voice recording with waveform visualization |
| `Sidebar.tsx` | 4.0 KB | Dashboard side navigation |
| `MobileNav.tsx` | 3.1 KB | Mobile navigation drawer |
| `Cards.tsx` | 2.8 KB | Reusable card components |
| `providers.tsx` | 0.5 KB | Theme provider wrapper |
| `ui/card.tsx` | 2.0 KB | Base card component |
| `ui/spotlight.tsx` | 1.5 KB | Spotlight effect component |
| `ui/splite.tsx` | 0.6 KB | Spline 3D scene wrapper |

### 8.4 API Integration Layer (`lib/api.ts` — 479 lines)
- **Zero mock data** — all data fetched dynamically from the backend
- 14 fully-typed API functions covering every backend endpoint
- TypeScript interfaces for all data models
- Transcript polling with 3-minute timeout and 2-second intervals
- Error handling with graceful fallbacks (empty data, not fake data)
- Configurable `API_BASE` via `NEXT_PUBLIC_API_URL` environment variable

### 8.5 Design Features
- **3D Interactive Hero** — Spline 3D scene on the landing page
- **Parallax Scrolling** — Scroll-driven opacity and scale transforms
- **Animated Text** — Split-text reveal animations with staggered timing
- **Bento Grid** — Feature showcase with hover effects
- **Spotlight Effect** — Dynamic cursor-following light effect
- **Dark Mode** — Full dark theme with carefully chosen neutral palette
- **Responsive** — Mobile-first with breakpoint-driven layouts
- **Framer Motion** — Page transitions and micro-interactions
- **Recharts** — Bar, Line, and Pie charts for analytics

---

## 9. AWS Services Used (Production)

| # | AWS Service | Usage |
|---|---|---|
| 1 | **Amazon Bedrock** | Claude 3 Sonnet LLM + Titan Embeddings V2 |
| 2 | **Amazon Aurora MySQL** | Primary ERP database |
| 3 | **Amazon S3** | File storage (audio, documents, TTS output) |
| 4 | **Amazon Transcribe** | Speech-to-text transcription |
| 5 | **Amazon Polly** | Neural text-to-speech (Joanna voice) |
| 6 | **AWS Lambda** | Serverless backend compute |
| 7 | **Amazon API Gateway** | REST API routing |
| 8 | **Amazon CloudFront** | Frontend CDN |
| 9 | **Amazon CloudWatch** | Lambda logging & monitoring |

---

## 10. DevOps & Deployment

### 10.1 Deployment Script (`deploy.ps1` — 137 lines)
Automated PowerShell deployment pipeline:
1. Clean previous builds
2. Create package directory
3. Install Python dependencies (Docker native or pip manylinux)
4. Copy all application modules (db, ai, services, routes)
5. Create `lambda_package.zip`
6. Upload to S3 → Update Lambda function code

### 10.2 Docker Compose (`docker-compose.yml` — 27 lines)
Local development infrastructure:
- **MySQL 8.0** container (port 3306, auto-creates `erp_assistant` DB)
- **Qdrant** container (ports 6333/6334, persistent storage volumes)

### 10.3 Environment Files
- `.env` — Production AWS credentials and configuration
- `.env.local` — Local development overrides
- `.env.sample` — Template with all available variables

---

## 11. Testing

### 11.1 Test Suites (2 files, 286 total lines)

**`test_ai.py`** — AI Pipeline Tests (113 lines, 6 test classes):
- `TestQueryClassification` — 6 tests validating intent classification for ERP, document, and general queries
- `TestLLMServiceInit` — 2 tests for Bedrock model configuration
- `TestEmbeddingServiceInit` — 2 tests for Titan embedding service
- `TestSQLSafety` — 1 test verifying dangerous SQL pattern rejection
- `TestEndToEnd` — 1 test for full query-to-response pipeline

**`test_api.py`** — API Integration Tests (173 lines, 10 test classes):
- `TestHealthEndpoint` — 2 tests
- `TestChatEndpoint` — 4 tests (empty, missing, valid messages, query types)
- `TestTextQueryEndpoint` — 1 test
- `TestVoiceEndpoint` — 1 test (422 on missing file)
- `TestAnalyticsEndpoint` — 2 tests (analytics data structure, dashboard stats)
- `TestDocumentsEndpoint` — 1 test
- `TestStudentsEndpoint` — 3 tests (listing, filters, 404)
- `TestAttendanceEndpoint` — 2 tests
- `TestGradesEndpoint` — 1 test
- `TestFacultyEndpoint` — 1 test

---

## 12. Codebase Statistics

### 12.1 File Counts

| Category | Files | Description |
|---|---|---|
| Backend Python | 30 | Core application, AI, DB, providers, routes, services, tests |
| Frontend TypeScript/TSX | 15 | Pages, components, lib, config |
| Configuration | 8 | `.env`, `.env.local`, `.env.sample`, `docker-compose.yml`, etc. |
| Infrastructure | 3 | `deploy.ps1`, `requirements.txt`, `package.json` |
| **Total Source Files** | **~56** | Excluding build artifacts and node_modules |

### 12.2 Lines of Code (Approximate)

| Module | Files | Lines (approx) |
|---|---|---|
| **Backend — Core** (`main.py`, `config.py`) | 2 | 245 |
| **Backend — Database** (`db/`) | 4 | 1,275 |
| **Backend — AI Pipeline** (`ai/`) | 5 | 749 |
| **Backend — AI Tools** (`ai/tools/`) | 10 | 625 |
| **Backend — Providers** (`providers/`) | 13 | 1,095 |
| **Backend — Routes** (`routes/`) | 8 | 1,601 |
| **Backend — Services** (`services/`) | 4 | 285 |
| **Backend — Tests** (`tests/`) | 3 | 286 |
| **Backend Total** | **49** | **~6,161** |
| **Frontend — Pages** | 8 | ~1,650 |
| **Frontend — Components** | 11 | ~1,250 |
| **Frontend — Lib/Config** | 4 | ~670 |
| **Frontend Total** | **23** | **~3,570** |
| **Infrastructure** | 4 | ~200 |
| **Grand Total** | **~76** | **~9,931** |

### 12.3 Backend Dependency Count
- **Python packages:** 15 direct dependencies (FastAPI, boto3, mangum, PyMySQL, qdrant-client, PyPDF2, python-docx, openpyxl, faster-whisper, edge-tts, requests, python-dotenv, cryptography, uvicorn, python-multipart)
- **npm packages:** 21 direct dependencies + 6 dev dependencies

### 12.4 Database Scale (Seeded Demo Data)

| Entity | Record Count |
|---|---|
| Departments | 5 |
| Faculty | 50 |
| Students | 1,000 |
| Courses | 40 |
| Faculty-Course Mappings | ~60 |
| Attendance Records | ~300,000+ |
| Grade Records | ~10,000+ |
| Timetable Entries | ~150 |
| Announcements | 20 |
| Database Views | 9 |
| Database Indexes | 21 |

---

## 13. Key Technical Achievements

### ✅ Dual-Mode Architecture
Seamless switching between full AWS production stack and completely offline local development using abstract provider interfaces.

### ✅ Tool-Based AI Agent (No Raw SQL Generation)
The AI agent uses structured tool dispatch instead of generating SQL directly, ensuring security and reliability. 8 specialized tools handle all ERP data queries.

### ✅ Complete Voice Pipeline
End-to-end voice interaction: Audio Upload → STT → AI Processing → TTS → Audio Response, with both async (polling) and synchronous modes.

### ✅ RAG Document Search
Full Retrieval-Augmented Generation pipeline supporting PDF, DOCX, XLSX, CSV, and TXT documents with Qdrant vector search.

### ✅ Enterprise-Scale Database
540-line schema with 10 tables, 21 indexes, 9 reporting views, and realistic seeded data (1,000 students, 300K+ attendance records).

### ✅ Full Database Management Console
Browser-based database admin with CRUD operations, raw SQL execution, search/filter/sort, pagination, CSV/JSON export, and data import.

### ✅ Production-Ready Deployment
Automated Lambda deployment script, Docker Compose for local infra, environment-based configuration, and connection pooling with warm-start reuse.

### ✅ Premium UI/UX
3D Spline hero, Framer Motion animations, Recharts analytics dashboards, responsive design, Markdown AI response rendering, and dark theme.

### ✅ Comprehensive Test Coverage
AI pipeline tests (intent classification, LLM init, SQL safety, E2E) and API integration tests (20+ test cases across all endpoints).

### ✅ 9 AWS Services Integrated
Bedrock, Aurora MySQL, S3, Transcribe, Polly, Lambda, API Gateway, CloudFront, CloudWatch — all orchestrated in a single application.

---

## 14. API Endpoint Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check |
| `GET` | `/mode` | Current runtime mode (aws/local) |
| `POST` | `/chat` | Text chat with AI agent |
| `POST` | `/text-query` | Alternative text query endpoint |
| `POST` | `/voice-input` | Upload audio for transcription |
| `GET` | `/get-transcript/{job}` | Poll transcription status |
| `POST` | `/voice-query` | Full voice pipeline (sync) |
| `GET` | `/analytics` | Analytics charts data |
| `GET` | `/dashboard/stats` | Dashboard summary statistics |
| `GET` | `/documents` | List uploaded documents |
| `POST` | `/documents` | Upload document + RAG ingestion |
| `GET` | `/students` | List students (filterable) |
| `GET` | `/student/{id}` | Student detail with attendance & grades |
| `GET` | `/attendance` | Attendance records (filterable) |
| `GET` | `/grades` | Grade records (filterable) |
| `GET` | `/faculty` | Faculty listing with courses |
| `GET` | `/db/tables` | List all database tables |
| `GET` | `/db/tables/{name}` | Paginated table data |
| `POST` | `/db/tables/{name}` | Insert row |
| `PUT` | `/db/tables/{name}/{id}` | Update row |
| `DELETE` | `/db/tables/{name}/{id}` | Delete row |
| `POST` | `/db/query` | Execute raw SQL |
| `GET` | `/db/export/{name}` | Export table (CSV/JSON) |
| `POST` | `/db/import/{name}` | Import data from file |

**Total: 24 REST API endpoints**

---

## 15. Project Directory Structure

```
AI-ERP-ASSISTANT/
├── backend/                          # Python FastAPI Backend
│   ├── main.py                       # App entry point + Lambda handler
│   ├── config.py                     # Centralized configuration
│   ├── requirements.txt              # Python dependencies
│   ├── deploy.ps1                    # AWS Lambda deployment script
│   │
│   ├── db/                           # Database Layer
│   │   ├── connection.py             # MySQL connection pool
│   │   ├── models.py                 # Schema DDL, indexes, views
│   │   ├── seed.py                   # Enterprise demo data seeder
│   │   └── migrate.py               # Schema migration utilities
│   │
│   ├── ai/                           # AI Pipeline
│   │   ├── agent.py                  # Query orchestrator (classify → route → format)
│   │   ├── llm_service.py            # LLM abstraction (Bedrock/Ollama)
│   │   ├── embeddings.py             # Embedding service (Titan/Ollama)
│   │   ├── rag_pipeline.py           # RAG: chunk → embed → store → search
│   │   └── tools/                    # AI Tool System
│   │       ├── base.py               # BaseTool abstract class
│   │       ├── attendance_tool.py    # Attendance queries
│   │       ├── grades_tool.py        # Grade queries
│   │       ├── student_tool.py       # Student directory
│   │       ├── faculty_tool.py       # Faculty directory
│   │       ├── course_tool.py        # Course catalog
│   │       ├── timetable_tool.py     # Schedule queries
│   │       ├── analytics_tool.py     # Department analytics
│   │       └── document_tool.py      # RAG document search
│   │
│   ├── providers/                    # Infrastructure Abstraction
│   │   ├── base.py                   # Abstract base classes (5 interfaces)
│   │   ├── registry.py               # Provider factory + singletons
│   │   ├── llm/                      # LLM providers (AWS + Ollama)
│   │   ├── embeddings/               # Embedding providers (AWS + Ollama)
│   │   ├── storage/                  # Storage providers (S3 + Local)
│   │   ├── stt/                      # STT providers (Transcribe + Whisper)
│   │   └── tts/                      # TTS providers (Polly + edge-tts)
│   │
│   ├── routes/                       # API Routes
│   │   ├── health.py                 # Health check
│   │   ├── chat.py                   # Text chat endpoints
│   │   ├── voice.py                  # Voice pipeline endpoints
│   │   ├── analytics.py              # Analytics & dashboard stats
│   │   ├── documents.py              # Document upload & listing
│   │   ├── students.py               # Student/attendance/grades CRUD
│   │   └── database.py               # Database management console
│   │
│   ├── services/                     # AWS Service Wrappers
│   │   ├── s3.py                     # S3 operations
│   │   ├── transcribe.py             # Transcribe operations
│   │   └── polly.py                  # Polly TTS operations
│   │
│   └── tests/                        # Test Suites
│       ├── test_ai.py                # AI pipeline tests
│       └── test_api.py               # API integration tests
│
├── AI-ERP-ASSISTANT/                 # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # Landing page (3D hero, bento grid)
│   │   │   ├── layout.tsx            # Root layout
│   │   │   ├── globals.css           # Global styles
│   │   │   └── (dashboard)/          # Dashboard route group
│   │   │       ├── layout.tsx        # Dashboard layout (sidebar)
│   │   │       ├── dashboard/        # Dashboard home
│   │   │       ├── voice/            # Voice interface
│   │   │       ├── analytics/        # Analytics charts
│   │   │       ├── documents/        # Document management
│   │   │       ├── database/         # Database console
│   │   │       └── settings/         # Settings
│   │   ├── components/               # Reusable components
│   │   │   ├── BentoGrid.tsx
│   │   │   ├── ChatUI.tsx
│   │   │   ├── Navbar.tsx
│   │   │   ├── VoiceRecorder.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── MobileNav.tsx
│   │   │   ├── Cards.tsx
│   │   │   └── ui/                   # UI primitives
│   │   └── lib/
│   │       ├── api.ts                # API integration (479 lines, 14 functions)
│   │       └── utils.ts              # Utility functions
│   ├── package.json
│   └── tsconfig.json
│
├── docker-compose.yml                # Local MySQL + Qdrant
└── .gitignore
```

---

*Generated on June 5, 2026 by comprehensive codebase analysis.*
