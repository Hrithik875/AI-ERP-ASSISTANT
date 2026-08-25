"""
AI ERP Assistant — Chat Route
================================
Text-based chat endpoint powered by real AI agent.
"""

import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ai.agent import process_query
from providers.registry import get_tts_provider

logger = logging.getLogger("erp-assistant")
router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_message(message: dict):
    """
    Handle text-based chat messages.
    Routes query through AI agent → DB/RAG/LLM → Response + Optional TTS.
    Accepts bounded conversation history to resolve conversational follow-ups.
    """
    user_message = message.get("message", "")
    history = message.get("history", [])
    include_audio = message.get("include_audio", False)

    logger.info(f"Chat: '{user_message[:100]}' (history_turns={len(history)})")

    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        # Process through AI agent with conversation history
        result = process_query(user_message, history=history)

        response_data = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": result["answer"],
            "query_type": result["query_type"],
            "response_time_ms": result["response_time_ms"],
            "source": result["source_info"],
            "sources": result.get("sources", []),
            "tool_used": result.get("tool_used", result["source_info"]),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Optional TTS
        if include_audio:
            tts = get_tts_provider().synthesize(result["answer"])
            response_data["audio_url"] = tts.get("audio_url")

        return response_data

    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.post("/text-query")
async def text_query(payload: dict):
    """
    Alternative text query endpoint matching the API spec.
    Same as /chat but with explicit field names.
    """
    query = payload.get("query", payload.get("message", ""))
    history = payload.get("history", [])
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    result = process_query(query, history=history)

    # Optional TTS
    audio_url = None
    if payload.get("include_audio", False):
        tts = get_tts_provider().synthesize(result["answer"])
        audio_url = tts.get("audio_url")

    return {
        "query": query,
        "response": result["answer"],
        "query_type": result["query_type"],
        "response_time_ms": result["response_time_ms"],
        "source": result["source_info"],
        "sources": result.get("sources", []),
        "tool_used": result.get("tool_used", result["source_info"]),
        "audio_url": audio_url,
        "timestamp": datetime.utcnow().isoformat(),
    }
