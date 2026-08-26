"""
AI ERP Assistant — Local Ollama LLM Provider
==============================================
Uses local Ollama instance via HTTP API.

Three generation modes:
  generate()        — full-quality model (OLLAMA_MODEL, e.g. qwen2.5:7b-instruct)
                       Used for the final user-visible answer formatting step.
  generate_fast()   — lightweight model (OLLAMA_FAST_MODEL, e.g. qwen2.5:3b-instruct)
                       Used for internal LLM calls (intent classification, tool dispatch).
  generate_stream() — streaming tokens from the full-quality model via generator.
                       Used by the /chat/stream SSE endpoint.
"""

import json
import logging
import time
from typing import Dict, Generator

import os
import requests

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_FAST_MODEL,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_NUM_THREADS,
    OLLAMA_NUM_CTX,
)
from ai.llm_service import ERP_SYSTEM_PROMPT
from providers.base import BaseLLMProvider

logger = logging.getLogger("erp-assistant")

try:
    import psutil
    _detected_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 4
except Exception:
    _detected_cores = os.cpu_count() or 4


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip("/")
        self.model = OLLAMA_MODEL
        self.fast_model = OLLAMA_FAST_MODEL
        self.timeout = LLM_TIMEOUT_SECONDS
        self.num_threads = OLLAMA_NUM_THREADS if OLLAMA_NUM_THREADS > 0 else _detected_cores
        self.num_ctx = OLLAMA_NUM_CTX if OLLAMA_NUM_CTX > 0 else 2048
        logger.info(
            f"Ollama LLM Provider initialized "
            f"(url={self.base_url}, model={self.model}, "
            f"fast_model={self.fast_model}, threads={self.num_threads}, "
            f"num_ctx={self.num_ctx}, timeout={self.timeout}s)"
        )

    @property
    def model_id(self) -> str:
        return self.model

    def _get_options(self, temperature: float, num_predict: int = 0) -> dict:
        opts = {"temperature": temperature}
        if self.num_threads > 0:
            opts["num_thread"] = self.num_threads
        if self.num_ctx > 0:
            opts["num_ctx"] = self.num_ctx
        # Phase 9: cap output tokens to prevent runaway generation / fabricated follow-up turns.
        if num_predict > 0:
            opts["num_predict"] = num_predict
        return opts

    # ── Private call helper ──────────────────────────────────────────────────

    def _call(self, model: str, system: str, user: str, temperature: float,
               num_predict: int = 0) -> str:
        """POST to Ollama /api/chat (non-streaming). Returns the response content string."""
        start = time.perf_counter()
        logger.info(f"Ollama HTTP request dispatch -> model='{model}'")
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": self._get_options(temperature, num_predict),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        answer = response.json().get("message", {}).get("content", "").strip()
        logger.info(
            f"Ollama [{model}] response generated in {elapsed_ms}ms ({len(answer)} chars)"
        )
        return answer

    # ── Public API ───────────────────────────────────────────────────────────

    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
        # Phase 9: 1024-token cap prevents fabricated follow-up generation.
        num_predict: int = 1024,
    ) -> str:
        """Generate a response using the full-quality model (OLLAMA_MODEL)."""
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        full_prompt = (
            f"Context:\n{context}\n\nUser Question: {user_message}"
            if context
            else user_message
        )
        try:
            return self._call(self.model, sys_prompt, full_prompt, temperature, num_predict)
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def generate_fast(
        self,
        user_message: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        """Generate a response using the fast/lightweight model (OLLAMA_FAST_MODEL).

        Intended for internal calls: intent classification fallback, tool-dispatch
        JSON extraction. Not used for user-visible output.
        Falls back to the full model on error so the pipeline is always functional
        even if the fast model is not yet downloaded.
        """
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        logger.info(f"Ollama generate_fast requested -> targeting fast_model='{self.fast_model}'")
        try:
            # num_predict=512: fast calls produce short JSON, no need for larger cap.
            return self._call(self.fast_model, sys_prompt, user_message, temperature, 512)
        except Exception as fast_err:
            logger.warning(
                f"Fast model '{self.fast_model}' failed ({fast_err}); "
                f"falling back to '{self.model}'"
            )
            try:
                return self._call(self.model, sys_prompt, user_message, temperature, 512)
            except Exception as e:
                logger.error(f"Ollama fast generation (with fallback) failed: {e}")
                raise

    def prewarm(self) -> Dict[str, int]:
        """Pre-warm configured models into memory with explicit thread/context options."""
        timings = {}
        # If fast_model and model are the same, only warm once
        models_to_warm = [self.model] if self.fast_model == self.model else [self.fast_model, self.model]
        for m in models_to_warm:
            t0 = time.perf_counter()
            try:
                logger.info(f"Pre-warming Ollama model '{m}' (threads={self.num_threads}, num_ctx={self.num_ctx})...")
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": m,
                        "prompt": "hi",
                        "keep_alive": "10m",
                        "options": self._get_options(0.0),
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                elapsed = int((time.perf_counter() - t0) * 1000)
                timings[m] = elapsed
                logger.info(f"Model '{m}' pre-warmed successfully in {elapsed}ms")
            except Exception as e:
                logger.warning(f"Failed to pre-warm model '{m}': {e}")
        return timings

    def generate_stream(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
        # Phase 9: 1024-token cap prevents fabricated follow-up generation during streaming.
        num_predict: int = 1024,
    ) -> Generator[str, None, None]:
        """Stream token chunks from the full-quality model via Ollama streaming API.

        Yields raw token strings as they arrive. Caller is responsible for framing
        them as SSE events.
        """
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        full_prompt = (
            f"Context:\n{context}\n\nUser Question: {user_message}"
            if context
            else user_message
        )
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": full_prompt},
                    ],
                    "stream": True,
                    "options": self._get_options(temperature, num_predict),
                },
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise

    def health_check(self) -> Dict:
        """Check Ollama availability and whether both models are downloaded."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return {
                "status": "ok",
                "provider": "ollama",
                "model": self.model,
                "fast_model": self.fast_model,
                "model_downloaded": any(m.startswith(self.model) for m in models),
                "fast_model_downloaded": any(
                    m.startswith(self.fast_model) for m in models
                ),
            }
        except Exception as e:
            return {"status": "error", "provider": "ollama", "error": str(e)}
