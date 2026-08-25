"""
AI ERP Assistant — Tool-Based Orchestrator
===========================================
Routes user queries to the appropriate specialized tool using LLM intent extraction.
No LLM-generated SQL is used for ERP queries, only parameterized tool execution.

Phase 7 changes:
  - Per-step perf instrumentation (classification / dispatch / format / total).
  - classify_query() and tool-dispatch extraction use the fast/lightweight model.
  - Final user-visible format step uses the full-quality model (unchanged UX).
  - process_query() accepts stream=True to return a generator for SSE endpoints.
"""

import logging
import json
import time
from typing import Dict, Generator, Tuple, Union

from ai.llm_service import get_llm
from ai.tools import REGISTERED_TOOLS
try:
    from middleware.request_id import get_request_id
except ImportError:
    def get_request_id():
        return ""

logger = logging.getLogger("erp-assistant")


def _format_history_context(history: list) -> str:
    """Format bounded prior turns into a clean conversation transcript snippet."""
    if not history:
        return ""
    formatted = []
    for turn in history[-4:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        content = str(turn.get("content", "")).strip()
        if len(content) > 300:
            content = content[:300] + "..."
        formatted.append(f"{role}: {content}")
    return "\n".join(formatted)


def _get_fast_llm():
    """Return the LLM provider if it supports generate_fast(); otherwise return the normal LLM.
    Avoids a hard dependency on OllamaLLMProvider in AWS mode (which lacks generate_fast)."""
    llm = get_llm()
    if hasattr(llm, "generate_fast"):
        return llm
    return llm  # AWS LLM uses generate() for both paths


def _fast_generate(llm, user_message: str, system_prompt: str) -> str:
    """Call generate_fast() if available; fall back to generate() for AWS compatibility."""
    if hasattr(llm, "generate_fast"):
        return llm.generate_fast(user_message=user_message, system_prompt=system_prompt, temperature=0.0)
    return llm.generate(user_message=user_message, system_prompt=system_prompt, temperature=0.0)


# ── Query Classification ───────────────────────────────────────────────────

def classify_query(query: str, history: list = None) -> str:
    """
    Classify a user query using fast heuristics with LLM fallback into: 'erp', 'document', 'general'.
    Utilizes conversation history to resolve contextual follow-ups.

    Phase 7: LLM fallback now uses the fast/lightweight model (generate_fast).
    """
    q_lower = query.lower()
    doc_keywords = [
        "document", "documents", "policy", "policies", "syllabus", "manual",
        "circular", "circulars", "notice", "regulation", "regulations", "guideline"
    ]
    erp_keywords = [
        "attendance", "absent", "present", "grade", "grades", "marks", "gpa", "cgpa", "schedule",
        "timetable", "student", "students", "faculty", "course", "courses",
        "department", "classes", "class", "at-risk", "risk", "miss", "bunk",
        "lowest", "highest", "which one", "who has", "how many", "usn"
    ]

    # Fast deterministic pre-checks (no LLM call)
    if any(k in q_lower for k in doc_keywords):
        return "document"
    if any(k in q_lower for k in erp_keywords):
        return "erp"
    if history:
        hist_text = " ".join(str(t.get("content", "")) for t in history[-2:]).lower()
        if any(k in hist_text for k in erp_keywords):
            return "erp"

    # LLM fallback for nuanced / ambiguous intents — uses fast model
    llm = _get_fast_llm()
    history_ctx = _format_history_context(history)
    history_section = f"\nRecent Conversation History:\n{history_ctx}\n" if history_ctx else ""

    prompt = f"""You are an Intent Detection and Query Classification engine for an academic ERP system.
Analyze the user's query (taking into account the conversation history if it is a follow-up) and classify it into exactly ONE of the following categories:

- 'erp': If the query asks for database records, student metrics, or follow-ups referencing prior ERP data (e.g., attendance, grades, GPA, schedules, timetables, \"which one has lowest\", \"how many more classes\", faculty/student info, courses).
- 'document': If the query asks for information likely found in documents (e.g., manual, syllabus, policy, circular, notice, report, assignment, notes).
- 'general': If it's a general greeting, casual conversation, or entirely unrelated to the academic system.
{history_section}
Reply ONLY with the exact word: erp, document, or general. Do not add any punctuation or explanation."""

    try:
        result = _fast_generate(llm, user_message=f"Query: {query}", system_prompt=prompt)
        intent = result.strip().lower()
        if "erp" in intent:
            return "erp"
        elif "document" in intent:
            return "document"
        else:
            return "general"
    except Exception as e:
        logger.error(f"LLM Intent Classification failed: {e}")
        return "general"  # Fallback


# ── Tool Dispatcher (No SQL Generation) ────────────────────────────────────

def execute_tool_query(
    question: str,
    history: list = None,
    stream: bool = False,
) -> Union[Tuple[str, str, list, str], Tuple[Generator, str, list, str]]:
    """
    Extract intent/entities and dispatch to the correct Tool.
    Uses conversation history to resolve referential entities and context.

    Phase 7:
      - Dispatch extraction uses the fast/lightweight model.
      - Final formatting uses the full-quality model.
      - When stream=True, returns (generator, source_info, sources, tool_used)
        where generator yields the format answer tokens.

    Returns (answer_or_generator, source_info, sources, tool_used).
    """
    llm = get_llm()
    history_ctx = _format_history_context(history)
    history_section = (
        f"\nRecent Conversation History (use this to resolve references like 'that student', 'which one is lowest', course codes, or USNs):\n{history_ctx}\n"
        if history_ctx else ""
    )

    # 1. Build tool definitions
    tools_info = []
    for t in REGISTERED_TOOLS:
        tools_info.append(f"Tool: {t.name}\nDescription: {t.description}\nParameters: {json.dumps(t.parameters)}")
    tools_str = "\n\n".join(tools_info)

    # 2. Extract tool intent and parameters via FAST model
    extract_prompt = f"""You are an intelligent router for an Academic ERP system.
Available tools:
{tools_str}

Analyze the user's question (and recent conversation history if it is a follow-up) and select the most appropriate tool and the necessary parameters.
{history_section}
Respond ONLY with a valid JSON object matching this schema:
{{
  "tool_name": "NameOfTheTool",
  "params": {{
    "action": "action_name",
    "param1": "value1"
  }}
}}

CRITICAL INSTRUCTIONS:
- ONLY output JSON. No markdown backticks, no explanations.
- Map entities properly: if the user asks for \"Aarav M\", the `usn` might be required but you might not know it. If a name is provided and USN is needed, you might need to use `action: search` to find the USN first, or pass it if you know it.
- If the user refers to a course or student from the conversation history (e.g., \"which one has lowest attendance in that course?\", \"what about CS601?\", \"how many more classes does he need?\"), extract the course_code or usn/name from the history!
- If the user asks how many classes a student needs to attend to reach 75%/85%, use AttendanceTool with action: 'calculate_classes_needed', usn/name, and target_pct.
- If the user asks how many classes a student can miss/bunk safely, use AttendanceTool with action: 'calculate_classes_can_miss', usn/name, and target_pct.
- If it's an attendance query or attendance risk query, use AttendanceTool.
- If it's grades, use GradesTool.
- If it's timetable, use TimetableTool.
- If it's courses, use CourseTool.
- If it's analytics, use AnalyticsTool.
- If it asks about college policies, documents, circulars, or general regulations, use DocumentTool.
"""

    json_resp = ""
    try:
        t_dispatch_start = time.perf_counter()
        json_resp = _fast_generate(llm, user_message=question, system_prompt=extract_prompt)
        t_dispatch_ms = int((time.perf_counter() - t_dispatch_start) * 1000)
        logger.info(f"[timing] dispatch_extract={t_dispatch_ms}ms")

        # Clean JSON
        json_resp = json_resp.strip()
        if json_resp.startswith("```json"):
            json_resp = json_resp[7:]
        if json_resp.startswith("```"):
            json_resp = json_resp[3:]
        if json_resp.endswith("```"):
            json_resp = json_resp[:-3]

        extraction = json.loads(json_resp.strip())
        tool_name = extraction.get("tool_name")
        params = extraction.get("params", {})

        logger.info(f"LLM Tool Extraction: {tool_name} with params {params}")

        # 3. Execute tool
        selected_tool = None
        for t in REGISTERED_TOOLS:
            if t.name == tool_name:
                selected_tool = t
                break

        if not selected_tool:
            return "I could not determine the right tool for your query.", "Extraction failed", [], "Error"

        t_tool_start = time.perf_counter()
        tool_results = selected_tool.execute(params)
        t_tool_ms = int((time.perf_counter() - t_tool_start) * 1000)
        logger.info(f"[timing] tool_execute={t_tool_ms}ms tool={tool_name}")

        sources = []

        # If DocumentTool was selected, check for fallback / sources
        if selected_tool.name == "DocumentTool":
            if not tool_results.get("has_relevant_results", True):
                return tool_results.get("message", "No relevant documents found."), "DocumentTool (no match)", [], "DocumentTool (no match)"
            sources = tool_results.get("sources", [])

        # 4. Format results — uses FULL-QUALITY model for user-visible answer
        format_prompt = """You are an AI ERP Assistant for a college.
Format the provided JSON data into a clean, professional response.
Use Markdown tables for lists.
If the data contains at-risk students or attendance calculations, explicitly state:
- The student's current attendance percentage and attended/total class numbers.
- The threshold being compared against (e.g. 75.0% or 85.0%).
- The exact shortage gap in percentage points.
- The number of consecutive classes needed to reach eligibility (or safe classes that can be missed).
If the user asked a specific follow-up question (e.g. 'which one has the lowest attendance?'), directly answer that question highlighting the specific record.
If the data contains an error or \"Not found\", explain it politely to the user.
Do NOT reveal internal IDs or backend details."""

        user_msg = f"Question: {question}\nData: {json.dumps(tool_results, default=str)}"
        if history_ctx:
            user_msg = f"Prior Conversation:\n{history_ctx}\n\nCurrent Question: {question}\nData: {json.dumps(tool_results, default=str)}"

        # Determine tool_used identifier for transparency
        if selected_tool.name == "AttendanceTool" and params.get("action") in (
            "calculate_classes_needed", "calculate_classes_can_miss", "classes_needed", "classes_can_miss", "safe_bunks"
        ):
            tool_used = "Reasoning (AttendanceTool)"
        else:
            tool_used = selected_tool.name

        if stream and hasattr(llm, "generate_stream"):
            # Return streaming generator — caller frames SSE events
            t_format_start = time.perf_counter()
            gen = llm.generate_stream(
                user_message=user_msg,
                system_prompt=format_prompt,
                temperature=0.3,
            )
            logger.info(f"[timing] format_stream_started (dispatch={t_dispatch_ms}ms, tool={t_tool_ms}ms)")
            return gen, f"{tool_name} {params}", sources, tool_used

        # Non-streaming format call
        t_format_start = time.perf_counter()
        answer = llm.generate(
            user_message=user_msg,
            system_prompt=format_prompt,
            temperature=0.3,
        )
        t_format_ms = int((time.perf_counter() - t_format_start) * 1000)
        logger.info(
            f"[timing] format={t_format_ms}ms | "
            f"total_inner={t_dispatch_ms + t_tool_ms + t_format_ms}ms"
        )

        return answer, f"{tool_name} {params}", sources, tool_used

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool JSON: {e} | Raw: {json_resp}")
        return "I encountered an error understanding your request.", "JSON Decode Error", [], "Error"
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return f"I encountered an error processing your query: {str(e)}", "Execution Error", [], "Error"


# ── Main Orchestrator ───────────────────────────────────────────────────────

def process_query(question: str, history: list = None, stream: bool = False) -> Dict:
    """Process a user query end-to-end.

    Phase 7: Instrumented with per-step timings. Accepts stream=True to return a
    streaming generator in result['answer_stream'] for use by the SSE endpoint.
    """
    t_total_start = time.perf_counter()

    # Classification
    t_classify_start = time.perf_counter()
    query_type = classify_query(question, history=history)
    t_classify_ms = int((time.perf_counter() - t_classify_start) * 1000)
    logger.info(f"[timing] classify={t_classify_ms}ms type={query_type} | Q: '{question[:80]}'")

    try:
        if query_type == "erp":
            answer, source_info, sources, tool_used = execute_tool_query(
                question, history=history, stream=stream
            )

        elif query_type == "document":
            sources = []
            try:
                selected_tool = None
                for t in REGISTERED_TOOLS:
                    if t.name == "DocumentTool":
                        selected_tool = t
                        break
                if selected_tool:
                    t_rag_start = time.perf_counter()
                    results = selected_tool.execute({"query": question})
                    t_rag_ms = int((time.perf_counter() - t_rag_start) * 1000)
                    logger.info(f"[timing] rag_tool={t_rag_ms}ms")

                    if results.get("has_relevant_results"):
                        sources = results.get("sources", [])
                        llm = get_llm()
                        t_format_start = time.perf_counter()

                        if stream and hasattr(llm, "generate_stream"):
                            gen = llm.generate_stream(
                                user_message=question,
                                context=f"Retrieved Documents:\n{results['context']}",
                            )
                            t_total_ms = int((time.perf_counter() - t_total_start) * 1000)
                            logger.info(f"[timing] total_to_stream_start={t_total_ms}ms (rag={t_rag_ms}ms)")
                            return {
                                "answer": None,
                                "answer_stream": gen,
                                "query_type": query_type,
                                "response_time_ms": t_total_ms,
                                "source_info": "DocumentTool",
                                "sources": sources,
                                "tool_used": "DocumentTool",
                            }

                        answer = llm.generate(
                            user_message=question,
                            context=f"Retrieved Documents:\n{results['context']}",
                        )
                        t_format_ms = int((time.perf_counter() - t_format_start) * 1000)
                        logger.info(f"[timing] format={t_format_ms}ms")
                        source_info = "DocumentTool"
                        tool_used = "DocumentTool"
                    else:
                        answer = results.get("message", "No relevant documents found.")
                        source_info = "DocumentTool (no match)"
                        tool_used = "DocumentTool (no match)"
                else:
                    answer = "Document tool not found."
                    source_info = "Missing Tool"
                    tool_used = "Missing Tool"
            except Exception as e:
                logger.warning(f"Document tool unavailable: {e}")
                llm = get_llm()
                answer = llm.generate(user_message=question)
                source_info = "Direct LLM"
                tool_used = "Direct LLM"

        else:  # general
            llm = get_llm()
            t_general_start = time.perf_counter()

            if stream and hasattr(llm, "generate_stream"):
                gen = llm.generate_stream(user_message=question)
                t_total_ms = int((time.perf_counter() - t_total_start) * 1000)
                return {
                    "answer": None,
                    "answer_stream": gen,
                    "query_type": query_type,
                    "response_time_ms": t_total_ms,
                    "source_info": "Direct LLM",
                    "sources": [],
                    "tool_used": "Direct LLM",
                }

            answer = llm.generate(user_message=question)
            t_general_ms = int((time.perf_counter() - t_general_start) * 1000)
            logger.info(f"[timing] general_llm={t_general_ms}ms")
            source_info = "Direct LLM"
            tool_used = "Direct LLM"
            sources = []

        elapsed_ms = int((time.perf_counter() - t_total_start) * 1000)
        logger.info(
            f"[timing] total={elapsed_ms}ms classify={t_classify_ms}ms type={query_type}"
        )

        # Structured summary log
        req_id = get_request_id()
        req_field = f"req_id={req_id!r} " if req_id else ""
        logger.info(
            f"[query_complete] {req_field}request_total_ms={elapsed_ms} "
            f"type={query_type} tool={tool_used!r} "
            f"classify_ms={t_classify_ms}"
        )

        # Log the query
        try:
            _log_query(question, query_type, str(answer)[:2000] if answer else "", elapsed_ms, tool_used)
        except Exception as e:
            logger.warning(f"Failed to log query: {e}")

        result = {
            "answer": answer,
            "query_type": query_type,
            "response_time_ms": elapsed_ms,
            "source_info": source_info,
            "sources": sources,
            "tool_used": tool_used,
        }

        # If execute_tool_query returned a streaming generator, surface it
        if callable(answer) or hasattr(answer, "__next__"):
            result["answer_stream"] = answer
            result["answer"] = None

        return result

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t_total_start) * 1000)
        logger.error(f"Query processing failed: {e}")
        return {
            "answer": f"I apologize, but I encountered an error: {str(e)[:200]}",
            "query_type": query_type,
            "response_time_ms": elapsed_ms,
            "source_info": "Error",
            "sources": [],
            "tool_used": "Error",
        }


def _log_query(query_text: str, query_type: str, response_text: str, response_time_ms: int, source: str):
    from db.connection import execute_write
    try:
        execute_write(
            """INSERT INTO query_logs (query_text, query_type, response_text, response_time_ms, source, status, tool_used)
               VALUES (%s, %s, %s, %s, 'text', 'success', %s)""",
            (query_text[:500], query_type, response_text[:2000], response_time_ms, source[:50]),
        )
    except Exception as e:
        logger.warning(f"Could not insert to query_logs (schema change?): {e}")
