"""
AI ERP Assistant — Student & Attendance Routes (Aurora MySQL)
==============================================================
CRUD endpoints for student data, attendance, and grades.
All data fetched dynamically from Aurora MySQL views and tables.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from db.connection import execute_query

logger = logging.getLogger("erp-assistant")
router = APIRouter(tags=["erp-data"])


# ══════════════════════════════════════════════════════════════════════════
# Students
# ══════════════════════════════════════════════════════════════════════════

@router.get("/students")
def list_students(
    department: Optional[str] = None,
    semester: Optional[int] = None,
    limit: int = Query(default=50, le=200),
):
    """List students with optional department/semester filters."""
    logger.info(f"List students: dept={department}, sem={semester}")

    try:
        conditions = ["status = 'active'"]
        params = []

        if department:
            conditions.append("department_name = %s")
            params.append(department)
        if semester:
            conditions.append("semester = %s")
            params.append(semester)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT usn, student_name AS name, email, department_name AS department,
                   semester, section, phone
            FROM vw_student_profile
            WHERE {where}
            ORDER BY student_name
            LIMIT %s
        """
        params.append(limit)
        return execute_query(sql, tuple(params))

    except Exception as e:
        logger.error(f"Student listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student/{student_id}")
def get_student(student_id: str):
    """Get detailed info about a single student by USN."""
    logger.info(f"Get student: {student_id}")

    try:
        students = execute_query(
            """SELECT usn, student_name AS name, email, department_name AS department,
                      semester, section, phone, parent_phone AS guardian_phone,
                      DATE_FORMAT(enrolled_at, '%Y-%m-%d') AS enrolled_at,
                      status
               FROM vw_student_profile
               WHERE usn = %s""",
            (student_id,),
        )

        if not students:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

        student = students[0]

        # Get attendance summary
        attendance = execute_query(
            """SELECT course_code, course_name,
                      total_classes, classes_attended AS present,
                      (total_classes - classes_attended) AS absent,
                      attendance_pct
               FROM vw_attendance_summary
               WHERE usn = %s
               ORDER BY course_code""",
            (student_id,),
        )

        # Get grades
        grades = execute_query(
            """SELECT course_code, course_name, final_grade AS grade,
                      final_exam_marks AS marks_obtained,
                      ia1_marks, ia2_marks, ia3_marks, graded_by
               FROM vw_grade_summary
               WHERE usn = %s
               ORDER BY course_code""",
            (student_id,),
        )

        student["attendance"] = attendance
        student["grades"] = grades

        return student

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Student detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Attendance
# ══════════════════════════════════════════════════════════════════════════

@router.get("/attendance")
def get_attendance(
    student_id: Optional[str] = None,
    course_code: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    """
    Get attendance records. Filter by student USN and/or course code.
    """
    logger.info(f"Attendance query: student={student_id}, course={course_code}")

    try:
        conditions = []
        params = []

        if student_id:
            conditions.append("usn = %s")
            params.append(student_id)
        if course_code:
            conditions.append("course_code = %s")
            params.append(course_code)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT usn, student_name AS name, department_name AS department, semester, section,
                   course_code, course_name, total_classes, classes_attended, attendance_pct AS overall_percentage
            FROM vw_attendance_summary
            {where}
            ORDER BY attendance_pct ASC
            LIMIT %s
        """
        params.append(limit)
        return execute_query(sql, tuple(params))

    except Exception as e:
        logger.error(f"Attendance query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Grades
# ══════════════════════════════════════════════════════════════════════════

@router.get("/grades")
def get_grades(
    student_id: Optional[str] = None,
    course_code: Optional[str] = None,
):
    """Get grades. Filter by student USN and/or course code."""
    logger.info(f"Grades query: student={student_id}, course={course_code}")

    try:
        conditions = []
        params = []

        if student_id:
            conditions.append("usn = %s")
            params.append(student_id)
        if course_code:
            conditions.append("course_code = %s")
            params.append(course_code)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT usn, student_name AS name, course_code, course_name,
                   final_grade AS grade, final_exam_marks AS marks_obtained,
                   ia1_marks, ia2_marks, ia3_marks, graded_by
            FROM vw_grade_summary
            {where}
            ORDER BY usn, course_code
            LIMIT 100
        """
        return execute_query(sql, tuple(params))

    except Exception as e:
        logger.error(f"Grades query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# Faculty
# ══════════════════════════════════════════════════════════════════════════

@router.get("/faculty")
def list_faculty(department: Optional[str] = None):
    """List all faculty members with their department and workload."""
    logger.info(f"Faculty listing: dept={department}")

    try:
        conditions = []
        params = []

        if department:
            conditions.append("department_name = %s")
            params.append(department)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT employee_code, faculty_name AS name, designation, department_name AS department,
                   courses_assigned, weekly_slots, students_taught
            FROM vw_faculty_workload
            {where}
            ORDER BY faculty_name
        """
        return execute_query(sql, tuple(params))

    except Exception as e:
        logger.error(f"Faculty query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
