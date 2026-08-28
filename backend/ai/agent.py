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

Phase 9 changes (critical regression fixes):
  - OLLAMA_NUM_CTX raised to 8192 in env (was 2048; 40-student payload hit 98% of old limit).
  - Format call temperature lowered to 0.1 (was 0.3) — deterministic for structured data.
  - num_predict=1024 cap added to prevent runaway fabricated follow-up generation.
  - format_prompt gains GROUNDING RULE: model forbidden from inventing student data.
  - _grounding_check() post-validates LLM output against actual tool result USNs;
    any phantom USN triggers a plain-template fallback (_plain_attendance_table).
  - extract_prompt gains explicit FacultyTool routing rule for 'who teaches' queries.
  - erp_keywords list gains teach/instructor/lecturer for fast-path classification.
"""

import logging
import json
import re
import time
from typing import Dict, Generator, List, Tuple, Union

from ai.llm_service import get_llm
from ai.tools import REGISTERED_TOOLS
try:
    from middleware.request_id import get_request_id
except ImportError:
    def get_request_id():
        return ""

logger = logging.getLogger("erp-assistant")


# ── Grounding safety-net (Phase 9) ─────────────────────────────────────────

def _extract_usns_from_text(text: str) -> List[str]:
    """
    Extract all USN-like tokens from a text string.
    Matches patterns like CS2022001, 1BM22CS001, etc.
    Conservative: only flags tokens that look like real academic USNs.
    """
    # Common patterns: <letters><4-digit year><letters/digits>
    # e.g. CS2022001, 1BM22CS001, BMS22CS001
    pattern = r'\b(?:[A-Z0-9]{2,4}\d{2}[A-Z]{2}\d{3}|[A-Z]{2}\d{7})\b'
    return re.findall(pattern, text.upper())


def _extract_usns_from_tool_result(tool_results: dict) -> List[str]:
    """Extract the set of real USNs present in the actual tool result JSON."""
    usns = set()
    # attendance_records, at_risk_students, results are common keys
    for key in ("attendance_records", "at_risk_students", "results", "calculation"):
        rows = tool_results.get(key, [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    usn = str(row.get("usn", "")).upper().strip()
                    if usn:
                        usns.add(usn)
    return list(usns)


def _plain_attendance_table(tool_results: dict, question: str) -> str:
    """
    Plain Python-generated Markdown table of attendance data.
    Used as fallback when LLM output contains hallucinated USNs.
    Never touches the LLM — renders purely from the raw tool JSON.
    """
    records = (
        tool_results.get("attendance_records")
        or tool_results.get("results")
        or tool_results.get("at_risk_students")
        or []
    )
    if not records:
        msg = tool_results.get("message", "No records found.")
        return f"**{msg}**"

    # Build header from first record keys
    headers = list(records[0].keys())
    # Filter to the most useful columns for display
    display_cols = [h for h in [
        "usn", "student_name", "course_code", "course_name",
        "classes_attended", "total_classes", "attendance_pct",
        "risk_level", "classes_needed_to_reach_75",
    ] if h in headers]
    if not display_cols:
        display_cols = headers[:7]  # fallback: first 7 cols

    col_labels = {
        "usn": "USN", "student_name": "Student", "course_code": "Course",
        "course_name": "Course Name", "classes_attended": "Attended",
        "total_classes": "Total", "attendance_pct": "Attendance %",
        "risk_level": "Risk", "classes_needed_to_reach_75": "Classes Needed (75%)",
    }
    header_row = " | ".join(col_labels.get(c, c.replace("_", " ").title()) for c in display_cols)
    sep_row = " | ".join("---" for _ in display_cols)
    rows = [f"| {header_row} |", f"| {sep_row} |"]
    for rec in records:
        vals = []
        for c in display_cols:
            v = rec.get(c, "")
            if c == "attendance_pct" and isinstance(v, (int, float)):
                v = f"{float(v):.2f}%"
            vals.append(str(v) if v is not None else "")
        rows.append("| " + " | ".join(vals) + " |")

    summary = tool_results.get("summary", "")
    note = (
        "\n\n> \u26a0\ufe0f *Data rendered directly from database records — "
        "plain-table fallback was used to ensure accuracy.*"
    )
    return "\n".join(rows) + (f"\n\n{summary}" if summary else "") + note


def _grounding_check(llm_answer: str, tool_results: dict) -> Tuple[bool, List[str]]:
    """
    Verify that every USN mentioned in the LLM-formatted answer is actually
    present in the tool result data.

    Returns:
        (ok: bool, phantom_usns: list)
        ok=True if all USNs in the answer are real (or there are no USNs to check).
        ok=False + phantom_usns lists any invented USN tokens.
    """
    answer_usns = set(_extract_usns_from_text(llm_answer))
    if not answer_usns:
        return True, []  # No USNs in answer — nothing to verify

    real_usns = set(u.upper() for u in _extract_usns_from_tool_result(tool_results))
    if not real_usns:
        return True, []  # Tool result has no USN structure (e.g. aggregates) — skip

    phantom = list(answer_usns - real_usns)
    if phantom:
        logger.warning(
            f"[grounding] HALLUCINATION DETECTED — phantom USNs in LLM answer: {phantom} "
            f"(real USNs: {sorted(real_usns)})"
        )
        return False, phantom
    return True, []


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
        "lowest", "highest", "which one", "who has", "how many", "usn",
        # Phase 9: added explicit faculty/teacher routing keywords so 'who teaches'
        # is caught by fast-path and never falls through to LLM fallback.
        "teaches", "who teach", "instructor", "lecturer", "professor", "who is the teacher",
        "who is teaching",
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
    # Phase 10: extract_prompt rebuilt with explicit AttendanceTool vs TimetableTool
    # disambiguation rules, few-shot examples, and AnalyticsTool valid-actions-only constraint.
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
- If it's grades, use GradesTool with the documented actions: 'student_grades', 'course_grades', 'top_performers', 'failing_students'.
- If it's courses (listing, info), use CourseTool with documented actions: 'search', 'details', 'statistics'.
- If it asks about college policies, documents, circulars, or general regulations, use DocumentTool.

ATTENDANCE vs TIMETABLE DISAMBIGUATION (Phase 10 — critical fix):
- Words "attendance", "attended", "present", "absent", "risk", "at-risk", "bunk", "miss classes" = AttendanceTool.
  * "Show me attendance for CS601" -> AttendanceTool, action='course_summary', course_code='CS601'
  * "Which students are at attendance risk in CS601?" -> AttendanceTool, action='risk_list', course_code='CS601'
  * "How many classes has Aarav attended?" -> AttendanceTool, action='student_summary', name='Aarav'
- Words "schedule", "timetable", "when does class meet", "what time", "which room", "classes on Monday" = TimetableTool.
  * "What is the timetable for CS601?" -> TimetableTool, action='course_schedule', course_code='CS601'
  * "Show me the schedule for Monday" -> TimetableTool, action='day_schedule', day='Monday'
- NEVER route attendance queries to TimetableTool. NEVER route timetable/schedule queries to AttendanceTool.

ANALYTICS TOOL — VALID ACTIONS ONLY (Phase 10 — critical fix):
- AnalyticsTool only implements TWO actions: 'department_performance' and 'overall_stats'.
- "How many departments are there?" / "List all departments" -> AnalyticsTool, action='department_performance'
  (department_performance returns all departments with their stats including count)
- "Overall stats / counts of students, faculty, courses" -> AnalyticsTool, action='overall_stats'
- NEVER use action='department_list' or any other action not in this list — it does not exist and will error.

FACULTY ROUTING (Phase 9 fix):
- If the user asks WHO TEACHES a course, WHO IS THE INSTRUCTOR/LECTURER/PROFESSOR for a course,
  or asks about a faculty member by name, use FacultyTool with action='by_course' (with course_code)
  or action='search' (with name). Never route 'who teaches X' to TimetableTool.

FEW-SHOT EXAMPLES (follow these exactly for similar queries):
Q: "Show me attendance for CS601"
A: {{"tool_name": "AttendanceTool", "params": {{"action": "course_summary", "course_code": "CS601"}}}}

Q: "Which students are at risk in CS601?"
A: {{"tool_name": "AttendanceTool", "params": {{"action": "risk_list", "course_code": "CS601"}}}}

Q: "What is the timetable for CS601?"
A: {{"tool_name": "TimetableTool", "params": {{"action": "course_schedule", "course_code": "CS601"}}}}

Q: "How many departments are there? List them"
A: {{"tool_name": "AnalyticsTool", "params": {{"action": "department_performance"}}}}

Q: "Give me overall stats"
A: {{"tool_name": "AnalyticsTool", "params": {{"action": "overall_stats"}}}}

Q: "Who teaches CS601?"
A: {{"tool_name": "FacultyTool", "params": {{"action": "by_course", "course_code": "CS601"}}}}
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
        # Phase 9: grounding instruction forbids inventing student data not in the payload.
        # temperature=0.1 (near-deterministic) — formatting structured data needs no creativity.
        # num_predict=1024 cap prevents runaway generation of fabricated follow-up turns.
        format_prompt = """You are an AI ERP Assistant for a college.
Format the provided JSON data into a clean, professional response.
Use Markdown tables for lists.
If the data contains at-risk students or attendance calculations, explicitly state:
- The student's current attendance percentage and attended/total class numbers.
- The threshold being compared against (e.g. 75.0% or 85.0%).
- The exact shortage gap in percentage points.
- The number of consecutive classes needed to reach eligibility (or safe classes that can be missed).
If the user asked a specific follow-up question (e.g. 'which one has the lowest attendance?'), directly answer that question highlighting the specific record.
If the data contains an error or "Not found", explain it politely to the user.
Do NOT reveal internal IDs or backend details.

==== GROUNDING RULE (MANDATORY — Phase 9 anti-hallucination) ====
You MUST use ONLY the student records, IDs, names, and numbers present in the JSON data provided below.
Do NOT invent, add, rename, or modify any student, USN, name, percentage, or count that is NOT
explicitly present in the data. If the data does not contain what the user asked about, say so
honestly instead of filling the gap with made-up information.
Your response ends after presenting the data. Do NOT generate any follow-up questions, additional
scenarios, example conversations, or additional turns after the real answer."""

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
            # Phase 9: temperature=0.1 (near-deterministic for data formatting),
            #          num_predict=1024 cap prevents fabricated follow-up turns.
            t_format_start = time.perf_counter()
            gen = llm.generate_stream(
                user_message=user_msg,
                system_prompt=format_prompt,
                temperature=0.1,
            )
            logger.info(f"[timing] format_stream_started (dispatch={t_dispatch_ms}ms, tool={t_tool_ms}ms)")
            return gen, f"{tool_name} {params}", sources, tool_used

        # Non-streaming format call
        # Phase 9: temperature=0.1 (near-deterministic) and num_predict=1024 cap.
        t_format_start = time.perf_counter()
        answer = llm.generate(
            user_message=user_msg,
            system_prompt=format_prompt,
            temperature=0.1,
        )
        t_format_ms = int((time.perf_counter() - t_format_start) * 1000)
        logger.info(
            f"[timing] format={t_format_ms}ms | "
            f"total_inner={t_dispatch_ms + t_tool_ms + t_format_ms}ms"
        )

        # Phase 9 grounding safety-net: verify no phantom USNs were hallucinated.
        ok, phantoms = _grounding_check(answer, tool_results)
        if not ok:
            logger.warning(
                f"[grounding] Falling back to plain-template render. "
                f"Phantom USNs: {phantoms}"
            )
            answer = _plain_attendance_table(tool_results, question)

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
