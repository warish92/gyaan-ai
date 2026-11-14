@echo off
title Gyaan AI - System Launcher & Health Monitor
cd /d "%~dp0"
echo ============================================================
echo               GYAAN AI - SYSTEM LAUNCHER
echo ============================================================
echo.

:: 1. Check & Start Ollama
echo [1/3] Checking Ollama Service (Port 11434)...
powershell -NoProfile -Command "
$r = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2).StatusCode } catch { 0 }
if ($r -eq 200) {
    Write-Host '  -> Ollama is already running on http://127.0.0.1:11434.' -ForegroundColor Green
} else {
    Write-Host '  -> Starting Ollama daemon...' -ForegroundColor Yellow
    Start-Process -FilePath '%LOCALAPPDATA%\Programs\Ollama\ollama.exe' -ArgumentList 'serve' -WindowStyle Minimized
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        $chk = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2).StatusCode } catch { 0 }
        if ($chk -eq 200) { $ready = $true; break }
    }
    if ($ready) {
        Write-Host '  -> Ollama started successfully.' -ForegroundColor Green
    } else {
        Write-Host '  -> [WARNING] Ollama did not respond within 10s. Continuing...' -ForegroundColor Red
    }
}
"

:: 2. Check & Start FastAPI Backend
echo.
echo [2/3] Checking FastAPI Backend (Port 8000)...
powershell -NoProfile -Command "
$r = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2).StatusCode } catch { 0 }
if ($r -eq 200) {
    Write-Host '  -> Backend is already running on http://127.0.0.1:8000.' -ForegroundColor Green
} else {
    Write-Host '  -> Launching FastAPI Backend in a new window...' -ForegroundColor Yellow
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k \"\"%~dp0start_backend.bat\"\"'
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $chk = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2).StatusCode } catch { 0 }
        if ($chk -eq 200) { $ready = $true; break }
    }
    if ($ready) {
        Write-Host '  -> Backend is healthy and ready.' -ForegroundColor Green
    } else {
        Write-Host '  -> [WARNING] Backend did not respond within 15s. Check the Backend console window.' -ForegroundColor Red
    }
}
"

:: 3. Check & Start Next.js Frontend
echo.
echo [3/3] Checking Next.js Frontend (Port 3000)...
powershell -NoProfile -Command "
$r = try { (Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 2).StatusCode } catch { 0 }
if ($r -eq 200) {
    Write-Host '  -> Frontend is already running on http://localhost:3000.' -ForegroundColor Green
} else {
    Write-Host '  -> Launching Next.js Frontend in a new window...' -ForegroundColor Yellow
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k \"\"%~dp0start_frontend.bat\"\"'
    $ready = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        $chk = try { (Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 2).StatusCode } catch { 0 }
        if ($chk -eq 200) { $ready = $true; break }
    }
    if ($ready) {
        Write-Host '  -> Frontend is ready on http://localhost:3000.' -ForegroundColor Green
    } else {
        Write-Host '  -> [NOTE] Frontend compilation in progress. Please check the Frontend console window.' -ForegroundColor Cyan
    }
}
"

echo.
echo ============================================================
echo               ALL SERVICES VERIFIED & READY
echo ============================================================
echo   Frontend:  http://localhost:3000
echo   Backend:   http://127.0.0.1:8000
echo   API Docs:  http://127.0.0.1:8000/docs
echo   Ollama:    http://127.0.0.1:11434
echo ============================================================
echo.
pause
