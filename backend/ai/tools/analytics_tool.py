"""
AI ERP Assistant — Analytics Tool
===================================
Handles department and institutional analytics queries.
"""

from typing import Any, Dict
from db.connection import execute_query
from .base import BaseTool

class AnalyticsTool(BaseTool):
    name = "AnalyticsTool"
    description = "Fetches department performance and overall ERP analytics."
    
    parameters = {
        "action": "One of: 'department_performance', 'overall_stats'",
        "department": "Department Code or Name (optional)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")

        if action == "department_performance":
            department = params.get("department")
            sql = "SELECT * FROM vw_department_performance"
            sql_params = []
            if department:
                sql += " WHERE department_code = %s OR department_name = %s"
                sql_params.extend([department, department])
                
            results = execute_query(sql, tuple(sql_params))
            return {"performance": results}
            
        elif action == "overall_stats":
            # Just an example of combining multiple small queries
            stats = {}
            stats['students'] = execute_query("SELECT COUNT(*) as count FROM students")[0]['count']
            stats['faculty'] = execute_query("SELECT COUNT(*) as count FROM faculty")[0]['count']
            stats['courses'] = execute_query("SELECT COUNT(*) as count FROM courses")[0]['count']
            return {"overall_stats": stats}
            
        else:
            return {"error": f"Unknown action: {action}"}
