#!/usr/bin/env bash
# interrogation-pipeline installer (macOS / Linux)
#
# Usage:  bash ./install.sh
#
# Idempotent — safe to re-run. Verifies prereqs, sets up venv, installs Python
# deps, builds the frontend, scaffolds .env if missing, prints next steps.

set -euo pipefail
cd "$(dirname "$0")"

check_cmd() {
  local name="$1" hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    printf '\033[31mERROR:\033[0m %s not found on PATH.\n' "$name"
    printf '  %s\n' "$hint"
    exit 1
  fi
  printf 'OK    %s -> %s\n' "$name" "$(command -v "$name")"
}

echo
echo "=== Checking prerequisites ==="
check_cmd python3 "Install Python 3.11+ (macOS: 'brew install python@3.12'; Ubuntu: 'sudo apt install python3 python3-venv')"
check_cmd node    "Install Node 20+ (macOS: 'brew install node'; Ubuntu: see https://nodejs.org/)"
check_cmd npm     "Comes with Node.js"

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=${PY_VER%.*}; PY_MINOR=${PY_VER#*.}
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" = "3" ] && [ "$PY_MINOR" -lt 11 ]; }; then
  printf '\033[31mERROR:\033[0m Python %s is too old. Need 3.11+.\n' "$PY_VER"
  exit 1
fi
echo "OK    python version $PY_VER"

echo
echo "=== Backend venv + dependencies ==="
cd backend
if [ ! -d .venv ]; then
  echo "Creating .venv..."
  python3 -m venv .venv
fi
echo "Upgrading pip..."
./.venv/bin/python -m pip install --upgrade --quiet pip setuptools wheel
echo "Installing interrogation-pipeline + dev extras (1-2 min)..."
./.venv/bin/python -m pip install --quiet -e ".[dev]"
echo "OK    backend installed"

echo
echo "=== Frontend build ==="
cd ../frontend
if [ ! -d node_modules ]; then
  echo "Running npm install (1-3 min)..."
  npm install --no-audit --no-fund --silent
fi
echo "Building React app -> backend/interrogation_pipeline/static/ ..."
npm run build 2>&1 | tail -5
echo "OK    frontend built"
cd ..

echo
echo "=== Configuration ==="
ENV_PATH="backend/.env"
if [ ! -f "$ENV_PATH" ]; then
  cp backend/.env.example "$ENV_PATH"
  echo "OK    created $ENV_PATH from .env.example"
  printf '\033[33m      EDIT THIS FILE to add your API keys before running.\033[0m\n'
else
  echo "OK    $ENV_PATH already exists (not touched)"
fi

if [ ! -f "backend/data/cookies/cookies_p4.txt" ]; then
  printf '\033[33mWARN  no cookies_p4.txt found at backend/data/cookies/\033[0m\n'
  echo "      Export YT cookies via 'Get cookies.txt LOCALLY' Chrome extension and save there."
fi

echo
echo "=== All set ==="
echo
echo "Next:"
echo "  1. Edit backend/.env and fill in your API keys"
echo "  2. Drop cookies_p4.txt into backend/data/cookies/"
echo "  3. Start the server:"
echo "       cd backend"
echo "       ./.venv/bin/python -m interrogation_pipeline"
echo "  4. Open http://localhost:8765 in your browser"
echo
