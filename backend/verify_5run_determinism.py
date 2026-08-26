"""
Phase 9 — Five-Run Determinism Verification Script
=====================================================
Runs "Show me attendance for CS601" five times against the live stack
and compares each response for identical student rows.

Run after starting the backend:
    python verify_5run_determinism.py

Requires: Ollama running, MySQL running, backend NOT needed (calls agent directly).
"""
import os
import sys
import json
import hashlib

os.environ.setdefault("APP_MODE", "local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

QUERY = "Show me attendance for CS601"
RUNS = 5

print("=" * 65)
print(f"Phase 9 — 5-Run Determinism Proof: '{QUERY}'")
print("=" * 65)

from ai.agent import execute_tool_query
from ai.tools import REGISTERED_TOOLS

# First get the raw tool result (ground truth from MySQL)
attendance_tool = next(t for t in REGISTERED_TOOLS if t.name == "AttendanceTool")
raw_data = attendance_tool.execute({"action": "course_summary", "course_code": "CS601"})
print(f"\nRaw MySQL tool result (course_summary for CS601):")
print(json.dumps(raw_data, default=str, indent=2))

print(f"\n--- Running '{QUERY}' {RUNS} times ---\n")

responses = []
for i in range(1, RUNS + 1):
    try:
        answer, source, sources, tool = execute_tool_query(QUERY)
        responses.append(answer)
        print(f"\n{'='*60}")
        print(f"Run {i}/{RUNS} | tool={tool}")
        print(f"{'='*60}")
        print(answer[:2000])  # First 2000 chars
    except Exception as e:
        responses.append(f"ERROR: {e}")
        print(f"\nRun {i} FAILED: {e}")

# Compare all runs
print(f"\n{'='*65}")
print("DETERMINISM ANALYSIS")
print(f"{'='*65}")
hashes = [hashlib.md5(r.encode()).hexdigest() for r in responses]
unique_hashes = set(hashes)
print(f"Unique response hashes: {len(unique_hashes)}/{RUNS}")
if len(unique_hashes) == 1:
    print("RESULT: PERFECTLY DETERMINISTIC — all 5 runs identical")
else:
    print(f"RESULT: {len(unique_hashes)} distinct outputs (non-deterministic)")
    for i, (r, h) in enumerate(zip(responses, hashes), 1):
        print(f"  Run {i}: hash={h[:8]}...")

print("\nAll 5 responses side by side (first 300 chars each):")
for i, r in enumerate(responses, 1):
    print(f"\n--- Run {i} ---")
    print(r[:300])
