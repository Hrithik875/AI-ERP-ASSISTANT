"""
AI ERP Assistant — Local edge-tts Provider
============================================
Uses edge-tts to generate speech locally.
"""

import asyncio
import logging
import uuid
import os
from typing import Dict
from providers.base import BaseTTSProvider

logger = logging.getLogger("erp-assistant")


class LocalTTSProvider(BaseTTSProvider):
    def __init__(self):
        # Determine voice. edge-tts has many voices. We'll use a good English female voice by default.
        self.voice = os.environ.get("LOCAL_TTS_VOICE", "en-US-AriaNeural")
        logger.info(f"Local TTS Provider initialized (voice={self.voice})")

    def synthesize(self, text: str) -> Dict:
        """
        Convert text to speech audio using edge-tts.
        """
        if not text or not text.strip():
            logger.warning("Empty text passed to Local TTS")
            return {"audio_url": None, "s3_key": None, "error": "Empty text"}

        # Truncate if too long
        synth_text = text[:3000] if len(text) > 3000 else text

        try:
            import edge_tts
            from providers.registry import get_storage_provider
            
            storage = get_storage_provider()
            audio_id = str(uuid.uuid4())
            key = f"tts/{audio_id}.mp3"
            
            # Since edge-tts works async and outputs to a file, we'll write it directly
            # to the local storage path.
            full_path = storage._get_full_path(key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Run edge-tts asynchronously
            communicate = edge_tts.Communicate(synth_text, self.voice)
            
            # Run in a synchronous wrapper since FastAPI routes might be synchronous
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(communicate.save(full_path))
            
            file_size = os.path.getsize(full_path)
            if file_size == 0:
                raise ValueError("Generated audio file is empty")
                
            # Get URL from storage provider
            audio_url = storage.get_url(key)
            
            # Approximate duration (~16kbps for MP3)
            duration_approx = file_size / (16000 / 8)
            
            logger.info(f"Local TTS generated: {key} ({file_size} bytes, ~{duration_approx:.1f}s)")
            
            return {
                "audio_url": audio_url,
                "s3_key": key,
                "duration_approx_s": round(duration_approx, 1),
            }

        except Exception as e:
            logger.error(f"Local TTS error: {e}")
            return {"audio_url": None, "error": str(e)}
