"""
Test script verifying IDOR / Unauthenticated bypass on /api/v1/assessments/history/{student_id}
and /api/v1/learning-journey/student/{student_id}
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

print("=" * 60)
print("TESTING UNAUTHENTICATED ACCESS TO STUDENT DATA")
print("=" * 60)

# Try fetching assessment history without Authorization header
resp = client.get("/api/v1/assessments/history/student_123")
print("GET /api/v1/assessments/history/student_123 (No Auth):")
print(f"  Status: {resp.status_code}")
print(f"  Body: {resp.text[:200]}")

# Try fetching learning journeys without Authorization header
resp2 = client.get("/api/v1/learning-journey/student/student_123")
print("\nGET /api/v1/learning-journey/student/student_123 (No Auth):")
print(f"  Status: {resp2.status_code}")
print(f"  Body: {resp2.text[:200]}")

# Now try with an authenticated token for another student (student_999)
from backend.services.auth_service import create_access_token
fake_token = create_access_token({"sub": "student_999", "role": "student"})

resp3 = client.get(
    "/api/v1/assessments/history/student_123",
    headers={"Authorization": f"Bearer {fake_token}"}
)
print("\nGET /api/v1/assessments/history/student_123 (Auth as student_999):")
print(f"  Status: {resp3.status_code}")
print(f"  Body: {resp3.text[:200]}")
