"""
AI ERP Assistant — Configuration Module
========================================
Centralized configuration loaded from environment variables.
All secrets and service parameters live here.

Supports dual runtime modes:
  APP_MODE=aws   → Full AWS stack (production)
  APP_MODE=local → Fully offline local stack (demo/dev)

Architecture — AWS Mode:
  - AI:        Amazon Bedrock (Claude 3 Sonnet) + Titan Embeddings
  - Database:  Amazon Aurora MySQL
  - Vector DB: Qdrant
  - Speech:    Amazon Transcribe + Amazon Polly
  - Storage:   Amazon S3
  - Backend:   AWS Lambda (via Mangum)
  - CDN:       CloudFront
  - Monitoring: CloudWatch

Architecture — Local Mode:
  - AI:        Ollama (local LLM + embeddings)
  - Database:  Local MySQL (same driver)
  - Vector DB: Qdrant (local)
  - Speech:    faster-whisper (STT) + Piper TTS (TTS)
  - Storage:   Local filesystem
  - Backend:   Uvicorn (local)
"""

import os
import logging

# ── Logging ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("erp-assistant")
logger.setLevel(logging.INFO)

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
if not logger.handlers:
    logger.addHandler(_handler)

try:
    from dotenv import load_dotenv
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
except ImportError:
    pass

# ── Runtime Mode ────────────────────────────────────────────────────────────
APP_MODE = os.environ.get("APP_MODE", "aws")  # "aws" or "local"


# ── Local Mode Settings ─────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large")

LOCAL_STORAGE_DIR = os.environ.get("LOCAL_STORAGE_DIR", "./local_storage")
LOCAL_SERVER_URL = os.environ.get("LOCAL_SERVER_URL", "http://localhost:8000")


# ── AWS ─────────────────────────────────────────────────────────────────────
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "bmsce-ai-erp-voice-bucket")

# ── Database (Aurora MySQL) ─────────────────────────────────────────────────
AURORA_HOST = os.environ.get("AURORA_HOST", "localhost")
AURORA_PORT = int(os.environ.get("AURORA_PORT", "3306"))
AURORA_USER = os.environ.get("AURORA_USER", "erp_admin")
AURORA_PASSWORD = os.environ.get("AURORA_PASSWORD", "changeme")
AURORA_DATABASE = os.environ.get("AURORA_DATABASE", "erp_assistant")
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
DB_POOL_RECYCLE = int(os.environ.get("DB_POOL_RECYCLE", "3600"))

# ── AI / LLM — Amazon Bedrock ──────────────────────────────────────────────
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", AWS_REGION)
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-sonnet-20240229-v1:0"
)
BEDROCK_MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "1024"))

# ── Embeddings — Amazon Bedrock Titan ───────────────────────────────────────
BEDROCK_EMBEDDING_REGION = os.environ.get("BEDROCK_EMBEDDING_REGION", "us-east-1")
BEDROCK_EMBEDDING_MODEL_ID = os.environ.get(
    "BEDROCK_EMBEDDING_MODEL_ID",
    "amazon.titan-embed-text-v2:0"
)
BEDROCK_EMBEDDING_DIMENSION = int(os.environ.get("BEDROCK_EMBEDDING_DIMENSION", "1024"))

# ── RAG / Vector DB — Qdrant ───────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "erp_documents")
RAG_CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "512"))
RAG_CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "64"))
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))

# ── Polly (TTS) ────────────────────────────────────────────────────────────
POLLY_VOICE_ID = os.environ.get("POLLY_VOICE_ID", "Joanna")
POLLY_ENGINE = os.environ.get("POLLY_ENGINE", "neural")  # "standard" or "neural"

# ── Admin Console Security ──────────────────────────────────────────────────
# Shared secret required in the X-Admin-Key header to access the raw-SQL
# database admin console (/db/* routes). This does NOT gate the assistant's
# normal /chat, /voice-query, or student-facing routes — only the admin UI.
# Change this to a strong random string before any deployment.
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "change-me-before-deployment")

# ── CORS ────────────────────────────────────────────────────────────────────
# Comma-separated list of allowed origins. Defaults to local Next.js dev server.
# In production, set to your CloudFront / frontend domain.
# Example: ALLOWED_ORIGINS=https://erp.bmsce.ac.in,https://www.erp.bmsce.ac.in
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
