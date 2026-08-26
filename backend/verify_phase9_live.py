"""
Phase 9 — Live Verification of Bug 2 and Bug 3 Queries & Latency Benchmark
"""
import os
import sys
import json
import time
import statistics

os.environ.setdefault("APP_MODE", "local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.agent import process_query

print("=" * 65)
print("VERIFICATION OF EXACT REPORTED QUERIES (LIVE STACK)")
print("=" * 65)

# Query 1: Exact RAG query
q_rag = "According to the uploaded academic policies document, what is the condonation fee?"
print(f"\n--- QUERY 1 (RAG): '{q_rag}' ---")
res_rag = process_query(q_rag)
print(f"Query Type   : {res_rag['query_type']}")
print(f"Tool Used    : {res_rag['tool_used']}")
print(f"Sources      : {res_rag.get('sources')}")
print(f"Response Time: {res_rag['response_time_ms']}ms")
print(f"Answer:\n{res_rag['answer']}")

# Query 2: Exact Faculty query
q_fac = "Who teaches machine learning?"
print(f"\n--- QUERY 2 (Faculty): '{q_fac}' ---")
res_fac = process_query(q_fac)
print(f"Query Type   : {res_fac['query_type']}")
print(f"Tool Used    : {res_fac['tool_used']}")
print(f"Sources      : {res_fac.get('sources')}")
print(f"Response Time: {res_fac['response_time_ms']}ms")
print(f"Answer:\n{res_fac['answer']}")

# Latency Benchmark: 5 representative queries
print("\n" + "=" * 65)
print("PHASE 9 LATENCY BENCHMARK")
print("=" * 65)

bench_queries = [
    "What is my attendance?",
    "Show me attendance for CS601",
    "Who teaches machine learning?",
    "Show at-risk students in CS601",
    "What is the condonation fee?",
]

latencies = []
for q in bench_queries:
    t0 = time.perf_counter()
    r = process_query(q)
    elapsed = int((time.perf_counter() - t0) * 1000)
    latencies.append(elapsed)
    print(f"Query: '{q[:40]:<40}' | Time: {elapsed}ms | Tool: {r['tool_used']}")

print(f"\nLatency Summary (Phase 9):")
print(f"  Min   : {min(latencies)}ms")
print(f"  Max   : {max(latencies)}ms")
print(f"  Mean  : {statistics.mean(latencies):.1f}ms")
print(f"  Median: {statistics.median(latencies):.1f}ms")
