"""
AI ERP Assistant — Document Routes (Aurora MySQL)
==================================================
Document upload, listing, and RAG ingestion.
DB inserts use MySQL-compatible syntax.
"""

import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException

from services.s3 import upload_bytes
from db.connection import execute_query, execute_insert_returning, execute_write

logger = logging.getLogger("erp-assistant")
router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "xlsx", "csv", "txt"]


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document → S3, save metadata in Aurora MySQL, trigger RAG ingestion.
    """
    logger.info(f"Document upload: {file.filename}, type={file.content_type}")

    file_ext = (file.filename or "unknown").rsplit(".", 1)[-1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    doc_id = str(uuid.uuid4())
    s3_key = f"documents/{doc_id}.{file_ext}"

    try:
        file_content = await file.read()
        file_size = len(file_content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Upload to S3
        upload_bytes(s3_key, file_content, file.content_type or "application/octet-stream")

        # Save metadata in Aurora MySQL
        try:
            execute_write(
                """INSERT IGNORE INTO documents
                   (doc_id, filename, file_type, file_size_bytes, s3_key, status)
                   VALUES (%s, %s, %s, %s, %s, 'processing')""",
                (doc_id, file.filename, file_ext.upper(), file_size, s3_key),
            )
        except Exception as db_err:
            logger.warning(f"DB insert failed (continuing): {db_err}")

        # Trigger RAG ingestion (best-effort)
        try:
            from ai.rag_pipeline import get_rag
            rag = get_rag()
            chunk_count = rag.ingest_document(s3_key, doc_id, file.filename)

            execute_write(
                "UPDATE documents SET status = 'processed', chunk_count = %s WHERE doc_id = %s",
                (chunk_count, doc_id),
            )
        except Exception as rag_err:
            logger.warning(f"RAG ingestion failed (doc saved to S3): {rag_err}")
            try:
                execute_write(
                    "UPDATE documents SET status = 'failed' WHERE doc_id = %s",
                    (doc_id,),
                )
            except Exception:
                pass

        # Format size for display
        if file_size >= 1024 * 1024:
            size_display = f"{file_size / (1024 * 1024):.1f} MB"
        else:
            size_display = f"{file_size / 1024:.0f} KB"

        return {
            "id": doc_id,
            "name": file.filename,
            "size": size_display,
            "type": file_ext.upper(),
            "uploadedAt": datetime.utcnow().strftime("%Y-%m-%d"),
            "status": "processing",
            "s3_key": s3_key,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.get("/documents")
def list_documents():
    """List all uploaded documents from Aurora MySQL."""
    try:
        docs = execute_query("""
            SELECT doc_id AS id, filename AS name, file_type AS type,
                   file_size_bytes, s3_key, status,
                   DATE_FORMAT(uploaded_at, '%Y-%m-%d') AS uploadedAt,
                   chunk_count
            FROM documents
            ORDER BY uploaded_at DESC
            LIMIT 50
        """)

        # Format sizes
        for doc in docs:
            size = doc.pop("file_size_bytes", 0)
            if size >= 1024 * 1024:
                doc["size"] = f"{size / (1024 * 1024):.1f} MB"
            else:
                doc["size"] = f"{size / 1024:.0f} KB"

        return docs

    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
