import base64
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")
public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")

credentials = f"{public_key}:{secret_key}"
encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

# Query observations from last 2 hours
now = datetime.now(timezone.utc)
from_time = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

url = f"{host}/api/public/v2/observations?fromStartTime={from_time}&limit=30"
req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json",
    }
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        observations = data.get("data", [])
        print(f"Fetched {len(observations)} observations from Langfuse Cloud (v2 API):")
        for obs in observations[:15]:
            oid = obs.get("id")
            trace_id = obs.get("traceId")
            name = obs.get("name")
            otype = obs.get("type")
            parent_id = obs.get("parentObservationId")
            start_time = obs.get("startTime")
            level = obs.get("level")
            print(f"  [{otype}] Name: '{name}' | TraceID: {trace_id} | Parent: {parent_id} | Level: {level}")

except Exception as e:
    print(f"Failed to query Langfuse Cloud v2 observations: {e}")
