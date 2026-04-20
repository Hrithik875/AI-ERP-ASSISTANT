"""
AI ERP Assistant — Transcribe Service
=======================================
Amazon Transcribe operations: start jobs, poll status, extract text.
"""

import json
import logging

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, S3_BUCKET_NAME

logger = logging.getLogger("erp-assistant")

_transcribe_client = boto3.client("transcribe", region_name=AWS_REGION)


def get_transcribe_client():
    return _transcribe_client


def start_transcription(job_name: str, s3_key: str, media_format: str = "webm") -> str:
    """Start a transcription job. Returns the job name."""
    try:
        _transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": f"s3://{S3_BUCKET_NAME}/{s3_key}"},
            MediaFormat=media_format,
            LanguageCode="en-IN",
            OutputBucketName=S3_BUCKET_NAME,
            OutputKey=f"transcripts/{job_name.replace('erp-voice-', '')}.json",
        )
        logger.info(f"Transcription job started: {job_name}")
        return job_name
    except ClientError as e:
        logger.error(f"Transcribe start failed: {e}")
        raise


def get_transcription_status(job_name: str) -> dict:
    """
    Check transcription job status.
    Returns: {status, transcript?, reason?}
    """
    try:
        response = _transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
    except ClientError as e:
        logger.error(f"Transcribe get failed: {e}")
        raise

    job = response["TranscriptionJob"]
    status = job["TranscriptionJobStatus"]

    if status == "IN_PROGRESS":
        return {"status": "IN_PROGRESS"}

    if status == "FAILED":
        return {"status": "FAILED", "reason": job.get("FailureReason", "Unknown")}

    if status == "COMPLETED":
        file_id = job_name.replace("erp-voice-", "")
        transcript_key = f"transcripts/{file_id}.json"

        try:
            from services.s3 import download_bytes
            data = download_bytes(transcript_key)
            transcript_data = json.loads(data.decode("utf-8"))
            transcript_text = ""
            if "results" in transcript_data:
                transcripts = transcript_data["results"].get("transcripts", [])
                if transcripts:
                    transcript_text = transcripts[0].get("transcript", "")

            if not transcript_text:
                transcript_text = "(No speech detected)"

            logger.info(f"Transcript: '{transcript_text[:100]}...'")
            return {"status": "COMPLETED", "transcript": transcript_text}

        except Exception as e:
            logger.error(f"Failed to fetch transcript from S3: {e}")
            return {
                "status": "COMPLETED",
                "transcript": "(Transcript available but failed to fetch text)",
                "error": str(e),
            }

    return {"status": status}
