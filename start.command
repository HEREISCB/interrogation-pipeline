#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  Interrogation Pipeline — one-click launcher (macOS)
#
#  Double-click this file. It will:
#    1. Verify Python + Node are installed
#    2. Run first-time setup if .venv is missing (~2-3 min)
#    3. Build the dashboard if missing
#    4. Start the server
#    5. Open the dashboard in your browser
#
#  To stop: press Ctrl+C in this terminal.
# ─────────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")"

echo ""
echo "===================================================="
echo "  Interrogation Pipeline launcher"
echo "===================================================="

# ── Prerequisite checks ────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    cat <<EOF

ERROR: python3 is not installed or not on PATH.

Install Python 3.11+ via Homebrew:
  brew install python@3.12

Or download from https://www.python.org/downloads/
Then re-run this file.

EOF
    read -r -p "Press enter to close..."
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    cat <<EOF

ERROR: node is not installed or not on PATH.

Install Node 20+ via Homebrew:
  brew install node

Or download from https://nodejs.org/

Node is needed both to build the dashboard AND at runtime for
yt-dlp's JavaScript challenge solver. Don't skip.

EOF
    read -r -p "Press enter to close..."
    exit 1
fi

# ── First-time setup ──────────────────────────────────────────
if [ ! -x "backend/.venv/bin/python" ]; then
    echo ""
    echo "============================================"
    echo "  First-time setup: 2-3 minutes"
    echo "============================================"
    bash ./install.sh || {
        echo ""
        echo "Setup failed. See messages above."
        read -r -p "Press enter to close..."
        exit 1
    }
fi

# ── Always re-sync Python deps (idempotent, fast) ──
echo "Syncing Python dependencies..."
(cd backend && ./.venv/bin/python -m pip install -e ".[dev]" --quiet)

# ── Build frontend if missing ─────────────────────────────────
if [ ! -f "backend/interrogation_pipeline/static/index.html" ]; then
    echo "Building dashboard (2-5 min on first build)..."
    pushd frontend >/dev/null
    if [ ! -d "node_modules/@types/node" ]; then
        echo "Installing npm packages..."
        npm install --no-audit --no-fund
    fi
    npm run build || {
        popd >/dev/null
        echo ""
        echo "Dashboard build failed. See messages above."
        read -r -p "Press enter to close..."
        exit 1
    }
    popd >/dev/null
fi

# Verify the build actually landed
if [ ! -f "backend/interrogation_pipeline/static/index.html" ]; then
    echo ""
    echo "ERROR: build finished but backend/interrogation_pipeline/static/index.html"
    echo "is missing. Try: cd frontend && npm run build"
    read -r -p "Press enter to close..."
    exit 1
fi

# ── Verify .env exists ────────────────────────────────────────
if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    cat <<EOF

============================================================
  IMPORTANT: backend/.env was just created from .env.example.
  Open it in a text editor and fill in your API keys:
    - ANTHROPIC_API_KEY  (https://console.anthropic.com)
    - TAVILY_API_KEY     (https://tavily.com)
    - TRELLO_API_KEY     (https://trello.com/power-ups/admin)
    - TRELLO_TOKEN       (see ONBOARDING.md)
    - WEBSHARE_USERNAME / WEBSHARE_PASSWORD  (optional)

  Then close this window and double-click start.command again.
============================================================

EOF
    open -e backend/.env || true
    read -r -p "Press enter to close..."
    exit 0
fi

# ── Kill any stale server on the port ────────────────────────
STALE_PIDS=$(lsof -ti :8765 2>/dev/null || true)
if [ -n "$STALE_PIDS" ]; then
    echo "Found existing process(es) on port 8765: $STALE_PIDS — stopping them..."
    kill -9 $STALE_PIDS 2>/dev/null || true
    sleep 1
fi

# ── Open browser after the server is ready ────────────────────
(sleep 6 && open "http://127.0.0.1:8765") &

cat <<EOF

====================================================
  Interrogation Pipeline starting...
  Dashboard:  http://127.0.0.1:8765

  Browser will open automatically in ~6 seconds.
  To stop the server: press Ctrl+C.
====================================================

EOF

cd backend
./.venv/bin/python -m interrogation_pipeline
echo ""
echo "--- Server stopped. ---"
read -r -p "Press enter to close..."
