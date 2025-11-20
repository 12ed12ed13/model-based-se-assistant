#!/bin/bash

# Complete UI System Startup Script
# Starts both FastAPI backend and React frontend

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Starting Model-Based SE Assistant"
echo "========================================="

# Check if virtual environment exists
if [ ! -d "ag" ]; then
    echo "Error: Virtual environment 'ag' not found"
    echo "Please run setup first"
    exit 1
fi

# Check if UI dependencies are installed
if [ ! -d "ui/node_modules" ]; then
    echo "Installing UI dependencies..."
    cd ui
    npm install
    cd ..
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo ""
echo "Starting FastAPI backend on http://localhost:8000..."
source ag/bin/activate
python -m uvicorn backend.api:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Check if backend started successfully
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "Error: Backend failed to start. Check backend.log for details."
    exit 1
fi

echo "Backend started successfully!"

# Start frontend
echo ""
echo "Starting React frontend on http://localhost:5173..."
cd ui
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "Frontend PID: $FRONTEND_PID"

# Wait for frontend to start
sleep 3

# Check if frontend started successfully
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo "Error: Frontend failed to start. Check frontend.log for details."
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "Frontend started successfully!"

echo ""
echo "========================================="
echo "✅ System is running!"
echo "========================================="
echo ""
echo "🌐 Frontend:  http://localhost:5173"
echo "🔌 API:       http://localhost:8000"
echo "📚 API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running and show logs
tail -f backend.log frontend.log

# Wait for cleanup
wait
