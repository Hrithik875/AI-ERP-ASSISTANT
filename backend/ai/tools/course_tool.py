"""
AI ERP Assistant — Course Tool
================================
Handles course queries via parameterized SQL.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool

class CourseTool(BaseTool):
    name = "CourseTool"
    description = "Fetches course details and enrollment statistics."
    
    parameters = {
        "action": "One of: 'details', 'statistics', 'search'",
        "course_code": "Course Code (optional)",
        "department": "Department Name (optional)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        course_code = params.get("course_code")

        if action == "details":
            if not course_code:
                return {"error": "Missing 'course_code' parameter"}
            sql = "SELECT * FROM courses JOIN departments ON courses.department_fk = departments.id WHERE course_code = %s"
            results = execute_query(sql, (course_code,))
            return {"course": results[0] if results else None}
            
        elif action == "statistics":
            if not course_code:
                return {"error": "Missing 'course_code' parameter"}
            sql = "SELECT * FROM vw_course_statistics WHERE course_code = %s"
            results = execute_query(sql, (course_code,))
            return {"statistics": results[0] if results else None}
            
        elif action == "search":
            department = params.get("department")
            sql = "SELECT course_code, course_name, credits, semester, department_name FROM courses JOIN departments ON courses.department_fk = departments.id WHERE 1=1"
            sql_params = []
            
            if department:
                sql += " AND department_name = %s"
                sql_params.append(department)
                
            results = execute_query(sql, tuple(sql_params))
            return {"results": results}
            
        else:
            return {"error": f"Unknown action: {action}"}
