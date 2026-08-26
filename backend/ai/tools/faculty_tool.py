"""
AI ERP Assistant — Faculty Tool
================================
Handles faculty profile and directory queries via parameterized SQL.

Phase 9: Added 'by_course' action so "who teaches <course>?" queries
route correctly to FacultyTool instead of TimetableTool.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool


class FacultyTool(BaseTool):
    name = "FacultyTool"
    description = (
        "Fetches faculty profiles, directory info, and workload. "
        "Use this tool when the user asks who teaches a course, "
        "who is the instructor/professor/lecturer for a subject, "
        "or asks about a faculty member by name or department."
    )

    parameters = {
        "action": "One of: 'profile', 'workload', 'search', 'by_course'",
        "employee_code": "Faculty Employee Code (optional)",
        "name": "Faculty Name (optional)",
        "department": "Department Name (optional)",
        "course_code": "Course Code e.g. CS601 (optional, used with action='by_course')",
        "course_name": "Course Name e.g. 'Machine Learning' (optional, used with action='by_course' when code unknown)",
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        employee_code = params.get("employee_code")

        if action == "profile":
            if not employee_code:
                return {"error": "Missing 'employee_code' parameter for profile"}
            sql = "SELECT * FROM vw_faculty_dashboard WHERE employee_code = %s"
            results = execute_query(sql, (employee_code,))
            return {"profile": results[0] if results else None}

        elif action == "workload":
            if not employee_code:
                return {"error": "Missing 'employee_code' parameter for workload"}
            sql = "SELECT * FROM vw_faculty_workload WHERE employee_code = %s"
            results = execute_query(sql, (employee_code,))
            return {"workload": results[0] if results else None}

        elif action == "search":
            name = params.get("name")
            department = params.get("department")

            sql = (
                "SELECT employee_code, faculty_name, designation, department_name "
                "FROM vw_faculty_dashboard WHERE 1=1"
            )
            sql_params = []

            if name:
                sql += " AND faculty_name LIKE %s"
                sql_params.append(f"%{name}%")
            if department:
                sql += " AND department_name = %s"
                sql_params.append(department)

            sql += " LIMIT 20"
            results = execute_query(sql, tuple(sql_params))
            return {"results": results}

        elif action == "by_course":
            # Phase 9: look up faculty who teach a given course (by code or name).
            # Used for queries like "Who teaches machine learning?" / "Who is the CS601 instructor?"
            course_code = params.get("course_code")
            course_name = params.get("course_name")

            if not course_code and not course_name:
                return {"error": "Provide 'course_code' or 'course_name' for by_course action"}

            # Resolve course_code from course_name if only name is given
            if not course_code and course_name:
                code_rows = execute_query(
                    "SELECT course_code FROM courses WHERE LOWER(course_name) LIKE %s LIMIT 1",
                    (f"%{course_name.lower()}%",)
                )
                if code_rows:
                    course_code = code_rows[0]["course_code"]
                else:
                    return {
                        "message": (
                            f"No course named '{course_name}' was found in the database. "
                            "Please check the course name or use the course code directly."
                        ),
                        "found": False,
                    }

            # Look up faculty via vw_timetable_summary (clean join of faculty, timetable, courses)
            sql = """
                SELECT DISTINCT employee_code, faculty_name, department_name,
                       course_name, course_code
                FROM vw_timetable_summary
                WHERE course_code = %s
                LIMIT 5
            """
            results = execute_query(sql, (course_code,))

            if not results:
                # Fallback: confirm the course exists even if no timetable row
                course_info = execute_query(
                    "SELECT course_code, course_name FROM courses WHERE course_code = %s LIMIT 1",
                    (course_code,)
                )
                if course_info:
                    return {
                        "message": (
                            f"The course '{course_info[0]['course_name']}' ({course_code}) "
                            "exists in the database but no faculty assignment was found in "
                            "the timetable. The instructor may not have been assigned yet."
                        ),
                        "course_code": course_code,
                        "found": False,
                    }
                return {
                    "message": (
                        f"No course or faculty found for '{course_code}'. "
                        "Please verify the course code or name."
                    ),
                    "found": False,
                }

            return {
                "course_code": course_code,
                "faculty": results,
                "found": True,
            }

        else:
            return {"error": f"Unknown action: {action}"}
