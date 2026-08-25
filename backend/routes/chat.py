"""
AI ERP Assistant — Chat Route
================================
Text-based chat endpoint powered by real AI agent.

Endpoints:
  POST /chat         — standard JSON response (unchanged)
  POST /chat/stream  — SSE streaming: tokens arrive progressively,
                       then a final [DONE] event carries metadata JSON.
"""

import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


@router.post("/chat/stream")
async def chat_stream(message: dict):
    """
    SSE streaming chat endpoint.

    The response is a text/event-stream with two event types:
      • token events  → data: <token text>\\n\\n
      • done event    → data: [DONE] <json metadata>\\n\\n

    The metadata JSON in the [DONE] event contains:
      { id, query_type, response_time_ms, source, sources, tool_used, timestamp }

    Clients should concatenate token payloads to build the full message, then parse
    the metadata from the [DONE] event.
    """
    user_message = message.get("message", "")
    history = message.get("history", [])

    logger.info(f"Chat/stream: '{user_message[:100]}' (history_turns={len(history)})")

    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    request_id = str(uuid.uuid4())

    async def event_generator():
        try:
            result = process_query(user_message, history=history, stream=True)

            # If streaming is supported, result["answer_stream"] is a token generator
            token_gen = result.get("answer_stream")
            if token_gen is not None:
                for token in token_gen:
                    if token:
                        # Escape newlines so each SSE payload is a single line
                        escaped = token.replace("\n", "\\n")
                        yield f"data: {escaped}\n\n"
                # Emit the [DONE] metadata event
                meta = {
                    "id": request_id,
                    "query_type": result["query_type"],
                    "response_time_ms": result["response_time_ms"],
                    "source": result["source_info"],
                    "sources": result.get("sources", []),
                    "tool_used": result.get("tool_used", result["source_info"]),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"data: [DONE] {json.dumps(meta)}\n\n"
            else:
                # Fall back: emit the full answer as a single token then [DONE]
                answer = result.get("answer", "")
                if answer:
                    escaped = answer.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"
                meta = {
                    "id": request_id,
                    "query_type": result["query_type"],
                    "response_time_ms": result["response_time_ms"],
                    "source": result["source_info"],
                    "sources": result.get("sources", []),
                    "tool_used": result.get("tool_used", result["source_info"]),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"data: [DONE] {json.dumps(meta)}\n\n"

        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            err_payload = json.dumps({"error": str(e)})
            yield f"data: [ERROR] {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )


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
