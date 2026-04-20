"""
AI ERP Assistant — Polly TTS Service
=======================================
Amazon Polly text-to-speech: converts AI response text to audio.
Returns a presigned S3 URL for the generated audio file.
"""

import logging
import uuid

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, S3_BUCKET_NAME, POLLY_VOICE_ID, POLLY_ENGINE
from services.s3 import upload_bytes, get_presigned_url

logger = logging.getLogger("erp-assistant")

_polly_client = boto3.client("polly", region_name=AWS_REGION)


def synthesize_speech(text: str) -> dict:
    """
    Convert text to speech using Amazon Polly.
    Stores the audio in S3 and returns a presigned URL.

    Returns: {audio_url, s3_key, duration_approx_s}
    """
    if not text or not text.strip():
        logger.warning("Empty text passed to Polly TTS")
        return {"audio_url": None, "s3_key": None, "error": "Empty text"}

    # Truncate very long texts (Polly has a 3000 character limit for non-SSML)
    synth_text = text[:2900] if len(text) > 2900 else text

    try:
        response = _polly_client.synthesize_speech(
            Text=synth_text,
            OutputFormat="mp3",
            VoiceId=POLLY_VOICE_ID,
            Engine=POLLY_ENGINE,
        )

        # Read the audio stream
        audio_data = response["AudioStream"].read()
        if not audio_data:
            logger.error("Polly returned empty audio stream")
            return {"audio_url": None, "error": "Empty audio stream"}

        # Store in S3
        audio_id = str(uuid.uuid4())
        s3_key = f"tts/{audio_id}.mp3"
        upload_bytes(s3_key, audio_data, content_type="audio/mpeg")

        # Generate presigned URL (1 hour expiry)
        audio_url = get_presigned_url(s3_key, expiration=3600)

        # Approximate duration (Polly's MP3 is ~16kbps for neural)
        duration_approx = len(audio_data) / (16000 / 8)

        logger.info(f"TTS generated: {s3_key} ({len(audio_data)} bytes, ~{duration_approx:.1f}s)")

        return {
            "audio_url": audio_url,
            "s3_key": s3_key,
            "duration_approx_s": round(duration_approx, 1),
        }

    except ClientError as e:
        logger.error(f"Polly synthesis failed: {e}")
        return {"audio_url": None, "error": str(e)}
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"audio_url": None, "error": str(e)}


def get_available_voices() -> list:
    """List available Polly voices for the configured region."""
    try:
        response = _polly_client.describe_voices(LanguageCode="en-US")
        return [
            {"id": v["Id"], "name": v["Name"], "gender": v["Gender"]}
            for v in response["Voices"]
        ]
    except Exception as e:
        logger.error(f"Failed to list Polly voices: {e}")
        return []
