import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(".env")
from langfuse import Langfuse

client = Langfuse()
client.flush()

trace_id = "e18fcdd9801446659e084be2b353072d"
print(f"Verifying Trace ID: {trace_id}")

found = False
for attempt in range(6):
    try:
        trace_data = client.api.trace.get(trace_id)
        print("SUCCESS: Trace found in Langfuse Cloud!")
        print(f"Trace ID: {trace_data.id}")
        print(f"Trace Name: {trace_data.name}")
        print(f"Created At: {trace_data.timestamp}")
        obs_list = getattr(trace_data, "observations", [])
        print(f"Observations Count: {len(obs_list)}")
        for obs in obs_list:
            o_id = getattr(obs, "id", "N/A")
            o_name = getattr(obs, "name", "N/A")
            o_type = getattr(obs, "type", "N/A")
            o_start = getattr(obs, "start_time", "N/A")
            o_end = getattr(obs, "end_time", "N/A")
            print(f"  - Observation: id={o_id}, name={o_name}, type={o_type}, start={o_start}, end={o_end}")
        url = client.get_trace_url(trace_id=trace_id)
        print(f"Dashboard URL: {url}")
        found = True
        break
    except Exception as exc:
        print(f"Attempt {attempt+1} waiting for ingestion: {exc}")
        time.sleep(3)

if not found:
    print("Listing recent traces:")
    try:
        traces = client.api.trace.list(limit=5)
        print("Recent traces:", [(t.id, t.name, t.timestamp) for t in traces.data])
    except Exception as list_exc:
        print("Failed to list traces:", list_exc)
