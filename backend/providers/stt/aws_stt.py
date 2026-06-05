"""
AI ERP Assistant — AWS Transcribe STT Provider
================================================
Wrapper around the existing Transcribe service.
"""

from typing import Dict
from providers.base import BaseSTTProvider
from services import transcribe


class AWSSTTProvider(BaseSTTProvider):
    def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> str:
        # Transcribe is async-only, so synchronous transcription isn't natively supported here.
        # This matches how the original voice route implemented it.
        raise NotImplementedError("AWSSTTProvider does not support synchronous transcribe(). Use transcribe_async instead.")

    def transcribe_async(self, audio_data: bytes, audio_format: str = "webm", job_name: str = None) -> Dict:
        # Wait, the interface expects us to pass the S3 key if we were fully abstracting,
        # but the original flow was: upload_bytes -> start_transcription.
        # So we should adapt to that. Let's assume the caller still uploads to S3,
        # OR we can let the STT provider handle the upload.
        # Actually, for AWS Transcribe, the audio MUST be in S3. 
        # But our interface says `transcribe_async(audio_data, audio_format)`.
        # To make it truly pluggable, AWSSTTProvider should handle the S3 upload internally.
        import uuid
        from services.s3 import upload_bytes
        
        if not job_name:
            file_id = str(uuid.uuid4())
            job_name = f"erp-voice-{file_id}"
        else:
            file_id = job_name.replace("erp-voice-", "")
            
        s3_key = f"audio/{file_id}.{audio_format}"
        upload_bytes(s3_key, audio_data, f"audio/{audio_format}")
        
        transcribe.start_transcription(job_name, s3_key, media_format=audio_format)
        
        return {
            "job_name": job_name,
            "status": "IN_PROGRESS",
            "file_id": file_id,
            "s3_key": s3_key,
        }

    def get_transcription_status(self, job_name: str) -> Dict:
        return transcribe.get_transcription_status(job_name)
