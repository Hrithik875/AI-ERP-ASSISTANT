"""
AI ERP Assistant — Database Seeder (Enterprise)
==================================================
Generates realistic ERP data with full referential integrity.

Scale:
  - 5 departments
  - 50 faculty (10 per dept)
  - 1000 students (200 per dept, semesters 1-8)
  - 40 courses (8 per dept)
  - Faculty-course mappings
  - 30 days attendance records
  - Grade records (IA1, IA2, IA3, final exam)
  - Full timetable
  - 20 announcements

All FK relationships are guaranteed valid.
"""

import logging
import random
from datetime import date, timedelta, datetime, time
from db.connection import get_cursor, execute_query

logger = logging.getLogger("erp-assistant")

# ── DEPARTMENT DATA ──────────────────────────────────────────────────────────

DEPARTMENTS = [
    ("CS", "Computer Science"),
    ("IS", "Information Science"),
    ("EC", "Electronics & Communication"),
    ("ME", "Mechanical Engineering"),
    ("CV", "Civil Engineering"),
]

# ── FACULTY DATA (10 per department = 50 total) ─────────────────────────────

FACULTY_TEMPLATES = {
    "CS": [
        ("FAC001", "Dr. Raghav Sharma",      "Professor",            "raghav.sharma"),
        ("FAC002", "Dr. Priya Nair",          "Associate Professor",  "priya.nair"),
        ("FAC003", "Prof. Anil Kumar",        "Assistant Professor",  "anil.kumar"),
        ("FAC004", "Dr. Meena Rao",           "Professor",            "meena.rao"),
        ("FAC005", "Prof. Suresh Reddy",      "Assistant Professor",  "suresh.reddy"),
        ("FAC006", "Dr. Karthik Hegde",       "Associate Professor",  "karthik.hegde"),
        ("FAC007", "Prof. Divya Kulkarni",    "Assistant Professor",  "divya.kulkarni"),
        ("FAC008", "Dr. Naveen Prasad",       "Professor",            "naveen.prasad"),
        ("FAC009", "Prof. Rashmi Patil",      "Assistant Professor",  "rashmi.patil"),
        ("FAC010", "Dr. Venkatesh Murthy",    "Associate Professor",  "venkatesh.murthy"),
    ],
    "IS": [
        ("FAC011", "Dr. Kavitha Iyer",        "Professor",            "kavitha.iyer"),
        ("FAC012", "Prof. Deepak Joshi",      "Associate Professor",  "deepak.joshi"),
        ("FAC013", "Dr. Swathi Menon",        "Assistant Professor",  "swathi.menon"),
        ("FAC014", "Prof. Harish Naik",       "Professor",            "harish.naik"),
        ("FAC015", "Dr. Pallavi Shetty",      "Assistant Professor",  "pallavi.shetty"),
        ("FAC016", "Prof. Manoj Desai",       "Associate Professor",  "manoj.desai"),
        ("FAC017", "Dr. Lakshmi Bhat",        "Assistant Professor",  "lakshmi.bhat"),
        ("FAC018", "Prof. Sachin Verma",      "Professor",            "sachin.verma"),
        ("FAC019", "Dr. Anitha Kamat",        "Assistant Professor",  "anitha.kamat"),
        ("FAC020", "Prof. Rajan Pillai",      "Associate Professor",  "rajan.pillai"),
    ],
    "EC": [
        ("FAC021", "Dr. Lakshmi Venkat",      "Professor",            "lakshmi.venkat"),
        ("FAC022", "Prof. Ashok Gowda",       "Associate Professor",  "ashok.gowda"),
        ("FAC023", "Dr. Sneha Chandra",       "Assistant Professor",  "sneha.chandra"),
        ("FAC024", "Prof. Ramesh Swamy",      "Professor",            "ramesh.swamy"),
        ("FAC025", "Dr. Pooja Mehta",         "Assistant Professor",  "pooja.mehta"),
        ("FAC026", "Prof. Vikram Singh",      "Associate Professor",  "vikram.singh"),
        ("FAC027", "Dr. Nidhi Ghosh",         "Assistant Professor",  "nidhi.ghosh"),
        ("FAC028", "Prof. Sanjay Das",        "Professor",            "sanjay.das"),
        ("FAC029", "Dr. Keerthi Shah",        "Assistant Professor",  "keerthi.shah"),
        ("FAC030", "Prof. Mohan Jain",        "Associate Professor",  "mohan.jain"),
    ],
    "ME": [
        ("FAC031", "Dr. Sunita Bhat",         "Professor",            "sunita.bhat"),
        ("FAC032", "Prof. Gopal Mishra",      "Associate Professor",  "gopal.mishra"),
        ("FAC033", "Dr. Tanmay Patel",        "Assistant Professor",  "tanmay.patel"),
        ("FAC034", "Prof. Uday Sinha",        "Professor",            "uday.sinha"),
        ("FAC035", "Dr. Vidya Gupta",         "Assistant Professor",  "vidya.gupta"),
        ("FAC036", "Prof. Shreyas Rao",       "Associate Professor",  "shreyas.rao"),
        ("FAC037", "Dr. Megha Kulkarni",      "Assistant Professor",  "megha.kulkarni"),
        ("FAC038", "Prof. Lokesh Patil",      "Professor",            "lokesh.patil"),
        ("FAC039", "Dr. Ishita Naik",         "Assistant Professor",  "ishita.naik"),
        ("FAC040", "Prof. Chinmay Hegde",     "Associate Professor",  "chinmay.hegde"),
    ],
    "CV": [
        ("FAC041", "Dr. Arjun Reddy",         "Professor",            "arjun.reddy"),
        ("FAC042", "Prof. Sanket Verma",      "Associate Professor",  "sanket.verma"),
        ("FAC043", "Dr. Ruchika Sharma",      "Assistant Professor",  "ruchika.sharma"),
        ("FAC044", "Prof. Shashank Bhat",     "Professor",            "shashank.bhat"),
        ("FAC045", "Dr. Yamini Prasad",       "Assistant Professor",  "yamini.prasad"),
        ("FAC046", "Prof. Tejas Murthy",      "Associate Professor",  "tejas.murthy"),
        ("FAC047", "Dr. Uma Rao",             "Assistant Professor",  "uma.rao"),
        ("FAC048", "Prof. Vivek Naik",        "Professor",            "vivek.naik"),
        ("FAC049", "Dr. Zara Iyer",           "Assistant Professor",  "zara.iyer"),
        ("FAC050", "Prof. Adwi Menon",        "Associate Professor",  "adwi.menon"),
    ],
}

# ── COURSES DATA (8 per department = 40 total) ──────────────────────────────

COURSES_BY_DEPT = {
    "CS": [
        ("CS601", "Machine Learning",              4, 6),
        ("CS602", "Computer Networks",              3, 6),
        ("CS603", "Database Management Systems",    4, 6),
        ("CS604", "Operating Systems",              4, 6),
        ("CS501", "Data Structures & Algorithms",   4, 5),
        ("CS502", "Theory of Computation",          3, 5),
        ("CS401", "Object Oriented Programming",    3, 4),
        ("CS301", "Discrete Mathematics",           3, 3),
    ],
    "IS": [
        ("IS601", "Information Security",           3, 6),
        ("IS602", "Cloud Computing",                3, 6),
        ("IS603", "Big Data Analytics",             4, 6),
        ("IS604", "Software Testing",               3, 6),
        ("IS501", "Web Technologies",               3, 5),
        ("IS502", "Computer Graphics",              3, 5),
        ("IS401", "Java Programming",               3, 4),
        ("IS301", "Digital Logic Design",           3, 3),
    ],
    "EC": [
        ("EC601", "VLSI Design",                    4, 6),
        ("EC602", "Digital Signal Processing",      3, 6),
        ("EC603", "Embedded Systems",               4, 6),
        ("EC604", "Control Systems",                3, 6),
        ("EC501", "Analog Electronics",             4, 5),
        ("EC502", "Microprocessors",                3, 5),
        ("EC401", "Network Analysis",               3, 4),
        ("EC301", "Electronic Devices",             3, 3),
    ],
    "ME": [
        ("ME601", "Finite Element Analysis",        4, 6),
        ("ME602", "Heat Transfer",                  3, 6),
        ("ME603", "Machine Design",                 4, 6),
        ("ME604", "Manufacturing Technology",       3, 6),
        ("ME501", "Fluid Mechanics",                4, 5),
        ("ME502", "Thermodynamics",                 3, 5),
        ("ME401", "Strength of Materials",          3, 4),
        ("ME301", "Engineering Mechanics",          3, 3),
    ],
    "CV": [
        ("CV601", "Structural Analysis",            4, 6),
        ("CV602", "Geotechnical Engineering",       3, 6),
        ("CV603", "Transportation Engineering",     4, 6),
        ("CV604", "Environmental Engineering",      3, 6),
        ("CV501", "Surveying",                      4, 5),
        ("CV502", "Building Materials",             3, 5),
        ("CV401", "Hydraulics",                     3, 4),
        ("CV301", "Engineering Drawing",            3, 3),
    ],
}

# ── STUDENT NAME POOLS ───────────────────────────────────────────────────────

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
    "Irfan", "Aditya", "Nandini", "Pavan", "Chaitra", "Darshan", "Gagan",
    "Hamsa", "Jayanth", "Kushal", "Likhitha", "Manoj", "Nishant", "Omkar",
    "Pushpa", "Rakesh", "Sagar", "Tanya", "Usha", "Vaibhav", "Waqar",
    "Yuvraj", "Zoya", "Abhishek", "Bhoomika", "Chandana", "Deeksha",
]

LAST_NAMES = [
    "M", "S", "K", "R", "N", "P", "Sharma", "Nair", "Kumar", "Rao",
    "Reddy", "Iyer", "Joshi", "Venkat", "Pillai", "Bhat", "Patil",
    "Desai", "Menon", "Gupta", "Singh", "Hegde", "Shetty", "Kamat",
    "Gowda", "Murthy", "Swamy", "Naik", "Verma", "Patel", "Shah",
    "Jain", "Mehta", "Kulkarni", "Mishra", "Prasad", "Chandra", "Sinha",
    "Das", "Ghosh", "Nayak", "Srinivasan", "Subramanian", "Raman",
]

GRADE_SCALE = {"S": 10.0, "A+": 9.0, "A": 8.5, "B+": 8.0, "B": 7.0, "C+": 6.0, "C": 5.5, "D": 5.0, "F": 0.0}
GRADE_WEIGHTS = [5, 15, 25, 20, 15, 10, 5, 3, 2]  # S rare, A/A+ common

ANNOUNCEMENT_TEMPLATES = [
    ("Mid-Semester Exam Schedule Released", "The mid-semester examination schedule has been published. Please check the notice board and departmental website.", "high"),
    ("Assignment Submission Deadline Extended", "Due to multiple requests, the deadline for Assignment 3 has been extended by one week.", "normal"),
    ("Guest Lecture on AI in Healthcare", "A guest lecture on 'Applications of AI in Healthcare' will be held in the Seminar Hall.", "normal"),
    ("Lab Equipment Maintenance Notice", "The lab will be closed for maintenance. Lab sessions will be rescheduled.", "high"),
    ("Workshop on Cloud Computing", "A two-day workshop on AWS Cloud Computing will be conducted. Registration is open.", "normal"),
    ("Semester Project Submission Guidelines", "All semester projects must be submitted in the prescribed format.", "urgent"),
    ("Library Hours Extended During Exams", "The central library will remain open until 10:00 PM during examinations.", "low"),
    ("Placement Drive Notification", "Company XYZ will be visiting campus for recruitment. Register on the placement portal.", "high"),
    ("Sports Day Announcement", "Annual sports day will be held next Friday. All students are encouraged to participate.", "normal"),
    ("Cultural Fest Registration Open", "Registration for the annual cultural fest is now open. Submit entries before the deadline.", "normal"),
    ("Research Paper Submission Call", "Faculty members are invited to submit research papers for the upcoming conference.", "high"),
    ("Hostel Fee Payment Reminder", "Hostel fee for the current semester must be paid before the end of this month.", "urgent"),
    ("Department Meeting Scheduled", "A department meeting has been scheduled for all faculty members.", "normal"),
    ("New Elective Courses Available", "New elective courses have been added for the upcoming semester. Check the catalog.", "normal"),
    ("Lab Safety Guidelines Updated", "Updated lab safety guidelines have been published. All students must review them.", "high"),
    ("Parent-Teacher Meeting Date", "The Parent-Teacher meeting is scheduled for next Saturday.", "normal"),
    ("Scholarship Application Deadline", "Applications for merit-based scholarships close next week.", "high"),
    ("Campus Wi-Fi Upgrade Notice", "Campus Wi-Fi infrastructure will be upgraded. Expect intermittent connectivity.", "low"),
    ("Internship Opportunities Posted", "New internship opportunities have been posted on the placement portal.", "normal"),
    ("End Semester Exam Timetable", "The end-semester examination timetable has been finalized and published.", "urgent"),
]


def _generate_students(dept_code: str, dept_id: int, count: int = 200):
    """Generate students for a single department across semesters 1-8."""
    random.seed(hash(dept_code) + 42)
    students = []
    used_names = set()
    sections = ["A", "B", "C"]

    # Distribute across semesters: more in upper semesters
    sem_distribution = {
        3: 20, 4: 25, 5: 35, 6: 40, 7: 40, 8: 40
    }
    # Fill remaining to reach count
    total_assigned = sum(sem_distribution.values())
    if total_assigned < count:
        sem_distribution[6] += (count - total_assigned)

    idx = 0
    for sem, sem_count in sorted(sem_distribution.items()):
        year = 2021 + (8 - sem) // 2
        for j in range(sem_count):
            idx += 1
            # Pick unique name
            attempt = 0
            while True:
                fn = FIRST_NAMES[(idx + attempt * 7) % len(FIRST_NAMES)]
                ln = LAST_NAMES[(idx + attempt * 13) % len(LAST_NAMES)]
                full_name = f"{fn} {ln}"
                if full_name not in used_names:
                    used_names.add(full_name)
                    break
                attempt += 1

            usn = f"{dept_code}{year}{idx:03d}"
            email_name = fn.lower().replace(" ", ".")
            email = f"{email_name}.{dept_code.lower()}{year}{idx:03d}@bmsce.ac.in"
            section = sections[idx % len(sections)]

            students.append((usn, full_name, email, dept_id, sem, section))

    return students


def seed_database():
    """Seed all tables with realistic demo data. Skips if data already exists."""
    try:
        # Check if already seeded
        try:
            existing = execute_query("SELECT COUNT(*) AS cnt FROM students")
            if existing and existing[0]["cnt"] > 0:
                logger.info(f"Database already seeded ({existing[0]['cnt']} students). Skipping.")
                return
        except Exception:
            pass  # Table may not exist yet

        logger.info("Seeding database with enterprise demo data...")

        with get_cursor(dict_cursor=False) as cur:

            # ── DEPARTMENTS ──────────────────────────────────────────────
            dept_ids = {}
            for code, name in DEPARTMENTS:
                cur.execute(
                    """INSERT IGNORE INTO departments (department_code, department_name)
                       VALUES (%s, %s)""",
                    (code, name),
                )
            # Fetch IDs
            cur.execute("SELECT id, department_code FROM departments")
            for row in cur.fetchall():
                dept_ids[row[1]] = row[0]

            # ── FACULTY ──────────────────────────────────────────────────
            faculty_ids = {}  # employee_code -> id
            for dept_code, faculty_list in FACULTY_TEMPLATES.items():
                dept_id = dept_ids[dept_code]
                for emp_code, name, designation, email_prefix in faculty_list:
                    cur.execute(
                        """INSERT IGNORE INTO faculty
                           (employee_code, name, email, phone, department_fk, designation)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (emp_code, name, f"{email_prefix}@bmsce.ac.in",
                         f"+91-99000{int(emp_code[3:]):05d}", dept_id, designation),
                    )
            # Fetch IDs
            cur.execute("SELECT id, employee_code FROM faculty")
            for row in cur.fetchall():
                faculty_ids[row[1]] = row[0]

            # Set HODs (first professor in each dept)
            for dept_code in DEPARTMENTS:
                code = dept_code[0]
                hod_list = FACULTY_TEMPLATES[code]
                hod_emp_code = hod_list[0][0]
                if hod_emp_code in faculty_ids:
                    cur.execute(
                        "UPDATE departments SET hod_fk = %s WHERE department_code = %s",
                        (faculty_ids[hod_emp_code], code),
                    )

            # ── COURSES ──────────────────────────────────────────────────
            course_ids = {}  # course_code -> id
            for dept_code, courses in COURSES_BY_DEPT.items():
                dept_id = dept_ids[dept_code]
                for code, name, credits, sem in courses:
                    cur.execute(
                        """INSERT IGNORE INTO courses
                           (course_code, course_name, credits, department_fk, semester)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (code, name, credits, dept_id, sem),
                    )
            # Fetch IDs
            cur.execute("SELECT id, course_code FROM courses")
            for row in cur.fetchall():
                course_ids[row[1]] = row[0]

            # ── FACULTY_COURSES MAPPING ──────────────────────────────────
            for dept_code, faculty_list in FACULTY_TEMPLATES.items():
                courses = COURSES_BY_DEPT[dept_code]
                for i, (emp_code, _, _, _) in enumerate(faculty_list):
                    # Each faculty teaches 1-2 courses
                    assigned_courses = [courses[i % len(courses)]]
                    if i < len(courses) and len(courses) > len(faculty_list):
                        # Extra course for some faculty
                        extra_idx = (i + len(faculty_list)) % len(courses)
                        if extra_idx != i % len(courses):
                            assigned_courses.append(courses[extra_idx])

                    for c_code, _, _, c_sem in assigned_courses:
                        if emp_code in faculty_ids and c_code in course_ids:
                            cur.execute(
                                """INSERT IGNORE INTO faculty_courses
                                   (faculty_fk, course_fk, academic_year, semester, section)
                                   VALUES (%s, %s, '2025-26', %s, 'A')""",
                                (faculty_ids[emp_code], course_ids[c_code], c_sem),
                            )

            # ── STUDENTS ─────────────────────────────────────────────────
            all_students = []  # (usn, name, email, dept_id, sem, section)
            student_ids = {}  # usn -> id

            for dept_code, dept_name in DEPARTMENTS:
                dept_id = dept_ids[dept_code]
                dept_students = _generate_students(dept_code, dept_id, 200)
                all_students.extend(dept_students)

            for usn, name, email, dept_id, sem, section in all_students:
                cur.execute(
                    """INSERT IGNORE INTO students
                       (usn, name, email, department_fk, semester, section)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (usn, name, email, dept_id, sem, section),
                )

            # Fetch IDs
            cur.execute("SELECT id, usn, semester, department_fk FROM students")
            student_rows = cur.fetchall()
            for row in student_rows:
                student_ids[row[1]] = (row[0], row[2], row[3])  # id, semester, dept_fk

            # ── ATTENDANCE (30 weekdays) ─────────────────────────────────
            logger.info("  Generating attendance records (this may take a moment)...")
            today = date.today()
            random.seed(99)

            # Build a map: course_code -> faculty_fk (who teaches it)
            course_faculty = {}
            for dept_code, faculty_list in FACULTY_TEMPLATES.items():
                courses = COURSES_BY_DEPT[dept_code]
                for i, (emp_code, _, _, _) in enumerate(faculty_list):
                    c_code = courses[i % len(courses)][0]
                    if emp_code in faculty_ids:
                        course_faculty[c_code] = faculty_ids[emp_code]

            # For each department, generate attendance for semester 5 and 6 students
            attendance_count = 0
            for dept_code, _ in DEPARTMENTS:
                dept_id = dept_ids[dept_code]
                dept_courses = COURSES_BY_DEPT[dept_code]

                for c_code, c_name, c_credits, c_sem in dept_courses:
                    cid = course_ids.get(c_code)
                    fac_id = course_faculty.get(c_code)
                    if not cid:
                        continue

                    # Get students in this semester from this department
                    eligible_students = [
                        (usn, info[0]) for usn, info in student_ids.items()
                        if info[1] == c_sem and info[2] == dept_id
                    ]

                    for day_offset in range(45):
                        d = today - timedelta(days=day_offset)
                        if d.weekday() >= 5:
                            continue  # skip weekends

                        for usn, sid in eligible_students:
                            r = random.random()
                            if r < 0.82:
                                status = "present"
                            elif r < 0.92:
                                status = "absent"
                            elif r < 0.97:
                                status = "late"
                            else:
                                status = "excused"

                            cur.execute(
                                """INSERT IGNORE INTO attendance
                                   (student_fk, course_fk, faculty_fk, attendance_date, status)
                                   VALUES (%s, %s, %s, %s, %s)""",
                                (sid, cid, fac_id, d.isoformat(), status),
                            )
                            attendance_count += 1

            logger.info(f"  Generated {attendance_count:,} attendance records")

            # ── GRADES ───────────────────────────────────────────────────
            logger.info("  Generating grade records...")
            grades_list = list(GRADE_SCALE.keys())
            grade_count = 0

            for dept_code, _ in DEPARTMENTS:
                dept_id = dept_ids[dept_code]
                dept_courses = COURSES_BY_DEPT[dept_code]

                for c_code, c_name, c_credits, c_sem in dept_courses:
                    cid = course_ids.get(c_code)
                    fac_id = course_faculty.get(c_code)
                    if not cid:
                        continue

                    eligible_students = [
                        (usn, info[0]) for usn, info in student_ids.items()
                        if info[1] == c_sem and info[2] == dept_id
                    ]

                    for usn, sid in eligible_students:
                        # Generate realistic marks
                        base = random.gauss(65, 15)
                        ia1 = max(0, min(50, round(base * 0.5 + random.gauss(0, 5), 1)))
                        ia2 = max(0, min(50, round(base * 0.5 + random.gauss(0, 5), 1)))
                        ia3 = max(0, min(50, round(base * 0.5 + random.gauss(0, 5), 1)))
                        final_marks = max(0, min(100, round(base + random.gauss(0, 8), 1)))

                        # Determine grade from final marks
                        if final_marks >= 90: grade = "S"
                        elif final_marks >= 80: grade = "A+"
                        elif final_marks >= 70: grade = "A"
                        elif final_marks >= 60: grade = "B+"
                        elif final_marks >= 55: grade = "B"
                        elif final_marks >= 50: grade = "C+"
                        elif final_marks >= 45: grade = "C"
                        elif final_marks >= 40: grade = "D"
                        else: grade = "F"

                        cur.execute(
                            """INSERT IGNORE INTO grades
                               (student_fk, course_fk, faculty_fk, ia1_marks, ia2_marks, ia3_marks,
                                final_exam_marks, final_grade)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                            (sid, cid, fac_id, ia1, ia2, ia3, final_marks, grade),
                        )
                        grade_count += 1

            logger.info(f"  Generated {grade_count:,} grade records")

            # ── TIMETABLE ────────────────────────────────────────────────
            logger.info("  Generating timetable...")
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            time_slots = [
                ("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
                ("14:00", "15:00"), ("15:00", "16:00"),
            ]
            timetable_count = 0

            for dept_code, faculty_list in FACULTY_TEMPLATES.items():
                courses = COURSES_BY_DEPT[dept_code]
                for i, (emp_code, _, _, _) in enumerate(faculty_list):
                    c_code = courses[i % len(courses)][0]
                    c_sem = courses[i % len(courses)][3]
                    cid = course_ids.get(c_code)
                    fid = faculty_ids.get(emp_code)
                    if not cid or not fid:
                        continue

                    # 3 classes per week per course
                    assigned_days = random.sample(days, min(3, len(days)))
                    slot = time_slots[i % len(time_slots)]
                    room = f"{dept_code}-{100 + c_sem * 100 + (i % 5) + 1}"

                    for day in assigned_days:
                        cur.execute(
                            """INSERT IGNORE INTO timetable
                               (faculty_fk, course_fk, day_of_week, start_time, end_time,
                                room, section, semester)
                               VALUES (%s, %s, %s, %s, %s, %s, 'A', %s)""",
                            (fid, cid, day, slot[0], slot[1], room, c_sem),
                        )
                        timetable_count += 1

            logger.info(f"  Generated {timetable_count} timetable entries")

            # ── ANNOUNCEMENTS ────────────────────────────────────────────
            random.seed(77)
            fac_id_list = list(faculty_ids.values())
            for i, (title, content, priority) in enumerate(ANNOUNCEMENT_TEMPLATES):
                fac_id = fac_id_list[i % len(fac_id_list)]
                dept_code = DEPARTMENTS[i % len(DEPARTMENTS)][0]
                dept_name = DEPARTMENTS[i % len(DEPARTMENTS)][1]
                pub_date = today - timedelta(days=random.randint(0, 14))
                expires = today + timedelta(days=random.randint(14, 60))

                cur.execute(
                    """INSERT IGNORE INTO announcements
                       (faculty_fk, title, content, department, priority, published_at, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (fac_id, title, content, dept_name, priority,
                     pub_date.isoformat(), expires.isoformat()),
                )

            # ── SEED QUERY_LOGS ──────────────────────────────────────────
            sample_queries = [
                ("What is the attendance for CS601?", "erp", "text", 450),
                ("Show grades for semester 6 students", "erp", "voice", 620),
                ("Who teaches Machine Learning?", "erp", "text", 380),
                ("What is the timetable for Monday?", "erp", "voice", 290),
                ("Show announcements for Computer Science", "erp", "text", 340),
                ("What is the average attendance percentage?", "erp", "text", 510),
                ("List all students in section A", "erp", "text", 420),
                ("Show me the grades for DBMS", "erp", "voice", 550),
            ]
            for query_text, query_type, source, resp_ms in sample_queries:
                days_ago = random.randint(0, 6)
                created = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 12))
                cur.execute(
                    """INSERT INTO query_logs
                       (query_text, query_type, response_text, response_time_ms, source, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, 'success', %s)""",
                    (query_text, query_type, "Response generated successfully.", resp_ms,
                     source, created.strftime("%Y-%m-%d %H:%M:%S")),
                )

        logger.info(f"Database seeding completed: {len(all_students)} students, "
                    f"{sum(len(v) for v in FACULTY_TEMPLATES.values())} faculty, "
                    f"{sum(len(v) for v in COURSES_BY_DEPT.values())} courses, "
                    f"{len(DEPARTMENTS)} departments")

    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        raise
