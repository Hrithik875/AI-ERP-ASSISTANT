"""
AI ERP Assistant — Base Tool
=============================
Defines the base class for all AI tools.
"""

from typing import Any, Dict

class BaseTool:
    """Base class for all tools."""
    name: str = "BaseTool"
    description: str = "Base description."
    parameters: dict = {}

    def execute(self, params: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters."""
        raise NotImplementedError("Tools must implement the execute method.")
