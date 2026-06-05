"""
AI ERP Assistant — Grades Tool
================================
Handles all grade-related queries via parameterized SQL.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")

class GradesTool(BaseTool):
    name = "GradesTool"
    description = "Fetches grade records and academic performance."
    
    parameters = {
        "action": "One of: 'student_grades', 'course_grades', 'top_performers', 'failing_students'",
        "usn": "Student USN (optional)",
        "course_code": "Course Code (optional)",
        "limit": "Number of records to return (optional, default 10)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        usn = params.get("usn")
        course_code = params.get("course_code")
        limit = params.get("limit", 10)

        logger.info(f"GradesTool executing action: {action} with params: {params}")

        if action == "student_grades":
            if not usn:
                return {"error": "Missing 'usn' parameter for student_grades"}
            
            sql = """
                SELECT course_code, course_name, ia1_marks, ia2_marks, ia3_marks, final_exam_marks, final_grade
                FROM vw_grade_summary
                WHERE usn = %s
            """
            
            if course_code:
                sql += " AND course_code = %s"
                results = execute_query(sql, (usn, course_code))
            else:
                results = execute_query(sql, (usn,))
                
            if not results:
                return {"message": f"No grade records found for USN: {usn}"}
            
            return {
                "usn": usn,
                "grades": results
            }
            
        elif action == "course_grades":
            if not course_code:
                return {"error": "Missing 'course_code' parameter for course_grades"}
                
            sql = """
                SELECT avg_final_marks, fail_count
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
            
        elif action == "top_performers":
            if not course_code:
                return {"error": "Missing 'course_code' parameter for top_performers"}
                
            sql = """
                SELECT usn, student_name, final_exam_marks, final_grade
                FROM vw_grade_summary
                WHERE course_code = %s AND final_exam_marks IS NOT NULL
                ORDER BY final_exam_marks DESC
                LIMIT %s
            """
            # Ensure limit is int
            try:
                limit_int = int(limit)
            except:
                limit_int = 10
                
            results = execute_query(sql, (course_code, limit_int))
            
            if not results:
                return {"message": f"No top performers found for course: {course_code}"}
                
            return {
                "course_code": course_code,
                "top_performers": results
            }
            
        elif action == "failing_students":
            if not course_code:
                return {"error": "Missing 'course_code' parameter for failing_students"}
                
            sql = """
                SELECT usn, student_name, final_exam_marks, final_grade
                FROM vw_grade_summary
                WHERE course_code = %s AND final_grade = 'F'
            """
            results = execute_query(sql, (course_code,))
            
            if not results:
                return {"message": f"No failing students found for course: {course_code}"}
                
            return {
                "course_code": course_code,
                "failing_students": results
            }
            
        else:
            return {"error": f"Unknown action: {action}"}
