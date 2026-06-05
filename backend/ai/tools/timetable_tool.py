"""
AI ERP Assistant — Timetable Tool
===================================
Handles timetable queries via parameterized SQL.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool

class TimetableTool(BaseTool):
    name = "TimetableTool"
    description = "Fetches timetable and class schedule info."
    
    parameters = {
        "action": "One of: 'faculty_schedule', 'course_schedule', 'day_schedule'",
        "employee_code": "Faculty Employee Code (optional)",
        "course_code": "Course Code (optional)",
        "day": "Day of the week (optional)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")

        if action == "faculty_schedule":
            employee_code = params.get("employee_code")
            day = params.get("day")
            if not employee_code:
                return {"error": "Missing 'employee_code' parameter"}
            
            sql = "SELECT day_of_week, start_time, end_time, room, course_name, course_code FROM vw_timetable_summary WHERE employee_code = %s"
            sql_params = [employee_code]
            if day:
                sql += " AND day_of_week = %s"
                sql_params.append(day)
                
            sql += " ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'), start_time"
            results = execute_query(sql, tuple(sql_params))
            return {"schedule": results}
            
        elif action == "course_schedule":
            course_code = params.get("course_code")
            if not course_code:
                return {"error": "Missing 'course_code' parameter"}
            
            sql = "SELECT day_of_week, start_time, end_time, room, faculty_name FROM vw_timetable_summary WHERE course_code = %s ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'), start_time"
            results = execute_query(sql, (course_code,))
            return {"schedule": results}
            
        elif action == "day_schedule":
            day = params.get("day")
            if not day:
                return {"error": "Missing 'day' parameter"}
            
            sql = "SELECT course_code, course_name, faculty_name, start_time, end_time, room FROM vw_timetable_summary WHERE day_of_week = %s ORDER BY start_time"
            results = execute_query(sql, (day,))
            return {"schedule": results}
            
        else:
            return {"error": f"Unknown action: {action}"}
