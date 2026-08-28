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
    return "\n".join(rows) + (f"\n\n{summary}" if summary else "")


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


# ── Phase 10: Plain-text templated fallbacks (no LLM) ───────────────────────

def _plain_generic_render(tool_results: dict, question: str, tool_name: str = "") -> str:
    """
    Universal plain-text renderer for any tool result.
    Called when the LLM formatting call times out or fails.
    Produces correct Markdown output from raw JSON — no LLM involved.
    A correct plain-text answer beats a fluent error message live in front of a panel.
    """
    # --- Check for error in tool result ---
    if "error" in tool_results:
        return f"**Error from {tool_name}:** {tool_results['error']}"
    if "message" in tool_results and not any(
        k in tool_results for k in (
            "attendance_records", "at_risk_students", "results", "calculation",
            "departments", "performance", "overall_stats", "grades", "profile",
            "schedule", "statistics", "faculty", "course", "top_performers",
            "failing_students", "workload",
        )
    ):
        return f"**{tool_results['message']}**"

    # --- Dispatch to specific renderers based on result keys ---

    # Attendance: course_summary (statistics block)
    if "statistics" in tool_results and "course_code" in tool_results:
        stats = tool_results["statistics"]
        course = tool_results.get("course_code", "")
        return (
            f"**Attendance Summary for {course}**\n\n"
            f"- Average Attendance: **{stats.get('avg_attendance_pct', 'N/A')}%**\n"
            f"- Enrolled Students: **{stats.get('enrolled_students', 'N/A')}**"
        )

    # Attendance: student_summary or risk_list records
    records = (
        tool_results.get("attendance_records")
        or tool_results.get("at_risk_students")
        or tool_results.get("results")
        or (tool_results.get("calculation") if isinstance(tool_results.get("calculation"), list) else None)
    )
    if records and isinstance(records, list) and records:
        return _plain_attendance_table(tool_results, question)

    # Analytics: departments list
    if "departments" in tool_results:
        depts = tool_results["departments"]
        total = tool_results.get("total_departments", len(depts))
        if not depts:
            return "**No department records found.**"
        headers = ["Dept Code", "Department", "Students", "Faculty", "Courses", "Avg Attendance", "Avg Marks"]
        sep = "|".join("---" for _ in headers)
        rows = ["| " + " | ".join(headers) + " |", "| " + sep + " |"]
        for d in depts:
            row = [
                str(d.get("department_code", "")),
                str(d.get("department_name", "")),
                str(d.get("total_students", "")),
                str(d.get("total_faculty", "")),
                str(d.get("total_courses", "")),
                f"{float(d.get('avg_attendance_pct', 0)):.1f}%" if d.get("avg_attendance_pct") is not None else "",
                f"{float(d.get('avg_marks', 0)):.1f}" if d.get("avg_marks") is not None else "",
            ]
            rows.append("| " + " | ".join(row) + " |")
        return f"**Departments ({total} total)**\n\n" + "\n".join(rows)

    # Analytics: overall_stats
    if "overall_stats" in tool_results:
        s = tool_results["overall_stats"]
        return (
            f"**Institution Overview**\n\n"
            f"- Total Students: **{s.get('total_students', 'N/A')}**\n"
            f"- Total Faculty: **{s.get('total_faculty', 'N/A')}**\n"
            f"- Total Courses: **{s.get('total_courses', 'N/A')}**\n"
            f"- Total Departments: **{s.get('total_departments', 'N/A')}**"
        )

    # Analytics: department_performance (old key)
    if "performance" in tool_results:
        perf = tool_results["performance"]
        if not perf:
            return "**No department performance data found.**"
        # Re-wrap and recurse
        return _plain_generic_render(
            {"departments": perf, "total_departments": len(perf)}, question, tool_name
        )

    # Faculty: by_course or search
    if "faculty" in tool_results:
        faculty_list = tool_results["faculty"]
        course_code = tool_results.get("course_code", "")
        if not faculty_list:
            return f"**No faculty found for {course_code}.**"
        lines = [f"**Faculty for {course_code}:**\n"]
        for f in faculty_list:
            lines.append(
                f"- **{f.get('faculty_name', 'N/A')}** — {f.get('designation', '')} ({f.get('department_name', '')})"
            )
        return "\n".join(lines)

    # Grades: student_grades
    if "grades" in tool_results:
        grades = tool_results["grades"]
        usn = tool_results.get("usn", "Student")
        if not grades:
            return f"**No grade records found for {usn}.**"
        headers = ["Course", "Name", "IA1", "IA2", "IA3", "Final", "Grade"]
        sep = "|".join("---" for _ in headers)
        rows = ["| " + " | ".join(headers) + " |", "| " + sep + " |"]
        for g in grades:
            rows.append("| " + " | ".join([
                str(g.get("course_code", "")),
                str(g.get("course_name", "")),
                str(g.get("ia1_marks", "")),
                str(g.get("ia2_marks", "")),
                str(g.get("ia3_marks", "")),
                str(g.get("final_exam_marks", "")),
                str(g.get("final_grade", "")),
            ]) + " |")
        return f"**Grades for {usn}**\n\n" + "\n".join(rows)

    # Schedule / timetable
    if "schedule" in tool_results:
        schedule = tool_results["schedule"]
        if not schedule:
            return "**No schedule records found.**"
        headers = list(schedule[0].keys()) if schedule else []
        display = [h for h in [
            "day_of_week", "start_time", "end_time", "course_code", "course_name",
            "faculty_name", "room",
        ] if h in headers] or headers[:6]
        sep = "|".join("---" for _ in display)
        col_labels = {
            "day_of_week": "Day", "start_time": "Start", "end_time": "End",
            "course_code": "Course", "course_name": "Course Name",
            "faculty_name": "Faculty", "room": "Room",
        }
        rows = [
            "| " + " | ".join(col_labels.get(h, h.title()) for h in display) + " |",
            "| " + sep + " |",
        ]
        for s in schedule:
            rows.append("| " + " | ".join(str(s.get(h, "")) for h in display) + " |")
        return "**Schedule**\n\n" + "\n".join(rows)

    # Student profile
    if "profile" in tool_results:
        p = tool_results["profile"]
        if not p:
            return "**No student profile found.**"
        return (
            f"**Student Profile**\n\n"
            f"- USN: **{p.get('usn', 'N/A')}**\n"
            f"- Name: **{p.get('student_name', 'N/A')}**\n"
            f"- Department: {p.get('department_name', 'N/A')} ({p.get('department_code', 'N/A')})\n"
            f"- Semester: {p.get('semester', 'N/A')}, Section: {p.get('section', 'N/A')}\n"
            f"- CGPA: {p.get('cgpa', 'N/A')}"
        )

    # Generic: try to render any list-of-dicts as a table
    for key in ("results", "top_performers", "failing_students"):
        rows_data = tool_results.get(key)
        if rows_data and isinstance(rows_data, list) and rows_data:
            headers = list(rows_data[0].keys())[:8]
            sep = "|".join("---" for _ in headers)
            header_line = "| " + " | ".join(h.replace("_", " ").title() for h in headers) + " |"
            tbl = [header_line, "| " + sep + " |"]
            for row in rows_data:
                tbl.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
            return f"**Results**\n\n" + "\n".join(tbl)

    # Last resort: dump JSON as code block
    logger.warning(f"[plain_render] No template matched for tool={tool_name}; dumping raw JSON")
    return (
        f"**Raw data from {tool_name}** (plain-text fallback):\n\n"
        f"```json\n{json.dumps(tool_results, default=str, indent=2)[:2000]}\n```"
    )


def _keyword_fallback_route(question: str) -> tuple:
    """
    Keyword-based tool routing fallback for when LLM extraction times out or produces
    invalid JSON. Covers the most common demo queries.

    Returns (tool_name, params) or (None, None) if no match.
    Phase 10: Safety net so the demo never shows a generic error for common queries.
    """
    q = question.lower()
    import re

    # Attendance keywords
    if any(k in q for k in ("attendance", "attended", "present", "absent", "at risk", "at-risk", "bunk")):
        # Extract course code if present
        course_match = re.search(r'\b([A-Z]{2,3}\d{3})\b', question.upper())
        course_code = course_match.group(1) if course_match else None
        if any(k in q for k in ("risk", "risky", "below", "low")):
            return "AttendanceTool", {"action": "risk_list", "course_code": course_code}
        elif course_code:
            return "AttendanceTool", {"action": "course_summary", "course_code": course_code}
        else:
            return "AttendanceTool", {"action": "risk_list"}

    # Department / analytics keywords
    if any(k in q for k in ("department", "departments", "how many dept")):
        return "AnalyticsTool", {"action": "department_performance"}
    if any(k in q for k in ("overall stats", "total students", "total faculty", "how many students",
                             "how many faculty", "institution")):
        return "AnalyticsTool", {"action": "overall_stats"}

    # Timetable/schedule keywords
    if any(k in q for k in ("timetable", "schedule", "when does", "which room", "classes on")):
        course_match = re.search(r'\b([A-Z]{2,3}\d{3})\b', question.upper())
        course_code = course_match.group(1) if course_match else None
        day_match = re.search(
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', q
        )
        day = day_match.group(1).capitalize() if day_match else None
        if course_code:
            return "TimetableTool", {"action": "course_schedule", "course_code": course_code}
        if day:
            return "TimetableTool", {"action": "day_schedule", "day": day}

    # Grades keywords
    if any(k in q for k in ("grade", "grades", "marks", "gpa", "cgpa", "top performers", "failing")):
        course_match = re.search(r'\b([A-Z]{2,3}\d{3})\b', question.upper())
        course_code = course_match.group(1) if course_match else None
        if "top" in q and course_code:
            return "GradesTool", {"action": "top_performers", "course_code": course_code}
        if "fail" in q and course_code:
            return "GradesTool", {"action": "failing_students", "course_code": course_code}
        if course_code:
            return "GradesTool", {"action": "course_grades", "course_code": course_code}

    return None, None



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

    # 1. Build compact tool definitions (Phase 10: compact schema cuts extraction prompt from 4.8k chars to 1.5k chars)
    tools_str = """- AttendanceTool: student_summary(usn/name), course_summary(course_code), risk_list(course_code?), calculate_classes_needed(usn/name, target_pct), calculate_classes_can_miss(usn/name, target_pct)
- AnalyticsTool: department_performance(department?), overall_stats()
- TimetableTool: course_schedule(course_code), day_schedule(day), faculty_schedule(employee_code)
- FacultyTool: by_course(course_code), search(name/department), profile(employee_code), workload(employee_code)
- GradesTool: student_grades(usn), course_grades(course_code), top_performers(course_code), failing_students(course_code)
- StudentTool: profile(usn), search(name/department/semester)
- CourseTool: search(department?), details(course_code), statistics(course_code)
- DocumentTool: college policies, syllabus, regulations"""

    # 2. Extract tool intent and parameters via FAST model
    extract_prompt = f"""You are an ERP router. Output ONLY valid JSON: {{"tool_name": "ToolName", "params": {{"action": "action_name", "key": "val"}}}}

TOOLS:
{tools_str}
{history_section}
ROUTING RULES:
- "attendance", "attended", "absent", "risk", "bunk" -> AttendanceTool. (e.g. "attendance for CS601" -> {{"tool_name":"AttendanceTool","params":{{"action":"course_summary","course_code":"CS601"}}}})
- "schedule", "timetable", "classes on [day]" -> TimetableTool. (e.g. "timetable for CS601" -> {{"tool_name":"TimetableTool","params":{{"action":"course_schedule","course_code":"CS601"}}}})
- "departments", "department list", "how many departments", "list them" -> {{"tool_name":"AnalyticsTool","params":{{"action":"department_performance"}}}}
- "overall stats", "institution count", "total students" -> {{"tool_name":"AnalyticsTool","params":{{"action":"overall_stats"}}}}
- "who teaches [course]" -> FacultyTool(action='by_course', course_code='...')
- NEVER route attendance queries to TimetableTool."""

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

        # Determine tool_used identifier for transparency
        if selected_tool.name == "AttendanceTool" and params.get("action") in (
            "calculate_classes_needed", "calculate_classes_can_miss", "classes_needed", "classes_can_miss", "safe_bunks"
        ):
            tool_used = "Reasoning (AttendanceTool)"
        else:
            tool_used = selected_tool.name

        # Step 4 & 5 (Phase 10): Default to deterministic renderer for standard ERP tool results
        # A fast, grounded table rendered in 10ms directly from SQL is 100% accurate,
        # perfectly formatted, never hallucinates, and avoids 15-30s formatting latency.
        # Reserve LLM formatting for complex reasoning / conversational context.
        use_direct_render = (
            selected_tool.name in (
                "AttendanceTool", "AnalyticsTool", "TimetableTool",
                "CourseTool", "GradesTool", "FacultyTool", "StudentTool"
            )
            and not (selected_tool.name == "AttendanceTool" and params.get("action") in (
                "calculate_classes_needed", "calculate_classes_can_miss", "classes_needed", "classes_can_miss", "safe_bunks"
            ) and history_ctx)  # Keep LLM for multi-turn reasoning conversations
        )

        if use_direct_render:
            direct_answer = _plain_generic_render(tool_results, question, selected_tool.name)
            logger.info(f"[timing] direct_plain_render applied for tool={tool_name} action={params.get('action')}")
            
            if stream:
                def _stream_direct():
                    # Stream tokens cleanly for SSE endpoint
                    words = direct_answer.split(" ")
                    for i, w in enumerate(words):
                        yield w + (" " if i < len(words) - 1 else "")
                return _stream_direct(), f"{tool_name} {params}", sources, tool_used
            
            return direct_answer, f"{tool_name} {params}", sources, tool_used

        # 4. Format results — uses FULL-QUALITY model for user-visible answer
        # Phase 10: Clean formatting prompt with zero "JSON data" framing leakage.
        format_prompt = """You are an AI ERP Assistant for B.M.S. College of Engineering (BMSCE).
Present the academic information clearly and professionally.
Use clean Markdown tables for lists.
If reporting attendance calculations, explicitly state:
- The student's current attendance percentage and attended/total class numbers.
- The minimum threshold (e.g. 75.0% or 85.0%).
- The shortage gap in percentage points.
- The number of consecutive classes needed to reach eligibility (or safe classes that can be missed).
Do NOT mention "JSON", "the data provided below", database schemas, internal IDs, or backend processes.
Present the information naturally as a helpful administrative assistant.

==== GROUNDING RULE ====
Use ONLY the student records, IDs, names, and numbers present in the data below.
Do NOT invent or modify any names, USNs, percentages, or counts.
Your response ends after presenting the answer. Do NOT generate follow-up questions or example conversations."""

        user_msg = f"User Question: {question}\nInformation:\n{json.dumps(tool_results, default=str)}"
        if history_ctx:
            user_msg = f"Prior Conversation:\n{history_ctx}\n\nCurrent Question: {question}\nInformation:\n{json.dumps(tool_results, default=str)}"

        # Determine tool_used identifier for transparency
        if selected_tool.name == "AttendanceTool" and params.get("action") in (
            "calculate_classes_needed", "calculate_classes_can_miss", "classes_needed", "classes_can_miss", "safe_bunks"
        ):
            tool_used = "Reasoning (AttendanceTool)"
        else:
            tool_used = selected_tool.name

        if stream and hasattr(llm, "generate_stream"):
            t_format_start = time.perf_counter()
            gen = llm.generate_stream(
                user_message=user_msg,
                system_prompt=format_prompt,
                temperature=0.1,
            )
            logger.info(f"[timing] format_stream_started (dispatch={t_dispatch_ms}ms, tool={t_tool_ms}ms)")
            return gen, f"{tool_name} {params}", sources, tool_used

        # Non-streaming format call
        t_format_start = time.perf_counter()
        try:
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

            # Grounding check
            ok, phantoms = _grounding_check(answer, tool_results)
            if not ok:
                logger.warning(
                    f"[grounding] Falling back to plain-template render. "
                    f"Phantom USNs: {phantoms}"
                )
                answer = _plain_attendance_table(tool_results, question)

        except Exception as fmt_err:
            t_format_ms = int((time.perf_counter() - t_format_start) * 1000)
            logger.warning(
                f"[fallback] Format LLM call failed after {t_format_ms}ms: {fmt_err}. "
                f"Falling back to plain-text render for tool={tool_name}."
            )
            answer = _plain_generic_render(tool_results, question, tool_name)

        return answer, f"{tool_name} {params}", sources, tool_used

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool JSON: {e} | Raw: {json_resp[:200]!r}")
        # Phase 10: attempt keyword-based fallback routing before giving up.
        logger.info("[fallback] Attempting keyword-based tool routing after JSON decode error")
        fb_tool_name, fb_params = _keyword_fallback_route(question)
        if fb_tool_name:
            fb_tool = next((t for t in REGISTERED_TOOLS if t.name == fb_tool_name), None)
            if fb_tool:
                try:
                    fb_results = fb_tool.execute(fb_params)
                    fb_answer = _plain_generic_render(fb_results, question, fb_tool_name)
                    logger.info(f"[fallback] Keyword-route succeeded: tool={fb_tool_name} params={fb_params}")
                    return fb_answer, f"fallback:{fb_tool_name}", [], fb_tool_name
                except Exception as fb_err:
                    logger.error(f"[fallback] Keyword-route execution also failed: {fb_err}")
        return (
            "I had trouble understanding that request. Please try rephrasing it.",
            "JSON Decode Error", [], "Error"
        )
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        # Phase 10: if we have a tool result in progress, try to render it plain.
        # Otherwise fall back to keyword routing.
        fb_tool_name, fb_params = _keyword_fallback_route(question)
        if fb_tool_name:
            fb_tool = next((t for t in REGISTERED_TOOLS if t.name == fb_tool_name), None)
            if fb_tool:
                try:
                    fb_results = fb_tool.execute(fb_params)
                    fb_answer = _plain_generic_render(fb_results, question, fb_tool_name)
                    logger.info(f"[fallback] Exception-route succeeded: tool={fb_tool_name}")
                    return fb_answer, f"fallback:{fb_tool_name}", [], fb_tool_name
                except Exception as fb_err:
                    logger.error(f"[fallback] Exception-route execution also failed: {fb_err}")
        return (
            f"I encountered an error processing your query. Please try again.",
            "Execution Error", [], "Error"
        )


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
