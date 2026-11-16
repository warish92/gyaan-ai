"""Inspect routes within sub-routers."""

import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from backend.adk.api import adk_router
from backend.a2a_protocol import a2a_router
from backend.mcp_integration import mcp_router
from backend.observability import observability_router

routers = [
    ("ADK Router", adk_router),
    ("A2A Router", a2a_router),
    ("MCP Router", mcp_router),
    ("Observability Router", observability_router),
]

for name, r in routers:
    print(f"\n=== {name} (prefix: '{getattr(r, 'prefix', '')}') ===")
    for route in r.routes:
        methods = ",".join(getattr(route, "methods", []))
        deps = [d.dependency.__name__ if hasattr(d, "dependency") and hasattr(d.dependency, "__name__") else str(d) for d in getattr(route, "dependencies", [])]
        print(f"  [{methods:10}] {route.path:40} | Deps: {deps}")
