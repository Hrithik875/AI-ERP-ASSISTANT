"""
AI ERP Assistant — Health Route
==================================
"""

from datetime import datetime
from fastapi import APIRouter

from config import AWS_REGION, S3_BUCKET_NAME, BEDROCK_MODEL_ID, BEDROCK_EMBEDDING_MODEL_ID

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "AI ERP Assistant API running",
        "service": "AI ERP Assistant API",
        "region": AWS_REGION,
        "bucket": S3_BUCKET_NAME,
        "llm_provider": "amazon-bedrock",
        "llm_model": BEDROCK_MODEL_ID,
        "embedding_model": BEDROCK_EMBEDDING_MODEL_ID,
        "database": "aurora-mysql",
        "vector_db": "qdrant",
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/init-db")
@router.post("/init-db")
def init_db():
    try:
        from db.models import create_tables
        from db.seed import seed_database
        from config import AURORA_DATABASE
        
        # Make sure DB exists
        import pymysql
        from config import AURORA_HOST, AURORA_PORT, AURORA_USER, AURORA_PASSWORD
        temp_conn = pymysql.connect(
            host=AURORA_HOST, port=AURORA_PORT, user=AURORA_USER, password=AURORA_PASSWORD, autocommit=True
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
