"""
AI ERP Assistant — Attendance Tool
====================================
Handles all attendance-related queries via parameterized SQL.
No LLM-generated SQL allowed.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")

class AttendanceTool(BaseTool):
    name = "AttendanceTool"
    description = "Fetches attendance records for students and courses."
    
    parameters = {
        "action": "One of: 'student_summary', 'course_summary', 'risk_list'",
        "usn": "Student USN (optional)",
        "name": "Student Name (optional)",
        "course_code": "Course Code (optional)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        usn = params.get("usn")
        name = params.get("name")
        course_code = params.get("course_code")

        logger.info(f"AttendanceTool executing action: {action} with params: {params}")

        if action == "student_summary":
            if not usn and not name:
                return {"error": "Missing 'usn' or 'name' parameter for student_summary"}
            
            sql = """
                SELECT usn, student_name, course_code, course_name, total_classes, classes_attended, attendance_pct
                FROM vw_attendance_summary
                WHERE 1=1
            """
            sql_params = []
            
            if usn:
                sql += " AND usn = %s"
                sql_params.append(usn)
            if name:
                sql += " AND student_name LIKE %s"
                sql_params.append(f"%{name}%")
            if course_code:
                sql += " AND course_code = %s"
                sql_params.append(course_code)
                
            results = execute_query(sql, tuple(sql_params))
                
            if not results:
                identifier = usn if usn else name
                return {"message": f"No attendance records found for student: {identifier}"}
            
            return {
                "attendance_records": results
            }
            
        elif action == "course_summary":
            if not course_code:
                return {"error": "Missing 'course_code' parameter for course_summary"}
                
            sql = """
                SELECT avg_attendance_pct, enrolled_students
                FROM vw_course_statistics
                WHERE course_code = %s
            """
            results = execute_query(sql, (course_code,))
            
            if not results:
                return {"message": f"No course statistics found for course: {course_code}"}
                
            return {
                "course_code": course_code,
                "statistics": results[0]
            }
            
        elif action == "risk_list":
            sql = """
                SELECT usn, student_name, course_code, attendance_pct, risk_level
                FROM vw_student_risk
            """
            
            if course_code:
                sql += " WHERE course_code = %s"
                results = execute_query(sql, (course_code,))
            else:
                results = execute_query(sql)
                
            if not results:
                return {"message": "No students are currently at attendance risk."}
                
            return {
                "at_risk_students": results
            }
            
        else:
            return {"error": f"Unknown action: {action}"}
