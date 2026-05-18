@echo off
SETLOCAL EnableDelayedExpansion

:: --- EduFeed Easy Launcher ---
:: This script starts the FastAPI backend and opens the frontend.

echo ==========================================
echo    EduFeed - Professional RSS Curation
echo ==========================================
echo.

:: 1. Navigate to backend and start server
echo [1/3] Starting Backend Server...
cd /d "%~dp0backend"

if exist "venv\Scripts\activate.bat" (
    echo [OK] Virtual environment found.
    :: Start backend in a minimized window
    start "EduFeed Backend" /min cmd /c "venv\Scripts\activate.bat && python main.py"
) else (
    echo [!] Virtual environment not found in backend/venv. 
    echo [!] Attempting to run with system python...
    start "EduFeed Backend" /min cmd /c "python main.py"
)

:: 2. Wait for backend to be ready
echo [2/3] Waiting for server to initialize (5s)...
timeout /t 5 /nobreak > nul

:: 3. Open the frontend
echo [3/3] Opening EduFeed in your browser...
start "" "%~dp0frontend\index.html"

echo.
echo ==========================================
echo    EduFeed is now running!
echo    KEEP THE MINIMIZED TERMINAL OPEN.
echo ==========================================
echo.
pause
exit
