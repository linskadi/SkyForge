#!/bin/sh
# SkyForge (天锻) 一键启动脚本
# 自动检测环境、安装依赖、启动服务

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo " SkyForge (天锻) 一键启动脚本"
echo "=============================================="
echo ""

# ====================== 检查服务端口 ======================
echo "[1/6] 检查服务端口..."

list_port_pids() {
    netstat -ano 2>/dev/null | grep ":$1 " | grep LISTENING | awk '{print $5}' | sort -u || true
}

kill_process_tree() {
    target_pid="$1"
    if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -NonInteractive -Command \
            "Stop-Process -Id $target_pid -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1 || true
    elif command -v taskkill.exe >/dev/null 2>&1; then
        MSYS_NO_PATHCONV=1 taskkill.exe /F /T /PID "$target_pid" >/dev/null 2>&1 || true
    else
        kill "$target_pid" 2>/dev/null || true
    fi
}

# 自动清理占用的端口
NEED_CLEANUP=false
for port in 8000 5173 5174 5175; do
    PIDS=$(list_port_pids "$port")
    for pid in $PIDS; do
        [ -z "$pid" ] && continue
        echo "  ⚠️  端口 $port 被占用，正在终止进程 PID=$pid"
        kill_process_tree "$pid"
        NEED_CLEANUP=true
    done
done

# 等待端口释放
if [ "$NEED_CLEANUP" = "true" ]; then
    release_attempt=0
    while [ "$release_attempt" -lt 20 ]; do
        STILL_OCCUPIED=""
        for port in 8000 5173 5174 5175; do
            PIDS=$(list_port_pids "$port")
            [ -n "$PIDS" ] && STILL_OCCUPIED="$STILL_OCCUPIED $port (PID $PIDS)"
        done
        [ -z "$STILL_OCCUPIED" ] && break
        release_attempt=$((release_attempt + 1))
        sleep 0.25
    done
    if [ -n "$STILL_OCCUPIED" ]; then
        echo "  ❌ 清理后端口仍被占用：$STILL_OCCUPIED"
        exit 1
    fi
fi
echo "  ✅ 服务端口可用"
echo ""

# ====================== 检测环境 ======================
echo "[2/6] 检测环境..."

# uv 负责 Python 版本与虚拟环境，避免 Windows Store 的 python.exe 别名误报。
if ! command -v uv >/dev/null 2>&1; then
    echo "  安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$USERPROFILE/.local/bin:$HOME/.local/bin:$PATH"
fi
echo "  uv: $(uv --version)"

if [ -f "$ROOT/.venv/Scripts/python.exe" ]; then
    DETECTED_PYTHON="$ROOT/.venv/Scripts/python.exe"
elif [ -f "$ROOT/.venv/bin/python" ]; then
    DETECTED_PYTHON="$ROOT/.venv/bin/python"
else
    DETECTED_PYTHON="$(uv python find 3.12 2>/dev/null || true)"
    if [ -z "$DETECTED_PYTHON" ]; then
        echo "  安装 uv 管理的 Python 3.12..."
        uv python install 3.12
        DETECTED_PYTHON="$(uv python find 3.12)"
    fi
fi
echo "  Python: $($DETECTED_PYTHON --version 2>&1)"

# Node.js
if ! command -v node >/dev/null 2>&1; then
    echo "  ❌ Node.js 未安装，请先安装 Node.js 18+"
    exit 1
fi
echo "  Node.js: $(node --version)"

# pnpm
if ! command -v pnpm >/dev/null 2>&1; then
    echo "  启用 pnpm..."
    corepack enable
fi
echo ""

# ====================== 安装后端依赖 ======================
echo "[3/6] 安装后端依赖..."

# 创建虚拟环境
if [ ! -d "$ROOT/.venv" ]; then
    echo "  创建虚拟环境..."
    cd "$ROOT"
    uv venv --python 3.12
fi

if [ -f "$ROOT/.venv/Scripts/python.exe" ]; then
    VENV_PYTHON="$ROOT/.venv/Scripts/python.exe"
elif [ -f "$ROOT/.venv/bin/python" ]; then
    VENV_PYTHON="$ROOT/.venv/bin/python"
else
    echo "  ❌ Python 虚拟环境异常"
    exit 1
fi

# 安装依赖
echo "  同步 Python 依赖..."
cd "$ROOT"
uv sync --extra dev --locked --python "$VENV_PYTHON"
echo "  ✅ 后端依赖已安装"
echo ""

# ====================== 检测形式化验证工具 ======================
echo "  检测形式化验证工具链..."

# z3（Python 包，已随上面安装）
if "$ROOT/.venv/Scripts/python.exe" -c "import z3" 2>/dev/null || "$ROOT/.venv/bin/python" -c "import z3" 2>/dev/null; then
    echo "  ✅ z3: 已安装（Python 包）"
else
    echo "  ⚠️  z3: 未安装（契约形式化验证将降级为 SKIPPED）"
fi

# cbmc（外部二进制，可选）
CBMC_WINDOWS_EXE='C:\Program Files\cbmc\bin\cbmc.exe'
if command -v cbmc >/dev/null 2>&1; then
    echo "  ✅ cbmc: $(cbmc --version 2>&1 | head -n1)"
elif [ -f "$CBMC_WINDOWS_EXE" ]; then
    echo "  ✅ cbmc: $("$CBMC_WINDOWS_EXE" --version 2>&1 | head -n1)（C:\\Program Files\\cbmc\\bin）"
elif [ -f "/c/Program Files/cbmc/bin/cbmc.exe" ]; then
    echo "  ✅ cbmc: 已安装（C:\\Program Files\\cbmc\\bin）"
else
    echo "  ⚠️  cbmc: 未安装（C 代码有界模型检查将降级为 SKIPPED）"
    echo "     安装方式："
    echo "       Windows: 下载 https://github.com/diffblue/cbmc/releases 最新 win64.msi 双击安装"
    echo "       Linux:   sudo apt install cbmc"
    echo "       macOS:   brew install cbmc"
fi
echo ""

# ====================== 安装前端依赖 ======================
echo "[4/6] 安装前端依赖..."
cd "$ROOT/studio/frontend"
echo "  pnpm（项目锁定版本）: $(pnpm --version)"
pnpm install --frozen-lockfile
cd "$ROOT"
echo "  ✅ 前端依赖已安装"
echo ""

# ====================== 配置环境 ======================
echo "[5/6] 配置环境..."

if [ ! -f "$ROOT/config/.env" ] && [ -f "$ROOT/config/.env.example" ]; then
    cp "$ROOT/config/.env.example" "$ROOT/config/.env"
    echo "  已创建 .env 配置文件"
fi

mkdir -p "$ROOT/project/work_dir"
echo "  ✅ 环境配置完成"
echo ""

# ====================== 启动服务 ======================
echo "[6/6] 启动服务..."

cleanup() {
    if [ -n "${FRONTEND_PID:-}" ] || [ -n "${BACKEND_PID:-}" ]; then
        echo ""
        echo "正在停止 SkyForge 服务..."
    fi
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

wait_for_service() {
    service_name="$1"
    service_url="$2"
    service_pid="$3"
    attempt=0
    while [ "$attempt" -lt 60 ]; do
        if ! kill -0 "$service_pid" 2>/dev/null; then
            echo "  ❌ $service_name 进程已提前退出，请查看上方错误日志"
            return 1
        fi
        if "$VENV_PYTHON" -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read(1)' "$service_url" >/dev/null 2>&1; then
            # 连续确认，避免旧监听进程或刚刚绑定失败的新进程造成假阳性。
            sleep 0.4
            if kill -0 "$service_pid" 2>/dev/null && \
                "$VENV_PYTHON" -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read(1)' "$service_url" >/dev/null 2>&1; then
                echo "  ✅ $service_name 已就绪: $service_url"
                return 0
            fi
        fi
        attempt=$((attempt + 1))
        sleep 0.25
    done
    echo "  ❌ $service_name 启动超时: $service_url"
    return 1
}

# 启动后端。--app-dir 由 Uvicorn 负责加入模块搜索路径，避免 Windows
# Python 与 POSIX shell 对 PYTHONPATH 分隔符（; / :）的解释差异。
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
# HIL 仅指硬件在环；HITL 才是人工审查。
export HIL_ENABLED="${HIL_ENABLED:-false}"
export HITL_ENABLED="${HITL_ENABLED:-false}"
UVICORN_RELOAD_ARG=""
if [ "${SKYFORGE_RELOAD:-false}" = "true" ]; then
    UVICORN_RELOAD_ARG="--reload"
fi
(
    cd "$ROOT"
    exec env ENV=dev "$VENV_PYTHON" -m uvicorn app.main:app --app-dir "$ROOT/studio" --host 0.0.0.0 --port 8000 --log-level info $UVICORN_RELOAD_ARG
) &
BACKEND_PID=$!
wait_for_service "后端" "http://localhost:8000/api/health" "$BACKEND_PID"

# 启动前端
cd "$ROOT/studio/frontend"
if command -v pnpm >/dev/null 2>&1; then
    (
        cd "$ROOT/studio/frontend"
        exec node node_modules/vite/bin/vite.js --strictPort
    ) &
    FRONTEND_PID=$!
    wait_for_service "前端" "http://localhost:5173" "$FRONTEND_PID"
fi

echo ""
echo "=============================================="
echo " SkyForge 启动完成！"
echo "=============================================="
echo ""
echo "  前端: http://localhost:5173"
echo "  后端: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo ""

wait
