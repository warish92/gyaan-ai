import json

compact_path = r"C:\Users\waris\.gemini\antigravity\brain\ee824e43-49ad-452b-908c-5e2df1c3a7ca\.system_generated\logs\transcript.jsonl"
full_path = r"C:\Users\waris\.gemini\antigravity\brain\ee824e43-49ad-452b-908c-5e2df1c3a7ca\.system_generated\logs\transcript_full.jsonl"

with open(compact_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("step_index") == 12305:
            print("compact entry truncated fields:", data.get("truncated_fields"))
            break

with open(full_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("step_index") == 12305:
            content = data.get("content", "")
            print("Full content length:", len(content))
            with open("scratch/phase5a_security_audit/user_request_5a_full.txt", "w", encoding="utf-8") as out:
                out.write(content)
            print("Written full prompt to scratch/phase5a_security_audit/user_request_5a_full.txt")
            break
