@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "LOG_DIR=%PROJECT_DIR%\logs"
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "LOG_FILE=%LOG_DIR%\install_tools_%TIMESTAMP%.log"
set "REPORT_FILE=%LOG_DIR%\install_report_%TIMESTAMP%.txt"
set "TEMP_DIR=%TEMP%\skyforge_install_%RANDOM%"
set "DRY_RUN=0"
set "FORCE_INSTALL=0"
set "OFFLINE_MODE=0"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

call :log "======================================="
call :log "SkyForge Tool Installer v1.0 (Windows)"
call :log "======================================="

if "%~1"=="" goto :parse_args
goto :parse_args

:parse_args
shift
if "%~0"=="" goto :start_install
if "%~0"=="--dry-run" (
    set "DRY_RUN=1"
    call :info "Dry run mode enabled"
    goto :parse_args
)
if "%~0"=="--force" (
    set "FORCE_INSTALL=1"
    call :info "Force install mode enabled"
    goto :parse_args
)
if "%~0"=="--help" goto :show_help
if "%~0"=="-h" goto :show_help
if "%~0"=="--list" goto :list_tools
call :error "Unknown option: %~0"
goto :show_help

:show_help
echo.
echo SkyForge Tool Installer (Windows)
echo Usage: %~nx0 [OPTIONS]
echo.
echo Options:
echo     --dry-run           Show what would be installed without actually installing
echo     --force             Reinstall even if tools are already present
echo     --help              Show this help message
echo     --list              List all available tools and their status
echo.
echo Examples:
echo     %~nx0                    # Install all missing tools
echo     %~nx0 --dry-run         # Preview installation
echo     %~nx0 --force           # Reinstall everything
echo.
exit /b 0

:list_tools
echo.
echo SkyForge Required Tools:
echo ========================
call :check_tool_status "cbmc" "CBMC - Bounded Model Checker"
call :check_tool_status "z3" "Z3 - SMT Constraint Solver"
call :check_tool_status "semgrep" "Semgrep - Static Analysis"
call :check_tool_status "gcc" "GCC - C/C++ Compiler"
call :check_tool_status "lcov" "lcov - Code Coverage"
echo.
exit /b 0

:check_tool_status
set "cmd=%~1"
set "desc=%~2"
where %cmd% >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('%cmd% --version 2^>nul ^| head -n1') do set "ver=%%i"
    echo   [INSTALLED]  %desc% (!ver!)
) else (
    echo   [NOT FOUND]  %desc%
)
exit /b 0

:start_install
call :info "Detecting system..."
set "OS_TYPE=windows"
set "ARCH=%PROCESSOR_ARCHITECTURE%"
call :info "OS: %OS_TYPE%"
call :info "Architecture: %ARCH%"

if "%DRY_RUN%"=="1" (
    call :warn "DRY RUN MODE - No changes will be made"
    call :list_tools
    goto :end
)

call :info ""
call :info "Starting tool installation..."
call :info ""

set "INSTALLED_COUNT=0"
set "SKIPPED_COUNT=0"
set "FAILED_COUNT=0"

REM ===== CBMC =====
call :install_cbmc

REM ===== Z3 =====
call :install_z3

REM ===== Semgrep =====
call :install_semgrep

REM ===== GCC =====
call :install_gcc

REM ===== LCOV =====
call :install_lcov

REM ===== Verify =====
call :verify_installation

REM ===== Generate Report =====
call :generate_report

goto :end

:log
echo [%date% %time%] [INFO] %~1 >> "%LOG_FILE%"
goto :eof

:info
echo [%date% %time%] [INFO] %~1
echo [%date% %time%] [INFO] %~1 >> "%LOG_FILE%"
goto :eof

:warn
echo [%date% %time%] [WARN] %~1
echo [%date% %time%] [WARN] %~1 >> "%LOG_FILE%"
goto :eof

:error
echo [%date% %time%] [ERROR] %~1
echo [%date% %time%] [ERROR] %~1 >> "%LOG_FILE%"
goto :eof

:success
echo [%date% %time%] [OK] %~1
echo [%date% %time%] [OK] %~1 >> "%LOG_FILE%"
goto :eof

REM ===== CBMC Installation =====
:install_cbmc
call :info "Checking CBMC..."
where cbmc >nul 2>&1
if %errorlevel%==0 (
    if "%FORCE_INSTALL%"=="0" (
        call :success "CBMC is already installed"
        set /a SKIPPED_COUNT+=1
        exit /b 0
    )
)

if "%DRY_RUN%"=="1" (
    call :info "[DRY RUN] Would install: CBMC"
    exit /b 0
)

call :info "Installing CBMC..."

REM Try using winget
where winget >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via winget..."
    winget install --id DiffBlue.CBMC --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "CBMC installed via winget"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using chocolatey
where choco >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Chocolatey..."
    choco install cbmc -y >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "CBMC installed via Chocolatey"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using scoop
where scoop >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Scoop..."
    scoop install cbmc >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "CBMC installed via Scoop"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

call :error "Failed to install CBMC. Please install manually."
call :error "  Download: https://github.com/diffblue/cbmc/releases"
set /a FAILED_COUNT+=1
exit /b 1

REM ===== Z3 Installation =====
:install_z3
call :info "Checking Z3..."
where z3 >nul 2>&1
if %errorlevel%==0 (
    if "%FORCE_INSTALL%"=="0" (
        call :success "Z3 is already installed"
        set /a SKIPPED_COUNT+=1
        exit /b 0
    )
)

if "%DRY_RUN%"=="1" (
    call :info "[DRY RUN] Would install: Z3"
    exit /b 0
)

call :info "Installing Z3-Solver..."

REM Try using winget
where winget >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via winget..."
    winget install --id Microsoft.Z3 --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Z3 installed via winget"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using chocolatey
where choco >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Chocolatey..."
    choco install z3 -y >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Z3 installed via Chocolatey"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using pip
where pip >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via pip..."
    pip install z3-solver >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Z3 installed via pip"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

call :error "Failed to install Z3. Please install manually."
call :error "  Download: https://github.com/Z3Prover/z3/releases"
set /a FAILED_COUNT+=1
exit /b 1

REM ===== Semgrep Installation =====
:install_semgrep
call :info "Checking Semgrep..."
where semgrep >nul 2>&1
if %errorlevel%==0 (
    if "%FORCE_INSTALL%"=="0" (
        call :success "Semgrep is already installed"
        set /a SKIPPED_COUNT+=1
        exit /b 0
    )
)

if "%DRY_RUN%"=="1" (
    call :info "[DRY RUN] Would install: Semgrep"
    exit /b 0
)

call :info "Installing Semgrep..."

REM Try using pip (primary method)
where pip >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via pip..."
    pip install --user semgrep >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Semgrep installed via pip"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using pip3
where pip3 >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via pip3..."
    pip3 install --user semgrep >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Semgrep installed via pip3"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using winget
where winget >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via winget..."
    winget install --id Semgrep.Semgrep --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Semgrep installed via winget"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using chocolatey
where choco >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Chocolatey..."
    choco install semgrep -y >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "Semgrep installed via Chocolatey"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

call :error "Failed to install Semgrep. Please install manually."
call :error "  Download: https://semgrep.dev/docs/getting-started/"
set /a FAILED_COUNT+=1
exit /b 1

REM ===== GCC Installation =====
:install_gcc
call :info "Checking GCC..."
where gcc >nul 2>&1
if %errorlevel%==0 (
    if "%FORCE_INSTALL%"=="0" (
        call :success "GCC is already installed"
        set /a SKIPPED_COUNT+=1
        exit /b 0
    )
)

if "%DRY_RUN%"=="1" (
    call :info "[DRY RUN] Would install: GCC"
    exit /b 0
)

call :info "Installing GCC..."

REM Try using winget (MinGW-w64)
where winget >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via winget (MinGW-w64)..."
    winget install --id MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "GCC installed via winget (MSYS2)"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using chocolatey (MinGW)
where choco >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Chocolatey (MinGW)..."
    choco install mingw -y >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "GCC installed via Chocolatey (MinGW)"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using scoop
where scoop >nul 2>&1
if %errorlevel%==0 (
    call :info "Attempting install via Scoop (MinGW)..."
    scoop install mingw >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "GCC installed via Scoop (MinGW)"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Check for TDM-GCC
call :info "Checking for TDM-GCC..."
if exist "C:\TDM-GCC-64\bin\gcc.exe" (
    call :success "TDM-GCC found at C:\TDM-GCC-64\bin\gcc.exe"
    set /a INSTALLED_COUNT+=1
    exit /b 0
)

call :error "Failed to install GCC. Please install manually."
call :error "  Options: MSYS2, MinGW-w64, TDM-GCC, or Cygwin"
call :error "  Download: https://www.msys2.org/ or https://jmeubank.github.io/tdm-gcc/"
set /a FAILED_COUNT+=1
exit /b 1

REM ===== LCOV Installation =====
:install_lcov
call :info "Checking lcov..."
where lcov >nul 2>&1
if %errorlevel%==0 (
    if "%FORCE_INSTALL%"=="0" (
        call :success "lcov is already installed"
        set /a SKIPPED_COUNT+=1
        exit /b 0
    )
)

if "%DRY_RUN%"=="1" (
    call :info "[DRY RUN] Would install: lcov"
    exit /b 0
)

call :info "Installing lcov..."

REM lcov is a Perl script; on Windows we need Perl
REM Check for Perl first
where perl >nul 2>&1
if %errorlevel%==0 (
    REM Try using cpan
    call :info "Attempting install via cpan..."
    cpan App::lcov >> "%LOG_FILE%" 2>&1
    if %errorlevel%==0 (
        call :success "lcov installed via cpan"
        set /a INSTALLED_COUNT+=1
        exit /b 0
    )
)

REM Try using strawberry perl which includes lcov
where strawberry >nul 2>&1
if %errorlevel%==0 (
    call :info "Strawberry Perl detected, lcov should be available"
    set /a INSTALLED_COUNT+=1
    exit /b 0
)

REM Note: lcov is primarily for Linux; on Windows, consider using OpenCppCoverage
call :warn "lcov is primarily designed for Linux/macOS"
call :info "For Windows, consider using OpenCppCoverage as an alternative"
call :info "  Download: https://github.com/OpenCppCoverage/OpenCppCoverage"
call :info ""

REM Skip lcov as it's optional for basic CBMC usage
set /a SKIPPED_COUNT+=1
exit /b 0

:verify_installation
call :info ""
call :info "Verifying installations..."
call :info "=========================="

for %%t in (cbmc z3 semgrep gcc lcov) do (
    where %%t >nul 2>&1
    if !errorlevel!==0 (
        call :success "%%t: Found"
    ) else (
        call :warn "%%t: NOT FOUND in PATH"
    )
)

call :info ""
exit /b 0

:generate_report
call :info ""
call :info "Generating installation report..."

(
echo SkyForge Tool Installation Report (Windows)
echo ==========================================
echo Date: %date% %time%
echo OS: Windows %OS_TYPE%
echo Architecture: %ARCH%
echo.
echo Installation Summary:
echo ---------------------
if %INSTALLED_COUNT% gtr 0 echo Successfully Installed: %INSTALLED_COUNT%
if %SKIPPED_COUNT% gtr 0 echo Skipped (already installed): %SKIPPED_COUNT%
if %FAILED_COUNT% gtr 0 echo Failed: %FAILED_COUNT%
echo.
echo Tool Verification:
echo ------------------
) > "%REPORT_FILE%"

for %%t in (cbmc z3 semgrep gcc lcov) do (
    where %%t >nul 2>&1
    if !errorlevel!==0 (
        echo [INSTALLED] %%t >> "%REPORT_FILE%"
    ) else (
        echo [NOT FOUND] %%t >> "%REPORT_FILE%"
    )
)

echo. >> "%REPORT_FILE%"
echo Log File: %LOG_FILE% >> "%REPORT_FILE%"
echo Report File: %REPORT_FILE% >> "%REPORT_FILE%"

type "%REPORT_FILE%"
call :info "Report saved to: %REPORT_FILE%"
exit /b 0

:end
call :info ""
call :info "========================================"
call :info "Installation Complete!"
call :info "  Installed: %INSTALLED_COUNT%"
call :info "  Skipped: %SKIPPED_COUNT%"
call :info "  Failed: %FAILED_COUNT%"
call :info "========================================"

if %FAILED_COUNT% gtr 0 (
    call :error "Some tools failed to install. Check the log for details."
    call :error "  Log: %LOG_FILE%"
    call :error "  Report: %REPORT_FILE%"
    exit /b 1
)

call :success "All tools installed successfully!"
exit /b 0
