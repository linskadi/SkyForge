@echo off
chcp 65001 >nul

:: Set working directory to script location
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ==============================================
echo  AirborneAI Development Server Launcher
echo ==============================================
echo.

:: ====================== Check Dependencies ======================
echo [1/5] Checking dependencies...

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found. Please install Python 3.12+
        goto :error
    )
    set "PYTHON_CMD=python3"
) else (
    set "PYTHON_CMD=python"
)
echo   Python: OK

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    goto :error
)
echo   Node.js: OK

:: Check/Install pnpm
where pnpm.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing pnpm...
    where npm.cmd >nul 2>&1
    if %errorlevel% equ 0 (
        call npm install -g pnpm
    ) else (
        echo [ERROR] npm not found. Please install Node.js first
        goto :error
    )
)
echo   pnpm: OK

echo.

:: ====================== Setup Backend ======================
echo [2/5] Setting up backend...
set "BACKEND_DIR=%ROOT%backend"

:: Create virtual environment if not exists
if not exist "%BACKEND_DIR%\.venv" (
    echo   Creating Python virtual environment...
    cd /d "%BACKEND_DIR%"
    call %PYTHON_CMD% -m venv .venv
    cd /d "%ROOT%"
)

:: Install dependencies
echo   Installing Python dependencies...
cd /d "%BACKEND_DIR%"
if exist "requirements.txt" (
    call .\.venv\Scripts\pip.exe install -r requirements.txt
) else (
    echo   [WARN] No requirements.txt found, skipping
)
cd /d "%ROOT%"

:: Create work directory
if not exist "%BACKEND_DIR%\project\work_dir" (
    mkdir "%BACKEND_DIR%\project\work_dir"
)
echo   Backend ready
echo.

:: ====================== Setup Frontend ======================
echo [3/5] Setting up frontend...
set "FRONTEND_DIR=%ROOT%frontend"

cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo   Installing Node.js dependencies...
    call pnpm install
) else (
    echo   node_modules exists, skipping install
)
cd /d "%ROOT%"
echo   Frontend ready
echo.

:: ====================== Start Redis (Optional) ======================
echo [4/5] Starting services...
where redis-server >nul 2>&1
if %errorlevel% equ 0 (
    start "Redis Service" cmd /k "redis-server"
    echo   [OK] Redis started
) else (
    echo   [SKIP] redis-server not found, Redis disabled
)
echo.

:: ====================== Start Backend ======================
echo [5/5] Starting backend and frontend...

set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
start "Backend Service" cmd /k "cd /d "%BACKEND_DIR%" && set "ENV=DEV" && "%VENV_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120 --reload"
echo   [OK] Backend started on http://localhost:8000

:: Start Frontend
where pnpm.exe >nul 2>&1
if %errorlevel% equ 0 (
    start "Frontend Service" cmd /k "cd /d "%FRONTEND_DIR%" && pnpm run dev"
    echo   [OK] Frontend started with pnpm
) else (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        start "Frontend Service" cmd /k "cd /d "%FRONTEND_DIR%" && "C:\Program Files\nodejs\npm.cmd" run dev"
        echo   [OK] Frontend started with npm
    )
)

echo.
echo ==============================================
echo  All services launched!
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo ==============================================
echo.
pause
exit /b 0

:error
echo.
echo ==============================================
echo  Setup failed! Please install missing dependencies.
echo ==============================================
echo.
pause
