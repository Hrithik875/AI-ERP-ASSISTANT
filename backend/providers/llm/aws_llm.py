"""
AI ERP Assistant — AWS Bedrock LLM Provider
=============================================
Wrapper around the existing LLMService.
"""

from typing import Dict
from providers.base import BaseLLMProvider


class AWSLLMProvider(BaseLLMProvider):
    def __init__(self):
        # We lazily import the existing service to avoid circular dependencies
        from ai.llm_service import LLMService
        self._svc = LLMService()

    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        return self._svc.generate(user_message, context, system_prompt, temperature)

    def health_check(self) -> Dict:
        return self._svc.health_check()
