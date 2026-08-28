"""
Token audit script — measures the ACTUAL size of extraction prompts
sent to the fast model on each ERP query.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("APP_MODE", "local")

from ai.tools import REGISTERED_TOOLS

# Reproduce the EXACT tools_str built in execute_tool_query
tools_info = []
for t in REGISTERED_TOOLS:
    tools_info.append(
        f"Tool: {t.name}\nDescription: {t.description}\nParameters: {json.dumps(t.parameters)}"
    )
tools_str = "\n\n".join(tools_info)

# Reproduce extract_prompt (copy from agent.py)
extract_prompt = (
    "You are an intelligent router for an Academic ERP system.\n"
    "Available tools:\n"
    + tools_str
    + "\n\nAnalyze the user's question (and recent conversation history if it is a follow-up) "
    "and select the most appropriate tool and the necessary parameters.\n"
    "\nRespond ONLY with a valid JSON object matching this schema:\n"
    '{\n  "tool_name": "NameOfTheTool",\n  "params": {\n    "action": "action_name",\n    "param1": "value1"\n  }\n}\n'
    "\nCRITICAL INSTRUCTIONS:\n"
    "- ONLY output JSON. No markdown backticks, no explanations.\n"
    "- Map entities properly: if the user asks for \"Aarav M\", the `usn` might be required "
    "but you might not know it. If a name is provided and USN is needed, you might need to "
    "use `action: search` to find the USN first, or pass it if you know it.\n"
    "- If the user refers to a course or student from the conversation history "
    "(e.g., \"which one has lowest attendance in that course?\", \"what about CS601?\", "
    "\"how many more classes does he need?\"), extract the course_code or usn/name from the history!\n"
    "- If the user asks how many classes a student needs to attend to reach 75%/85%, "
    "use AttendanceTool with action: 'calculate_classes_needed', usn/name, and target_pct.\n"
    "- If the user asks how many classes a student can miss/bunk safely, "
    "use AttendanceTool with action: 'calculate_classes_can_miss', usn/name, and target_pct.\n"
    "- If it's an attendance query or attendance risk query, use AttendanceTool.\n"
    "- If it's grades, use GradesTool.\n"
    "- If it's timetable or class schedule, use TimetableTool.\n"
    "- If it's courses (listing, info), use CourseTool.\n"
    "- If it's analytics, use AnalyticsTool.\n"
    "- If it asks about college policies, documents, circulars, or general regulations, use DocumentTool.\n"
    "- IMPORTANT — Phase 9 fix: If the user asks WHO TEACHES a course, WHO IS THE INSTRUCTOR/LECTURER/PROFESSOR\n"
    "  for a course, or asks about a faculty member by name, use FacultyTool with action='search' and the\n"
    "  relevant name or course info as params. Never route 'who teaches X' to TimetableTool.\n"
)

q1 = "Show me attendance for CS601"
q2 = "how many departments are there? list them"

print("=== EXTRACTION PROMPT TOKEN AUDIT ===")
print(f"System prompt (extract_prompt) chars: {len(extract_prompt)}")
print(f"Estimated tokens (chars/4):           ~{len(extract_prompt) // 4}")
print()
print(f"Full payload Q1 ({q1!r}):")
print(f"  {len(extract_prompt) + len(q1)} chars ~ {(len(extract_prompt) + len(q1)) // 4} tokens")
print()
print(f"Full payload Q2 ({q2!r}):")
print(f"  {len(extract_prompt) + len(q2)} chars ~ {(len(extract_prompt) + len(q2)) // 4} tokens")
print()
print("--- Tool-by-tool schema sizes ---")
for t in REGISTERED_TOOLS:
    chunk = f"Tool: {t.name}\nDescription: {t.description}\nParameters: {json.dumps(t.parameters)}"
    print(f"  {t.name:25s}: {len(chunk):5d} chars ~ {len(chunk) // 4:4d} tokens")
print()
print(f"  tools_str total:          : {len(tools_str):5d} chars ~ {len(tools_str) // 4:4d} tokens")
