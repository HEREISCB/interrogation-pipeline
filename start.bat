@echo off
REM ────────────────────────────────────────────────────────────────
REM  Interrogation Pipeline — one-click launcher (Windows)
REM
REM  Double-click this file. It will:
REM    1. Verify Python + Node are installed
REM    2. Run first-time setup if .venv is missing (~2-3 min)
REM    3. Build the dashboard if missing
REM    4. Start the server
REM    5. Open the dashboard in your browser
REM
REM  To stop: press Ctrl+C, then close this window.
REM ────────────────────────────────────────────────────────────────

title Interrogation Pipeline
cd /d "%~dp0"

REM ── Prerequisite checks ────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not on PATH.
    echo.
    echo Install Python 3.11 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: check "Add Python to PATH" during install.
    echo Then re-run this file.
    echo.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Node.js is not installed or not on PATH.
    echo.
    echo Install Node.js 20 or newer from:
    echo   https://nodejs.org/
    echo.
    echo Node is needed both to build the dashboard AND at runtime
    echo for yt-dlp's JavaScript challenge solver. Don't skip.
    echo.
    pause
    exit /b 1
)

REM ── First-time setup ──────────────────────────────────────────
if not exist "backend\.venv\Scripts\python.exe" (
    echo.
    echo ============================================
    echo  First-time setup: 2-3 minutes
    echo ============================================
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    if errorlevel 1 (
        echo.
        echo Setup failed. See the messages above.
        pause
        exit /b 1
    )
)

REM ── Always re-sync Python deps (idempotent, fast when nothing changed) ──
echo Syncing Python dependencies...
pushd backend
".venv\Scripts\python.exe" -m pip install -e ".[dev]" --quiet 2>nul
popd

REM ── Build frontend if missing ─────────────────────────────────
if not exist "backend\interrogation_pipeline\static\index.html" (
    echo Building dashboard ^(2-5 min on first build^)...
    pushd frontend
    if not exist "node_modules\@types\node" (
        echo Installing npm packages...
        call npm install --no-audit --no-fund
    )
    call npm run build
    if errorlevel 1 (
        popd
        echo.
        echo ============================================
        echo  Dashboard build FAILED. See messages above.
        echo  Common fix: run 'npm install' in frontend^\
        echo ============================================
        pause
        exit /b 1
    )
    popd
)

REM Verify the build actually landed where the server expects it
if not exist "backend\interrogation_pipeline\static\index.html" (
    echo.
    echo ============================================
    echo  ERROR: build finished but
    echo    backend\interrogation_pipeline\static\index.html
    echo  is missing. The dashboard won't load.
    echo  Try: cd frontend ^&^& npm run build
    echo ============================================
    pause
    exit /b 1
)

REM ── Verify .env exists ────────────────────────────────────────
if not exist "backend\.env" (
    copy /Y "backend\.env.example" "backend\.env" >nul
    echo.
    echo ============================================================
    echo  IMPORTANT: backend\.env was just created from .env.example
    echo  Open it in a text editor and fill in your API keys:
    echo    - ANTHROPIC_API_KEY   ^(from https://console.anthropic.com^)
    echo    - TAVILY_API_KEY      ^(from https://tavily.com^)
    echo    - TRELLO_API_KEY      ^(from https://trello.com/power-ups/admin^)
    echo    - TRELLO_TOKEN        ^(see ONBOARDING.md^)
    echo    - WEBSHARE_USERNAME / WEBSHARE_PASSWORD  ^(optional^)
    echo.
    echo  Then close this window and run start.bat again.
    echo ============================================================
    echo.
    echo Press any key to open backend\.env in Notepad...
    pause >nul
    start notepad "backend\.env"
    exit /b 0
)

REM ── Kill any stale server on the port ─────────────────────────
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":8765 " ^| findstr "LISTENING"') do (
    echo Found existing process on port 8765 ^(PID %%P^). Stopping it...
    taskkill /F /PID %%P >nul 2>&1
)

REM ── Open the browser after the server is up ───────────────────
start /min cmd /c "timeout /t 7 /nobreak >nul && start http://127.0.0.1:8765"

echo.
echo ====================================================
echo   Interrogation Pipeline starting...
echo   Dashboard:  http://127.0.0.1:8765
echo.
echo   Browser will open automatically in ~7 seconds.
echo   To stop the server: press Ctrl+C, then close.
echo ====================================================
echo.

cd backend
".venv\Scripts\python.exe" -m interrogation_pipeline

REM ── If the server exits, keep the window open so the user can read errors ──
echo.
echo --- Server stopped. Press any key to close. ---
pause >nul
