"""
AI ERP Assistant — AWS Polly TTS Provider
===========================================
Wrapper around the existing Polly service.
"""

from typing import Dict
from providers.base import BaseTTSProvider
from services import polly


class AWSTTSProvider(BaseTTSProvider):
    def synthesize(self, text: str) -> Dict:
        return polly.synthesize_speech(text)
