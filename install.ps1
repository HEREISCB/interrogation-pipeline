# interrogation-pipeline installer (Windows PowerShell)
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# Idempotent — safe to re-run. Verifies prerequisites, sets up the venv,
# installs Python deps, builds the frontend, scaffolds .env if missing,
# and prints next steps.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Check-Cmd($name, $hint) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $found) {
        Write-Host "ERROR: '$name' not found on PATH." -ForegroundColor Red
        Write-Host "  $hint" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "OK    $name -> $($found.Source)"
}

Write-Host ""
Write-Host "=== Checking prerequisites ==="
Check-Cmd "python" "Install Python 3.11+ from https://www.python.org/downloads/"
Check-Cmd "node"   "Install Node 20+ from https://nodejs.org/ (needed for the dashboard build AND for yt-dlp's JS challenge solver at runtime)"
Check-Cmd "npm"    "Comes with Node.js"

# Python version check (>= 3.11)
$pyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([Version]$pyVer -lt [Version]"3.11") {
    Write-Host "ERROR: Python $pyVer is too old. Need 3.11+." -ForegroundColor Red
    exit 1
}
Write-Host "OK    python version $pyVer"

Write-Host ""
Write-Host "=== Backend venv + dependencies ==="
Push-Location backend
if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv..."
    & python -m venv .venv
}
Write-Host "Upgrading pip..."
& .\.venv\Scripts\python.exe -m pip install --upgrade --quiet pip setuptools wheel
Write-Host "Installing interrogation-pipeline + dev extras (this can take 1-2 minutes)..."
& .\.venv\Scripts\python.exe -m pip install --quiet -e ".[dev]"
Write-Host "OK    backend installed"

Write-Host ""
Write-Host "=== Frontend build ==="
Pop-Location
Push-Location frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "Running npm install (this can take 1-3 minutes)..."
    & npm install --no-audit --no-fund --silent
}
Write-Host "Building React app -> backend/interrogation_pipeline/static/ ..."
& npm run build 2>&1 | Select-Object -Last 5
Write-Host "OK    frontend built"
Pop-Location

Write-Host ""
Write-Host "=== Configuration ==="
$envPath = "backend\.env"
if (-not (Test-Path $envPath)) {
    Copy-Item "backend\.env.example" $envPath
    Write-Host "OK    created $envPath from .env.example"
    Write-Host "      EDIT THIS FILE to add your API keys before running." -ForegroundColor Yellow
} else {
    Write-Host "OK    $envPath already exists (not touched)"
}

if (-not (Test-Path "backend\data\cookies\cookies_p4.txt")) {
    Write-Host "WARN  no cookies_p4.txt found at backend\data\cookies\" -ForegroundColor Yellow
    Write-Host "      Export YT cookies via 'Get cookies.txt LOCALLY' Chrome extension and save there."
}

Write-Host ""
Write-Host "=== All set ==="
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Edit backend\.env and fill in your API keys"
Write-Host "  2. Drop cookies_p4.txt into backend\data\cookies\"
Write-Host "  3. Start the server:"
Write-Host "       cd backend"
Write-Host "       .\.venv\Scripts\python.exe -m interrogation_pipeline"
Write-Host "  4. Open http://localhost:8765 in your browser"
Write-Host ""
