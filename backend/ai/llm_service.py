"""
AI ERP Assistant — LLM Service (Amazon Bedrock)
=================================================
Unified LLM wrapper using Amazon Bedrock with Claude 3 Sonnet.
All inference goes through Bedrock — no Ollama or OpenAI.
"""

import json
import logging
import time
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

from config import (
    BEDROCK_REGION, BEDROCK_MODEL_ID, BEDROCK_MAX_TOKENS,
)

logger = logging.getLogger("erp-assistant")

# ── System Prompt ───────────────────────────────────────────────────────────

ERP_SYSTEM_PROMPT = """You are an intelligent ERP (Enterprise Resource Planning) assistant for B.M.S. College of Engineering (BMSCE).
Your role is to help students and faculty access academic data including attendance records, grades, course information, schedules, and faculty details.

IMPORTANT RULES:
1. Provide concise, accurate answers based on the data provided in the context.
2. If data is provided in the context, use it directly. Do not make up data.
3. Format numbers, percentages, and grades clearly.
4. If asked about something not in the provided context, say so honestly.
5. Be professional, helpful, and concise.
6. When presenting tabular data, use clean formatting.
7. Include relevant student IDs, course codes, and specific numbers when available.
"""


class LLMService:
    """LLM interface using Amazon Bedrock (Claude 3 Sonnet)."""

    def __init__(self):
        self.model_id = BEDROCK_MODEL_ID
        self._client = None
        logger.info(f"LLM Service initialized: provider=bedrock, model={self.model_id}")

    @property
    def client(self):
        """Lazy-init Bedrock runtime client (reused across warm Lambda starts)."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=BEDROCK_REGION,
            )
        return self._client

    def generate(
        self,
        user_message: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> str:
        """Generate a response from Bedrock Claude 3 Sonnet."""
        sys_prompt = system_prompt or ERP_SYSTEM_PROMPT
        if context:
            full_prompt = f"Context:\n{context}\n\nUser Question: {user_message}"
        else:
            full_prompt = user_message

        start = time.time()

        try:
            result = self._call_bedrock(sys_prompt, full_prompt, temperature)
            elapsed = int((time.time() - start) * 1000)
            logger.info(f"Bedrock response generated in {elapsed}ms ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Bedrock generation failed: {e}")
            raise  # Raise the actual error so the caller knows it failed

    def _call_bedrock(self, system: str, user: str, temperature: float) -> str:
        """Call Amazon Bedrock with support for Claude and Titan."""
        is_titan = self.model_id.startswith("amazon.titan")
        
        if is_titan:
            # Titan Text format
            body = json.dumps({
                "inputText": f"{system}\n\n{user}",
                "textGenerationConfig": {
                    "maxTokenCount": BEDROCK_MAX_TOKENS,
                    "stopSequences": [],
                    "temperature": temperature,
                    "topP": 0.9
                }
            })
        else:
            # Claude Messages API format
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": BEDROCK_MAX_TOKENS,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}]
            })

        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())

        if is_titan:
            if "results" in response_body and len(response_body["results"]) > 0:
                return response_body["results"][0]["outputText"].strip()
        else:
            if "content" in response_body and len(response_body["content"]) > 0:
                return response_body["content"][0]["text"].strip()

        logger.warning(f"Unexpected Bedrock response format: {response_body}")
        return "(No response generated)"

    def health_check(self) -> Dict:
        """Check if the Bedrock service is available."""
        try:
            # Minimal test invocation
            is_titan = self.model_id.startswith("amazon.titan")
            if is_titan:
                test_body = json.dumps({"inputText": "hi"})
            else:
                test_body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}],
                })
                
            self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=test_body,
            )
            return {"status": "ok", "provider": "bedrock", "model": self.model_id}
        except Exception as e:
            return {"status": "error", "provider": "bedrock", "error": str(e)}


# ── Singleton ───────────────────────────────────────────────────────────────
_llm_instance: Optional[LLMService] = None


def get_llm() -> LLMService:
    """Return a singleton LLM service instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance
