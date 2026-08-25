"""
AI ERP Assistant — Latency Measurement Script
==============================================
Runs 5 iterations each of:
  - ERP tool query (AttendanceTool via /chat)
  - RAG document query (DocumentTool via /chat)
  - Voice pipeline query (STT → AI → TTS via /voice-query, mocked)

Reads response_time_ms from the API response payload (set by agent.py).
Also queries the query_logs table for the last 5 entries per type.

Reports: min / max / median for each category.

Usage:
  cd backend
  python scripts/measure_latency.py [--iterations 5] [--url http://localhost:8000]
"""

import argparse
import statistics
import sys
import os
import time
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests")
    sys.exit(1)

# ── CLI ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="AI-ERP Response Latency Benchmark")
parser.add_argument("--iterations", type=int, default=5, help="Number of iterations per category")
parser.add_argument("--url", default="http://localhost:8000", help="Backend base URL")
parser.add_argument("--timeout", type=int, default=240, help="Request timeout seconds")
args = parser.parse_args()

BASE_URL = args.url
N = args.iterations
TIMEOUT = args.timeout


# ── Benchmark Queries ────────────────────────────────────────────────────────

ERP_QUERY = "Show me the attendance summary for CS601"
RAG_QUERY = "According to the uploaded academic policies document, what is the condonation fee?"
VOICE_SAMPLE = b"\x00" * 4096  # silent 4 KB placeholder audio (webm container header)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _median(values):
    return round(statistics.median(values), 1) if values else "N/A"

def _run_chat(message: str) -> dict:
    """POST /chat and return (response_time_ms_from_api, wall_clock_ms)."""
    t0 = time.monotonic()
    try:
        r = requests.post(
            f"{BASE_URL}/chat",
            json={"message": message},
            timeout=TIMEOUT,
        )
        wall_ms = int((time.monotonic() - t0) * 1000)
        r.raise_for_status()
        data = r.json()
        api_ms = data.get("response_time_ms", wall_ms)
        return {"api_ms": api_ms, "wall_ms": wall_ms, "tool_used": data.get("tool_used", "?"), "ok": True}
    except Exception as e:
        wall_ms = int((time.monotonic() - t0) * 1000)
        return {"api_ms": wall_ms, "wall_ms": wall_ms, "tool_used": "ERROR", "ok": False, "error": str(e)}

def _run_voice(audio_bytes: bytes) -> dict:
    """POST /voice-query with fake audio and return latency stats."""
    t0 = time.monotonic()
    try:
        r = requests.post(
            f"{BASE_URL}/voice-query",
            files={"audio": ("test.webm", io.BytesIO(audio_bytes), "audio/webm")},
            timeout=TIMEOUT,
        )
        wall_ms = int((time.monotonic() - t0) * 1000)
        if r.status_code in (400, 422):
            # Backend accepted the request but rejected the audio (e.g. empty check)
            # Use wall clock and mark OK=False for reporting
            return {"api_ms": wall_ms, "wall_ms": wall_ms, "tool_used": "N/A (audio rejected)", "ok": False, "error": r.json().get("detail", "")}
        r.raise_for_status()
        data = r.json()
        api_ms = data.get("response_time_ms", wall_ms)
        return {"api_ms": api_ms, "wall_ms": wall_ms, "tool_used": data.get("query_type", "?"), "ok": True}
    except Exception as e:
        wall_ms = int((time.monotonic() - t0) * 1000)
        return {"api_ms": wall_ms, "wall_ms": wall_ms, "tool_used": "ERROR", "ok": False, "error": str(e)}


# ── Verify backend is reachable ───────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  AI-ERP Latency Benchmark  |  {N} iterations  |  {BASE_URL}")
print(f"{'='*60}\n")

try:
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    mode = r.json().get("mode", "unknown")
    print(f"[OK] Backend is UP - mode={mode}\n")
except Exception as e:
    print(f"[ERROR] Backend is not reachable at {BASE_URL}: {e}")
    print("   Start the backend with: cd backend && uvicorn main:app --port 8000")
    sys.exit(1)


# ── Run ERP Benchmark ─────────────────────────────────────────────────────────

print(f"[1/3] ERP Tool Query Benchmark ({N}x)")
print(f"      Query: {ERP_QUERY!r}")
erp_results = []
for i in range(N):
    res = _run_chat(ERP_QUERY)
    status = "[PASS]" if res["ok"] else "[FAIL]"
    print(f"      Run {i+1}: {status}  api={res['api_ms']}ms  wall={res['wall_ms']}ms  tool={res['tool_used']}")
    if res["ok"]:
        erp_results.append(res["api_ms"])
    else:
        print(f"             Error: {res.get('error', '')}")
    time.sleep(1)  # Brief cooldown between runs


# ── Run RAG Benchmark ─────────────────────────────────────────────────────────

print(f"\n[2/3] RAG Document Query Benchmark ({N}x)")
print(f"      Query: {RAG_QUERY!r}")
rag_results = []
for i in range(N):
    res = _run_chat(RAG_QUERY)
    status = "[PASS]" if res["ok"] else "[FAIL]"
    print(f"      Run {i+1}: {status}  api={res['api_ms']}ms  wall={res['wall_ms']}ms  tool={res['tool_used']}")
    if res["ok"]:
        rag_results.append(res["api_ms"])
    else:
        print(f"             Error: {res.get('error', '')}")
    time.sleep(1)


# ── Run Voice Benchmark ────────────────────────────────────────────────────────

print(f"\n[3/3] Voice Pipeline Query Benchmark ({N}x)")
print(f"      Audio: {len(VOICE_SAMPLE)} bytes webm (silent)")
voice_results = []
for i in range(N):
    res = _run_voice(VOICE_SAMPLE)
    status = "[PASS]" if res["ok"] else "[WARN]"
    print(f"      Run {i+1}: {status}  wall={res['wall_ms']}ms  result={res['tool_used']}")
    if not res["ok"] and res.get("error"):
        print(f"             Note: {res.get('error', '')}")
    if res["ok"]:
        voice_results.append(res["wall_ms"])
    time.sleep(1)


# ── Summary Table ─────────────────────────────────────────────────────────────

def _stats(values):
    if not values:
        return "N/A", "N/A", "N/A"
    return min(values), max(values), _median(values)

erp_min, erp_max, erp_med = _stats(erp_results)
rag_min, rag_max, rag_med = _stats(rag_results)
voice_min, voice_max, voice_med = _stats(voice_results)

print(f"\n{'='*60}")
print(f"  LATENCY SUMMARY  (all values in ms)")
print(f"{'='*60}")
print(f"  {'Category':<25} {'n':>3} {'Min':>8} {'Max':>8} {'Median':>8}")
print(f"  {'-'*55}")
print(f"  {'ERP Tool Query':<25} {len(erp_results):>3} {str(erp_min):>8} {str(erp_max):>8} {str(erp_med):>8}")
print(f"  {'RAG Document Query':<25} {len(rag_results):>3} {str(rag_min):>8} {str(rag_max):>8} {str(rag_med):>8}")
print(f"  {'Voice Pipeline':<25} {len(voice_results):>3} {str(voice_min):>8} {str(voice_max):>8} {str(voice_med):>8}")
print(f"{'='*60}\n")

# ── Also dump from query_logs table ──────────────────────────────────────────

print("Attempting to read last 5 entries per type from query_logs table...")
os.environ.setdefault("APP_MODE", "local")
try:
    from db.connection import execute_query
    for qtype in ("erp", "document"):
        rows = execute_query(
            "SELECT response_time_ms, tool_used, created_at FROM query_logs "
            "WHERE query_type = %s ORDER BY created_at DESC LIMIT 5",
            (qtype,)
        )
        if rows:
            times = [r["response_time_ms"] for r in rows if r.get("response_time_ms")]
            print(f"  query_logs [{qtype}]: last 5 times = {times}  median={_median(times)}ms")
        else:
            print(f"  query_logs [{qtype}]: no entries found")
except Exception as e:
    print(f"  Could not read query_logs (DB may not be accessible from script): {e}")

print("\nBenchmark complete.")
