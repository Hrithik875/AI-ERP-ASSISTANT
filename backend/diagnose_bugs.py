"""
Phase 9 — Bug Diagnosis Script
================================
Diagnoses Bug 1 (hallucinated attendance), Bug 2 (RAG no results),
Bug 3 (wrong tool routing). Produces concrete evidence without making
any fixes.
"""
import os
import sys
import json

os.environ.setdefault("APP_MODE", "local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────────
# BUG 1 — Context truncation & temperature analysis
# ─────────────────────────────────────────────────────────────────
print("=" * 65)
print("BUG 1 DIAGNOSIS: Attendance hallucination — context & temperature")
print("=" * 65)

from config import OLLAMA_NUM_CTX, OLLAMA_MODEL, OLLAMA_FAST_MODEL
from ai.llm_service import ERP_SYSTEM_PROMPT
from ai.tools import REGISTERED_TOOLS

print(f"OLLAMA_NUM_CTX  = {OLLAMA_NUM_CTX}")
print(f"OLLAMA_MODEL    = {OLLAMA_MODEL}")
print(f"OLLAMA_FAST_MODEL = {OLLAMA_FAST_MODEL}")

# Realistic 40-student CS601 payload
sample = {
    "usn": "CS2022001", "student_name": "Aarav Kumar",
    "course_code": "CS601", "course_name": "Machine Learning",
    "total_classes": 48, "classes_attended": 42, "attendance_pct": 87.5
}
big_payload = {
    "attendance_records": [
        dict(sample, usn=f"CS2022{i:03d}", student_name=f"Student {i}")
        for i in range(1, 41)
    ]
}
payload_json = json.dumps(big_payload, default=str)

tools_info = []
for t in REGISTERED_TOOLS:
    tools_info.append(
        f"Tool: {t.name}\nDescription: {t.description}\n"
        f"Parameters: {json.dumps(t.parameters)}"
    )
tools_str = "\n\n".join(tools_info)

# Format prompt (from agent.py)
format_sys = (
    "You are an AI ERP Assistant for a college.\n"
    "Format the provided JSON data into a clean, professional response.\n"
    "Use Markdown tables for lists.\n"
    "If the data contains at-risk students or attendance calculations, explicitly state:\n"
    "- The student's current attendance percentage and attended/total class numbers.\n"
    "- The threshold being compared against (e.g. 75.0% or 85.0%).\n"
    "- The exact shortage gap in percentage points.\n"
    "- The number of consecutive classes needed to reach eligibility "
    "(or safe classes that can be missed).\n"
    "If the user asked a specific follow-up question (e.g. 'which one has the lowest "
    "attendance?'), directly answer that question highlighting the specific record.\n"
    "If the data contains an error or \"Not found\", explain it politely to the user.\n"
    "Do NOT reveal internal IDs or backend details."
)
format_user = f"Question: Show me attendance for CS601\nData: {payload_json}"

erp_sys_chars = len(ERP_SYSTEM_PROMPT)
tools_chars = len(tools_str)
payload_chars = len(payload_json)
format_sys_chars = len(format_sys)
format_user_chars = len(format_user)

# Tokens approx chars / 4 (conservative for English + JSON)
fmt_total_tokens = (format_sys_chars + format_user_chars) // 4
dispatch_total_tokens = (erp_sys_chars + tools_chars + 100) // 4

print(f"\n--- Format call (user-visible answer) ---")
print(f"  format_system_prompt : {format_sys_chars:>6} chars  ~{format_sys_chars//4:>5} tokens")
print(f"  format_user_msg      : {format_user_chars:>6} chars  ~{format_user_chars//4:>5} tokens")
print(f"  40-student payload   : {payload_chars:>6} chars  ~{payload_chars//4:>5} tokens")
print(f"  TOTAL for format call: ~{fmt_total_tokens:>5} tokens")
print(f"  OLLAMA_NUM_CTX       : {OLLAMA_NUM_CTX:>6}")

if fmt_total_tokens > OLLAMA_NUM_CTX:
    print(f"  *** TRUNCATION CONFIRMED: payload EXCEEDS context by "
          f"{fmt_total_tokens - OLLAMA_NUM_CTX} tokens ***")
elif fmt_total_tokens > int(OLLAMA_NUM_CTX * 0.8):
    print(f"  *** HIGH TRUNCATION RISK: {fmt_total_tokens}/{OLLAMA_NUM_CTX} = "
          f"{100*fmt_total_tokens//OLLAMA_NUM_CTX}% of context used ***")
else:
    print(f"  Context OK: {fmt_total_tokens}/{OLLAMA_NUM_CTX} tokens")

print(f"\n--- Dispatch call ---")
print(f"  ERP system prompt: {erp_sys_chars:>6} chars  ~{erp_sys_chars//4:>5} tokens")
print(f"  Tool schemas     : {tools_chars:>6} chars  ~{tools_chars//4:>5} tokens")
print(f"  TOTAL dispatch   : ~{dispatch_total_tokens:>5} tokens")

print(f"\n--- Temperature audit (agent.py) ---")
print(f"  Non-streaming format generate() call: temperature=0.3 (line 267)")
print(f"  Streaming generate_stream() call    : temperature=0.3 (line 257)")
print(f"  => temperature=0.3 is NON-DETERMINISTIC => different output every call")

# ─────────────────────────────────────────────────────────────────
# BUG 2 — RAG Ingestion analysis
# ─────────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("BUG 2 DIAGNOSIS: RAG — ingestion / retrieval model consistency")
print("=" * 65)

from config import (
    OLLAMA_EMBEDDING_MODEL, RAG_MIN_SCORE, RAG_TOP_K,
    RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, QDRANT_URL, QDRANT_COLLECTION
)

print(f"OLLAMA_EMBEDDING_MODEL : {OLLAMA_EMBEDDING_MODEL}")
print(f"RAG_MIN_SCORE          : {RAG_MIN_SCORE}")
print(f"RAG_TOP_K              : {RAG_TOP_K}")
print(f"RAG_CHUNK_SIZE         : {RAG_CHUNK_SIZE}")
print(f"RAG_CHUNK_OVERLAP      : {RAG_CHUNK_OVERLAP}")
print(f"QDRANT_URL             : {QDRANT_URL}")
print(f"QDRANT_COLLECTION      : {QDRANT_COLLECTION}")

print("\n--- Exception handling in ingest_document ---")
print("  embed_batch() in rag_pipeline.py line ~235:")
print("    embeddings = self.embedder.embed_batch(chunk_texts)")
print("    => No try/except around embed_batch. Exception propagates up.")
print("  embed() in local_embeddings.py: raises on failure (not silently swallowed).")

try:
    from qdrant_client import QdrantClient
    qclient = QdrantClient(url=QDRANT_URL, timeout=3)
    collections = [c.name for c in qclient.get_collections().collections]
    print(f"\nQdrant reachable: YES")
    print(f"Collections present: {collections}")
    if QDRANT_COLLECTION in collections:
        info = qclient.get_collection(QDRANT_COLLECTION)
        count = info.points_count
        vec_size = info.config.params.vectors.size
        print(f"Collection '{QDRANT_COLLECTION}': {count} vectors, dim={vec_size}")
        if count == 0:
            print("  *** NO VECTORS IN COLLECTION — ingestion produced no data ***")
        else:
            # Run a test search to get raw similarity scores
            test_query = "condonation fee"
            try:
                from providers.registry import get_embedding_provider
                embedder = get_embedding_provider()
                q_vec = embedder.embed(test_query)
                hits = qclient.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=q_vec,
                    limit=RAG_TOP_K,
                    with_payload=True
                )
                print(f"\nRaw similarity scores for query: '{test_query}'")
                for h in hits:
                    print(f"  score={h.score:.4f}  file={h.payload.get('filename','?')}  "
                          f"chunk={h.payload.get('chunk_index','?')}")
                above = [h for h in hits if h.score >= RAG_MIN_SCORE]
                print(f"  Hits above RAG_MIN_SCORE={RAG_MIN_SCORE}: {len(above)}/{len(hits)}")
                if not above:
                    print(f"  *** ALL SCORES BELOW THRESHOLD — this is Bug 2 ***")
            except Exception as e2:
                print(f"  Could not run test search: {e2}")
    else:
        print(f"  Collection '{QDRANT_COLLECTION}' does NOT exist")
        print("  => Document was never successfully ingested into Qdrant")
except Exception as e:
    print(f"\nQdrant NOT reachable: {e}")
    print("  => Cannot verify ingestion. Check if Qdrant container is running.")

# ─────────────────────────────────────────────────────────────────
# BUG 3 — Tool routing for "Who teaches machine learning?"
# ─────────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("BUG 3 DIAGNOSIS: 'Who teaches machine learning?' routing")
print("=" * 65)

query = "Who teaches machine learning?"
q_lower = query.lower()

erp_keywords = [
    "attendance", "absent", "present", "grade", "grades", "marks", "gpa", "cgpa",
    "schedule", "timetable", "student", "students", "faculty", "course", "courses",
    "department", "classes", "class", "at-risk", "risk", "miss", "bunk",
    "lowest", "highest", "which one", "who has", "how many", "usn"
]
doc_keywords = [
    "document", "documents", "policy", "policies", "syllabus", "manual",
    "circular", "circulars", "notice", "regulation", "regulations", "guideline"
]

matched_erp = [k for k in erp_keywords if k in q_lower]
matched_doc = [k for k in doc_keywords if k in q_lower]

print(f"Query: '{query}'")
print(f"ERP keywords matched: {matched_erp}")
print(f"Doc keywords matched: {matched_doc}")

if matched_doc:
    fast_class = "document"
elif matched_erp:
    fast_class = "erp"
else:
    fast_class = "LLM_FALLBACK"

print(f"Fast-path classification: {fast_class}")
print()
print("--- agent.py extract_prompt analysis ---")
print("Rules present in dispatch prompt (lines 172-178):")
print("  'If it's attendance ... use AttendanceTool'")
print("  'If it's grades, use GradesTool'")
print("  'If it's timetable, use TimetableTool'     <-- ambiguous for 'who teaches'")
print("  'If it's courses, use CourseTool'")
print("  'If it's analytics, use AnalyticsTool'")
print("  'If it asks about college policies ... use DocumentTool'")
print("  NO rule: 'If user asks who teaches a course, use FacultyTool'")
print()
print("FacultyTool description: 'Fetches faculty profiles, directory info, and workload.'")
print("TimetableTool description: 'Fetches timetable and class schedule info.'")
print()
print("LLM likely interprets 'who teaches' as 'schedule' => TimetableTool (WRONG)")
print()

# Check if 'machine learning' matches a real course via DB
try:
    from db.connection import execute_query
    results = execute_query(
        "SELECT course_code, course_name FROM courses WHERE LOWER(course_name) LIKE %s LIMIT 5",
        ("%machine learning%",)
    )
    if results:
        print(f"DB: 'machine learning' matches courses: {results}")
    else:
        print("DB: 'machine learning' matches NO courses in the database")
        print("  => Correct response should be 'no course by that name found'")
except Exception as e:
    print(f"DB query failed: {e}")

print()
print("--- Runaway generation / stop sequence audit ---")
print("  _call() uses /api/chat (chat messages format): YES (correct)")
print("  stop sequences in format call: NONE set")
print("  num_predict / max_tokens cap: NONE set")
print("  => Model can generate past the real answer => fabricated follow-up turns")

print()
print("=" * 65)
print("DIAGNOSIS COMPLETE")
print("=" * 65)
