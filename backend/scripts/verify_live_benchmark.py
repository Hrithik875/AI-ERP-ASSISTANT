"""
Live Verification Script for Priority 1, 2, and 3 fixes.
Runs the exact test queries 3 times each and records timings and correctness.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("APP_MODE", "local")

from ai.agent import process_query
from providers.registry import get_llm_provider

print("=" * 80)
print("PRE-WARMING OLLAMA MODELS...")
print("=" * 80)
llm = get_llm_provider()
if hasattr(llm, "prewarm"):
    timings = llm.prewarm()
    print(f"Pre-warm timings: {timings}")

queries = [
    "how many departments are there? list them",
    "Show me attendance for CS601"
]

results = {}

for q in queries:
    print("\n" + "=" * 80)
    print(f"TESTING QUERY: {q!r}")
    print("=" * 80)
    results[q] = []
    
    for run in range(1, 4):
        print(f"\n--- Run {run} ---")
        t0 = time.perf_counter()
        resp = process_query(q)
        total_time = int((time.perf_counter() - t0) * 1000)
        
        tool_used = resp.get("tool_used")
        source_info = resp.get("source_info")
        answer = resp.get("answer")
        resp_time = resp.get("response_time_ms")
        
        print(f"Total time (outer): {total_time}ms | Backend recorded: {resp_time}ms")
        print(f"Tool used: {tool_used}")
        print(f"Source info (dispatch details): {source_info}")
        print(f"Answer snippet:\n{answer[:300]}...\n")
        
        results[q].append({
            "run": run,
            "total_ms": total_time,
            "resp_ms": resp_time,
            "tool_used": tool_used,
            "source_info": source_info,
            "answer": answer
        })

print("\n" + "=" * 80)
print("FINAL BENCHMARK SUMMARY (3 RUNS EACH)")
print("=" * 80)

for q, runs in results.items():
    print(f"\nQuery: {q}")
    for r in runs:
        print(f"  Run {r['run']}: {r['total_ms']}ms | Tool: {r['tool_used']} | Source: {r['source_info']}")
