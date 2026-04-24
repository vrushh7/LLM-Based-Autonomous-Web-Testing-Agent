#!/bin/bash

# Start the AI Testing Agent
# This script starts both backend and frontend in the background

set -e

echo "🚀 Starting AI Testing Agent..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./setup.sh first"
    exit 1
fi

# Start backend in background
echo "Starting backend server..."
cd backend
source ../venv/bin/activate
python main.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 3

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend is running (PID: $BACKEND_PID)"
else
    echo "✗ Backend failed to start. Check logs/backend.log"
    exit 1
fi

# Start frontend in background
echo "Starting frontend server..."
cd frontend
python -m http.server 3000 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 2

echo ""
echo "✓ Application started successfully!"
echo ""
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "  Backend PID:  $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo ""
echo "To stop the application:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Or create a stop.sh script with these PIDs"
echo ""

# Create stop script
cat > stop.sh << EOF
#!/bin/bash
echo "Stopping AI Testing Agent..."
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
echo "✓ Application stopped"
EOF
chmod +x stop.sh

echo "Logs are being written to:"
echo "  Backend:  logs/backend.log"
echo "  Frontend: logs/frontend.log"
echo ""
