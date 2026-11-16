"""Inspect mounts and routers in backend/app/main.py."""

import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app

print("=== MOUNTED ROUTERS & SUB-APPS ===")
for route in app.routes:
    if hasattr(route, "app"):
        print(f"Mounted Sub-App: {route.path} -> {route.app}")
        if hasattr(route.app, "routes"):
            for sub in route.app.routes:
                methods = ",".join(getattr(sub, "methods", []))
                print(f"   [{methods:10}] {route.path}{sub.path}")
    elif hasattr(route, "methods"):
        # Check if observability or mcp or a2a or adk
        if any(term in route.path for term in ["observability", "mcp", "a2a", "adk"]):
            methods = ",".join(route.methods)
            print(f"Protocol Route: [{methods:10}] {route.path}")
