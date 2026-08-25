"""
AI ERP Assistant — Health Route
==================================
Provides two endpoints:
  GET /health         — lightweight liveness check (no external calls).
  GET /system-status  — deep health check: probes each service and reports
                        per-service status + latency, suitable for a
                        frontend status panel.
"""

import time
import requests as _requests
from datetime import datetime
from fastapi import APIRouter

from config import (
    APP_MODE, AWS_REGION, S3_BUCKET_NAME, BEDROCK_MODEL_ID,
    BEDROCK_EMBEDDING_MODEL_ID, OLLAMA_BASE_URL, OLLAMA_MODEL,
    AURORA_HOST, AURORA_PORT, AURORA_USER, AURORA_PASSWORD, AURORA_DATABASE,
    QDRANT_URL, QDRANT_COLLECTION,
)
from providers.registry import get_llm_provider, get_embedding_provider

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Lightweight liveness check — no external service probes."""
    llm = get_llm_provider()
    embedding = get_embedding_provider()

    return {
        "status": "healthy",
        "message": "AI ERP Assistant API running",
        "mode": APP_MODE,
        "llm_provider": type(llm).__name__,
        "embedding_provider": type(embedding).__name__,
        "database": "aurora-mysql",
        "vector_db": "qdrant",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/system-status")
def system_status():
    """
    Deep health check — probes every downstream service and returns per-service
    status and measured round-trip latency.

    Response schema:
    {
      "mode": "local" | "aws",
      "services": {
        "mysql":  { "status": "ok"|"error", "latency_ms": int, "error"?: str },
        "qdrant": { "status": "ok"|"error", "latency_ms": int, "error"?: str },
        "ollama": { "status": "ok"|"error", "latency_ms": int, "model": str, "error"?: str },
        "stt":    { "status": "ok"|"error", "provider": str, "error"?: str },
        "tts":    { "status": "ok"|"error", "provider": str, "error"?: str }
      },
      "overall": "ok" | "degraded" | "error",
      "timestamp": "<iso>"
    }
    """
    services = {}

    # ── MySQL ────────────────────────────────────────────────────────────────
    try:
        import pymysql
        t0 = time.perf_counter()
        conn = pymysql.connect(
            host=AURORA_HOST,
            port=AURORA_PORT,
            user=AURORA_USER,
            password=AURORA_PASSWORD,
            database=AURORA_DATABASE,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        latency_ms = int((time.perf_counter() - t0) * 1000)
        services["mysql"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        services["mysql"] = {"status": "error", "latency_ms": -1, "error": str(e)[:120]}

    # ── Qdrant ───────────────────────────────────────────────────────────────
    try:
        t0 = time.perf_counter()
        r = _requests.get(f"{QDRANT_URL}/healthz", timeout=5)
        r.raise_for_status()
        latency_ms = int((time.perf_counter() - t0) * 1000)
        services["qdrant"] = {"status": "ok", "latency_ms": latency_ms, "url": QDRANT_URL}
    except Exception as e:
        services["qdrant"] = {"status": "error", "latency_ms": -1, "error": str(e)[:120]}

    # ── LLM (Ollama or Bedrock) ───────────────────────────────────────────────
    try:
        llm = get_llm_provider()
        t0 = time.perf_counter()
        hc = llm.health_check()
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if hc.get("status") == "ok":
            services["llm"] = {
                "status": "ok",
                "latency_ms": latency_ms,
                "provider": type(llm).__name__,
                "model": hc.get("model", ""),
            }
            if "fast_model" in hc:
                services["llm"]["fast_model"] = hc["fast_model"]
                services["llm"]["fast_model_downloaded"] = hc.get("fast_model_downloaded", None)
        else:
            services["llm"] = {
                "status": "error",
                "latency_ms": latency_ms,
                "provider": type(llm).__name__,
                "error": hc.get("error", "unknown"),
            }
    except Exception as e:
        services["llm"] = {"status": "error", "latency_ms": -1, "error": str(e)[:120]}

    # ── STT ──────────────────────────────────────────────────────────────────
    try:
        from providers.registry import get_stt_provider
        stt = get_stt_provider()
        services["stt"] = {"status": "ok", "provider": type(stt).__name__}
    except Exception as e:
        services["stt"] = {"status": "error", "provider": "unknown", "error": str(e)[:120]}

    # ── TTS ──────────────────────────────────────────────────────────────────
    try:
        from providers.registry import get_tts_provider
        tts = get_tts_provider()
        services["tts"] = {"status": "ok", "provider": type(tts).__name__}
    except Exception as e:
        services["tts"] = {"status": "error", "provider": "unknown", "error": str(e)[:120]}

    # ── Overall ───────────────────────────────────────────────────────────────
    statuses = [s["status"] for s in services.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "ok" for s in statuses):
        overall = "degraded"
    else:
        overall = "error"

    return {
        "mode": APP_MODE,
        "services": services,
        "overall": overall,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/init-db")
@router.post("/init-db")
def init_db():
    try:
        from db.models import create_tables
        from db.seed import seed_database

        import pymysql
        temp_conn = pymysql.connect(
            host=AURORA_HOST, port=AURORA_PORT, user=AURORA_USER,
            password=AURORA_PASSWORD, autocommit=True
        )
        with temp_conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{AURORA_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        temp_conn.close()

        create_tables()
        seed_database()
        return {"status": "success", "message": "Tables created and seeded!"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
