"""
AI ERP Assistant — Database Models & Schema (Aurora MySQL)
============================================================
DDL for all ERP tables + migration helper.
All SQL is MySQL-compatible (Aurora MySQL 8.0+).
"""

import logging
from db.connection import get_cursor

logger = logging.getLogger("erp-assistant")

# ── Schema DDL (MySQL) ─────────────────────────────────────────────────────

SCHEMA_SQL = """
-- ────────────────────────────────────────────────────────────────
-- Faculty
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS faculty (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    employee_id     VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    department      VARCHAR(80) NOT NULL,
    designation     VARCHAR(80) NOT NULL DEFAULT 'Assistant Professor',
    phone           VARCHAR(20),
    joined_at       DATE NOT NULL DEFAULT (CURRENT_DATE),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Courses
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS courses (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    course_code     VARCHAR(20) NOT NULL UNIQUE,
    course_name     VARCHAR(150) NOT NULL,
    department      VARCHAR(80) NOT NULL,
    credits         INT NOT NULL DEFAULT 3,
    semester        INT NOT NULL,
    faculty_id      INT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Students
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    department      VARCHAR(80) NOT NULL,
    semester        INT NOT NULL DEFAULT 1,
    section         VARCHAR(5) DEFAULT 'A',
    phone           VARCHAR(20),
    guardian_phone  VARCHAR(20),
    enrolled_at     DATE NOT NULL DEFAULT (CURRENT_DATE),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Attendance
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attendance (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    course_id       INT NOT NULL,
    date            DATE NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'present',
    marked_by       INT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attendance (student_id, course_id, date),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (marked_by) REFERENCES faculty(id),
    CHECK (status IN ('present', 'absent', 'late', 'excused'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Grades
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grades (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    course_id       INT NOT NULL,
    semester        INT NOT NULL,
    grade           VARCHAR(5) NOT NULL,
    grade_points    DECIMAL(3,1) NOT NULL,
    exam_type       VARCHAR(30) NOT NULL DEFAULT 'final',
    max_marks       INT DEFAULT 100,
    marks_obtained  INT,
    graded_by       INT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_grades (student_id, course_id, exam_type, semester),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (graded_by) REFERENCES faculty(id),
    CHECK (exam_type IN ('midterm', 'final', 'assignment', 'lab', 'project'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Query Log (analytics tracking)
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS query_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    query_text      TEXT NOT NULL,
    query_type      VARCHAR(30) NOT NULL DEFAULT 'general',
    response_text   TEXT,
    response_time_ms INT,
    source          VARCHAR(20) NOT NULL DEFAULT 'text',
    status          VARCHAR(20) NOT NULL DEFAULT 'success',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (query_type IN ('attendance', 'grades', 'schedule', 'documents', 'general', 'faculty')),
    CHECK (source IN ('text', 'voice')),
    CHECK (status IN ('success', 'failed', 'partial'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ────────────────────────────────────────────────────────────────
-- Documents metadata
-- ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    doc_id          VARCHAR(40) NOT NULL UNIQUE,
    filename        VARCHAR(255) NOT NULL,
    file_type       VARCHAR(10) NOT NULL,
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    s3_key          VARCHAR(500) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'processing',
    chunk_count     INT DEFAULT 0,
    uploaded_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('processing', 'processed', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

INDEX_SQL = """
CREATE INDEX idx_attendance_student ON attendance(student_id);
CREATE INDEX idx_attendance_course  ON attendance(course_id);
CREATE INDEX idx_attendance_date    ON attendance(date);
CREATE INDEX idx_grades_student     ON grades(student_id);
CREATE INDEX idx_grades_course      ON grades(course_id);
CREATE INDEX idx_query_log_created  ON query_log(created_at);
CREATE INDEX idx_query_log_type     ON query_log(query_type);
CREATE INDEX idx_documents_status   ON documents(status);
"""


def create_tables():
    """Run the DDL to create all tables."""
    try:
        with get_cursor(dict_cursor=False) as cur:
            # MySQL requires executing statements one at a time
            for statement in SCHEMA_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)

            # Create indexes (ignore errors if they already exist)
            for statement in INDEX_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                    except Exception:
                        pass  # Index already exists

        logger.info("Database tables created / verified")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


def get_table_info() -> str:
    """Return a human-readable summary of tables and columns for LLM context."""
    sql = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
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
            nullable = "NULL" if row['IS_NULLABLE'] == 'YES' else "NOT NULL"
            lines.append(f"   {row['COLUMN_NAME']} ({row['DATA_TYPE']}) {nullable}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get table info: {e}")
        return "(Could not fetch schema info)"
