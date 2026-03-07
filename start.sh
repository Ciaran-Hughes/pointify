#!/bin/bash
# Start Pointify app (backend + frontend)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Pointify..."

# Backend
cd "$ROOT/backend"
if [ ! -f ".venv/bin/activate" ]; then
  echo "ERROR: Python venv not found. Run: cd backend && python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend running on http://localhost:8000 (PID $BACKEND_PID)"

# Frontend
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "ERROR: node_modules not found. Run: cd frontend && npm install"
  kill $BACKEND_PID
  exit 1
fi
npm run dev &
FRONTEND_PID=$!
echo "Frontend running on http://localhost:5173 (PID $FRONTEND_PID)"

echo ""
echo "Pointify is running:"
echo "  App:    http://localhost:5173"
echo "  API:    http://localhost:8000"
echo "  Health: http://localhost:8000/api/v1/health"
echo "  Docs:   http://localhost:8000/docs"
echo ""
echo "Default login: admin / admin  (YOU MUST CHANGE THIS ON FIRST LOGIN)"
echo ""
echo "Make sure Ollama is running: ollama serve"
echo "And the model is pulled:     ollama pull gpt-oss:20b"
echo ""
echo "Press Ctrl+C to stop all services"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
