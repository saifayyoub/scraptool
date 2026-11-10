@echo off
SETLOCAL EnableExtensions EnableDelayedExpansion
title EduFeed Launcher

echo ==========================================
echo    EduFeed - Professional RSS Curation
echo ==========================================
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "PY=%BACKEND%\venv\Scripts\python.exe"
set "LOG=%BACKEND%\server.log"
set "ADDR=http://127.0.0.1:8002"

:: --- 1. Stop any old EduFeed server still holding port 8002 ---
echo [1/4] Checking for an old server on port 8002...
set "OLD="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "127.0.0.1:8002" ^| findstr "LISTENING"') do (
    set "OLD=1"
    echo       Stopping old server process %%P ...
    taskkill /PID %%P /T /F >nul 2>&1
)
if not defined OLD echo       No old server running. Good.
echo.

:: --- 2. Start the backend in its own window that shows live activity ---
echo [2/4] Starting the backend server...
echo       A new window named "EduFeed Backend - Live Activity Log" will open.
echo       That window shows everything the tool is doing.
start "EduFeed Backend - Live Activity Log" "%BACKEND%\run_backend.bat"
if errorlevel 1 (
    echo.
    echo [X] Could not open the backend window.
    echo     Try running "%BACKEND%\run_backend.bat" directly.
    echo.
    pause
    exit /b 1
)
echo.

:: --- 3. Wait until the server is really listening (max ~40s) ---
echo [3/4] Waiting for the server to be ready (max 40s)...
set /a tries=0
:wait
set /a tries+=1
netstat -ano | findstr "127.0.0.1:8002" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto ready
if %tries% geq 40 goto failed
<nul set /p "=."
timeout /t 1 /nobreak >nul
goto wait

:ready
echo.
echo       Server is up after %tries% second^(s^).
echo.

:: --- 4. Open the frontend ---
echo [4/4] Opening EduFeed in your browser...
start "" "%ADDR%/index.html"
echo.
echo ==========================================
echo    EduFeed is now running!
echo ==========================================
echo    URL      : %ADDR%
echo    Live log : the "EduFeed Backend - Live Activity Log"
echo               window (keep it open, it shows every action)
echo    Log file : %LOG%
echo.
echo    If something looks wrong, read that backend window:
echo    errors from feeds, imports, publishing, etc. show there.
echo ==========================================
echo.
echo Press any key to close THIS launcher only.
echo (The backend keeps running, so EduFeed stays available.)
pause >nul
exit /b 0

:failed
echo.
echo ==========================================
echo [X] The server did not start within the time limit.
echo     Log file: %LOG%
echo ==========================================
echo.
if exist "%LOG%" (
    echo ---- last lines of the log ----
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 30"
    echo -------------------------------
) else (
    echo [i] No log file yet - the backend probably failed before writing.
    echo     Open "%BACKEND%\run_backend.bat" directly to see the error.
)
echo.
pause
exit /b 1
