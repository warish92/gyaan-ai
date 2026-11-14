"""Pytest Configuration for Gyaan AI Test Suite.

Enforces:
1. Safe UTF-8 encoding across Windows terminal I/O and CrewAI event listeners.
2. Complete test database isolation via automatic temporary SQLite database fixtures.
   Ensures tests NEVER write to data/gyaan_ai.db or the Phase 4 backup.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure workspace root is in sys.path
workspace_dir = Path(__file__).resolve().parent.parent
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

# 1. Enforce UTF-8 in environment
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ.setdefault("A2A_INTERNAL_SECRET", "gyaan_ai_internal_test_secret_key_2026")
os.environ.setdefault("TELEMETRY_HMAC_SECRET", "gyaan_ai_telemetry_test_secret_2026")

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


@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """Session-wide fixture ensuring ALL pytest executions operate on an isolated
    temporary SQLite database.
    Prevents tests from writing to data/gyaan_ai.db or modifying production/dev student records.
    """
    from backend.db.database import DEFAULT_DB_PATH, get_db_path, init_db

    test_dir = tempfile.mkdtemp(prefix="gyaan_test_isolated_db_")
    test_db_path = Path(test_dir) / "isolated_test_gyaan_ai.db"

    # Initialize complete schema in temporary database
    init_db(custom_path=test_db_path)

    # Export environment overrides for all application modules and background tasks
    os.environ["GYAAN_DB_PATH"] = str(test_db_path)
    os.environ["DATABASE_PATH"] = str(test_db_path)
    os.environ["GYAAN_TEST_MODE"] = "1"

    # Verify isolation immediately
    resolved = get_db_path()
    assert resolved == test_db_path.resolve(), f"Database isolation failed! Expected {test_db_path}, got {resolved}"
    assert resolved != DEFAULT_DB_PATH, "CRITICAL: Test database resolved to active project database!"

    yield test_db_path

    # Teardown: Clean up temporary test database only
    os.environ.pop("GYAAN_DB_PATH", None)
    os.environ.pop("DATABASE_PATH", None)
    os.environ.pop("GYAAN_TEST_MODE", None)
    try:
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass
