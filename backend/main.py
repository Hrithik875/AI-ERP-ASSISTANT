"""
AI ERP Assistant — AWS Backend (Iteration-1)
=============================================
FastAPI application deployed on AWS Lambda via Mangum.

Services Used:
  - Amazon S3: store audio files and transcription outputs
  - Amazon Transcribe: speech-to-text transcription
  - CloudWatch: logging (automatic on Lambda)

Environment Variables:
  - S3_BUCKET_NAME: name of the S3 bucket (default: bmsce-ai-erp-voice-bucket)
  - AWS_REGION: AWS region (default: ap-south-1)
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# ── Logging Configuration ───────────────────────────────────────────────────
# On Lambda, logs auto-ship to CloudWatch. We configure a standard logger
# so that all print/log statements appear in CloudWatch Log Groups.
logger = logging.getLogger("erp-assistant")
logger.setLevel(logging.INFO)

# Console handler for local dev / Lambda CloudWatch
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
logger.addHandler(handler)

# ── Configuration ───────────────────────────────────────────────────────────
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "bmsce-ai-erp-voice-bucket")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")

# ── AWS Clients ─────────────────────────────────────────────────────────────
# boto3 clients are initialized at module level so they persist across
# Lambda invocations (connection reuse / warm starts).
s3_client = boto3.client("s3", region_name=AWS_REGION)
transcribe_client = boto3.client("transcribe", region_name=AWS_REGION)

# Google Gemini API Key (Will be set via AWS Lambda Environment Variables)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def ensure_bucket_exists():
    """Automatically create the S3 bucket if it doesn't exist to prevent NoSuchBucket errors"""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            logger.info(f"Bucket {S3_BUCKET_NAME} does not exist. Creating it now in {AWS_REGION}...")
            try:
                if AWS_REGION == "us-east-1":
                    s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
                else:
                    s3_client.create_bucket(
                        Bucket=S3_BUCKET_NAME,
                        CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                    )
                logger.info(f"Successfully created bucket {S3_BUCKET_NAME}")
            except Exception as create_error:
                logger.error(f"Failed to create bucket automatically: {create_error}")
        else:
            logger.error(f"Error checking bucket: {e}")

# Call this on cold start
ensure_bucket_exists()

# ── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI ERP Assistant API",
    description="Backend API for voice-powered ERP assistant",
    version="1.0.0",
)

# CORS — allow frontend to call backend from any origin during development.
# In production, restrict `allow_origins` to your deployed frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: Health Check
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    Returns confirmation that the backend is running.
    """
    logger.info("Health check called")
    return {
        "status": "healthy",
        "message": "Backend running",
        "service": "AI ERP Assistant API",
        "region": AWS_REGION,
        "bucket": S3_BUCKET_NAME,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: Voice Input — Upload Audio & Start Transcription
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/voice-input")
async def voice_input(audio: UploadFile = File(...)):
    """
    Accept an audio file (multipart/form-data), store it in S3,
    and start an Amazon Transcribe job.

    Flow:
      1. Validate the uploaded file
      2. Generate unique file ID
      3. Upload to S3 under audio/ prefix
      4. Start Transcribe job with output to transcripts/ prefix
      5. Return job_name for polling

    Accepts: audio/webm, audio/wav, audio/mp3, audio/mp4, audio/ogg, audio/flac
    Returns: { job_name, file_id, message, s3_key }
    """
    logger.info(f"Voice input received: filename={audio.filename}, content_type={audio.content_type}")

    # ── Step 1: Validate audio file ──────────────────────────────────────
    allowed_types = [
        "audio/webm", "audio/wav", "audio/wave", "audio/x-wav",
        "audio/mp3", "audio/mpeg", "audio/mp4", "audio/ogg",
        "audio/flac", "audio/x-flac",
        "video/webm",  # browsers sometimes report webm as video/webm
    ]

    content_type = audio.content_type or "audio/webm"
    if content_type not in allowed_types:
        logger.warning(f"Invalid content type: {content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {content_type}. "
                   f"Supported formats: webm, wav, mp3, mp4, ogg, flac"
        )

    # ── Step 2: Generate unique file ID ──────────────────────────────────
    file_id = str(uuid.uuid4())

    # Determine file extension from content type
    ext_map = {
        "audio/webm": "webm",
        "video/webm": "webm",
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/x-wav": "wav",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/mp4": "mp4",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/x-flac": "flac",
    }
    extension = ext_map.get(content_type, "webm")
    s3_key = f"audio/{file_id}.{extension}"

    # ── Step 3: Read file content and upload to S3 ───────────────────────
    try:
        file_content = await audio.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logger.info(f"Uploading to S3: bucket={S3_BUCKET_NAME}, key={s3_key}, size={len(file_content)} bytes")

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )
        logger.info(f"S3 upload successful: {s3_key}")

    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload audio to S3: {str(e)}")

    # ── Step 4: Start Amazon Transcribe job ──────────────────────────────
    job_name = f"erp-voice-{file_id}"

    # Map extension to Transcribe media format
    transcribe_format_map = {
        "webm": "webm",
        "wav": "wav",
        "mp3": "mp3",
        "mp4": "mp4",
        "ogg": "ogg",
        "flac": "flac",
    }
    media_format = transcribe_format_map.get(extension, "webm")

    try:
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={
                "MediaFileUri": f"s3://{S3_BUCKET_NAME}/{s3_key}"
            },
            MediaFormat=media_format,
            LanguageCode="en-IN",  # English (India)
            OutputBucketName=S3_BUCKET_NAME,
            OutputKey=f"transcripts/{file_id}.json",
        )
        logger.info(f"Transcribe job started: {job_name}")

    except ClientError as e:
        logger.error(f"Transcribe job start failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start transcription: {str(e)}"
        )

    # ── Step 5: Return job info ──────────────────────────────────────────
    return {
        "job_name": job_name,
        "file_id": file_id,
        "s3_key": s3_key,
        "message": "Audio uploaded and transcription started",
        "status": "IN_PROGRESS",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: Get Transcript — Check Status & Return Transcript Text
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/get-transcript/{job_name}")
def get_transcript(job_name: str):
    """
    Check the status of a transcription job. If completed, fetch the
    actual transcript TEXT from S3 (not just the URL).

    Returns:
      - If IN_PROGRESS: { status: "IN_PROGRESS" }
      - If COMPLETED: { status: "COMPLETED", transcript: "..." }
      - If FAILED: { status: "FAILED", reason: "..." }
    """
    logger.info(f"Checking transcript status for: {job_name}")

    try:
        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
    except ClientError as e:
        logger.error(f"Failed to get transcription job: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Transcription job not found: {job_name}"
        )

    job = response["TranscriptionJob"]
    status = job["TranscriptionJobStatus"]

    # ── Job still in progress ────────────────────────────────────────────
    if status == "IN_PROGRESS":
        logger.info(f"Job {job_name} still in progress")
        return {
            "status": "IN_PROGRESS",
            "message": "Transcription is still processing. Please poll again.",
        }

    # ── Job failed ───────────────────────────────────────────────────────
    if status == "FAILED":
        failure_reason = job.get("FailureReason", "Unknown error")
        logger.error(f"Job {job_name} failed: {failure_reason}")
        return {
            "status": "FAILED",
            "reason": failure_reason,
        }

    # ── Job completed — fetch transcript text from S3 ────────────────────
    if status == "COMPLETED":
        logger.info(f"Job {job_name} completed. Fetching transcript from S3.")

        # Extract the file_id from job_name (format: erp-voice-<uuid>)
        file_id = job_name.replace("erp-voice-", "")
        transcript_key = f"transcripts/{file_id}.json"

        try:
            # Fetch the transcript JSON from S3
            s3_response = s3_client.get_object(
                Bucket=S3_BUCKET_NAME,
                Key=transcript_key,
            )
            transcript_data = json.loads(s3_response["Body"].read().decode("utf-8"))

            # Extract the actual text from Transcribe output JSON
            # Structure: { results: { transcripts: [{ transcript: "text" }] } }
            transcript_text = ""
            if "results" in transcript_data:
                transcripts = transcript_data["results"].get("transcripts", [])
                if transcripts:
                    transcript_text = transcripts[0].get("transcript", "")

            if not transcript_text:
                transcript_text = "(No speech detected)"

            logger.info(f"Transcript extracted: '{transcript_text[:100]}...'")

            return {
                "status": "COMPLETED",
                "transcript": transcript_text,
            }

        except ClientError as e:
            logger.error(f"Failed to fetch transcript from S3: {e}")

            # Fallback: try to get transcript URL from Transcribe response
            transcript_uri = job.get("Transcript", {}).get("TranscriptFileUri", "")
            return {
                "status": "COMPLETED",
                "transcript": "(Transcript available but failed to fetch text)",
                "transcript_uri": transcript_uri,
                "error": str(e),
            }

    # ── Unknown status ───────────────────────────────────────────────────
    return {
        "status": status,
        "message": f"Unexpected transcription status: {status}",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: Analytics — Return Dashboard Analytics Data
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/analytics")
def get_analytics():
    """
    Return analytics data.
    Retrieves data dynamically from S3 (simulating our database).
    """
    logger.info("Analytics data requested")
    ensure_bucket_exists()
    
    db_key = "database/analytics.json"
    
    default_data = {
        "queriesPerDay": [
            {"date": "Mon", "count": 24}, {"date": "Tue", "count": 18},
            {"date": "Wed", "count": 32}, {"date": "Thu", "count": 28},
            {"date": "Fri", "count": 42}, {"date": "Sat", "count": 15},
            {"date": "Sun", "count": 8},
        ],
        "usageStats": [
            {"name": "Attendance", "value": 340}, {"name": "Grades", "value": 280},
            {"name": "Schedule", "value": 190}, {"name": "Documents", "value": 120},
            {"name": "General", "value": 90},
        ],
        "responseTimes": [
            {"date": "Mon", "avgMs": 320}, {"date": "Tue", "avgMs": 280},
            {"date": "Wed", "avgMs": 350}, {"date": "Thu", "avgMs": 290},
            {"date": "Fri", "avgMs": 310}, {"date": "Sat", "avgMs": 250},
            {"date": "Sun", "avgMs": 220},
        ],
    }

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=db_key)
        analytics_data = json.loads(response["Body"].read().decode("utf-8"))
        logger.info("Successfully fetched Database (Analytics) from S3")
    except ClientError as e:
        logger.info("Initializing new Database (Analytics) in S3")
        # Initialize the 'database' in S3 if it doesn't exist
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=db_key,
            Body=json.dumps(default_data),
            ContentType="application/json"
        )
        analytics_data = default_data

    return analytics_data


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5: Dashboard Stats — Return Summary Statistics
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/dashboard/stats")
def get_dashboard_stats():
    """
    Return summary statistics for the dashboard page.
    Retrieves dynamic data out of the S3 database.
    """
    logger.info("Dashboard stats requested")
    ensure_bucket_exists()
    
    db_key = "database/dashboard.json"
    
    default_stats = {
        "totalQueries": "1,247",
        "totalQueriesTrend": "+12.5%",
        "avgResponse": "0.8s",
        "avgResponseTrend": "-15%",
        "activeSessions": "23",
        "activeSessionsTrend": "+3",
        "successRate": "98.2%",
        "successRateTrend": "+0.5%",
        "recentQueries": [
            {
                "query": "What is my attendance for CSE301?",
                "time": "2 min ago",
                "status": "answered",
            },
            {
                "query": "Show me last semester grades",
                "time": "15 min ago",
                "status": "answered",
            },
            {
                "query": "When is the next exam?",
                "time": "1 hour ago",
                "status": "answered",
            },
            {
                "query": "Download attendance report",
                "time": "3 hours ago",
                "status": "completed",
            },
        ],
    }

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=db_key)
        stats = json.loads(response["Body"].read().decode("utf-8"))
        logger.info("Successfully fetched Database (Dashboard) from S3")
    except ClientError as e:
        logger.info("Initializing new Database (Dashboard) in S3")
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=db_key,
            Body=json.dumps(default_stats),
            ContentType="application/json"
        )
        stats = default_stats

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: Chat — Handle Text Chat Messages
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/chat")
async def chat_message(message: dict):
    """
    Handle text-based chat messages via Google Gemini API (Free Tier).
    It injects data from our simulated ERP Database directly into the prompt.
    """
    user_message = message.get("message", "")
    logger.info(f"Chat message received: '{user_message[:100]}'")

    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # ── INDESTRUCTIBLE MOCK AI GENERATOR (100% Offline for Guarantee) ─────
    def generate_local_response(query):
        q = query.lower()
        if any(word in q for word in ["grade", "grades", "score", "marks", "gpa"]):
            return "Based on your ERP records (CS-2024-819), your previous semester grades are: Operating Systems (A+) and Automata Theory (B). You are in Good Academic Standing!"
        elif any(word in q for word in ["attendance", "absent", "present", "shortage"]):
            return "Your attendance is 88% in Computer Networks and 92% in Machine Learning. Please note: Database Management is currently at 74%, which triggers a low-attendance warning."
        elif any(word in q for word in ["exam", "schedule", "test", "when"]):
            return "Looking at your schedule, your next upcoming exam is the Machine Learning Lab on October 25th at 10:00 AM."
        elif any(word in q for word in ["fee", "dues", "library", "pay"]):
            return "Your university tuition fees are fully paid. However, there is a pending Library fine of $12.50 that needs to be cleared."
        elif any(word in q for word in ["name", "who am i", "department", "semester"]):
            return "You are Adwi, a 6th-semester student in the Computer Science and Engineering department."
        elif any(word in q for word in ["college name","university name"]):
            return "Your college/university name is B.M.S. College of Engineering"
        else:
            return f"I have processed your query: '{user_message}'. This data requires deeper ERP synchronization, but I have logged your request under your Student ID."

    logger.info("Executing fail-proof local AI generation...")
    response_text = generate_local_response(user_message)



    return {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 7: Documents — Upload Documents to S3
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document file to S3 under the documents/ prefix.

    Accepts: PDF, DOCX, XLSX, CSV, TXT
    Returns: document metadata { id, name, size, type, uploadedAt, status }
    """
    logger.info(f"Document upload: filename={file.filename}, type={file.content_type}")

    # Validate file type
    allowed_extensions = ["pdf", "doc", "docx", "xlsx", "csv", "txt"]
    file_ext = (file.filename or "unknown").rsplit(".", 1)[-1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    # Generate unique ID and S3 key
    doc_id = str(uuid.uuid4())
    s3_key = f"documents/{doc_id}.{file_ext}"

    try:
        file_content = await file.read()
        file_size = len(file_content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type or "application/octet-stream",
        )
        logger.info(f"Document uploaded to S3: {s3_key} ({file_size} bytes)")

        # Format file size for display
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

    except ClientError as e:
        logger.error(f"Document upload to S3 failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# Lambda Handler — Mangum Adapter
# ══════════════════════════════════════════════════════════════════════════════
# Mangum wraps the FastAPI ASGI app so it can run on AWS Lambda.
# The Lambda handler is configured as: main.handler

handler = Mangum(app, lifespan="off")


# ══════════════════════════════════════════════════════════════════════════════
# Local Development Server
# ══════════════════════════════════════════════════════════════════════════════
# Run locally with: python main.py
# This starts uvicorn on port 8000 for local testing.

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting local development server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
