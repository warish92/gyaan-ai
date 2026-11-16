import json
import urllib.request
import time

url = "http://127.0.0.1:8000/api/v1/ask"
payload = {
    "question": "What is the formula for Ohm's law and how do resistance, voltage, and current relate?",
    "grade": "Class 10",
    "subject": "Science",
    "topic": "Electricity",
    "lesson_mode": "conceptual"
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

print("Sending request to /api/v1/ask...")
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        elapsed = round(time.time() - t0, 2)
        print(f"Request succeeded in {elapsed}s!")
        print(f"Status: {data.get('status')}")
        print(f"Workflow Executed: {data.get('workflow_executed')}")
        print(f"Agent Name: {data.get('agent_name')}")
        print(f"Duration MS: {data.get('duration_ms')}")
        print(f"Answer snippet: {data.get('answer', '')[:200]}...")
except Exception as e:
    print(f"Request failed: {e}")
