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

import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_FAST_MODEL, LLM_TIMEOUT_SECONDS
from ai.llm_service import ERP_SYSTEM_PROMPT
from providers.base import BaseLLMProvider

logger = logging.getLogger("erp-assistant")


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip("/")
        self.model = OLLAMA_MODEL
        self.fast_model = OLLAMA_FAST_MODEL
        self.timeout = LLM_TIMEOUT_SECONDS
        logger.info(
            f"Ollama LLM Provider initialized "
            f"(url={self.base_url}, model={self.model}, "
            f"fast_model={self.fast_model}, timeout={self.timeout}s)"
        )

    @property
    def model_id(self) -> str:
        return self.model

    # ── Private call helper ──────────────────────────────────────────────────

    def _call(self, model: str, system: str, user: str, temperature: float) -> str:
        """POST to Ollama /api/chat (non-streaming). Returns the response content string."""
        start = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        answer = response.json().get("message", {}).get("content", "").strip()
        logger.info(
            f"Ollama [{model}] response in {elapsed_ms}ms ({len(answer)} chars)"
        )
        return answer

    # ── Public API ───────────────────────────────────────────────────────────

    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Generate a response using the full-quality model (OLLAMA_MODEL)."""
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        full_prompt = (
            f"Context:\n{context}\n\nUser Question: {user_message}"
            if context
            else user_message
        )
        try:
            return self._call(self.model, sys_prompt, full_prompt, temperature)
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
        try:
            return self._call(self.fast_model, sys_prompt, user_message, temperature)
        except Exception as fast_err:
            logger.warning(
                f"Fast model '{self.fast_model}' failed ({fast_err}); "
                f"falling back to '{self.model}'"
            )
            try:
                return self._call(self.model, sys_prompt, user_message, temperature)
            except Exception as e:
                logger.error(f"Ollama fast generation (with fallback) failed: {e}")
                raise

    def generate_stream(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
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
                    "options": {"temperature": temperature},
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
