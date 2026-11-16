"""
Audit script for Prompt Injection, Toxicity, Multi-Agent Delegation, and Content Moderation.
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

print("=" * 60)
print("1. PROMPT INJECTION & GUARDRAIL INSPECTION")
print("=" * 60)

# Check A2A security prompt injection regex
a2a_sec_file = PROJECT_ROOT / "backend/a2a_protocol/security.py"
if a2a_sec_file.exists():
    content = a2a_sec_file.read_text(encoding="utf-8")
    print("A2A Security prompt injection patterns:")
    for line in content.splitlines():
        if "PROMPT_INJECTION" in line or "INJECTION" in line or "re.compile" in line:
            print("  ", line.strip())

# Check MCP security prompt injection
mcp_sec_file = PROJECT_ROOT / "backend/mcp_integration/security.py"
if mcp_sec_file.exists():
    content = mcp_sec_file.read_text(encoding="utf-8")
    print("\nMCP Security injection patterns:")
    for line in content.splitlines():
        if "PROMPT_INJECTION" in line or "INJECTION" in line or "re.compile" in line:
            print("  ", line.strip())

# Search for any guardrail / moderation libraries or files across backend
print("\n" + "=" * 60)
print("2. TOXICITY / MODERATION / GUARDRAIL SEARCH")
print("=" * 60)

toxicity_terms = ["toxic", "profan", "moderation", "abuse", "hate", "harass", "guardrail", "nemo", "llama_guard"]
found_files = {}

for py_file in PROJECT_ROOT.glob("backend/**/*.py"):
    text = py_file.read_text(encoding="utf-8", errors="ignore").lower()
    for term in toxicity_terms:
        if term in text:
            rel = str(py_file.relative_to(PROJECT_ROOT))
            found_files.setdefault(term, []).append(rel)

if found_files:
    for term, files in found_files.items():
        print(f"Term '{term}' found in: {files}")
else:
    print("NO toxicity, profanity, or moderation terms found in backend Python files!")

# Search in dependencies (requirements.txt, pyproject.toml)
print("\n" + "=" * 60)
print("3. DEPENDENCY SCAN FOR SECURITY / MODERATION / RATE-LIMITING")
print("=" * 60)

for req_name in ["requirements.txt", "pyproject.toml"]:
    req_file = PROJECT_ROOT / req_name
    if req_file.exists():
        print(f"\n--- {req_name} ---")
        lines = req_file.read_text(encoding="utf-8").splitlines()
        for l in lines:
            low = l.lower()
            if any(k in low for k in ["guard", "limit", "slowapi", "auth", "crypt", "pydantic", "fastapi", "cors", "jwt", "passlib", "moderation"]):
                print("  ", l.strip())

# Inspect Multi-Agent Delegation in Orchestrator
print("\n" + "=" * 60)
print("4. ORCHESTRATOR & AGENT DELEGATION SECURITY")
print("=" * 60)

orch_file = PROJECT_ROOT / "backend/agents/orchestrator.py"
if orch_file.exists():
    orch_content = orch_file.read_text(encoding="utf-8")
    print(f"Orchestrator file size: {len(orch_content)} chars")
    # check delegation patterns
    print("Delegation methods/functions:")
    for line in orch_content.splitlines():
        if any(keyword in line for keyword in ["def ", "class ", "delegate", "session", "student", "authenticate", "authorize"]):
            if "def " in line or "class " in line:
                print("  ", line.strip())

# Check Agent files list
print("\n" + "=" * 60)
print("5. AGENT FILES AND CANONICAL AGENTS")
print("=" * 60)
agent_files = list((PROJECT_ROOT / "backend/agents").glob("*.py"))
for af in agent_files:
    print("  ", af.name, f"({af.stat().st_size} bytes)")
