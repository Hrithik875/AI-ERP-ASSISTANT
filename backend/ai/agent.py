"""
AI ERP Assistant — LangChain Agent / Query Orchestrator
=========================================================
Routes user queries to the appropriate tool:
  - ERP/DB queries → SQL execution (Aurora MySQL)
  - Document queries → RAG vector search (Qdrant + Titan Embeddings)
  - General questions → Direct LLM (Bedrock Claude 3 Sonnet)
"""

import logging
import re
import time
from typing import Dict, Tuple

from db.connection import execute_query
from db.models import get_table_info
from ai.llm_service import get_llm

logger = logging.getLogger("erp-assistant")

# ── Query Classification ───────────────────────────────────────────────────

ERP_KEYWORDS = {
    "attendance": "attendance",
    "absent": "attendance",
    "present": "attendance",
    "shortage": "attendance",
    "bunked": "attendance",
    "grade": "grades",
    "grades": "grades",
    "marks": "grades",
    "score": "grades",
    "gpa": "grades",
    "cgpa": "grades",
    "result": "grades",
    "exam": "schedule",
    "schedule": "schedule",
    "timetable": "schedule",
    "class": "schedule",
    "faculty": "faculty",
    "professor": "faculty",
    "teacher": "faculty",
    "instructor": "faculty",
    "student": "general",
    "students": "general",
    "course": "general",
    "courses": "general",
    "department": "general",
    "semester": "general",
    "fee": "general",
    "library": "general",
}

DOCUMENT_KEYWORDS = [
    "document", "file", "upload", "pdf", "report",
    "syllabus", "circular", "notice", "manual",
    "lab manual", "assignment", "notes",
]


def classify_query(query: str) -> str:
    """
    Classify a user query into one of: 'erp', 'document', 'general'.
    """
    q = query.lower()

    # Check document keywords first
    for kw in DOCUMENT_KEYWORDS:
        if kw in q:
            return "document"

    # Check ERP keywords
    for kw in ERP_KEYWORDS:
        if kw in q:
            return "erp"

    return "general"


# ── SQL Generation (MySQL) ─────────────────────────────────────────────────

SQL_GENERATION_PROMPT = """You are a MySQL SQL expert for an Education ERP system running on Amazon Aurora MySQL.
Given the database schema below, generate a SINGLE, safe, read-only SQL query that answers the user's question.

RULES:
1. ONLY generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
2. Always use explicit column names (no SELECT *).
3. Use proper JOINs when combining tables.
4. Limit results to 50 rows max.
5. Return ONLY the SQL query, nothing else. No markdown, no explanation.
6. If the query asks about a specific student, try to match by name or student_id.
7. For attendance percentage, calculate: (SUM(CASE WHEN status IN ('present','late') THEN 1 ELSE 0 END) / COUNT(*)) * 100.
8. For GPA, use the grade_points column.
9. Use MySQL-compatible syntax ONLY (no PostgreSQL-specific features).
10. Use DATE_FORMAT() for date formatting, not TO_CHAR().
11. Use IFNULL() instead of COALESCE where appropriate.
12. Use CAST() or implicit conversion instead of :: for type casting.

DATABASE SCHEMA:
{schema}
"""


def generate_sql(question: str, schema_info: str) -> str:
    """Use LLM to generate a safe SQL query from natural language."""
    llm = get_llm()
    prompt = SQL_GENERATION_PROMPT.format(schema=schema_info)
    sql = llm.generate(
        user_message=question,
        system_prompt=prompt,
        temperature=0.1,
    )
    # Clean up: strip markdown fences
    sql = sql.strip()
    sql = re.sub(r'^```(?:sql)?\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)
    sql = sql.strip()

    # Safety check
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    sql_upper = sql.upper()
    for d in dangerous:
        if d in sql_upper and d != "CREATE":  # Allow CREATE in schema context check
            raise ValueError(f"Unsafe SQL detected: contains {d}")

    if not sql_upper.startswith("SELECT"):
        raise ValueError(f"AI failed to generate a valid SELECT query. Response: {sql[:100]}")

    return sql


def execute_erp_query(question: str) -> Tuple[str, str]:
    """
    Full ERP query pipeline:
      1. Get schema info
      2. Generate SQL from question
      3. Execute SQL
      4. Format results with LLM
    Returns (answer, sql_used).
    """
    try:
        schema_info = get_table_info()
        sql = generate_sql(question, schema_info)
        logger.info(f"Generated SQL: {sql}")

        rows = execute_query(sql)

        if not rows:
            return "No matching records found for your query.", sql

        # Format results with LLM
        llm = get_llm()
        context = f"SQL Query: {sql}\n\nResults ({len(rows)} rows):\n"
        for i, row in enumerate(rows[:20]):  # Limit context to 20 rows
            context += f"  Row {i+1}: {dict(row)}\n"

        answer = llm.generate(
            user_message=question,
            context=context,
            temperature=0.3,
        )

        return answer, sql

    except Exception as e:
        logger.error(f"ERP query failed: {e}")
        return f"I encountered an error processing your query: {str(e)}", ""


# ── Main Orchestrator ───────────────────────────────────────────────────────

def process_query(question: str) -> Dict:
    """
    Main query orchestrator. Routes to appropriate tool:
      - ERP → SQL query (Aurora MySQL)
      - Document → RAG search (Qdrant + Titan Embeddings)
      - General → Direct LLM (Bedrock Claude 3 Sonnet)
    Returns {answer, query_type, response_time_ms, source_info}.
    """
    start = time.time()
    query_type = classify_query(question)
    logger.info(f"Query classified as: {query_type} | Q: '{question[:80]}'")

    try:
        if query_type == "erp":
            answer, sql = execute_erp_query(question)
            source_info = f"SQL: {sql}" if sql else "No SQL generated"

        elif query_type == "document":
            try:
                from ai.rag_pipeline import get_rag
                rag = get_rag()
                context = rag.get_context(question)
                if context:
                    llm = get_llm()
                    answer = llm.generate(
                        user_message=question,
                        context=f"Retrieved Documents:\n{context}",
                    )
                    source_info = "RAG vector search"
                else:
                    answer = "I couldn't find any relevant documents. Please upload documents first or rephrase your query."
                    source_info = "RAG (no results)"
            except Exception as e:
                logger.warning(f"RAG unavailable, falling back to LLM: {e}")
                llm = get_llm()
                answer = llm.generate(user_message=question)
                source_info = "Direct LLM (RAG unavailable)"

        else:  # general
            llm = get_llm()
            # Even for general queries, try to add ERP context
            try:
                schema_info = get_table_info()
                answer = llm.generate(
                    user_message=question,
                    context=f"You have access to an ERP database with the following schema (use this context if the question relates to academic data):\n{schema_info}",
                )
            except Exception:
                answer = llm.generate(user_message=question)
            source_info = "Direct LLM"

        elapsed_ms = int((time.time() - start) * 1000)

        # Log the query
        try:
            _log_query(question, query_type, answer, elapsed_ms)
        except Exception as e:
            logger.warning(f"Failed to log query: {e}")

        return {
            "answer": answer,
            "query_type": query_type,
            "response_time_ms": elapsed_ms,
            "source_info": source_info,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Query processing failed: {e}")
        return {
            "answer": f"I apologize, but I encountered an error: {str(e)[:200]}",
            "query_type": query_type,
            "response_time_ms": elapsed_ms,
            "source_info": "Error",
        }


def _log_query(query_text: str, query_type: str, response_text: str, response_time_ms: int):
    """Log the query to the database for analytics."""
    from db.connection import execute_write
    execute_write(
        """INSERT INTO query_log (query_text, query_type, response_text, response_time_ms, source, status)
           VALUES (%s, %s, %s, %s, 'text', 'success')""",
        (query_text[:500], query_type, response_text[:2000], response_time_ms),
    )
