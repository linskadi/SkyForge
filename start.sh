#!/bin/bash
# SkyForge (天锻) Development Server Launcher
# 自动构建虚拟环境、安装依赖、启动服务

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo " SkyForge (天锻) Development Server Launcher"
echo "=============================================="
echo ""

# ====================== Kill Residual Processes (MUST run first) ======================
echo "[0/5] Cleaning up residual processes..."
# Kill any leftover uvicorn/python on port 8000
for pid in $(netstat -ano 2>/dev/null | grep ':8000 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID $pid 2>/dev/null && echo "  Killed process on port 8000 (PID $pid)" || true
done
# Kill lingering uvicorn.exe/python.exe
taskkill //F //IM uvicorn.exe 2>/dev/null | grep -q "SUCCESS" && echo "  Killed uvicorn.exe" || true
taskkill //F //IM python.exe 2>/dev/null | grep -q "SUCCESS" && echo "  Killed python.exe" || true
# Kill any vite/node on common frontend ports
for port in 5173 5174 5175; do
    for pid in $(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $5}' | sort -u); do
        taskkill //F //PID $pid 2>/dev/null && echo "  Killed process on port $port (PID $pid)" || true
    done
done
# Wait briefly for sockets to release
sleep 0.5
echo ""

# ====================== Check Dependencies ======================
echo "[1/5] Checking dependencies..."

# Check Python (Git Bash on Windows may not have python in PATH)
# uv can find python even if it's not in PATH, so try uv first
PYTHON_CMD=""
if command -v uv &> /dev/null; then
    PYTHON_CMD="uv run python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v py &> /dev/null; then
    PYTHON_CMD="py -3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
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
BACKEND_DIR="$ROOT/src"

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
    ./.venv/Scripts/python.exe -m pip install -e . 2>/dev/null || \
    ./.venv/bin/python -m pip install -e . 2>/dev/null || \
    echo "  [WARN] pip install failed, skipping"
fi
cd "$ROOT"

# Create work directory
mkdir -p "$ROOT/project/work_dir"
echo "  Backend ready"
echo ""

# ====================== Setup Frontend ======================
echo "[3/5] Setting up frontend..."
FRONTEND_DIR="$ROOT/studio/frontend"

cd "$FRONTEND_DIR"
echo "  Installing Node.js dependencies..."
pnpm install
cd "$ROOT"
echo "  Frontend ready"
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
if [ -f "$ROOT/.venv/Scripts/python.exe" ]; then
    VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
else
    VENV_PYTHON="$ROOT/.venv/bin/python"
fi

# PYTHONPATH: src/ → skyforge_engine/llm/core, studio/ → app/
export PYTHONPATH="$ROOT/src:$ROOT/studio:$PYTHONPATH"
(cd "$ROOT" && ENV=DEV UVICORN_RELOAD_EXCLUDE="\.venv|node_modules|__pycache__|\.ruff_cache" "$VENV_PYTHON" -m uvicorn studio.app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload) &
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
