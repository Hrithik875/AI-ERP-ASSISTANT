"""
AI ERP Assistant — Analytics Tool
===================================
Handles department and institutional analytics queries.

Phase 10: Added 'department_list' as alias for 'department_performance' (LLM
sometimes requests this non-existent action). Also expanded description so LLM
knows exactly what actions are valid.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")


class AnalyticsTool(BaseTool):
    name = "AnalyticsTool"
    description = (
        "Fetches department performance and overall ERP analytics. "
        "Use action='department_performance' to list all departments with their student/faculty/course counts and average attendance. "
        "Use action='overall_stats' to get total counts of students, faculty, and courses institution-wide. "
        "Valid actions: 'department_performance', 'overall_stats'. "
        "Do NOT use 'department_list' — it does not exist; use 'department_performance' instead."
    )

    parameters = {
        "action": "One of: 'department_performance' (lists all departments with stats), 'overall_stats' (total institution counts)",
        "department": "Department Code or Name (optional filter for department_performance)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")

        # Phase 10: alias invalid actions like 'department_list', 'departments', 'list' → 'department_performance'
        # This catches variations the LLM might output for department listing.
        if action in ("department_list", "departments", "list_departments", "list", "dept_list"):
            logger.warning(
                f"[AnalyticsTool] LLM requested action='{action}'; "
                "remapping to 'department_performance' (safe fallback)"
            )
            action = "department_performance"

        if action == "department_performance":
            department = params.get("department")
            sql = "SELECT * FROM vw_department_performance"
            sql_params = []
            if department:
                sql += " WHERE department_code = %s OR department_name = %s"
                sql_params.extend([department, department])

            results = execute_query(sql, tuple(sql_params))
            return {
                "departments": results,
                "total_departments": len(results),
                "summary": f"Found {len(results)} department(s)."
            }

        elif action == "overall_stats":
            stats = {}
            try:
                stats['total_students'] = execute_query("SELECT COUNT(*) as count FROM students")[0]['count']
            except Exception:
                stats['total_students'] = "N/A"
            try:
                stats['total_faculty'] = execute_query("SELECT COUNT(*) as count FROM faculty")[0]['count']
            except Exception:
                stats['total_faculty'] = "N/A"
            try:
                stats['total_courses'] = execute_query("SELECT COUNT(*) as count FROM courses")[0]['count']
            except Exception:
                stats['total_courses'] = "N/A"
            try:
                stats['total_departments'] = execute_query("SELECT COUNT(*) as count FROM departments")[0]['count']
            except Exception:
                stats['total_departments'] = "N/A"
            return {"overall_stats": stats}

        else:
            # Log the bad action and return actionable error (not a silent 500)
            logger.error(
                f"[AnalyticsTool] Invalid action requested: '{action}'. "
                f"Valid actions: 'department_performance', 'overall_stats'"
            )
            return {
                "error": (
                    f"Invalid action '{action}'. "
                    "AnalyticsTool only supports: 'department_performance', 'overall_stats'."
                )
            }
