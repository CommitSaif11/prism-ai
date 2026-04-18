#!/bin/bash
# Samsung PRISM — Quick Start Script
# Run from project root: bash run.sh

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Samsung PRISM — UE Cap Parser v3   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Start backend in background
echo "[1/2] Starting FastAPI backend on :8000..."
cd backend
pip install -r requirements.txt -q
python api.py &
BACKEND_PID=$!
cd ..
sleep 2

# Start frontend
echo "[2/2] Starting React frontend on :5173..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Both servers running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT
wait
