"""Pytest Configuration for Gyaan AI Test Suite.

Enforces safe UTF-8 encoding across Windows terminal I/O and CrewAI event listeners.
Prevents 'charmap' codec errors on Unicode characters (e.g. \U0001f4cb).
"""

import os
import sys

# 1. Enforce UTF-8 in environment
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# 2. Reconfigure standard streams if available
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 3. Call backend UTF-8 enforcement
try:
    from backend import enforce_utf8_encoding
    enforce_utf8_encoding()
except Exception:
    pass
