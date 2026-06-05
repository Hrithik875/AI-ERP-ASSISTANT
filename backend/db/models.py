"""
AI ERP Assistant — Database Models & Schema (Aurora MySQL)
============================================================
Enterprise-grade DDL for Faculty-Centric ERP.
All SQL is MySQL-compatible (Aurora MySQL 8.0+).

Naming Conventions:
  - Primary keys: `id` (BIGINT AUTO_INCREMENT)
  - Foreign keys: `<entity>_fk` (BIGINT) — always suffix with _fk
  - Business identifiers: `usn` (students), `employee_code` (faculty), `course_code` (courses)
  - Internal IDs are never exposed to users
"""

import logging
from db.connection import get_cursor

logger = logging.getLogger("erp-assistant")

# ── Schema DDL (MySQL) ─────────────────────────────────────────────────────

SCHEMA_SQL = """
-- ════════════════════════════════════════════════════════════════
-- DEPARTMENTS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS departments (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    department_code VARCHAR(10)  NOT NULL UNIQUE,
    department_name VARCHAR(120) NOT NULL UNIQUE,
    hod_fk          BIGINT       DEFAULT NULL,
    phone           VARCHAR(20),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- FACULTY
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS faculty (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_code   VARCHAR(20)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20),
    department_fk   BIGINT       NOT NULL,
    designation     VARCHAR(80)  NOT NULL DEFAULT 'Assistant Professor',
    joining_date    DATE         NOT NULL DEFAULT (CURRENT_DATE),
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_fk) REFERENCES departments(id) ON DELETE RESTRICT,
    CHECK (status IN ('active', 'inactive', 'on_leave', 'retired'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Add HOD foreign key after faculty table exists
-- ALTER TABLE departments ADD CONSTRAINT fk_dept_hod FOREIGN KEY (hod_fk) REFERENCES faculty(id) ON DELETE SET NULL;

-- ════════════════════════════════════════════════════════════════
-- STUDENTS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS students (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    usn             VARCHAR(20)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20),
    department_fk   BIGINT       NOT NULL,
    semester        INT          NOT NULL DEFAULT 1,
    section         VARCHAR(5)   DEFAULT 'A',
    cgpa            DECIMAL(4,2) DEFAULT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    enrolled_at     DATE         NOT NULL DEFAULT (CURRENT_DATE),
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (department_fk) REFERENCES departments(id) ON DELETE RESTRICT,
    CHECK (status IN ('active', 'inactive', 'graduated', 'suspended'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- COURSES
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS courses (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    course_code     VARCHAR(20)  NOT NULL UNIQUE,
    course_name     VARCHAR(150) NOT NULL,
    credits         INT          NOT NULL DEFAULT 3,
    department_fk   BIGINT       NOT NULL,
    semester        INT          NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_fk) REFERENCES departments(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- FACULTY_COURSES (many-to-many mapping)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS faculty_courses (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    faculty_fk      BIGINT       NOT NULL,
    course_fk       BIGINT       NOT NULL,
    academic_year   VARCHAR(10)  NOT NULL DEFAULT '2025-26',
    semester        INT          NOT NULL,
    section         VARCHAR(5)   DEFAULT 'A',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_fac_course (faculty_fk, course_fk, academic_year, section),
    FOREIGN KEY (faculty_fk) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (course_fk) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- ATTENDANCE
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS attendance (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_fk      BIGINT       NOT NULL,
    course_fk       BIGINT       NOT NULL,
    faculty_fk      BIGINT       DEFAULT NULL,
    attendance_date DATE         NOT NULL,
    status          VARCHAR(10)  NOT NULL DEFAULT 'present',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attendance (student_fk, course_fk, attendance_date),
    FOREIGN KEY (student_fk) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_fk) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_fk) REFERENCES faculty(id) ON DELETE SET NULL,
    CHECK (status IN ('present', 'absent', 'late', 'excused'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- GRADES
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS grades (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_fk      BIGINT       NOT NULL,
    course_fk       BIGINT       NOT NULL,
    faculty_fk      BIGINT       DEFAULT NULL,
    ia1_marks       DECIMAL(5,2) DEFAULT NULL,
    ia2_marks       DECIMAL(5,2) DEFAULT NULL,
    ia3_marks       DECIMAL(5,2) DEFAULT NULL,
    final_exam_marks DECIMAL(5,2) DEFAULT NULL,
    final_grade     VARCHAR(5)   DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_grades (student_fk, course_fk),
    FOREIGN KEY (student_fk) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_fk) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_fk) REFERENCES faculty(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- TIMETABLE
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS timetable (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    faculty_fk      BIGINT       NOT NULL,
    course_fk       BIGINT       NOT NULL,
    day_of_week     VARCHAR(10)  NOT NULL,
    start_time      TIME         NOT NULL,
    end_time        TIME         NOT NULL,
    room            VARCHAR(30),
    section         VARCHAR(5)   DEFAULT 'A',
    semester        INT          NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_fk) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (course_fk) REFERENCES courses(id) ON DELETE CASCADE,
    CHECK (day_of_week IN ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- ANNOUNCEMENTS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS announcements (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    faculty_fk      BIGINT       NOT NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT         NOT NULL,
    department      VARCHAR(80),
    priority        VARCHAR(10)  NOT NULL DEFAULT 'normal',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    published_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_fk) REFERENCES faculty(id) ON DELETE CASCADE,
    CHECK (priority IN ('low', 'normal', 'high', 'urgent'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- DOCUMENTS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS documents (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_uuid        VARCHAR(40)  NOT NULL UNIQUE,
    filename        VARCHAR(255) NOT NULL,
    file_type       VARCHAR(10)  NOT NULL,
    file_size_bytes BIGINT       NOT NULL DEFAULT 0,
    storage_path    VARCHAR(500) NOT NULL,
    uploaded_by     BIGINT,
    embedding_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    chunk_count     INT          DEFAULT 0,
    department      VARCHAR(80),
    document_type   VARCHAR(50),
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES faculty(id) ON DELETE SET NULL,
    CHECK (embedding_status IN ('pending', 'processing', 'processed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ════════════════════════════════════════════════════════════════
-- QUERY_LOGS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS query_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    query_text      TEXT         NOT NULL,
    query_type      VARCHAR(30)  NOT NULL DEFAULT 'general',
    response_text   TEXT,
    response_time_ms INT,
    source          VARCHAR(20)  NOT NULL DEFAULT 'text',
    status          VARCHAR(20)  NOT NULL DEFAULT 'success',
    tool_used       VARCHAR(50),
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (source IN ('text', 'voice')),
    CHECK (status IN ('success', 'failed', 'partial'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# ── Indexes ────────────────────────────────────────────────────────────────

INDEX_SQL = """
CREATE INDEX idx_students_usn          ON students(usn);
CREATE INDEX idx_students_dept         ON students(department_fk);
CREATE INDEX idx_students_semester     ON students(semester);
CREATE INDEX idx_faculty_empcode       ON faculty(employee_code);
CREATE INDEX idx_faculty_dept          ON faculty(department_fk);
CREATE INDEX idx_courses_code          ON courses(course_code);
CREATE INDEX idx_courses_dept          ON courses(department_fk);
CREATE INDEX idx_attendance_student    ON attendance(student_fk);
CREATE INDEX idx_attendance_course     ON attendance(course_fk);
CREATE INDEX idx_attendance_faculty    ON attendance(faculty_fk);
CREATE INDEX idx_attendance_date       ON attendance(attendance_date);
CREATE INDEX idx_grades_student        ON grades(student_fk);
CREATE INDEX idx_grades_course         ON grades(course_fk);
CREATE INDEX idx_timetable_faculty     ON timetable(faculty_fk);
CREATE INDEX idx_timetable_course      ON timetable(course_fk);
CREATE INDEX idx_timetable_day         ON timetable(day_of_week);
CREATE INDEX idx_announcements_faculty ON announcements(faculty_fk);
CREATE INDEX idx_query_logs_created    ON query_logs(created_at);
CREATE INDEX idx_query_logs_type       ON query_logs(query_type);
CREATE INDEX idx_documents_status      ON documents(embedding_status);
CREATE INDEX idx_faculty_courses_fac   ON faculty_courses(faculty_fk);
CREATE INDEX idx_faculty_courses_crs   ON faculty_courses(course_fk);
"""

# ── Reporting Views ────────────────────────────────────────────────────────

VIEWS_SQL = """
-- ── vw_student_profile ────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_student_profile AS
SELECT
    s.id,
    s.usn,
    s.name        AS student_name,
    s.email,
    s.phone,
    d.department_name,
    d.department_code,
    s.semester,
    s.section,
    s.cgpa,
    s.status,
    s.enrolled_at
FROM students s
JOIN departments d ON d.id = s.department_fk;

-- ── vw_attendance_summary ─────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_attendance_summary AS
SELECT
    s.usn,
    s.name          AS student_name,
    c.course_code,
    c.course_name,
    d.department_name,
    s.semester,
    s.section,
    COUNT(*)        AS total_classes,
    SUM(CASE WHEN a.status IN ('present','late') THEN 1 ELSE 0 END) AS classes_attended,
    ROUND(SUM(CASE WHEN a.status IN ('present','late') THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS attendance_pct
FROM attendance a
JOIN students s   ON s.id = a.student_fk
JOIN courses  c   ON c.id = a.course_fk
JOIN departments d ON d.id = s.department_fk
GROUP BY s.usn, s.name, c.course_code, c.course_name, d.department_name, s.semester, s.section;

-- ── vw_grade_summary ──────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_grade_summary AS
SELECT
    s.usn,
    s.name          AS student_name,
    c.course_code,
    c.course_name,
    d.department_name,
    g.ia1_marks,
    g.ia2_marks,
    g.ia3_marks,
    g.final_exam_marks,
    g.final_grade,
    f.name          AS graded_by,
    f.employee_code AS graded_by_code
FROM grades g
JOIN students s    ON s.id = g.student_fk
JOIN courses  c    ON c.id = g.course_fk
JOIN departments d ON d.id = s.department_fk
LEFT JOIN faculty f ON f.id = g.faculty_fk;

-- ── vw_faculty_workload ───────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_faculty_workload AS
SELECT
    f.employee_code,
    f.name          AS faculty_name,
    f.designation,
    d.department_name,
    COUNT(DISTINCT fc.course_fk)  AS courses_assigned,
    COUNT(DISTINCT t.id)          AS weekly_slots,
    (SELECT COUNT(DISTINCT a.student_fk) FROM attendance a WHERE a.faculty_fk = f.id) AS students_taught
FROM faculty f
JOIN departments d     ON d.id = f.department_fk
LEFT JOIN faculty_courses fc ON fc.faculty_fk = f.id
LEFT JOIN timetable t  ON t.faculty_fk = f.id AND t.is_active = TRUE
GROUP BY f.id, f.employee_code, f.name, f.designation, d.department_name;

-- ── vw_course_statistics ──────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_course_statistics AS
SELECT
    c.course_code,
    c.course_name,
    c.credits,
    d.department_name,
    c.semester,
    (SELECT COUNT(DISTINCT a.student_fk) FROM attendance a WHERE a.course_fk = c.id) AS enrolled_students,
    (SELECT ROUND(AVG(
        CASE WHEN sub_a.status IN ('present','late') THEN 100.0 ELSE 0.0 END
    ), 2) FROM attendance sub_a WHERE sub_a.course_fk = c.id) AS avg_attendance_pct,
    (SELECT ROUND(AVG(sub_g.final_exam_marks), 2) FROM grades sub_g WHERE sub_g.course_fk = c.id AND sub_g.final_exam_marks IS NOT NULL) AS avg_final_marks,
    (SELECT COUNT(*) FROM grades sub_g2 WHERE sub_g2.course_fk = c.id AND sub_g2.final_grade = 'F') AS fail_count
FROM courses c
JOIN departments d ON d.id = c.department_fk
WHERE c.is_active = TRUE;

-- ── vw_student_risk ───────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_student_risk AS
SELECT
    s.usn,
    s.name          AS student_name,
    d.department_name,
    s.semester,
    s.section,
    att.course_code,
    att.course_name,
    att.attendance_pct,
    CASE
        WHEN att.attendance_pct < 65 THEN 'critical'
        WHEN att.attendance_pct < 75 THEN 'warning'
        ELSE 'safe'
    END AS risk_level
FROM students s
JOIN departments d ON d.id = s.department_fk
JOIN vw_attendance_summary att ON att.usn = s.usn
WHERE att.attendance_pct < 75;

-- ── vw_department_performance ─────────────────────────────────────────
CREATE OR REPLACE VIEW vw_department_performance AS
SELECT
    d.department_code,
    d.department_name,
    (SELECT COUNT(*) FROM students s2 WHERE s2.department_fk = d.id AND s2.status = 'active') AS total_students,
    (SELECT COUNT(*) FROM faculty f2 WHERE f2.department_fk = d.id AND f2.status = 'active') AS total_faculty,
    (SELECT COUNT(*) FROM courses c2 WHERE c2.department_fk = d.id AND c2.is_active = TRUE) AS total_courses,
    (SELECT ROUND(AVG(CASE WHEN sub_a.status IN ('present','late') THEN 100.0 ELSE 0.0 END), 2)
     FROM attendance sub_a
     JOIN students sub_s ON sub_s.id = sub_a.student_fk
     WHERE sub_s.department_fk = d.id) AS avg_attendance_pct,
    (SELECT ROUND(AVG(sub_g.final_exam_marks), 2)
     FROM grades sub_g
     JOIN students sub_s2 ON sub_s2.id = sub_g.student_fk
     WHERE sub_s2.department_fk = d.id AND sub_g.final_exam_marks IS NOT NULL) AS avg_marks
FROM departments d
WHERE d.is_active = TRUE;

-- ── vw_timetable_summary ──────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_timetable_summary AS
SELECT
    t.id,
    f.employee_code,
    f.name          AS faculty_name,
    c.course_code,
    c.course_name,
    d.department_name,
    t.day_of_week,
    t.start_time,
    t.end_time,
    t.room,
    t.section,
    t.semester
FROM timetable t
JOIN faculty f     ON f.id = t.faculty_fk
JOIN courses c     ON c.id = t.course_fk
JOIN departments d ON d.id = c.department_fk
WHERE t.is_active = TRUE;

-- ── vw_faculty_dashboard ──────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_faculty_dashboard AS
SELECT
    f.id            AS faculty_id,
    f.employee_code,
    f.name          AS faculty_name,
    f.designation,
    d.department_name,
    (SELECT COUNT(DISTINCT fc2.course_fk) FROM faculty_courses fc2 WHERE fc2.faculty_fk = f.id) AS courses_count,
    (SELECT COUNT(DISTINCT a2.student_fk) FROM attendance a2 WHERE a2.faculty_fk = f.id) AS students_count,
    (SELECT COUNT(DISTINCT t2.id) FROM timetable t2 WHERE t2.faculty_fk = f.id AND t2.is_active = TRUE) AS weekly_classes,
    (SELECT COUNT(*) FROM announcements ann WHERE ann.faculty_fk = f.id AND ann.is_active = TRUE) AS active_announcements
FROM faculty f
JOIN departments d ON d.id = f.department_fk
WHERE f.status = 'active';
"""


def create_tables():
    """Run the DDL to create all tables, indexes, and views."""
    import re

    def _split_statements(sql_text):
        """Split SQL by semicolons but skip empty/comment-only fragments."""
        parts = sql_text.split(";")
        for part in parts:
            stmt = part.strip()
            # Remove lines that are only comments
            lines = [l for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
            clean = "\n".join(lines).strip()
            if clean:
                yield clean

    try:
        with get_cursor(dict_cursor=False) as cur:
            # Create tables one at a time
            for stmt in _split_statements(SCHEMA_SQL):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    logger.warning(f"Schema statement warning: {e}")

            # Create indexes (ignore errors if they already exist)
            for stmt in _split_statements(INDEX_SQL):
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # Index already exists

            # Create views one at a time
            for stmt in _split_statements(VIEWS_SQL):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    logger.warning(f"View creation warning: {e}")

        # Add HOD FK constraint (may fail if already exists)
        try:
            with get_cursor(dict_cursor=False) as cur:
                cur.execute("""
                    ALTER TABLE departments
                    ADD CONSTRAINT fk_dept_hod FOREIGN KEY (hod_fk) REFERENCES faculty(id) ON DELETE SET NULL
                """)
        except Exception:
            pass  # Constraint already exists

        logger.info("Database tables, indexes, and views created / verified")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


def get_table_info() -> str:
    """Return a human-readable schema summary for AI context.

    This includes table structures AND foreign key relationships
    so the AI tools can understand the data model.
    """
    sql = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    try:
        with get_cursor() as cur:
            from config import AURORA_DATABASE
            cur.execute(sql, (AURORA_DATABASE,))
            rows = cur.fetchall()

        lines = []
        current_table = None
        for row in rows:
            if row['TABLE_NAME'] != current_table:
                current_table = row['TABLE_NAME']
                lines.append(f"\n-- Table: {current_table}")
            key_info = f" [{row['COLUMN_KEY']}]" if row['COLUMN_KEY'] else ""
            nullable = "NULL" if row['IS_NULLABLE'] == 'YES' else "NOT NULL"
            lines.append(f"   {row['COLUMN_NAME']} ({row['DATA_TYPE']}) {nullable}{key_info}")

        schema_str = "\n".join(lines)

        # Explicit FK documentation
        schema_str += "\n\n-- FOREIGN KEY RELATIONSHIPS (column -> referenced_table.column) --\n"
        schema_str += "faculty.department_fk          -> departments.id\n"
        schema_str += "students.department_fk         -> departments.id\n"
        schema_str += "courses.department_fk          -> departments.id\n"
        schema_str += "faculty_courses.faculty_fk     -> faculty.id\n"
        schema_str += "faculty_courses.course_fk      -> courses.id\n"
        schema_str += "attendance.student_fk          -> students.id\n"
        schema_str += "attendance.course_fk           -> courses.id\n"
        schema_str += "attendance.faculty_fk          -> faculty.id\n"
        schema_str += "grades.student_fk              -> students.id\n"
        schema_str += "grades.course_fk               -> courses.id\n"
        schema_str += "grades.faculty_fk              -> faculty.id\n"
        schema_str += "timetable.faculty_fk           -> faculty.id\n"
        schema_str += "timetable.course_fk            -> courses.id\n"
        schema_str += "documents.uploaded_by          -> faculty.id\n"
        schema_str += "departments.hod_fk             -> faculty.id\n"

        # Business identifiers
        schema_str += "\n-- BUSINESS IDENTIFIERS (user-facing, for lookups) --\n"
        schema_str += "students.usn                   = Student USN (e.g., 'CS2021001')\n"
        schema_str += "faculty.employee_code           = Faculty ID (e.g., 'FAC001')\n"
        schema_str += "courses.course_code            = Course code (e.g., 'CS601')\n"
        schema_str += "departments.department_code     = Dept code (e.g., 'CS')\n"

        return schema_str
    except Exception as e:
        logger.error(f"Failed to get table info: {e}")
        return "(Could not fetch schema info)"
