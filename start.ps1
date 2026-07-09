#Requires -Version 5.1
<#
.SYNOPSIS
    SkyForge (天锻) PowerShell 启动脚本

.DESCRIPTION
    AI智能体驱动的机载软件轻量化开发工具
    航空工业软件开源创新大赛 参赛作品

.EXAMPLE
    .\start.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "    SkyForge (天锻) - AI智能体驱动的机载软件轻量化开发工具" -ForegroundColor Cyan
Write-Host "    航空工业软件开源创新大赛 参赛作品" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 步骤 1/5: 环境检查
# ============================================================
Write-Host "[1/5] 检查运行环境..." -ForegroundColor Yellow

# 检查 Python
try {
    $pythonVersion = python --version 2>&1 | Select-String -Pattern "\d+\.\d+\.\d+" | ForEach-Object { $_.Matches.Value }
    Write-Host "  [OK] Python $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [错误] 未找到 Python，请安装 Python 3.12+" -ForegroundColor Red
    Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Gray
    exit 1
}

# 检查 Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  [OK] Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  [错误] 未找到 Node.js，请安装 Node.js 18+" -ForegroundColor Red
    Write-Host "  下载地址: https://nodejs.org/" -ForegroundColor Gray
    exit 1
}

# 检查 pnpm
try {
    $pnpmVersion = pnpm --version 2>&1
    Write-Host "  [OK] pnpm $pnpmVersion" -ForegroundColor Green
} catch {
    Write-Host "  [信息] pnpm 未安装，正在安装..." -ForegroundColor Yellow
    npm install -g pnpm
    Write-Host "  [OK] pnpm 已安装" -ForegroundColor Green
}

# 检查 uv
try {
    $uvVersion = uv --version 2>&1
    Write-Host "  [OK] uv $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "  [信息] uv 未安装，正在安装..." -ForegroundColor Yellow
    pip install uv
    Write-Host "  [OK] uv 已安装" -ForegroundColor Green
}

Write-Host ""

# ============================================================
# 步骤 2/5: 虚拟环境创建
# ============================================================
Write-Host "[2/5] 创建后端虚拟环境..." -ForegroundColor Yellow

$backendDir = Join-Path $PSScriptRoot "backend"
$venvDir = Join-Path $backendDir ".venv"

if (-not (Test-Path $venvDir)) {
    Write-Host "  创建虚拟环境..." -ForegroundColor Gray
    Push-Location $backendDir
    python -m venv .venv
    Pop-Location
}

# 激活虚拟环境
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
. $activateScript
Write-Host "  [OK] 虚拟环境已激活" -ForegroundColor Green

Write-Host ""

# ============================================================
# 步骤 3/5: 依赖安装
# ============================================================
Write-Host "[3/5] 安装依赖..." -ForegroundColor Yellow

# 后端依赖
Write-Host "  安装后端依赖..." -ForegroundColor Gray
Push-Location $backendDir
uv sync --quiet
Pop-Location

# 前端依赖
$frontendDir = Join-Path $PSScriptRoot "frontend"
$nodeModulesDir = Join-Path $frontendDir "node_modules"

Write-Host "  安装前端依赖..." -ForegroundColor Gray
if (-not (Test-Path $nodeModulesDir)) {
    Push-Location $frontendDir
    pnpm install --frozen-lockfile
    Pop-Location
} else {
    Write-Host "  [OK] 前端依赖已存在" -ForegroundColor Green
}

Write-Host ""

# ============================================================
# 步骤 4/5: 清理残留进程
# ============================================================
Write-Host "[4/5] 清理残留进程..." -ForegroundColor Yellow

# 清理后端端口 (8000)
$backendProcesses = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $backendProcesses) {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

# 清理前端端口 (5173)
$frontendProcesses = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $frontendProcesses) {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Write-Host "  [OK] 进程清理完成" -ForegroundColor Green
Write-Host ""

# ============================================================
# 步骤 5/5: 启动服务
# ============================================================
Write-Host "[5/5] 启动 SkyForge 服务..." -ForegroundColor Yellow
Write-Host ""

# 启动后端
Write-Host "  启动后端服务 (http://localhost:8000)..." -ForegroundColor Gray
$backendJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$backendDir`" && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -PassThru
Write-Host "  [OK] 后端进程 ID: $($backendJob.Id)" -ForegroundColor Green

# 等待后端启动
Write-Host "  等待后端启动..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# 启动前端
Write-Host "  启动前端服务 (http://localhost:5173)..." -ForegroundColor Gray
$frontendJob = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$frontendDir`" && pnpm dev" -PassThru
Write-Host "  [OK] 前端进程 ID: $($frontendJob.Id)" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "    SkyForge 启动完成！" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "    前端界面: http://localhost:5173" -ForegroundColor White
Write-Host "    后端 API: http://localhost:8000" -ForegroundColor White
Write-Host "    API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "    按 Ctrl+C 停止所有服务..." -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    # 清理进程
    Write-Host ""
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue
    Write-Host "服务已停止" -ForegroundColor Green
}
