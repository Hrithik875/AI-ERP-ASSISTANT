"""
Test compact router prompt size and execution speed.
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("APP_MODE", "local")

from providers.registry import get_llm_provider

llm = get_llm_provider()

compact_tools = """TOOLS:
- AttendanceTool: student_summary(usn/name), course_summary(course_code), risk_list(course_code?), calculate_classes_needed(usn/name, target_pct), calculate_classes_can_miss(usn/name, target_pct)
- AnalyticsTool: department_performance(department?), overall_stats()
- TimetableTool: course_schedule(course_code), day_schedule(day), faculty_schedule(employee_code)
- FacultyTool: by_course(course_code), search(name/department), profile(employee_code), workload(employee_code)
- GradesTool: student_grades(usn), course_grades(course_code), top_performers(course_code), failing_students(course_code)
- StudentTool: profile(usn), search(name/department/semester)
- CourseTool: search(department?), details(course_code), statistics(course_code)
- DocumentTool: college policies, syllabus, regulations"""

compact_system = f"""You are an ERP router. Output ONLY valid JSON: {{"tool_name": "ToolName", "params": {{"action": "action_name", "key": "val"}}}}

{compact_tools}

RULES:
- "attendance", "attended", "absent", "risk", "bunk" -> AttendanceTool. (e.g. "attendance for CS601" -> {{"tool_name":"AttendanceTool","params":{{"action":"course_summary","course_code":"CS601"}}}})
- "schedule", "timetable", "classes on [day]" -> TimetableTool. (e.g. "timetable for CS601" -> {{"tool_name":"TimetableTool","params":{{"action":"course_schedule","course_code":"CS601"}}}})
- "departments", "department list", "dept stats" -> AnalyticsTool(action='department_performance')
- "overall stats", "institution count" -> AnalyticsTool(action='overall_stats')
- "who teaches [course]" -> FacultyTool(action='by_course', course_code='...')"""

print(f"Compact system prompt chars: {len(compact_system)} (~{len(compact_system)//4} tokens)")

queries = [
    "how many departments are there? list them",
    "Show me attendance for CS601"
]

for q in queries:
    print(f"\nTesting: {q}")
    t0 = time.perf_counter()
    resp = llm.generate_fast(user_message=q, system_prompt=compact_system)
    elapsed = int((time.perf_counter() - t0) * 1000)
    print(f"Time: {elapsed}ms")
    print(f"Result: {resp}")
