#!/bin/bash
# =============================================================================
# Nexus Development Environment Starter
# =============================================================================
# Usage: ./start.sh [options]
# Options:
#   --services-only   Only start Docker services (chromadb, redis)
#   --no-services     Skip Docker services, start apps only
#   --help            Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
SERVICES_ONLY=false
NO_SERVICES=false

for arg in "$@"; do
    case $arg in
        --services-only)
            SERVICES_ONLY=true
            shift
            ;;
        --no-services)
            NO_SERVICES=true
            shift
            ;;
        --help)
            echo "Nexus Development Environment Starter"
            echo ""
            echo "Usage: ./start.sh [options]"
            echo ""
            echo "Options:"
            echo "  --services-only   Only start Docker services (chromadb, redis)"
            echo "  --no-services     Skip Docker services, start apps only"
            echo "  --help            Show this help message"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Starting Nexus Development Setup${NC}"
echo -e "${BLUE}========================================${NC}"

# Check prerequisites
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed${NC}"
        exit 1
    fi
}

check_command docker
check_command npm
check_command python3

# Start Docker services
if [ "$NO_SERVICES" = false ]; then
    echo -e "\n${YELLOW}Starting Docker services...${NC}"
    cd "$PROJECT_ROOT"
    docker-compose up -d

    echo -e "${GREEN}Docker services started:${NC}"
    echo "  - ChromaDB: http://localhost:8001"
    echo "  - Redis: localhost:6379"
fi

if [ "$SERVICES_ONLY" = true ]; then
    echo -e "\n${GREEN}Services started successfully!${NC}"
    exit 0
fi

# Create data directories if they don't exist
mkdir -p "$PROJECT_ROOT/data/chroma"

# Start backend
echo -e "\n${YELLOW}Starting backend...${NC}"
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: backend/.env not found. Copying from .env.example${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit backend/.env with your configuration${NC}"
fi

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
    touch venv/.installed
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo -e "\n${YELLOW}Starting frontend...${NC}"
cd "$PROJECT_ROOT/frontend"

if [ ! -f ".env.local" ]; then
    echo -e "${YELLOW}Warning: frontend/.env.local not found. Copying from .env.local.example${NC}"
    cp .env.local.example .env.local
fi

# Install dependencies if needed
if [ ! -d "node_modules" ] || [ ! -f "node_modules/.package-lock.json" ]; then
    echo -e "${YELLOW}Installing npm dependencies...${NC}"
    npm install
fi

npm run dev &
FRONTEND_PID=$!

# Print success message
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}   Nexus is starting up!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Services:${NC}"
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  ChromaDB:  http://localhost:8001"
echo "  Redis:     localhost:6379"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}Goodbye!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
