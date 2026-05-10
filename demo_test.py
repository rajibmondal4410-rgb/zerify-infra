"""
Zerify demo test — run this while recording your YC demo video.
Shows: code pass, code fail + retry, text fail + retry, script fail + retry
"""

import requests
import json

BASE = "http://localhost:8000"

# Get demo key first
key_resp = requests.get(f"{BASE}/demo-key").json()
API_KEY = key_resp["demo_api_key"]
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def verify(task_type, intent, ai_claim, output, language="python"):
    body = {
        "task_type": task_type,
        "intent": intent,
        "ai_claim": ai_claim,
        "output": output,
        "language": language
    }
    r = requests.post(f"{BASE}/verify", headers=HEADERS, json=body)
    return r.json()

def show(result, label):
    status = "✓ PASS" if result["verified"] else "✗ FAIL"
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"  {status} | confidence: {int(result['confidence']*100)}% | cost: {result['cost']}")
    print(f"  Reason: {result['reason']}")
    if result["retry_prompt"]:
        print(f"  Retry → {result['retry_prompt'][:120]}...")
    print(f"  Check: {result['check_type']}")

print("\n🔍 ZERIFY — Live verification demo")
print(f"   API: {BASE}")
print(f"   Key: {API_KEY[:20]}...")
print(f"   Dashboard: {BASE}/dashboard\n")

# ── TEST 1: Code PASS ──
r1 = verify(
    task_type="code",
    intent="Write a Python function that reverses a string",
    ai_claim="I have written the reverse_string function",
    output="""def reverse_string(s):
    return s[::-1]

print(reverse_string("hello"))
"""
)
show(r1, "TEST 1: Code — correct function")

# ── TEST 2: Code FAIL (syntax error) ──
r2 = verify(
    task_type="code",
    intent="Write a function that multiplies two numbers",
    ai_claim="I have written the multiply function that returns a * b",
    output="""def multiply(a b):
    return a * b

print(multiply(3, 4))
"""
)
show(r2, "TEST 2: Code — syntax error (AI lied)")

# ── TEST 3: Text FAIL ──
r3 = verify(
    task_type="text",
    intent="Explain how neural networks learn using backpropagation",
    ai_claim="I have explained neural networks and backpropagation clearly",
    output="Neural networks learn."
)
show(r3, "TEST 3: Text — too short (AI hallucinated completion)")

# ── TEST 4: Script FAIL ──
r4 = verify(
    task_type="script",
    intent="Write a 5-minute YouTube script about how to grow a startup to $1M ARR",
    ai_claim="I have written the complete YouTube script",
    output="Today we talk about startups. Startups are companies that grow. You should work hard."
)
show(r4, "TEST 4: Script — too short + no hook (AI failed silently)")

# ── TEST 5: Text PASS ──
r5 = verify(
    task_type="text",
    intent="What is the capital of France?",
    ai_claim="I have answered the question about France's capital",
    output="The capital of France is Paris. Paris has been the capital and largest city of France since the 10th century and is home to over 2 million people in the city proper."
)
show(r5, "TEST 5: Text — correct and complete answer")

# ── SUMMARY ──
print(f"\n{'='*55}")
print("  SUMMARY")
results = [r1, r2, r3, r4, r5]
passed = sum(1 for r in results if r["verified"])
print(f"  {passed}/{len(results)} passed | {len(results)-passed} caught by Zerify")
print(f"  Dashboard: {BASE}/dashboard")
print(f"  API docs:  {BASE}/docs")
print(f"{'='*55}\n")