"""
AI ERP Assistant — Student Tool
=================================
Handles student profile and directory queries via parameterized SQL.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")

class StudentTool(BaseTool):
    name = "StudentTool"
    description = "Fetches student profiles and directory info."
    
    parameters = {
        "action": "One of: 'profile', 'search'",
        "usn": "Student USN (optional)",
        "name": "Student Name (optional)",
        "department": "Department Code (optional)",
        "semester": "Semester (optional)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        usn = params.get("usn")
        
        logger.info(f"StudentTool executing action: {action} with params: {params}")

        if action == "profile":
            if not usn:
                return {"error": "Missing 'usn' parameter for profile"}
            
            sql = """
                SELECT usn, student_name, email, phone, department_name, department_code, semester, section, cgpa, status, enrolled_at
                FROM vw_student_profile
                WHERE usn = %s
            """
            results = execute_query(sql, (usn,))
                
            if not results:
                return {"message": f"No student found for USN: {usn}"}
            
            return {
                "profile": results[0]
            }
            
        elif action == "search":
            name = params.get("name")
            department = params.get("department")
            semester = params.get("semester")
            
            sql = """
                SELECT usn, student_name, department_code, semester, section
                FROM vw_student_profile
                WHERE 1=1
            """
            sql_params = []
            
            if name:
                sql += " AND student_name LIKE %s"
                sql_params.append(f"%{name}%")
            if department:
                sql += " AND department_code = %s"
                sql_params.append(department)
            if semester:
                sql += " AND semester = %s"
                sql_params.append(semester)
                
            sql += " LIMIT 20"
            
            results = execute_query(sql, tuple(sql_params))
            
            if not results:
                return {"message": "No students found matching the criteria."}
                
            return {
                "results": results
            }
            
        else:
            return {"error": f"Unknown action: {action}"}
