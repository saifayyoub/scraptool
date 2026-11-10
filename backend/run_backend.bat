@echo off
SETLOCAL EnableExtensions
title EduFeed Backend - Live Activity Log
cd /d "%~dp0"

set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "LOG=%~dp0server.log"

:: Keep the previous run's log for troubleshooting, and start a fresh one.
if exist "%LOG%" move /y "%LOG%" "%~dp0server.prev.log" >nul 2>&1

if /i "%PY%"=="python" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ============================================================
        echo  [X] Python was not found.
        echo      Expected: %~dp0venv\Scripts\python.exe
        echo      Install the virtual environment or Python, then retry.
        echo ============================================================
        echo.
        pause
        exit /b 1
    )
)

echo ============================================================
echo   EduFeed Backend
echo ------------------------------------------------------------
echo   Everything the tool does is printed in THIS window:
echo   requests, feed syncs, full-text fetches, errors, etc.
echo.
echo   Python  : %PY%
echo   Log file: %LOG%
echo   Address : http://127.0.0.1:8002
echo ============================================================
echo.
echo Starting the server... (first start can take a few seconds)
echo.

:: Run the server and show its output live in this window,
:: while also saving it (UTF-8, no BOM) to server.log.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $sw = New-Object System.IO.StreamWriter('%LOG%', $false, (New-Object System.Text.UTF8Encoding($false))); $sw.AutoFlush = $true; try { & '%PY%' -u main.py *>&1 | ForEach-Object { $line = \"$_\"; Write-Host $line; $sw.WriteLine($line) } } finally { $sw.Close() } }"
set "RC=%errorlevel%"

echo.
echo ============================================================
echo   [!] The EduFeed backend has stopped. Exit code: %RC%
echo       Scroll up to read the last messages.
echo       Full log: %LOG%
echo ============================================================
echo.
pause
exit /b %RC%
