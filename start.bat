@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo    SkyForge (天锻) - AI智能体驱动的机载软件轻量化开发工具
echo    航空工业软件开源创新大赛 参赛作品
echo ============================================================
echo.

:: ============================================================
:: 步骤 1/5: 环境检查
:: ============================================================
echo [1/5] 检查运行环境...

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.12+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo   [OK] Python %PYTHON_VERSION%

:: 检查 Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)
for /f %%v in ('node --version 2^>^&1') do set NODE_VERSION=%%v
echo   [OK] Node.js %NODE_VERSION%

:: 检查 pnpm
pnpm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [信息] pnpm 未安装，正在安装...
    npm install -g pnpm
)
echo   [OK] pnpm

:: 检查 uv
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [信息] uv 未安装，正在安装...
    pip install uv
)
echo   [OK] uv

:: 检查 Git Bash（可选）
where bash >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Git Bash
) else (
    echo   [信息] Git Bash 未安装（可选）
)

echo.

:: ============================================================
:: 步骤 2/5: 虚拟环境创建
:: ============================================================
echo [2/5] 创建后端虚拟环境...

cd /d "%~dp0backend"

if not exist ".venv" (
    echo   创建虚拟环境...
    python -m venv .venv
)

:: 激活虚拟环境
call .venv\Scripts\activate.bat
echo   [OK] 虚拟环境已激活

echo.

:: ============================================================
:: 步骤 3/5: 依赖安装
:: ============================================================
echo [3/5] 安装依赖...

:: 后端依赖
echo   安装后端依赖...
uv sync --quiet

:: 前端依赖
echo   安装前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    pnpm install --frozen-lockfile
) else (
    echo   [OK] 前端依赖已存在
)

cd /d "%~dp0"
echo.

:: ============================================================
:: 步骤 4/5: 清理残留进程
:: ============================================================
echo [4/5] 清理残留进程...

:: 清理后端端口 (8000)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: 清理前端端口 (5173)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo   [OK] 进程清理完成
echo.

:: ============================================================
:: 步骤 5/5: 启动服务
:: ============================================================
echo [5/5] 启动 SkyForge 服务...
echo.

:: 启动后端（新窗口）
echo   启动后端服务 (http://localhost:8000)...
start "SkyForge Backend" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 等待后端启动
echo   等待后端启动...
timeout /t 3 /nobreak >nul

:: 启动前端（新窗口）
echo   启动前端服务 (http://localhost:5173)...
start "SkyForge Frontend" cmd /k "cd /d %~dp0frontend && pnpm dev"

echo.
echo ============================================================
echo    SkyForge 启动完成！
echo ============================================================
echo.
echo    前端界面: http://localhost:5173
echo    后端 API: http://localhost:8000
echo    API 文档: http://localhost:8000/docs
echo.
echo    按任意键关闭此窗口...
echo ============================================================
pause >nul
