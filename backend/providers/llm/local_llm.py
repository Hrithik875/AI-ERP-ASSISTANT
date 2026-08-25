"""
AI ERP Assistant — Local Ollama LLM Provider
==============================================
Uses local Ollama instance via HTTP API.
"""

import json
import logging
import time
import requests
from typing import Dict

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from ai.llm_service import ERP_SYSTEM_PROMPT
from providers.base import BaseLLMProvider

logger = logging.getLogger("erp-assistant")


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        self.model = OLLAMA_MODEL
        logger.info(f"Ollama LLM Provider initialized (url={self.base_url}, model={self.model})")

    @property
    def model_id(self) -> str:
        return self.model

    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        if context:
            full_prompt = f"Context:\n{context}\n\nUser Question: {user_message}"
        else:
            full_prompt = user_message

        start = time.time()
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": full_prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                },
                timeout=180
            )
            response.raise_for_status()
            result = response.json()
            
            elapsed = int((time.time() - start) * 1000)
            answer = result.get("message", {}).get("content", "").strip()
            
            logger.info(f"Ollama response generated in {elapsed}ms ({len(answer)} chars)")
            return answer
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def health_check(self) -> Dict:
        try:
            # Minimal health check
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return {
                "status": "ok", 
                "provider": "ollama", 
                "model": self.model,
                "model_downloaded": any(m.startswith(self.model) for m in models)
            }
        except Exception as e:
            return {"status": "error", "provider": "ollama", "error": str(e)}
