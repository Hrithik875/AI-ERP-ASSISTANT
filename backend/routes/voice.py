"""
AI ERP Assistant — Voice Routes
==================================
Voice input pipeline: Upload → S3 → Transcribe → AI → TTS → Response
"""

import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException

from services.s3 import upload_bytes
from services.transcribe import start_transcription, get_transcription_status
from services.polly import synthesize_speech
from ai.agent import process_query
from config import S3_BUCKET_NAME

logger = logging.getLogger("erp-assistant")
router = APIRouter(tags=["voice"])

# ── Content type → extension mapping ───────────────────────────────────────
ALLOWED_AUDIO_TYPES = {
    "audio/webm": "webm", "video/webm": "webm",
    "audio/wav": "wav", "audio/wave": "wav", "audio/x-wav": "wav",
    "audio/mp3": "mp3", "audio/mpeg": "mp3",
    "audio/mp4": "mp4", "audio/ogg": "ogg",
    "audio/flac": "flac", "audio/x-flac": "flac",
}


@router.post("/voice-input")
async def voice_input(audio: UploadFile = File(...)):
    """
    Upload audio → S3 → Start Transcribe job.
    Returns job_name for polling.
    """
    logger.info(f"Voice input: filename={audio.filename}, type={audio.content_type}")

    content_type = audio.content_type or "audio/webm"
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {content_type}")

    file_id = str(uuid.uuid4())
    extension = ALLOWED_AUDIO_TYPES.get(content_type, "webm")
    s3_key = f"audio/{file_id}.{extension}"

    try:
        file_content = await audio.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        upload_bytes(s3_key, file_content, content_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload audio: {str(e)}")

    job_name = f"erp-voice-{file_id}"
    try:
        start_transcription(job_name, s3_key, media_format=extension)
    except Exception as e:
        logger.error(f"Transcribe start failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start transcription: {str(e)}")

    return {
        "job_name": job_name,
        "file_id": file_id,
        "s3_key": s3_key,
        "message": "Audio uploaded and transcription started",
        "status": "IN_PROGRESS",
    }


@router.get("/get-transcript/{job_name}")
def get_transcript(job_name: str):
    """
    Poll transcription status. Returns transcript text when complete.
    """
    logger.info(f"Transcript status check: {job_name}")

    try:
        result = get_transcription_status(job_name)
        return result
    except Exception as e:
        logger.error(f"Transcript check failed: {e}")
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_name}")


@router.post("/voice-query")
async def voice_query(audio: UploadFile = File(...)):
    """
    Complete voice pipeline (synchronous):
      Audio → S3 → Transcribe → AI → TTS → Response

    Note: This is a convenience endpoint. For real-time UX, use
    /voice-input + polling /get-transcript + /chat separately.
    """
    logger.info(f"Full voice query: filename={audio.filename}")

    # Step 1: Upload
    content_type = audio.content_type or "audio/webm"
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {content_type}")

    file_id = str(uuid.uuid4())
    ext = ALLOWED_AUDIO_TYPES.get(content_type, "webm")
    s3_key = f"audio/{file_id}.{ext}"

    file_content = await audio.read()
    if len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    upload_bytes(s3_key, file_content, content_type)

    # Step 2: Start transcription
    job_name = f"erp-voice-{file_id}"
    start_transcription(job_name, s3_key, media_format=ext)

    # Step 3: Poll for completion (max 60s)
    import time
    transcript_text = None
    for _ in range(30):
        time.sleep(2)
        result = get_transcription_status(job_name)
        if result["status"] == "COMPLETED":
            transcript_text = result.get("transcript", "")
            break
        elif result["status"] == "FAILED":
            raise HTTPException(status_code=500, detail=f"Transcription failed: {result.get('reason')}")

    if not transcript_text:
        raise HTTPException(status_code=504, detail="Transcription timed out")

    # Step 4: Process through AI
    ai_result = process_query(transcript_text)

    # Step 5: Generate TTS
    tts_result = synthesize_speech(ai_result["answer"])

    return {
        "transcript": transcript_text,
        "response": ai_result["answer"],
        "query_type": ai_result["query_type"],
        "response_time_ms": ai_result["response_time_ms"],
        "audio_url": tts_result.get("audio_url"),
        "timestamp": datetime.utcnow().isoformat(),
    }
