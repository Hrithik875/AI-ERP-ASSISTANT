"""
AI ERP Assistant — Local Piper TTS Provider
=============================================
Uses piper-tts to generate speech fully offline.

Piper is a fast, local, neural text-to-speech engine that runs entirely
on-device with no network calls at synthesis time (network is used only
once, on first run, to download the voice model weights ~60 MB).

Voice model: en_US-amy-medium (English US, female, natural-sounding)
Output format: WAV (native Piper output; supported by all modern browsers)

Dependencies (see requirements.txt):
    pip install piper-tts
    # Also requires espeak-ng on the host system:
    # Windows:  winget install espeak-ng
    # Ubuntu:   sudo apt-get install espeak-ng
    # macOS:    brew install espeak-ng
"""

import logging
import os
import urllib.request
import uuid
import wave
from pathlib import Path
from typing import Dict

from providers.base import BaseTTSProvider

logger = logging.getLogger("erp-assistant")

# ── Voice model configuration ─────────────────────────────────────────────────
# Model files live inside the backend directory so they persist across restarts
# and are NOT committed to git (add piper_voices/ to .gitignore).
_VOICES_DIR = Path(__file__).parent.parent.parent / "piper_voices"

PIPER_VOICE_NAME = os.environ.get("PIPER_VOICE", "en_US-amy-medium")
PIPER_MODEL_PATH = _VOICES_DIR / f"{PIPER_VOICE_NAME}.onnx"
PIPER_CONFIG_PATH = _VOICES_DIR / f"{PIPER_VOICE_NAME}.onnx.json"

# Hugging Face rhasspy/piper-voices repository (v1.0.0 tag — stable)
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
_VOICE_URLS = {
    "en_US-amy-medium": {
        "onnx":   f"{_HF_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config": f"{_HF_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    }
}


def _ensure_voice_model() -> None:
    """
    Download the Piper voice model files if they are not already present.
    This runs at most once; subsequent calls return immediately.
    Raises RuntimeError if an unsupported voice is requested.
    """
    if PIPER_MODEL_PATH.exists() and PIPER_CONFIG_PATH.exists():
        return  # Already downloaded

    urls = _VOICE_URLS.get(PIPER_VOICE_NAME)
    if not urls:
        raise RuntimeError(
            f"Piper voice '{PIPER_VOICE_NAME}' is not in the pre-configured download list. "
            f"Supported voices: {list(_VOICE_URLS.keys())}. "
            f"To use a custom voice, place the .onnx and .onnx.json files in: {_VOICES_DIR}"
        )

    _VOICES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Piper voice model not found locally. Downloading '{PIPER_VOICE_NAME}' "
        f"(~60 MB) from Hugging Face — this happens only once."
    )

    for file_type, url in [("onnx", urls["onnx"]), ("config", urls["config"])]:
        dest = PIPER_MODEL_PATH if file_type == "onnx" else PIPER_CONFIG_PATH
        logger.info(f"  Downloading {dest.name} ...")
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            # Clean up partial files so the next startup retries cleanly
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download Piper voice model ({file_type}): {e}. "
                f"Check internet connectivity for first-run model download."
            ) from e

    logger.info(f"Piper voice model downloaded successfully to: {_VOICES_DIR}")


class LocalTTSProvider(BaseTTSProvider):
    """
    Text-to-speech provider using Piper TTS (fully offline after first run).

    Piper loads the ONNX voice model into memory on first synthesis call
    and reuses it for all subsequent calls (singleton pattern via lazy init).
    """

    def __init__(self):
        self._voice = None  # Lazy-loaded PiperVoice instance
        logger.info(
            f"Local TTS Provider initialized (Piper TTS, voice={PIPER_VOICE_NAME})"
        )

    @property
    def voice(self):
        """Lazy-load PiperVoice model (downloads model files if needed)."""
        if self._voice is None:
            _ensure_voice_model()
            try:
                from piper import PiperVoice
                self._voice = PiperVoice.load(str(PIPER_MODEL_PATH))
                logger.info("Piper TTS voice model loaded into memory.")
            except ImportError as e:
                raise ImportError(
                    "piper-tts is not installed. Run: pip install piper-tts"
                ) from e
        return self._voice

    def synthesize(self, text: str) -> Dict:
        """
        Convert text to speech audio using Piper TTS.

        Returns:
            {
                "audio_url": str,           # URL to fetch the WAV file
                "s3_key": str,              # Storage key (local path relative to base_dir)
                "duration_approx_s": float, # Approximate playback duration
            }
            On error:
            {
                "audio_url": None,
                "error": str,
            }
        """
        if not text or not text.strip():
            logger.warning("Empty text passed to Piper TTS")
            return {"audio_url": None, "s3_key": None, "error": "Empty text"}

        # Truncate very long inputs to stay within synthesis time limits
        synth_text = text[:3000] if len(text) > 3000 else text

        try:
            from providers.registry import get_storage_provider

            storage = get_storage_provider()
            audio_id = str(uuid.uuid4())
            key = f"tts/{audio_id}.wav"

            # Determine the full filesystem path via the storage provider
            full_path = storage._get_full_path(key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Synthesize directly to a WAV file using PiperVoice
            with wave.open(full_path, "wb") as wav_file:
                self.voice.synthesize_wav(synth_text, wav_file)

            file_size = os.path.getsize(full_path)
            if file_size == 0:
                raise ValueError("Piper TTS produced an empty WAV file")

            # Retrieve a servable URL from the storage provider
            audio_url = storage.get_url(key)

            # Approximate duration from WAV header parameters.
            # We open the file to read the exact sample rate and frame count.
            try:
                with wave.open(full_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration_approx = frames / float(rate) if rate > 0 else file_size / 32000
            except Exception:
                duration_approx = file_size / 32000  # conservative fallback

            logger.info(
                f"Piper TTS generated: {key} ({file_size} bytes, ~{duration_approx:.1f}s)"
            )

            return {
                "audio_url": audio_url,
                "s3_key": key,
                "duration_approx_s": round(duration_approx, 1),
            }

        except Exception as e:
            logger.error(f"Piper TTS synthesis error: {e}")
            return {"audio_url": None, "error": str(e)}

