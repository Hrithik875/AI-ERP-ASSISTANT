"""
AI ERP Assistant — AWS Backend (Production)
=============================================
FastAPI application deployed on AWS Lambda via Mangum.

Architecture (per workflow diagram):
  - AI:        Amazon Bedrock (Claude 3 Sonnet) + Titan Embeddings V2
  - Vector DB: Qdrant (document semantic search)
  - Database:  Amazon Aurora MySQL (ERP data)
  - Speech:    Amazon Transcribe (STT) + Amazon Polly (TTS)
  - Storage:   Amazon S3 (audio, documents, transcripts)
  - Backend:   AWS Lambda + API Gateway (via Mangum)
  - CDN:       CloudFront (frontend hosting)
  - Monitoring: CloudWatch (Lambda logs)

Handler: main.handler
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from config import logger, AWS_REGION, S3_BUCKET_NAME, BEDROCK_MODEL_ID

# ── Import Routes ───────────────────────────────────────────────────────────
from routes.health    import router as health_router
from routes.voice     import router as voice_router
from routes.chat      import router as chat_router
from routes.analytics import router as analytics_router
from routes.documents import router as documents_router
from routes.students  import router as students_router


# Attempt auto-migration on cold start
try:
    from db.models import create_tables
    from db.seed import seed_database
    create_tables()
    logger.info("Aurora MySQL tables verified (cold start)")
    seed_database()
    logger.info("Database seeding completed (cold start)")
except Exception as e:
    logger.warning(f"Database init failed (non-fatal): {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("AI ERP Assistant Backend — Starting up")
    logger.info(f"  Region:     {AWS_REGION}")
    logger.info(f"  Bucket:     {S3_BUCKET_NAME}")
    logger.info(f"  LLM:        Amazon Bedrock / {BEDROCK_MODEL_ID}")
    logger.info(f"  DB:         Aurora MySQL")
    logger.info(f"  Vector DB:  Qdrant")
    logger.info("=" * 60)

    # Ensure S3 bucket exists
    try:
        from services.s3 import ensure_bucket_exists
        ensure_bucket_exists()
    except Exception as e:
        logger.warning(f"S3 bucket check failed (non-fatal): {e}")

    yield  # Application runs here

    # Seed demo data (100 students)
    try:
        from db.seed import seed_database
        seed_database()
    except Exception as e:
        logger.warning(f"Database seeding failed (non-fatal): {e}")

    yield  # Application runs here

    # ── Shutdown ─────────────────────────────────────────────────────────
    try:
        from db.connection import close_pool
        close_pool()
    except Exception:
        pass
    logger.info("AI ERP Assistant Backend — Shut down")


# ── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI ERP Assistant API",
    description=(
        "Production backend for voice-powered ERP assistant. "
        "Powered by Amazon Bedrock (Claude 3 Sonnet), Aurora MySQL, "
        "Qdrant, Transcribe, and Polly."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend (CloudFront) and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict to CloudFront domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routes ─────────────────────────────────────────────────────────

app.include_router(health_router)
app.include_router(voice_router)
app.include_router(chat_router)
app.include_router(analytics_router)
app.include_router(documents_router)
app.include_router(students_router)


# ── Lambda Handler ──────────────────────────────────────────────────────────
# Mangum wraps the FastAPI ASGI app for AWS Lambda.
# Lambda handler is configured as: main.handler

handler = Mangum(app, lifespan="off")


# ── Local Development ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting local development server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
