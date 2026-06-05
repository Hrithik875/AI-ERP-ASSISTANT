"""
AI ERP Assistant — Faculty Tool
================================
Handles faculty profile and directory queries via parameterized SQL.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool

class FacultyTool(BaseTool):
    name = "FacultyTool"
    description = "Fetches faculty profiles, directory info, and workload."
    
    parameters = {
        "action": "One of: 'profile', 'workload', 'search'",
        "employee_code": "Faculty Employee Code (optional)",
        "name": "Faculty Name (optional)",
        "department": "Department Name (optional)"
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
            
            sql = "SELECT employee_code, faculty_name, designation, department_name FROM vw_faculty_dashboard WHERE 1=1"
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
            
        else:
            return {"error": f"Unknown action: {action}"}
