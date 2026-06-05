"""
AI ERP Assistant — Tools Registry
===================================
Exports all available AI tools.
"""

from .base import BaseTool
from .attendance_tool import AttendanceTool
from .grades_tool import GradesTool
from .student_tool import StudentTool
from .faculty_tool import FacultyTool
from .course_tool import CourseTool
from .timetable_tool import TimetableTool
from .analytics_tool import AnalyticsTool
from .document_tool import DocumentTool

# Registry of all available tools
REGISTERED_TOOLS = [
    AttendanceTool(),
    GradesTool(),
    StudentTool(),
    FacultyTool(),
    CourseTool(),
    TimetableTool(),
    AnalyticsTool(),
    DocumentTool(),
]

def get_tool(tool_name: str) -> BaseTool:
    """Get a tool instance by name."""
    for tool in REGISTERED_TOOLS:
        if tool.name == tool_name:
            return tool
    return None
