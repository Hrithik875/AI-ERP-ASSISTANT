"""
AI ERP Assistant — Attendance Tool
====================================
Handles all attendance-related queries via parameterized SQL.
No LLM-generated SQL allowed.
"""

import math
from typing import Any, Dict, List
from db.connection import execute_query
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")


def compute_classes_needed_to_reach_target(attended: int, total: int, target_pct: float) -> int:
    """
    Compute minimal additional consecutive classes attended (x) to achieve:
        (attended + x) / (total + x) >= target_pct / 100
        x >= (target_pct * total - 100 * attended) / (100 - target_pct)
    """
    if total <= 0:
        return 0
    current_pct = (attended / total) * 100.0
    if current_pct >= target_pct:
        return 0
    if target_pct >= 100.0:
        return 0 if attended == total else 999  # Cannot achieve 100% if any class missed
    needed = math.ceil((target_pct * total - 100.0 * attended) / (100.0 - target_pct))
    return max(0, needed)


def compute_classes_can_miss(attended: int, total: int, target_pct: float) -> int:
    """
    Compute maximum consecutive classes missed (y) while maintaining:
        attended / (total + y) >= target_pct / 100
        y <= (100 * attended - target_pct * total) / target_pct
    """
    if total <= 0 or target_pct <= 0:
        return 0
    current_pct = (attended / total) * 100.0
    if current_pct < target_pct:
        return 0  # Already below threshold, cannot miss any
    max_miss = math.floor((100.0 * attended - target_pct * total) / target_pct)
    return max(0, max_miss)


class AttendanceTool(BaseTool):
    name = "AttendanceTool"
    description = (
        "Fetches attendance records for students/courses and performs deterministic "
        "arithmetic calculations for attendance thresholds, classes needed, and safe miss limits."
    )
    
    parameters = {
        "action": (
            "One of: 'student_summary', 'course_summary', 'risk_list', "
            "'calculate_classes_needed', 'calculate_classes_can_miss'"
        ),
        "usn": "Student USN (optional)",
        "name": "Student Name (optional)",
        "course_code": "Course Code (optional)",
        "target_pct": "Target attendance percentage, e.g. 75.0 or 85.0 (optional, default 75.0)"
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        action = params.get("action")
        usn = params.get("usn")
        name = params.get("name")
        course_code = params.get("course_code")
        target_pct_raw = params.get("target_pct", 75.0)
        try:
            target_pct = float(target_pct_raw)
        except (ValueError, TypeError):
            target_pct = 75.0

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
                SELECT r.usn, r.student_name, r.course_code, r.attendance_pct, r.risk_level,
                       att.total_classes, att.classes_attended, att.course_name
                FROM vw_student_risk r
                JOIN vw_attendance_summary att ON att.usn = r.usn AND att.course_code = r.course_code
            """
            
            if course_code:
                sql += " WHERE r.course_code = %s"
                raw_results = execute_query(sql, (course_code,))
            else:
                raw_results = execute_query(sql)
                
            if not raw_results:
                return {"message": "No students are currently at attendance risk."}
                
            enriched = []
            for r in raw_results:
                total = int(r["total_classes"])
                attended = int(r["classes_attended"])
                curr_pct = float(r["attendance_pct"])
                threshold = 75.0
                gap = round(threshold - curr_pct, 2)
                needed_75 = compute_classes_needed_to_reach_target(attended, total, 75.0)
                needed_85 = compute_classes_needed_to_reach_target(attended, total, 85.0)

                enriched.append({
                    "usn": r["usn"],
                    "student_name": r["student_name"],
                    "course_code": r["course_code"],
                    "course_name": r.get("course_name", ""),
                    "current_attendance_pct": curr_pct,
                    "classes_attended": attended,
                    "total_classes": total,
                    "threshold_pct": threshold,
                    "shortage_percentage_points": gap,
                    "risk_level": r["risk_level"],
                    "classes_needed_to_reach_75": needed_75,
                    "classes_needed_to_reach_85": needed_85,
                    "explanation": (
                        f"Current attendance is {curr_pct}% ({attended}/{total} classes). "
                        f"Short by {gap}% points below the {threshold}% minimum threshold. "
                        f"Needs to attend {needed_75} consecutive classes to reach 75%."
                    )
                })

            return {
                "at_risk_students": enriched,
                "summary": f"{len(enriched)} student(s) currently below the 75.0% attendance threshold."
            }

        elif action in ("calculate_classes_needed", "classes_needed"):
            if not usn and not name and not course_code:
                return {"error": "Provide 'usn', 'name', or 'course_code' to calculate required classes."}

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

            records = execute_query(sql, tuple(sql_params))
            if not records:
                identifier = usn or name or course_code
                return {"message": f"No attendance records found for: {identifier}"}

            calculations = []
            for r in records:
                total = int(r["total_classes"])
                attended = int(r["classes_attended"])
                curr_pct = float(r["attendance_pct"])
                needed = compute_classes_needed_to_reach_target(attended, total, target_pct)
                proj_total = total + needed
                proj_attended = attended + needed
                proj_pct = round((proj_attended / proj_total) * 100.0, 2) if proj_total > 0 else 0.0

                calculations.append({
                    "usn": r["usn"],
                    "student_name": r["student_name"],
                    "course_code": r["course_code"],
                    "course_name": r["course_name"],
                    "current_attended": attended,
                    "current_total": total,
                    "current_attendance_pct": curr_pct,
                    "target_threshold_pct": target_pct,
                    "classes_needed_to_reach_target": needed,
                    "projected_attended": proj_attended,
                    "projected_total": proj_total,
                    "projected_attendance_pct": proj_pct,
                    "gap_percentage_points": round(max(0.0, target_pct - curr_pct), 2),
                    "already_eligible": curr_pct >= target_pct,
                    "calculation_type": "deterministic_python_arithmetic",
                })

            return {
                "calculation": "classes_needed_to_reach_target",
                "target_threshold_pct": target_pct,
                "results": calculations,
            }

        elif action in ("calculate_classes_can_miss", "classes_can_miss", "safe_bunks"):
            if not usn and not name and not course_code:
                return {"error": "Provide 'usn', 'name', or 'course_code' to calculate allowed missed classes."}

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

            records = execute_query(sql, tuple(sql_params))
            if not records:
                identifier = usn or name or course_code
                return {"message": f"No attendance records found for: {identifier}"}

            calculations = []
            for r in records:
                total = int(r["total_classes"])
                attended = int(r["classes_attended"])
                curr_pct = float(r["attendance_pct"])
                can_miss = compute_classes_can_miss(attended, total, target_pct)
                proj_total = total + can_miss
                proj_pct = round((attended / proj_total) * 100.0, 2) if proj_total > 0 else 0.0

                calculations.append({
                    "usn": r["usn"],
                    "student_name": r["student_name"],
                    "course_code": r["course_code"],
                    "course_name": r["course_name"],
                    "current_attended": attended,
                    "current_total": total,
                    "current_attendance_pct": curr_pct,
                    "target_threshold_pct": target_pct,
                    "classes_can_miss_safely": can_miss,
                    "projected_attended": attended,
                    "projected_total": proj_total,
                    "projected_attendance_pct": proj_pct,
                    "buffer_percentage_points": round(max(0.0, curr_pct - target_pct), 2),
                    "below_threshold": curr_pct < target_pct,
                    "calculation_type": "deterministic_python_arithmetic",
                })

            return {
                "calculation": "classes_can_miss_safely",
                "target_threshold_pct": target_pct,
                "results": calculations,
            }

        else:
            return {"error": f"Unknown action: {action}"}
