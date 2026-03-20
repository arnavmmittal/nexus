#!/bin/bash
# Nexus - Personal Life Operating System
# Start both backend and frontend with a single command

echo "=========================================="
echo "   NEXUS - Your Personal AI Assistant"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Kill any existing processes
echo "Stopping any existing Nexus processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null
sleep 1

# Start backend
echo ""
echo -e "${BLUE}Starting Backend (FastAPI)...${NC}"
cd /Users/arnavmmittal/Documents/nexus/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/nexus-backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}Backend ready!${NC}"
        break
    fi
    sleep 1
done

# Start frontend
echo ""
echo -e "${BLUE}Starting Frontend (Next.js)...${NC}"
cd /Users/arnavmmittal/Documents/nexus/frontend
npm run dev > /tmp/nexus-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for frontend to be ready
echo "Waiting for frontend to start..."
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}Frontend ready!${NC}"
        break
    fi
    sleep 1
done

echo ""
echo "=========================================="
echo -e "${GREEN}NEXUS IS RUNNING!${NC}"
echo "=========================================="
echo ""
echo "Access your dashboard at:"
echo -e "  ${BLUE}http://localhost:3000${NC}"
echo ""
echo "API documentation at:"
echo -e "  ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo "Logs:"
echo "  Backend:  tail -f /tmp/nexus-backend.log"
echo "  Frontend: tail -f /tmp/nexus-frontend.log"
echo ""
echo "To stop Nexus:"
echo "  pkill -f 'uvicorn app.main:app'"
echo "  pkill -f 'next dev'"
echo ""
echo "=========================================="

# Keep script running
wait
