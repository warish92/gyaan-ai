"""Gyaan AI Site Customization for Universal Windows UTF-8 Encoding.

Automatically executed on Python interpreter startup.
Enforces UTF-8 encoding across Windows terminal I/O, preventing
'charmap' UnicodeEncodeError across all CrewAI event handlers.
"""

import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
