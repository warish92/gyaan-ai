import json

transcript_path = r"C:\Users\waris\.gemini\antigravity\brain\ee824e43-49ad-452b-908c-5e2df1c3a7ca\.system_generated\logs\transcript.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in reversed(lines):
    entry = json.loads(line)
    if entry.get("type") == "USER_INPUT":
        idx = entry.get("step_index")
        print(f"Found USER_INPUT at step {idx}")
        content = entry.get("content", "")
        print("Length:", len(content))
        with open("scratch/phase5a_security_audit/user_request_5a.txt", "w", encoding="utf-8") as out:
            out.write(content)
        print("Written to scratch/phase5a_security_audit/user_request_5a.txt")
        break
