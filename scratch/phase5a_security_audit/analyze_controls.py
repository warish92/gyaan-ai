"""Analyze security controls in backend source files."""

import inspect
import os
import re
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

def analyze_main_py():
    print("=== 1. FastAPI App Analysis (backend/app/main.py) ===")
    content = (PROJECT_ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    
    # Check middleware
    has_cors = "CORSMiddleware" in content
    cors_origins = re.findall(r"allow_origins=([^,\)]+)", content)
    has_rate_limit = "limiter" in content.lower() or "ratelimit" in content.lower()
    has_trusted_host = "TrustedHostMiddleware" in content
    has_https_redirect = "HTTPSRedirectMiddleware" in content
    has_security_headers = "SecurityHeaders" in content or "X-Frame-Options" in content or "X-Content-Type-Options" in content
    
    print(f"CORS enabled: {has_cors}, Origins: {cors_origins}")
    print(f"Rate limiting: {has_rate_limit}")
    print(f"TrustedHost: {has_trusted_host}")
    print(f"HTTPS redirect: {has_https_redirect}")
    print(f"Security headers middleware: {has_security_headers}")
    
    # Check endpoints and auth dependencies
    routes = re.findall(r"@app\.(get|post|put|delete|patch)\(([^)]+)\)", content)
    print(f"Direct app routes found: {len(routes)}")
    for method, path in routes[:15]:
        print(f"  {method.upper()} {path.split(',')[0].strip()}")
    if len(routes) > 15:
        print(f"  ... and {len(routes) - 15} more routes")
        
    # Check included routers
    routers = re.findall(r"app\.include_router\(([^)]+)\)", content)
    print(f"Included routers: {len(routers)}")
    for r in routers:
        print(f"  {r.strip()}")

def analyze_auth():
    print("\n=== 2. Auth Service Analysis (backend/services/auth_service.py) ===")
    auth_file = PROJECT_ROOT / "backend/services/auth_service.py"
    if auth_file.exists():
        content = auth_file.read_text(encoding="utf-8")
        has_bcrypt = "bcrypt" in content
        has_pbkdf2 = "pbkdf2" in content
        has_hashlib = "hashlib" in content
        has_jwt = "jwt" in content.lower()
        secret_key_matches = re.findall(r"(?:SECRET|KEY|SALT)\s*=\s*['\"]([^'\"]+)['\"]", content, re.IGNORECASE)
        print(f"Password hashing: bcrypt={has_bcrypt}, pbkdf2={has_pbkdf2}, hashlib={has_hashlib}")
        print(f"JWT usage: {has_jwt}")
        print(f"Hardcoded keys/salts in auth: {len(secret_key_matches)}")
        for line in content.splitlines():
            if any(term in line.lower() for term in ["hash", "token", "password", "algorithm", "secret"]):
                if not line.strip().startswith("#"):
                    print(f"  [AUTH CODE] {line.strip()[:100]}")

def analyze_database():
    print("\n=== 3. Database Operations Analysis (backend/db/database.py) ===")
    db_file = PROJECT_ROOT / "backend/db/database.py"
    if db_file.exists():
        content = db_file.read_text(encoding="utf-8")
        # Check for string formatting in execute calls
        unsafe_executes = re.findall(r"\.execute\(\s*f['\"][^'\"]+['\"]", content)
        safe_executes = re.findall(r"\.execute\(\s*['\"][^'\"]+\?['\"]", content)
        print(f"Safe parameterized executes (?): {len(safe_executes)}")
        print(f"Potentially unsafe f-string executes: {len(unsafe_executes)}")
        if unsafe_executes:
            for ue in unsafe_executes[:5]:
                print(f"  [UNSAFE SQL CANDIDATE] {ue[:100]}")

def analyze_mcp_security():
    print("\n=== 4. MCP Security Analysis (backend/mcp_integration/security.py) ===")
    mcp_sec = PROJECT_ROOT / "backend/mcp_integration/security.py"
    if mcp_sec.exists():
        content = mcp_sec.read_text(encoding="utf-8")
        print(f"File size: {len(content)} chars")
        for line in content.splitlines():
            if any(term in line.lower() for term in ["sandbox", "path", "allowed", "restrict", "validate", "traversal"]):
                if not line.strip().startswith("#"):
                    print(f"  [MCP SEC] {line.strip()[:100]}")

def analyze_a2a_security():
    print("\n=== 5. A2A Security Analysis (backend/a2a_protocol/security.py) ===")
    a2a_sec = PROJECT_ROOT / "backend/a2a_protocol/security.py"
    if a2a_sec.exists():
        content = a2a_sec.read_text(encoding="utf-8")
        print(f"File size: {len(content)} chars")
        for line in content.splitlines():
            if any(term in line.lower() for term in ["token", "verify", "auth", "secret", "validate", "signature"]):
                if not line.strip().startswith("#"):
                    print(f"  [A2A SEC] {line.strip()[:100]}")

if __name__ == "__main__":
    analyze_main_py()
    analyze_auth()
    analyze_database()
    analyze_mcp_security()
    analyze_a2a_security()
