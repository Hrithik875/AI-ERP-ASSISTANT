"""
Quick end-to-end test of the two demo queries without the LLM
(tests tool routing + plain rendering).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai.tools import REGISTERED_TOOLS
from ai.agent import _plain_generic_render, _keyword_fallback_route

def get_tool(name):
    for t in REGISTERED_TOOLS:
        if t.name == name:
            return t
    return None

print("=" * 70)
print("TEST 1: 'Show me attendance for CS601'")
print("=" * 70)
tool_name, params = _keyword_fallback_route("Show me attendance for CS601")
print(f"  Keyword route: tool={tool_name}, params={params}")
tool = get_tool(tool_name)
result = tool.execute(params)
print(f"  Tool result keys: {list(result.keys())}")
rendered = _plain_generic_render(result, "Show me attendance for CS601", tool_name)
print(f"  Rendered output ({len(rendered)} chars):")
print(rendered[:500])
print()

print("=" * 70)
print("TEST 2: 'how many departments are there? list them'")
print("=" * 70)
tool_name2, params2 = _keyword_fallback_route("how many departments are there? list them")
print(f"  Keyword route: tool={tool_name2}, params={params2}")
tool2 = get_tool(tool_name2)
result2 = tool2.execute(params2)
print(f"  Tool result keys: {list(result2.keys())}")
rendered2 = _plain_generic_render(result2, "how many departments are there? list them", tool_name2)
print(f"  Rendered output ({len(rendered2)} chars):")
print(rendered2)
