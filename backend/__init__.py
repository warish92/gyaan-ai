"""Gyaan AI Backend Package.

Initializes safe UTF-8 encoding across Windows terminal I/O, Rich Consoles,
and CrewAI event handlers to prevent 'charmap' codec errors on Unicode emojis.
"""

import os
import sys

# Ensure project root (D:\Gyaan AI) is always in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)


def enforce_utf8_encoding() -> None:
    """Safely configure process I/O, terminal logging, and CrewAI event consoles for UTF-8 on Windows.

    Guarantees that CrewAI event bus notifications (task_started, task_completed)
    with Unicode emojis (e.g. \U0001f4cb clipboard) render without 'charmap' codec errors.
    """
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    # 1. Reconfigure standard streams safely in place without wrapping
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # 2. Reconfigure CrewAI event bus console and listeners if already imported
    try:
        from crewai.events.event_bus import crewai_event_bus

        if hasattr(crewai_event_bus, "_console") and hasattr(crewai_event_bus._console, "console"):
            c_file = getattr(crewai_event_bus._console.console, "file", None)
            if hasattr(c_file, "reconfigure"):
                try:
                    c_file.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        sync_handlers = getattr(crewai_event_bus, "_sync_handlers", {})
        for _, handlers in sync_handlers.items():
            for handler in handlers:
                if hasattr(handler, "__closure__") and handler.__closure__:
                    for cell in handler.__closure__:
                        obj = getattr(cell, "cell_contents", None)
                        if hasattr(obj, "formatter") and hasattr(obj.formatter, "console"):
                            f_file = getattr(obj.formatter.console, "file", None)
                            if hasattr(f_file, "reconfigure"):
                                try:
                                    f_file.reconfigure(encoding="utf-8", errors="replace")
                                except Exception:
                                    pass
    except Exception:
        pass


# Enforce UTF-8 immediately on backend package import
enforce_utf8_encoding()
