#!/usr/bin/env bash
# Start the ElephantVoices Denoiser demo (backend + frontend dev server)
# Usage: bash scripts/start_demo.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== ElephantVoices Denoiser — HackSMU 2026 ==="
echo ""

# Check Python deps
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Start FastAPI backend in background
echo "Starting FastAPI backend on http://localhost:8001 (matches Vite /api proxy) ..."
uvicorn api.main:app --reload --port 8001 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Start frontend dev server
if [ -d "frontend/node_modules" ]; then
    echo "Starting Vite frontend on http://localhost:5173 ..."
    cd frontend && npm run dev
else
    echo ""
    echo "Frontend dependencies not installed. Run:"
    echo "  cd frontend && npm install && npm run dev"
    echo ""
    echo "Backend is running. API available at http://localhost:8001"
    wait $BACKEND_PID
fi
