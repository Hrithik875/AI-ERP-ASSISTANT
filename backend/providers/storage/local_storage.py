"""
AI ERP Assistant — Local Storage Provider
===========================================
Saves files to a local directory and serves them via FastAPI.
"""

import os
import shutil
import logging
from providers.base import BaseStorageProvider
from config import LOCAL_STORAGE_DIR, LOCAL_SERVER_URL

logger = logging.getLogger("erp-assistant")


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self):
        self.base_dir = os.path.abspath(LOCAL_STORAGE_DIR)
        self.ensure_ready()
        logger.info(f"Local Storage Provider initialized (dir={self.base_dir})")

    def _get_full_path(self, key: str) -> str:
        # Prevent directory traversal attacks
        safe_key = key.lstrip('/')
        full_path = os.path.abspath(os.path.join(self.base_dir, safe_key))
        if not full_path.startswith(self.base_dir):
            raise ValueError(f"Invalid storage key: {key}")
        return full_path

    def ensure_ready(self) -> None:
        """Create the storage directory and subdirectories if they don't exist."""
        os.makedirs(self.base_dir, exist_ok=True)
        # Create standard subdirectories
        for subdir in ["audio", "documents", "tts", "transcripts"]:
            os.makedirs(os.path.join(self.base_dir, subdir), exist_ok=True)

    def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        full_path = self._get_full_path(key)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            with open(full_path, "wb") as f:
                f.write(data)
            logger.info(f"Local file saved: {key} ({len(data)} bytes)")
            return key
        except Exception as e:
            logger.error(f"Local file save failed for {key}: {e}")
            raise

    def download_bytes(self, key: str) -> bytes:
        full_path = self._get_full_path(key)
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            logger.info(f"Local file read: {key} ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.error(f"Local file read failed for {key}: {e}")
            raise

    def get_url(self, key: str, expiration: int = 3600) -> str:
        # In local mode, files are served statically from /files/
        base_url = LOCAL_SERVER_URL.rstrip('/')
        safe_key = key.lstrip('/')
        return f"{base_url}/files/{safe_key}"

    def delete(self, key: str) -> None:
        full_path = self._get_full_path(key)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"Local file deleted: {key}")
        except Exception as e:
            logger.error(f"Local file delete failed for {key}: {e}")
            raise
