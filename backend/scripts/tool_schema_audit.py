"""
Full tool schema vs implementation audit.
Checks that every action documented in tool parameters actually exists in execute().
"""
import sys
import os
import ast
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai.tools import REGISTERED_TOOLS

print("=== TOOL SCHEMA vs IMPLEMENTATION AUDIT ===\n")

for tool in REGISTERED_TOOLS:
    # Get documented actions from parameters
    action_desc = tool.parameters.get("action", "")
    
    # Parse documented actions from "One of: 'x', 'y', 'z'" format
    import re
    documented_actions = re.findall(r"'([^']+)'", action_desc)
    
    # Get source code of execute() and find if/elif branches
    src = inspect.getsource(tool.execute)
    # Find all action == '...' patterns
    implemented_actions = re.findall(r'action\s*(?:==|in)\s*[\(\["]([^"\)\]]+)', src)
    # Also find action in ("x", "y") patterns
    tuple_actions = re.findall(r'action in \(([^)]+)\)', src)
    all_impl = set()
    for a in implemented_actions:
        all_impl.add(a.strip().strip("'\""))
    for t in tuple_actions:
        for a in re.findall(r'"([^"]+)"|\'([^\']+)\'', t):
            all_impl.add((a[0] or a[1]).strip())
    
    print(f"{'='*60}")
    print(f"Tool: {tool.name}")
    print(f"  Documented actions: {documented_actions}")
    print(f"  Implemented actions: {sorted(all_impl)}")
    
    # Find mismatches
    doc_set = set(documented_actions)
    impl_set = all_impl
    
    in_doc_not_impl = doc_set - impl_set
    in_impl_not_doc = impl_set - doc_set
    
    if in_doc_not_impl:
        print(f"  [WARN] DOCUMENTED but NOT IMPLEMENTED: {in_doc_not_impl}")
    if in_impl_not_doc:
        print(f"  [INFO] Implemented aliases/extras (not in doc): {in_impl_not_doc}")
    if not in_doc_not_impl and not in_impl_not_doc:
        print(f"  [OK] Schema matches implementation")
    print()
