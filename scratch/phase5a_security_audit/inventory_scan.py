import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path("D:/Gyaan AI").resolve()

def scan_files():
    backend_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT / "backend"):
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for f in files:
            if f.endswith(".py"):
                rel_path = Path(root, f).relative_to(PROJECT_ROOT).as_posix()
                backend_files.append(rel_path)
                
    frontend_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT / "frontend"):
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if ".next" in dirs:
            dirs.remove(".next")
        for f in files:
            rel_path = Path(root, f).relative_to(PROJECT_ROOT).as_posix()
            frontend_files.append(rel_path)

    test_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT / "tests"):
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for f in files:
            if f.endswith(".py"):
                rel_path = Path(root, f).relative_to(PROJECT_ROOT).as_posix()
                test_files.append(rel_path)

    return {
        "backend_files": sorted(backend_files),
        "frontend_files": sorted(frontend_files),
        "test_files": sorted(test_files),
    }

if __name__ == "__main__":
    res = scan_files()
    print(f"Total backend python files: {len(res['backend_files'])}")
    for f in res['backend_files']:
        print(" ", f)
    print(f"\nTotal test python files: {len(res['test_files'])}")
    for f in res['test_files']:
        print(" ", f)
    print(f"\nTotal frontend files: {len(res['frontend_files'])}")
    for f in res['frontend_files'][:30]:
        print(" ", f)
    if len(res['frontend_files']) > 30:
        print(f"  ... and {len(res['frontend_files']) - 30} more frontend files.")
