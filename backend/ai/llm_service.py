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
Your primary role is to help FACULTY members (Professors, HODs, Deans) access academic data including class attendance records, student grades, course assignments, schedules, and administrative details.

IMPORTANT RULES:
1. Provide concise, accurate answers based on the data provided in the context.
2. If data is provided in the context, use it directly. Do not make up data.
3. Format numbers, percentages, and grades clearly.
4. If asked about something not in the provided context, say so honestly.
5. Be professional, helpful, and concise.
6. When presenting tabular data, you MUST use strict Github Flavored Markdown (GFM) table syntax. Every row MUST have the same number of columns separated by pipes (|). Do NOT use leading spaces to indent rows, and do NOT leave columns empty if they share a value with the row above (repeat the value instead).
7. Include relevant student IDs, course codes, and specific numbers when available.
8. Assume the user is a faculty member querying about their classes or students.
9. NEVER mention the SQL query, database schemas, or internal system processes. Your response must be purely conversational and informative for a non-technical faculty user. If there are 0 results, just state that no records were found.
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


def get_llm():
    """
    Returns the active LLM provider instance from the registry.
    This maintains compatibility with existing code while supporting dual-mode.
    """
    from providers.registry import get_llm_provider
    return get_llm_provider()
