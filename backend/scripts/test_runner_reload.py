"""
Hypothesis Test Script:
Test Ollama runner reload overhead when alternating num_ctx vs keeping same num_ctx.
"""
import time
import requests
import json

base_url = "http://localhost:11434"
model = "qwen2.5:3b-instruct"

def call_ollama(prompt, num_ctx, threads=12):
    t0 = time.perf_counter()
    resp = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_thread": threads,
                "num_ctx": num_ctx,
                "num_predict": 64
            }
        },
        timeout=60
    )
    elapsed = int((time.perf_counter() - t0) * 1000)
    return elapsed, resp.status_code

print("=" * 60)
print("WARM-UP CALL (ctx=2048)")
print("=" * 60)
t, s = call_ollama("hi", 2048)
print(f"Warmup: {t}ms (status={s})")

print("\n" + "=" * 60)
print("TEST A: SAME num_ctx (2048 -> 2048)")
print("=" * 60)
t1, s1 = call_ollama("Respond with 'A1': ping", 2048)
print(f"Call 1 (ctx=2048): {t1}ms")
t2, s2 = call_ollama("Respond with 'A2': pong", 2048)
print(f"Call 2 (ctx=2048): {t2}ms")
print(f"Total Same-ctx: {t1 + t2}ms")

print("\n" + "=" * 60)
print("TEST B: ALTERNATING num_ctx (2048 -> 8192 -> 2048)")
print("=" * 60)
t3, s3 = call_ollama("Respond with 'B1': ping", 2048)
print(f"Call 1 (ctx=2048): {t3}ms")
t4, s4 = call_ollama("Respond with 'B2': switch to 8192", 8192)
print(f"Call 2 (ctx=8192): {t4}ms  <-- SWITCH")
t5, s5 = call_ollama("Respond with 'B3': switch back to 2048", 2048)
print(f"Call 3 (ctx=2048): {t5}ms  <-- SWITCH BACK")
print(f"Total Alternating (Call 1 + Call 2): {t3 + t4}ms")

print("\n" + "=" * 60)
print("TEST C: SINGLE STANDARDIZED num_ctx (4096 -> 4096)")
print("=" * 60)
t6, s6 = call_ollama("Respond with 'C1': ping 4096", 4096)
print(f"Call 1 (ctx=4096): {t6}ms")
t7, s7 = call_ollama("Respond with 'C2': pong 4096", 4096)
print(f"Call 2 (ctx=4096): {t7}ms")
print(f"Total Same-4096: {t6 + t7}ms")
