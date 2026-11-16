"""Inspect FastAPI app.routes for complete endpoint inventory and security dependencies."""

import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app

print("=== COMPLETE FASTAPI ROUTE AUDIT ===")
print(f"Total routes in app: {len(app.routes)}\n")

unauthenticated_endpoints = []
authenticated_endpoints = []
optional_auth_endpoints = []

for route in app.routes:
    # Skip static or mounted apps
    if not hasattr(route, "methods"):
        continue
    
    methods = ",".join(route.methods)
    path = route.path
    endpoint_func = route.endpoint
    
    # Check dependencies on the route and endpoint
    deps = []
    if hasattr(route, "dependencies"):
        deps.extend([d.dependency.__name__ if hasattr(d, "dependency") and hasattr(d.dependency, "__name__") else str(d) for d in route.dependencies])
    
    # Check signature parameters for Depends
    import inspect
    sig = inspect.signature(endpoint_func)
    func_deps = []
    for param in sig.parameters.values():
        if "Depends" in str(param.default):
            func_deps.append(param.name)
            
    all_deps_str = " ".join(deps + func_deps)
    
    is_auth = "current_student" in all_deps_str or "auth" in all_deps_str.lower() or "verify" in all_deps_str.lower()
    is_optional = "optional" in all_deps_str.lower()
    
    if is_optional:
        status = "OPTIONAL_AUTH"
        optional_auth_endpoints.append((methods, path, all_deps_str))
    elif is_auth:
        status = "AUTHENTICATED"
        authenticated_endpoints.append((methods, path, all_deps_str))
    else:
        status = "PUBLIC"
        unauthenticated_endpoints.append((methods, path))
        
    print(f"[{methods:10}] {path:45} | {status:15} | Deps: {all_deps_str}")

print("\n--- SUMMARY ---")
print(f"Total API Routes: {len(authenticated_endpoints) + len(unauthenticated_endpoints) + len(optional_auth_endpoints)}")
print(f"Authenticated Routes: {len(authenticated_endpoints)}")
print(f"Optional Auth Routes: {len(optional_auth_endpoints)}")
print(f"Public / Unauthenticated Routes: {len(unauthenticated_endpoints)}")
