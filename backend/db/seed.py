"""
AI ERP Assistant — Database Seeder (Aurora MySQL)
==================================================
Populates the database with 100 realistic students + full ERP data.
MySQL-compatible SQL throughout.
"""

import logging
import random
from datetime import date, timedelta

from db.connection import get_cursor, execute_query

logger = logging.getLogger("erp-assistant")

# ── Faculty Data ─────────────────────────────────────────────────────────────

FACULTY_DATA = [
    ("FAC001", "Dr. Raghav Sharma",    "raghav.sharma@bmsce.ac.in",    "Computer Science",       "Professor",            "+91-9900001001"),
    ("FAC002", "Dr. Priya Nair",       "priya.nair@bmsce.ac.in",       "Computer Science",       "Associate Professor",  "+91-9900001002"),
    ("FAC003", "Prof. Anil Kumar",     "anil.kumar@bmsce.ac.in",       "Computer Science",       "Assistant Professor",  "+91-9900001003"),
    ("FAC004", "Dr. Meena Rao",        "meena.rao@bmsce.ac.in",        "Computer Science",       "Professor",            "+91-9900001004"),
    ("FAC005", "Prof. Suresh Reddy",   "suresh.reddy@bmsce.ac.in",     "Computer Science",       "Assistant Professor",  "+91-9900001005"),
    ("FAC006", "Dr. Kavitha Iyer",     "kavitha.iyer@bmsce.ac.in",     "Information Science",    "Associate Professor",  "+91-9900001006"),
    ("FAC007", "Prof. Deepak Joshi",   "deepak.joshi@bmsce.ac.in",     "Information Science",    "Assistant Professor",  "+91-9900001007"),
    ("FAC008", "Dr. Lakshmi Venkat",   "lakshmi.venkat@bmsce.ac.in",   "Electronics",            "Professor",            "+91-9900001008"),
    ("FAC009", "Prof. Rajan Pillai",   "rajan.pillai@bmsce.ac.in",     "Electronics",            "Assistant Professor",  "+91-9900001009"),
    ("FAC010", "Dr. Sunita Bhat",      "sunita.bhat@bmsce.ac.in",      "Mechanical",             "Associate Professor",  "+91-9900001010"),
]

# ── Courses Data ─────────────────────────────────────────────────────────────

COURSES_DATA = [
    ("CS601", "Machine Learning",                "Computer Science",    4, 6, "FAC001"),
    ("CS602", "Computer Networks",               "Computer Science",    3, 6, "FAC002"),
    ("CS603", "Database Management Systems",     "Computer Science",    4, 6, "FAC003"),
    ("CS604", "Operating Systems",               "Computer Science",    4, 6, "FAC004"),
    ("CS605", "Software Engineering",            "Computer Science",    3, 6, "FAC005"),
    ("CS501", "Data Structures & Algorithms",    "Computer Science",    4, 5, "FAC003"),
    ("CS502", "Theory of Computation",           "Computer Science",    3, 5, "FAC004"),
    ("CS503", "Microprocessors & Interfaces",    "Computer Science",    3, 5, "FAC008"),
    ("IS601", "Information Security",            "Information Science", 3, 6, "FAC006"),
    ("IS501", "Web Technologies",                "Information Science", 3, 5, "FAC007"),
]

# ── 100 Students ─────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Akshay", "Amith", "Ananya", "Anjali", "Ankit",
    "Arjun", "Aryan", "Ashish", "Bhavya", "Chinmay", "Deepak", "Deepika",
    "Dhruv", "Divya", "Gaurav", "Gopal", "Harish", "Hemanth", "Hrithik",
    "Ishaan", "Ishita", "Jatin", "Kavitha", "Keerthi", "Kiran", "Kriti",
    "Lakshmi", "Lavanya", "Lokesh", "Madhav", "Manish", "Megha", "Mohammed",
    "Mohan", "Mrudula", "Naresh", "Naveen", "Nidhi", "Nikitha", "Nikhil",
    "Pallavi", "Pooja", "Pradeep", "Pranav", "Preethi", "Priya", "Rahul",
    "Rajan", "Ramesh", "Ravi", "Riya", "Rohit", "Roshan", "Ruchika",
    "Sachin", "Sahana", "Sanjay", "Sanket", "Santosh", "Sarath", "Shaheen",
    "Shashank", "Sheetal", "Shivam", "Shreya", "Shruthi", "Sidharth",
    "Smitha", "Sneha", "Sourabh", "Sreedhar", "Srinivas", "Suhas", "Sunil",
    "Supriya", "Swathi", "Tanmay", "Tejas", "Uday", "Uma", "Varun",
    "Vedant", "Vidya", "Vikram", "Vinay", "Vishal", "Vivek", "Yamini",
    "Yashas", "Yashwant", "Yogesh", "Zara", "Adwi", "Karthik", "Divyanka",
    "Mohammed Irfan"
]

LAST_NAMES = [
    "M", "S", "K", "R", "N", "P", "Sharma", "Nair", "Kumar", "Rao",
    "Reddy", "Iyer", "Joshi", "Venkat", "Pillai", "Bhat", "Patil",
    "Desai", "Menon", "Gupta", "Singh", "Hegde", "Shetty", "Kamat",
    "Gowda", "Murthy", "Swamy", "Naik", "Verma", "Patel", "Shah",
    "Jain", "Mehta", "Kulkarni", "Mishra", "Prasad", "Chandra", "Sinha",
    "Das", "Ghosh"
]

DEPARTMENTS = [
    ("Computer Science",    "CS"),
    ("Information Science", "IS"),
    ("Electronics",         "EC"),
    ("Mechanical",          "ME"),
]

GRADE_SCALE = {
    "S":  10.0, "A+": 9.0, "A": 8.5, "B+": 8.0,
    "B":  7.0,  "C+": 6.0, "C": 5.5, "D":  5.0, "F": 0.0,
}
GRADE_WEIGHTS = [5, 20, 25, 20, 15, 8, 4, 2, 1]   # S rare, A/A+ common


def _make_students(count: int = 100):
    """
    Generate `count` unique students deterministically.
    Returns list of (student_id, name, email, dept, semester, section).
    """
    students = []
    used_names = set()

    dept_dist = [
        ("Computer Science", "CS", 5),
        ("Computer Science", "CS", 6),
        ("Information Science", "IS", 5),
        ("Information Science", "IS", 6),
        ("Electronics", "EC", 5),
        ("Electronics", "EC", 6),
        ("Mechanical", "ME", 5),
        ("Mechanical", "ME", 6),
    ]

    # Fixed 100 students across departments / semesters
    records = [
        # CS Sem 6 — 30 students
        *[("Computer Science", "CS", 6)] * 30,
        # CS Sem 5 — 20 students
        *[("Computer Science", "CS", 5)] * 20,
        # IS Sem 6 — 15 students
        *[("Information Science", "IS", 6)] * 15,
        # IS Sem 5 — 10 students
        *[("Information Science", "IS", 5)] * 10,
        # EC Sem 6 — 15 students
        *[("Electronics", "EC", 6)] * 15,
        # ME Sem 5 — 10 students
        *[("Mechanical", "ME", 5)] * 10,
    ]

    sections = ["A", "B", "C"]
    random.seed(42)  # deterministic

    first_names_pool = FIRST_NAMES * 2   # ensure enough names
    last_names_pool = LAST_NAMES * 5

    for idx, (dept, code, sem) in enumerate(records[:count]):
        i = idx + 1
        # Pick a unique name
        attempt = 0
        while True:
            fn = first_names_pool[(idx + attempt * 7) % len(first_names_pool)]
            ln = last_names_pool[(idx + attempt * 13) % len(last_names_pool)]
            full_name = f"{fn} {ln}" if ln not in ("M", "S", "K", "R", "N", "P") else f"{fn} {ln}"
            if full_name not in used_names:
                used_names.add(full_name)
                break
            attempt += 1

        year = 2021 + (6 - sem) // 2  # approximate enrollment year
        student_id = f"{code}{year}{i:03d}"
        email_first = fn.lower().replace(" ", ".")
        email = f"{email_first}.{year}{i:03d}@bmsce.ac.in"
        section = sections[idx % len(sections)]

        students.append((student_id, full_name, email, dept, sem, section))

    return students


def seed_database():
    """Seed all tables with demo data. Skips if data already exists."""
    try:
        # Check if already seeded
        existing = execute_query("SELECT COUNT(*) as cnt FROM students")
        if existing and existing[0]["cnt"] > 0:
            logger.info(f"Database already seeded ({existing[0]['cnt']} students). Skipping.")
            return

        logger.info("Seeding database with 100 student demo data...")

        students_data = _make_students(100)

        with get_cursor(dict_cursor=False) as cur:

            # ── Faculty ───────────────────────────────────────────────────
            for emp_id, name, email, dept, designation, phone in FACULTY_DATA:
                cur.execute(
                    """INSERT IGNORE INTO faculty
                       (employee_id, name, email, department, designation, phone)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (emp_id, name, email, dept, designation, phone),
                )

            # ── Courses ───────────────────────────────────────────────────
            for code, name, dept, credits, sem, fac_emp_id in COURSES_DATA:
                cur.execute(
                    """INSERT IGNORE INTO courses
                       (course_code, course_name, department, credits, semester, faculty_id)
                       VALUES (%s, %s, %s, %s, %s,
                               (SELECT id FROM faculty WHERE employee_id = %s))""",
                    (code, name, dept, credits, sem, fac_emp_id),
                )

            # ── Students ──────────────────────────────────────────────────
            for sid, name, email, dept, sem, sec in students_data:
                cur.execute(
                    """INSERT IGNORE INTO students
                       (student_id, name, email, department, semester, section)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (sid, name, email, dept, sem, sec),
                )

            # ── Attendance (last 30 weekdays) ─────────────────────────────
            today = date.today()

            cur.execute("SELECT id FROM courses WHERE semester = 6")
            course_ids = [r[0] for r in cur.fetchall()]

            cur.execute("SELECT id FROM students WHERE semester = 6")
            student_ids = [r[0] for r in cur.fetchall()]

            random.seed(99)
            for day_offset in range(45):        # enough to get 30 weekdays
                d = today - timedelta(days=day_offset)
                if d.weekday() >= 5:            # skip weekends
                    continue
                for sid in student_ids:
                    for cid in course_ids:
                        r = random.random()
                        if r < 0.85:
                            status = "present"
                        elif r < 0.93:
                            status = "absent"
                        elif r < 0.97:
                            status = "late"
                        else:
                            status = "excused"

                        cur.execute(
                            """INSERT IGNORE INTO attendance
                               (student_id, course_id, date, status)
                               VALUES (%s, %s, %s, %s)""",
                            (sid, cid, d.isoformat(), status),
                        )

            # ── Grades ────────────────────────────────────────────────────
            grades_list = list(GRADE_SCALE.keys())

            cur.execute("SELECT id FROM courses")
            all_course_ids = [r[0] for r in cur.fetchall()]

            # Fetch all student IDs for grading (all semesters)
            cur.execute("SELECT id FROM students")
            all_student_ids = [r[0] for r in cur.fetchall()]

            for sid in all_student_ids:
                for cid in all_course_ids:
                    g = random.choices(grades_list, weights=GRADE_WEIGHTS, k=1)[0]
                    gp = GRADE_SCALE[g]
                    marks = int(gp * 10) + random.randint(-5, 5)
                    marks = max(0, min(100, marks))

                    cur.execute(
                        """INSERT IGNORE INTO grades
                           (student_id, course_id, semester, grade,
                            grade_points, exam_type, marks_obtained)
                           VALUES (%s, %s, 6, %s, %s, 'final', %s)""",
                        (sid, cid, g, gp, marks),
                    )

        logger.info(f"Database seeding completed: {len(students_data)} students, "
                    f"{len(FACULTY_DATA)} faculty, {len(COURSES_DATA)} courses.")

    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        raise
