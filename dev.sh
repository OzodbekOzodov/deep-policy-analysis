#!/bin/bash

# =============================================================================
# DAP (Deep Policy Analyst) - Local Development Startup Script
# =============================================================================
# Starts all services in the correct order:
#   1. LLM Gateway (port 8001)
#   2. Backend API (port 8000)
#   3. Frontend Dev Server (port 3000)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       DAP - Deep Policy Analyst Development Server       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        log_warn "Port $port is in use (PID: $pid). Killing..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

wait_for_port() {
    local port=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1 || \
           curl -s "http://localhost:$port" > /dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 1
}

cleanup() {
    echo ""
    log_warn "Shutting down all services..."
    
    # Kill background processes
    if [ -n "$LLM_PID" ]; then kill $LLM_PID 2>/dev/null || true; fi
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID 2>/dev/null || true; fi
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID 2>/dev/null || true; fi
    
    # Kill by port as fallback
    kill_port 8001
    kill_port 8000
    kill_port 3000
    
    log_success "All services stopped."
    exit 0
}

# Trap Ctrl+C to cleanup
trap cleanup SIGINT SIGTERM

# -----------------------------------------------------------------------------
# Pre-flight Checks
# -----------------------------------------------------------------------------

log_info "Running pre-flight checks..."

# Check Node.js
if ! command -v node &> /dev/null; then
    log_error "Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    log_error "Python is not installed. Please install Python 3.9+ first."
    exit 1
fi

log_success "Node.js: $(node --version)"
log_success "Python: $($PYTHON_CMD --version)"

# -----------------------------------------------------------------------------
# Setup Virtual Environment (if needed)
# -----------------------------------------------------------------------------

VENV_PATH="$SCRIPT_DIR/backend/venv"

if [ ! -d "$VENV_PATH" ]; then
    log_info "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_PATH"
    log_success "Virtual environment created at $VENV_PATH"
fi

# Activate venv
source "$VENV_PATH/bin/activate"

# Install backend dependencies if needed
if [ ! -f "$VENV_PATH/.deps_installed" ]; then
    log_info "Installing backend dependencies..."
    pip install -q --upgrade pip
    pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
    touch "$VENV_PATH/.deps_installed"
    log_success "Backend dependencies installed"
fi

# Install llm-gateway dependencies if needed
if [ ! -f "$VENV_PATH/.llm_deps_installed" ]; then
    log_info "Installing LLM Gateway dependencies..."
    pip install -q -r "$SCRIPT_DIR/llm-gateway/requirements.txt"
    touch "$VENV_PATH/.llm_deps_installed"
    log_success "LLM Gateway dependencies installed"
fi

# Install frontend dependencies if needed
if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
    log_info "Installing frontend dependencies..."
    npm install --silent
    log_success "Frontend dependencies installed"
fi

# -----------------------------------------------------------------------------
# Kill existing services on target ports
# -----------------------------------------------------------------------------

log_info "Checking for existing services..."
kill_port 8001
kill_port 8000
kill_port 3000

# -----------------------------------------------------------------------------
# Start Services
# -----------------------------------------------------------------------------

echo ""
echo -e "${BLUE}Starting services...${NC}"
echo ""

# 1. Start LLM Gateway (port 8001)
log_info "Starting LLM Gateway on port 8001..."
cd "$SCRIPT_DIR/llm-gateway"
uvicorn app.main:app --port 8001 --log-level warning > /tmp/dap-llm-gateway.log 2>&1 &
LLM_PID=$!
sleep 2

if ps -p $LLM_PID > /dev/null 2>&1; then
    log_success "LLM Gateway started (PID: $LLM_PID)"
else
    log_error "LLM Gateway failed to start. Check /tmp/dap-llm-gateway.log"
    cat /tmp/dap-llm-gateway.log
    exit 1
fi

# 2. Start Backend API (port 8000)
log_info "Starting Backend API on port 8000..."
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --port 8000 --log-level warning > /tmp/dap-backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

if ps -p $BACKEND_PID > /dev/null 2>&1; then
    log_success "Backend API started (PID: $BACKEND_PID)"
else
    log_error "Backend failed to start. Check /tmp/dap-backend.log"
    cat /tmp/dap-backend.log
    exit 1
fi

# 3. Start Frontend (port 3000)
log_info "Starting Frontend on port 3000..."
cd "$SCRIPT_DIR"
npm run dev > /tmp/dap-frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 3

if ps -p $FRONTEND_PID > /dev/null 2>&1; then
    log_success "Frontend started (PID: $FRONTEND_PID)"
else
    log_error "Frontend failed to start. Check /tmp/dap-frontend.log"
    cat /tmp/dap-frontend.log
    exit 1
fi

# -----------------------------------------------------------------------------
# Health Checks
# -----------------------------------------------------------------------------

echo ""
log_info "Running health checks..."

# Check LLM Gateway
if curl -s "http://localhost:8001/health" > /dev/null 2>&1; then
    log_success "LLM Gateway is healthy"
else
    log_warn "LLM Gateway health check failed (may still be starting)"
fi

# Check Backend
if curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
    log_success "Backend API is healthy"
else
    log_warn "Backend health check failed (may still be starting)"
fi

# -----------------------------------------------------------------------------
# Ready!
# -----------------------------------------------------------------------------

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    All Services Ready!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC}    http://localhost:3000"
echo -e "  ${BLUE}Backend:${NC}     http://localhost:8000"
echo -e "  ${BLUE}LLM Gateway:${NC} http://localhost:8001"
echo -e "  ${BLUE}API Docs:${NC}    http://localhost:8000/docs"
echo ""
echo -e "  Logs:"
echo -e "    - Frontend:    /tmp/dap-frontend.log"
echo -e "    - Backend:     /tmp/dap-backend.log"
echo -e "    - LLM Gateway: /tmp/dap-llm-gateway.log"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep script running and wait for Ctrl+C
wait
