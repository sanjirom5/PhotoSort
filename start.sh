#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== PhotoSort ==="

# Backend
echo "[1/2] Starting FastAPI backend on :8000 …"
cd "$ROOT"
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# Frontend
echo "[2/2] Starting React frontend on :5173 …"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend  → http://localhost:8001"
echo "Frontend → http://localhost:5173"
echo "API docs → http://localhost:8001/docs"
echo ""
echo "Press Ctrl+C to stop both."

trap "echo 'Stopping…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
