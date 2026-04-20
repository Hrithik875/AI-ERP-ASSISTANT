"""
AI ERP Assistant — Student & Attendance Routes (Aurora MySQL)
==============================================================
CRUD endpoints for student data, attendance, and grades.
All data fetched dynamically from Aurora MySQL.
MySQL-compatible SQL throughout.
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
    """List students with optional filters."""
    logger.info(f"List students: dept={department}, sem={semester}")

    try:
        conditions = ["s.is_active = TRUE"]
        params = []

        if department:
            conditions.append("s.department = %s")
            params.append(department)
        if semester:
            conditions.append("s.semester = %s")
            params.append(semester)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT s.student_id, s.name, s.email, s.department,
                   s.semester, s.section, s.phone
            FROM students s
            WHERE {where}
            ORDER BY s.name
            LIMIT %s
        """
        params.append(limit)
        return execute_query(sql, tuple(params))

    except Exception as e:
        logger.error(f"Student listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student/{student_id}")
def get_student(student_id: str):
    """Get detailed info about a single student."""
    logger.info(f"Get student: {student_id}")

    try:
        students = execute_query(
            """SELECT s.student_id, s.name, s.email, s.department,
                      s.semester, s.section, s.phone, s.guardian_phone,
                      DATE_FORMAT(s.enrolled_at, '%Y-%m-%d') AS enrolled_at,
                      s.is_active
               FROM students s
               WHERE s.student_id = %s""",
            (student_id,),
        )

        if not students:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

        student = students[0]

        # Get attendance summary (MySQL-compatible aggregation)
        attendance = execute_query(
            """SELECT c.course_code, c.course_name,
                      COUNT(*) AS total_classes,
                      SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
                      SUM(CASE WHEN a.status = 'absent'  THEN 1 ELSE 0 END) AS absent,
                      ROUND(
                          SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END)
                          / COUNT(*) * 100, 1
                      ) AS attendance_pct
               FROM attendance a
               JOIN courses  c ON c.id = a.course_id
               JOIN students s ON s.id = a.student_id
               WHERE s.student_id = %s
               GROUP BY c.course_code, c.course_name
               ORDER BY c.course_code""",
            (student_id,),
        )

        # Get grades
        grades = execute_query(
            """SELECT c.course_code, c.course_name, g.grade,
                      g.grade_points, g.marks_obtained, g.exam_type
               FROM grades g
               JOIN courses  c ON c.id = g.course_id
               JOIN students s ON s.id = g.student_id
               WHERE s.student_id = %s
               ORDER BY c.course_code""",
            (student_id,),
        )

        # Calculate GPA
        gpa = None
        if grades:
            total_gp = sum(float(g["grade_points"]) for g in grades)
            gpa = round(total_gp / len(grades), 2)

        student["attendance"] = attendance
        student["grades"] = grades
        student["gpa"] = gpa

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
    Get attendance records. Filter by student and/or course.
    Returns per-course attendance percentage when student is specified.
    """
    logger.info(f"Attendance query: student={student_id}, course={course_code}")

    try:
        if student_id:
            sql = """
                SELECT c.course_code, c.course_name,
                       COUNT(*) AS total_classes,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
                       SUM(CASE WHEN a.status = 'absent'  THEN 1 ELSE 0 END) AS absent,
                       SUM(CASE WHEN a.status = 'late'    THEN 1 ELSE 0 END) AS late,
                       ROUND(
                           SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END)
                           / COUNT(*) * 100, 1
                       ) AS percentage
                FROM attendance a
                JOIN courses  c ON c.id = a.course_id
                JOIN students s ON s.id = a.student_id
                WHERE s.student_id = %s
            """
            params = [student_id]

            if course_code:
                sql += " AND c.course_code = %s"
                params.append(course_code)

            sql += " GROUP BY c.course_code, c.course_name ORDER BY c.course_code"
            return execute_query(sql, tuple(params))
        else:
            sql = """
                SELECT s.student_id, s.name, s.department, s.semester,
                       COUNT(*) AS total_classes,
                       ROUND(
                           SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END)
                           / COUNT(*) * 100, 1
                       ) AS overall_percentage
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                GROUP BY s.student_id, s.name, s.department, s.semester
                ORDER BY overall_percentage ASC
                LIMIT %s
            """
            return execute_query(sql, (limit,))

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
    """Get grades. Filter by student and/or course."""
    logger.info(f"Grades query: student={student_id}, course={course_code}")

    try:
        conditions = []
        params = []

        if student_id:
            conditions.append("s.student_id = %s")
            params.append(student_id)
        if course_code:
            conditions.append("c.course_code = %s")
            params.append(course_code)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        sql = f"""
            SELECT s.student_id, s.name, c.course_code, c.course_name,
                   g.grade, g.grade_points, g.marks_obtained,
                   g.exam_type, g.semester
            FROM grades g
            JOIN students s ON s.id = g.student_id
            JOIN courses  c ON c.id = g.course_id
            {where}
            ORDER BY s.student_id, c.course_code
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
    """List all faculty members with their assigned courses."""
    logger.info(f"Faculty listing: dept={department}")

    try:
        conditions = ["f.is_active = TRUE"]
        params = []

        if department:
            conditions.append("f.department = %s")
            params.append(department)

        where = " AND ".join(conditions)

        faculty = execute_query(
            f"""SELECT f.employee_id, f.name, f.email, f.department,
                       f.designation, f.phone,
                       DATE_FORMAT(f.joined_at, '%Y-%m-%d') AS joined_at
                FROM faculty f
                WHERE {where}
                ORDER BY f.name""",
            tuple(params),
        )

        # Attach courses for each faculty
        for f in faculty:
            courses = execute_query(
                """SELECT c.course_code, c.course_name, c.credits, c.semester
                   FROM courses c
                   JOIN faculty fac ON fac.id = c.faculty_id
                   WHERE fac.employee_id = %s AND c.is_active = TRUE""",
                (f["employee_id"],),
            )
            f["courses"] = courses

        return faculty

    except Exception as e:
        logger.error(f"Faculty query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
