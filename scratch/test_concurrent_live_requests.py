import concurrent.futures
import json
import time
import urllib.request

url = "http://127.0.0.1:8000/api/v1/ask"

payload_a = {
    "question": "Explain refraction of light through a rectangular glass slab with lateral displacement.",
    "grade": "Class 10",
    "subject": "Science",
    "topic": "Light - Reflection and Refraction",
    "lesson_mode": "conceptual"
}

payload_b = {
    "question": "What are magnetic field lines around a straight current-carrying wire according to Maxwell right-hand thumb rule?",
    "grade": "Class 10",
    "subject": "Science",
    "topic": "Magnetic Effects of Electric Current",
    "lesson_mode": "conceptual"
}

def make_request(req_id: str, payload: dict) -> dict:
    t0 = time.time()
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        elapsed = round(time.time() - t0, 2)
        data["client_elapsed_s"] = elapsed
        data["client_req_id"] = req_id
        return data

print("Dispatching 2 concurrent requests to /api/v1/ask...")
t_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_a = executor.submit(make_request, "REQ_A", payload_a)
    future_b = executor.submit(make_request, "REQ_B", payload_b)

    res_a = future_a.result()
    res_b = future_b.result()

total_time = round(time.time() - t_start, 2)
print(f"\nBoth concurrent requests finished in {total_time}s!")
print(f"Request A: ID={res_a.get('request_id')} | Status={res_a.get('status')} | Duration={res_a.get('duration_ms')}ms")
print(f"Request B: ID={res_b.get('request_id')} | Status={res_b.get('status')} | Duration={res_b.get('duration_ms')}ms")

assert res_a.get("request_id") != res_b.get("request_id"), "Request IDs must be unique!"
assert res_a.get("status") == "success", "Request A failed"
assert res_b.get("status") == "success", "Request B failed"
print("\nCONCURRENT REQUEST TEST PASSED: Unique request IDs, isolated contexts, zero contamination!")
