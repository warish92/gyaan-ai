@echo off
title Gyaan AI - Next.js Frontend (Port 3000)
cd /d "%~dp0frontend"
echo ============================================================
echo Starting Gyaan AI Next.js Frontend...
echo URL: http://localhost:3000
echo ============================================================
call npm run dev -- -p 3000
pause
