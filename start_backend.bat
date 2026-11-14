@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title Gyaan AI - FastAPI Backend (Port 8000)
cd /d "%~dp0"
echo ============================================================
echo Starting Gyaan AI Backend Server (UTF-8 Enforced)...
echo Host: http://127.0.0.1:8000
echo Docs: http://127.0.0.1:8000/docs
echo ============================================================
"%~dp0.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
pause
