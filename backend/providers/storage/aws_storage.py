"""
AI ERP Assistant — AWS S3 Storage Provider
============================================
Wrapper around the existing S3 service.
"""

from providers.base import BaseStorageProvider
from services import s3


class AWSStorageProvider(BaseStorageProvider):
    def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return s3.upload_bytes(key, data, content_type)

    def download_bytes(self, key: str) -> bytes:
        return s3.download_bytes(key)

    def get_url(self, key: str, expiration: int = 3600) -> str:
        return s3.get_presigned_url(key, expiration)

    def delete(self, key: str) -> None:
        s3.delete_object(key)

    def ensure_ready(self) -> None:
        s3.ensure_bucket_exists()
