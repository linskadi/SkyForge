#!/bin/bash
# SkyForge (天锻) Development Server Launcher
# 自动构建虚拟环境、安装依赖、启动服务

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo " SkyForge (天锻) Development Server Launcher"
echo "=============================================="
echo ""

# ====================== Check Dependencies ======================
echo "[1/5] Checking dependencies..."

# Check Python (Git Bash on Windows may not have python in PATH, try py launcher)
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v py &> /dev/null; then
    PYTHON_CMD="py -3"
elif command -v uv &> /dev/null; then
    # uv can find python even if it's not in PATH
    PYTHON_CMD="uv run python"
else
    echo "[ERROR] Python not found. Please install Python 3.12+"
    echo "  Windows: install from https://www.python.org/downloads/"
    echo "  macOS:   brew install python"
    echo "  Linux:   sudo apt install python3"
    exit 1
fi
echo "  Python: $($PYTHON_CMD --version 2>&1)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js not found. Please install Node.js 18+"
    exit 1
fi
echo "  Node.js: $(node --version)"

# Check/Install pnpm
if ! command -v pnpm &> /dev/null; then
    echo "  Installing pnpm..."
    npm install -g pnpm
fi
echo "  pnpm: $(pnpm --version)"

# Check uv (Python package manager)
if ! command -v uv &> /dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null || \
    $PYTHON_CMD -m pip install uv 2>/dev/null || \
    echo "  [WARN] Could not install uv automatically, please install manually"
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  uv: $(uv --version 2>/dev/null || echo 'installed')"

echo ""

# ====================== Setup Backend ======================
echo "[2/5] Setting up backend..."
BACKEND_DIR="$ROOT/backend"

# Create virtual environment if not exists
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "  Creating Python virtual environment..."
    cd "$BACKEND_DIR"
    uv venv
    cd "$ROOT"
fi

# Activate venv and install dependencies
echo "  Installing Python dependencies..."
cd "$BACKEND_DIR"
if [ -f "uv.lock" ]; then
    uv sync
else
    ./.venv/Scripts/python.exe -m pip install -r requirements.txt 2>/dev/null || \
    ./.venv/bin/python -m pip install -r requirements.txt 2>/dev/null || \
    echo "  [WARN] No requirements.txt found, skipping"
fi
cd "$ROOT"

# Create work directory
mkdir -p "$BACKEND_DIR/project/work_dir"
echo "  Backend ready"
echo ""

# ====================== Setup Frontend ======================
echo "[3/5] Setting up frontend..."
FRONTEND_DIR="$ROOT/frontend"

cd "$FRONTEND_DIR"
echo "  Installing Node.js dependencies..."
pnpm install
cd "$ROOT"
echo "  Frontend ready"
echo ""

# ====================== Kill Residual Processes ======================
echo "[4/5] Cleaning up residual processes..."
# Kill any leftover uvicorn/python backend processes on port 8000
for pid in $(netstat -ano 2>/dev/null | grep ':8000 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID $pid 2>/dev/null && echo "  Killed residual process on port 8000 (PID $pid)" || true
done
# Kill any leftover vite/node frontend processes on common ports
for port in 5173 5174 5175; do
    for pid in $(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $5}' | sort -u); do
        taskkill //F //PID $pid 2>/dev/null && echo "  Killed residual process on port $port (PID $pid)" || true
    done
done
echo ""

# ====================== Start Redis (Optional) ======================
echo "[4/5] Starting services..."
if command -v redis-server &> /dev/null; then
    redis-server &
    echo "  [OK] Redis started"
else
    echo "  [SKIP] redis-server not found, Redis disabled"
fi
echo ""

# ====================== Start Backend ======================
echo "[5/5] Starting backend and frontend..."

# Get Python path based on OS
if [ -f "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    VENV_PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
else
    VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
fi

(cd "$BACKEND_DIR" && ENV=DEV UVICORN_RELOAD_EXCLUDE="\.venv|node_modules|__pycache__|\.ruff_cache" "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload) &
echo "  [OK] Backend started on http://localhost:8000"

# Start frontend
cd "$FRONTEND_DIR"
if command -v pnpm &> /dev/null; then
    pnpm run dev &
    echo "  [OK] Frontend started with pnpm"
elif command -v npm &> /dev/null; then
    npm run dev &
    echo "  [OK] Frontend started with npm"
fi

echo ""
echo "=============================================="
echo " All services launched!"
echo " Backend:  http://localhost:8000"
echo " Frontend: http://localhost:5173"
echo "=============================================="
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for all background processes
wait
