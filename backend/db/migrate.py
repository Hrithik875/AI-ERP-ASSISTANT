"""
AI ERP Assistant — Database Migration Script
===============================================
Drops the old schema and creates the new enterprise-grade schema.
Run this ONCE to migrate from the old naming to the new _fk convention.

Usage:
    cd backend
    python -m db.migrate
"""

import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import logger, AURORA_DATABASE
from db.connection import get_cursor, execute_query

# Old tables to drop (in dependency order — children first)
OLD_TABLES = [
    "query_log",
    "documents",
    "announcements",
    "timetable",
    "grades",
    "attendance",
    "students",
    "courses",
    "faculty",
    "departments",
    # New tables too, in case of re-run
    "query_logs",
    "faculty_courses",
]

# Views to drop
OLD_VIEWS = [
    "vw_student_profile",
    "vw_attendance_summary",
    "vw_grade_summary",
    "vw_faculty_workload",
    "vw_course_statistics",
    "vw_student_risk",
    "vw_department_performance",
    "vw_timetable_summary",
    "vw_faculty_dashboard",
]


def drop_all():
    """Drop all old tables and views."""
    logger.info("=" * 60)
    logger.info("MIGRATION: Dropping old schema...")

    with get_cursor(dict_cursor=False) as cur:
        # Disable FK checks during drop
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        for view in OLD_VIEWS:
            try:
                cur.execute(f"DROP VIEW IF EXISTS `{view}`")
                logger.info(f"  Dropped view: {view}")
            except Exception:
                pass

        for table in OLD_TABLES:
            try:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                logger.info(f"  Dropped table: {table}")
            except Exception as e:
                logger.warning(f"  Could not drop {table}: {e}")

        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    logger.info("Old schema dropped successfully.")


def create_new_schema():
    """Create new enterprise schema + views."""
    from db.models import create_tables
    logger.info("MIGRATION: Creating new enterprise schema...")
    create_tables()
    logger.info("New schema created successfully.")


def seed_new_data():
    """Seed the database with realistic data."""
    from db.seed import seed_database
    logger.info("MIGRATION: Seeding database with realistic data...")
    seed_database()
    logger.info("Database seeded successfully.")


def validate_schema():
    """Validate all foreign key relationships and report orphan counts."""
    logger.info("MIGRATION: Validating schema integrity...")

    checks = [
        ("faculty → departments", "SELECT COUNT(*) AS cnt FROM faculty f LEFT JOIN departments d ON d.id = f.department_fk WHERE d.id IS NULL"),
        ("students → departments", "SELECT COUNT(*) AS cnt FROM students s LEFT JOIN departments d ON d.id = s.department_fk WHERE d.id IS NULL"),
        ("courses → departments", "SELECT COUNT(*) AS cnt FROM courses c LEFT JOIN departments d ON d.id = c.department_fk WHERE d.id IS NULL"),
        ("attendance → students", "SELECT COUNT(*) AS cnt FROM attendance a LEFT JOIN students s ON s.id = a.student_fk WHERE s.id IS NULL"),
        ("attendance → courses", "SELECT COUNT(*) AS cnt FROM attendance a LEFT JOIN courses c ON c.id = a.course_fk WHERE c.id IS NULL"),
        ("attendance → faculty", "SELECT COUNT(*) AS cnt FROM attendance a LEFT JOIN faculty f ON f.id = a.faculty_fk WHERE a.faculty_fk IS NOT NULL AND f.id IS NULL"),
        ("grades → students", "SELECT COUNT(*) AS cnt FROM grades g LEFT JOIN students s ON s.id = g.student_fk WHERE s.id IS NULL"),
        ("grades → courses", "SELECT COUNT(*) AS cnt FROM grades g LEFT JOIN courses c ON c.id = g.course_fk WHERE c.id IS NULL"),
        ("timetable → faculty", "SELECT COUNT(*) AS cnt FROM timetable t LEFT JOIN faculty f ON f.id = t.faculty_fk WHERE f.id IS NULL"),
        ("timetable → courses", "SELECT COUNT(*) AS cnt FROM timetable t LEFT JOIN courses c ON c.id = t.course_fk WHERE c.id IS NULL"),
        ("faculty_courses → faculty", "SELECT COUNT(*) AS cnt FROM faculty_courses fc LEFT JOIN faculty f ON f.id = fc.faculty_fk WHERE f.id IS NULL"),
        ("faculty_courses → courses", "SELECT COUNT(*) AS cnt FROM faculty_courses fc LEFT JOIN courses c ON c.id = fc.course_fk WHERE c.id IS NULL"),
    ]

    all_ok = True
    for label, sql in checks:
        result = execute_query(sql)
        orphans = result[0]["cnt"] if result else -1
        status = "✓" if orphans == 0 else "✗ ORPHANS"
        if orphans > 0:
            all_ok = False
        logger.info(f"  {status} {label}: {orphans} orphan(s)")

    # Report counts
    tables = ["departments", "faculty", "students", "courses", "faculty_courses",
              "attendance", "grades", "timetable", "announcements", "documents", "query_logs"]
    logger.info("\n  Table Row Counts:")
    for table in tables:
        try:
            result = execute_query(f"SELECT COUNT(*) AS cnt FROM `{table}`")
            count = result[0]["cnt"] if result else 0
            logger.info(f"    {table}: {count:,}")
        except Exception:
            logger.info(f"    {table}: (not found)")

    if all_ok:
        logger.info("\n  ✓ All FK relationships are valid. Zero orphan records.")
    else:
        logger.error("\n  ✗ Some FK relationships have orphan records!")

    return all_ok


def run_migration():
    """Full migration: drop → create → seed → validate."""
    logger.info("=" * 60)
    logger.info("AI ERP Assistant — Database Migration")
    logger.info(f"Target Database: {AURORA_DATABASE}")
    logger.info("=" * 60)

    drop_all()
    create_new_schema()
    seed_new_data()
    ok = validate_schema()

    logger.info("=" * 60)
    if ok:
        logger.info("MIGRATION COMPLETE — All checks passed!")
    else:
        logger.error("MIGRATION COMPLETE — Some validation errors detected.")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_migration()
