"""
AI ERP Assistant — Tool-Based Orchestrator
===========================================
Routes user queries to the appropriate specialized tool using LLM intent extraction.
No LLM-generated SQL is used for ERP queries, only parameterized tool execution.
"""

import logging
import json
import time
from typing import Dict, Tuple

from ai.llm_service import get_llm
from ai.tools import REGISTERED_TOOLS

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


# ── Query Classification ───────────────────────────────────────────────────

def classify_query(query: str, history: list = None) -> str:
    """
    Classify a user query using fast heuristics with LLM fallback into: 'erp', 'document', 'general'.
    Utilizes conversation history to resolve contextual follow-ups.
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

    # Fast deterministic pre-checks
    if any(k in q_lower for k in doc_keywords):
        return "document"
    if any(k in q_lower for k in erp_keywords):
        return "erp"
    if history:
        hist_text = " ".join(str(t.get("content", "")) for t in history[-2:]).lower()
        if any(k in hist_text for k in erp_keywords):
            return "erp"

    # LLM fallback for nuanced / ambiguous intents
    llm = get_llm()
    history_ctx = _format_history_context(history)
    history_section = f"\nRecent Conversation History:\n{history_ctx}\n" if history_ctx else ""

    prompt = f"""You are an Intent Detection and Query Classification engine for an academic ERP system.
Analyze the user's query (taking into account the conversation history if it is a follow-up) and classify it into exactly ONE of the following categories:

- 'erp': If the query asks for database records, student metrics, or follow-ups referencing prior ERP data (e.g., attendance, grades, GPA, schedules, timetables, "which one has lowest", "how many more classes", faculty/student info, courses).
- 'document': If the query asks for information likely found in documents (e.g., manual, syllabus, policy, circular, notice, report, assignment, notes).
- 'general': If it's a general greeting, casual conversation, or entirely unrelated to the academic system.
{history_section}
Reply ONLY with the exact word: erp, document, or general. Do not add any punctuation or explanation."""

    try:
        result = llm.generate(
            user_message=f"Query: {query}",
            system_prompt=prompt,
            temperature=0.0
        )
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

def execute_tool_query(question: str, history: list = None) -> Tuple[str, str, list]:
    """
    Extract intent/entities and dispatch to the correct Tool.
    Uses conversation history to resolve referential entities and context.
    Returns (answer, source_info, sources).
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
    
    # 2. Extract tool intent and parameters via LLM
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
- Map entities properly: if the user asks for "Aarav M", the `usn` might be required but you might not know it. If a name is provided and USN is needed, you might need to use `action: search` to find the USN first, or pass it if you know it.
- If the user refers to a course or student from the conversation history (e.g., "which one has lowest attendance in that course?", "what about CS601?", "how many more classes does he need?"), extract the course_code or usn/name from the history!
- If the user asks how many classes a student needs to attend to reach 75%/85%, use AttendanceTool with action: 'calculate_classes_needed', usn/name, and target_pct.
- If the user asks how many classes a student can miss/bunk safely, use AttendanceTool with action: 'calculate_classes_can_miss', usn/name, and target_pct.
- If it's an attendance query or attendance risk query, use AttendanceTool.
- If it's grades, use GradesTool.
- If it's timetable, use TimetableTool.
- If it's courses, use CourseTool.
- If it's analytics, use AnalyticsTool.
- If it asks about college policies, documents, circulars, or general regulations, use DocumentTool.
"""
    
    try:
        json_resp = llm.generate(
            user_message=question,
            system_prompt=extract_prompt,
            temperature=0.0
        )
        
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
            return "I could not determine the right tool for your query.", "Extraction failed", []
            
        tool_results = selected_tool.execute(params)
        sources = []

        # If DocumentTool was selected, check for fallback / sources
        if selected_tool.name == "DocumentTool":
            if not tool_results.get("has_relevant_results", True):
                return tool_results.get("message", "No relevant documents found."), "DocumentTool (no match)", []
            sources = tool_results.get("sources", [])
        
        # 4. Format results
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
Do NOT reveal internal IDs or backend details."""
        
        user_msg = f"Question: {question}\nData: {json.dumps(tool_results, default=str)}"
        if history_ctx:
            user_msg = f"Prior Conversation:\n{history_ctx}\n\nCurrent Question: {question}\nData: {json.dumps(tool_results, default=str)}"
            
        answer = llm.generate(
            user_message=user_msg,
            system_prompt=format_prompt,
            temperature=0.3
        )
        
        # Determine tool_used identifier for transparency
        if selected_tool.name == "AttendanceTool" and params.get("action") in (
            "calculate_classes_needed", "calculate_classes_can_miss", "classes_needed", "classes_can_miss", "safe_bunks"
        ):
            tool_used = "Reasoning (AttendanceTool)"
        else:
            tool_used = selected_tool.name

        return answer, f"{tool_name} {params}", sources, tool_used
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool JSON: {e} | Raw: {json_resp}")
        return "I encountered an error understanding your request.", "JSON Decode Error", [], "Error"
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return f"I encountered an error processing your query: {str(e)}", "Execution Error", [], "Error"


# ── Main Orchestrator ───────────────────────────────────────────────────────

def process_query(question: str, history: list = None) -> Dict:
    start = time.time()
    query_type = classify_query(question, history=history)
    logger.info(f"Query classified as: {query_type} | Q: '{question[:80]}'")

    try:
        if query_type == "erp":
            answer, source_info, sources, tool_used = execute_tool_query(question, history=history)

        elif query_type == "document":
            sources = []
            try:
                # Direct route to DocumentTool
                selected_tool = None
                for t in REGISTERED_TOOLS:
                    if t.name == "DocumentTool":
                        selected_tool = t
                        break
                if selected_tool:
                    results = selected_tool.execute({"query": question})

                    if results.get("has_relevant_results"):
                        # Good match — pass context to LLM for a grounded answer
                        sources = results.get("sources", [])
                        llm = get_llm()
                        answer = llm.generate(
                            user_message=question,
                            context=f"Retrieved Documents:\n{results['context']}",
                        )
                        source_info = "DocumentTool"
                        tool_used = "DocumentTool"
                    else:
                        # No relevant document found — return explicit fallback
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
            answer = llm.generate(user_message=question)
            source_info = "Direct LLM"
            tool_used = "Direct LLM"
            sources = []

        elapsed_ms = int((time.time() - start) * 1000)

        # Log the query
        try:
            _log_query(question, query_type, answer, elapsed_ms, tool_used)
        except Exception as e:
            logger.warning(f"Failed to log query: {e}")

        return {
            "answer": answer,
            "query_type": query_type,
            "response_time_ms": elapsed_ms,
            "source_info": source_info,
            "sources": sources,
            "tool_used": tool_used,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
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
