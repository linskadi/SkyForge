#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/install_tools_$(date +%Y%m%d_%H%M%S).log"
REPORT_FILE="$LOG_DIR/install_report_$(date +%Y%m%d_%H%M%S).txt"
TEMP_DIR="/tmp/skyforge_install_$$"
ROLLBACK_LOG=()
INSTALLED_TOOLS=()
SKIPPED_TOOLS=()
FAILED_TOOLS=()
DRY_RUN=false
FORCE_INSTALL=false
OFFLINE_MODE=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] [$level] $msg" | tee -a "$LOG_FILE"
}

info() { log "INFO" "${BLUE}$*${NC}"; }
success() { log "OK" "${GREEN}$*${NC}"; }
warn() { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

show_help() {
    cat << EOF
SkyForge Tool Installer
Usage: $(basename "$0") [OPTIONS]

Options:
    --dry-run           Show what would be installed without actually installing
    --force             Reinstall even if tools are already present
    --offline           Use cached/offline packages when available
    --only TOOL         Install only the specified tool (cbmc|z3|semgrep|gcc|lcov)
    --skip TOOL         Skip the specified tool
    --help              Show this help message
    --list              List all available tools and their status

Examples:
    $(basename "$0")                    # Install all missing tools
    $(basename "$0") --only cbmc       # Install only CBMC
    $(basename "$0") --dry-run         # Preview installation
    $(basename "$0") --force           # Reinstall everything
EOF
}

list_tools() {
    echo ""
    echo -e "${CYAN}SkyForge Required Tools:${NC}"
    echo "========================"
    check_tool_status "cbmc"      "CBMC - Bounded Model Checker"
    check_tool_status "z3"        "Z3 - SMT Constraint Solver"
    check_tool_status "semgrep"   "Semgrep - Static Analysis"
    check_tool_status "gcc"       "GCC - C/C++ Compiler"
    check_tool_status "lcov"      "lcov - Code Coverage"
    echo ""
}

check_tool_status() {
    local cmd="$1"
    local desc="$2"
    local status
    local version

    if command -v "$cmd" &>/dev/null; then
        version=$($cmd --version 2>/dev/null | head -n1 || echo "installed")
        status="${GREEN}INSTALLED${NC}"
        echo -e "  $status  $desc ($version)"
    else
        status="${RED}NOT FOUND${NC}"
        echo -e "  $status  $desc"
    fi
}

detect_system() {
    local os arch

    case "$(uname -s)" in
        Linux*)     os="linux";;
        Darwin*)    os="macos";;
        MINGW*|MSYS*|CYGWIN*)  os="windows";;
        *)          os="unknown";;
    esac

    case "$(uname -m)" in
        x86_64|amd64)   arch="x86_64";;
        aarch64|arm64)   arch="aarch64";;
        armv7l|armhf)    arch="armv7";;
        *)               arch="unknown";;
    esac

    echo "$os|$arch"
}

detect_package_manager() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v brew &>/dev/null; then
        echo "brew"
    elif command -v yum &>/dev/null; then
        echo "yum"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v apk &>/dev/null; then
        echo "apk"
    else
        echo "unknown"
    fi
}

check_tool() {
    local tool="$1"
    command -v "$tool" &>/dev/null
}

check_cbmc() {
    if check_tool "cbmc"; then
        local version
        version=$(cbmc --version 2>/dev/null | head -n1)
        success "CBMC is already installed: $version"
        return 0
    fi
    return 1
}

install_cbmc() {
    local system_info="$1"
    local os="${system_info%%|*}"
    local arch="${system_info##*|}"
    local pkg_mgr="$2"

    info "Installing CBMC (Bounded Model Checker)..."

    if [[ "$OFFLINE_MODE" == true ]]; then
        warn "Offline mode: attempting to use cached CBMC package"
    fi

    case "$os" in
        linux)
            case "$pkg_mgr" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq cbmc 2>&1 | tee -a "$LOG_FILE"
                    ;;
                brew)
                    brew install cbmc 2>&1 | tee -a "$LOG_FILE"
                    ;;
                yum|dnf)
                    sudo $pkg_mgr install -y cbmc 2>&1 | tee -a "$LOG_FILE"
                    ;;
                *)
                    install_cbmc_from_source "$os" "$arch"
                    ;;
            esac
            ;;
        macos)
            if command -v brew &>/dev/null; then
                brew install cbmc 2>&1 | tee -a "$LOG_FILE"
            else
                install_cbmc_from_source "$os" "$arch"
            fi
            ;;
        *)
            install_cbmc_from_source "$os" "$arch"
            ;;
    esac
}

install_cbmc_from_source() {
    local os="$1"
    local arch="$2"
    info "Building CBMC from source..."

    if ! command -v cmake &>/dev/null; then
        error "cmake is required to build CBMC from source"
        return 1
    fi
    if ! command -v g++ &>/dev/null && ! command -v clang++ &>/dev/null; then
        error "A C++ compiler is required to build CBMC from source"
        return 1
    fi

    mkdir -p "$TEMP_DIR/cbmc"
    cd "$TEMP_DIR/cbmc"

    local cbmc_version="6.2.0"
    local cbmc_url="https://github.com/diffblue/cbmc/archive/refs/tags/cbmc-${cbmc_version}.tar.gz"

    info "Downloading CBMC v${cbmc_version}..."
    if curl -sSL "$cbmc_url" -o cbmc.tar.gz 2>&1 | tee -a "$LOG_FILE"; then
        tar -xzf cbmc.tar.gz
        cd "cbmc-cbmc-${cbmc_version}"
        mkdir -p build && cd build
        cmake -DCMAKE_INSTALL_PREFIX="$HOME/.local" -G "Unix Makefiles" .. 2>&1 | tee -a "$LOG_FILE"
        cmake --build . -j"$(nproc 2>/dev/null || echo 4)" 2>&1 | tee -a "$LOG_FILE"
        cmake --install . 2>&1 | tee -a "$LOG_FILE"
    else
        error "Failed to download CBMC"
        return 1
    fi
}

check_z3() {
    if check_tool "z3"; then
        local version
        version=$(z3 --version 2>/dev/null | head -n1)
        success "Z3 is already installed: $version"
        return 0
    fi
    if python3 -c "import z3; print(z3.get_version_string())" 2>/dev/null; then
        local version
        version=$(python3 -c "import z3; print(z3.get_version_string())" 2>/dev/null)
        success "Z3 Python module is available: $version"
        return 0
    fi
    return 1
}

install_z3() {
    local system_info="$1"
    local os="${system_info%%|*}"
    local arch="${system_info##*|}"
    local pkg_mgr="$2"

    info "Installing Z3-Solver..."

    case "$os" in
        linux)
            case "$pkg_mgr" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq z3 libz3-dev 2>&1 | tee -a "$LOG_FILE"
                    ;;
                brew)
                    brew install z3 2>&1 | tee -a "$LOG_FILE"
                    ;;
                yum|dnf)
                    sudo $pkg_mgr install -y z3 z3-devel 2>&1 | tee -a "$LOG_FILE"
                    ;;
                *)
                    install_z3_from_source "$os" "$arch"
                    ;;
            esac
            ;;
        macos)
            if command -v brew &>/dev/null; then
                brew install z3 2>&1 | tee -a "$LOG_FILE"
            else
                install_z3_from_source "$os" "$arch"
            fi
            ;;
        windows)
            install_z3_win "$arch"
            ;;
        *)
            install_z3_from_source "$os" "$arch"
            ;;
    esac
}

install_z3_win() {
    local arch="$1"
    info "Installing Z3 via pip (z3-solver)..."

    if pip install "z3-solver>=4.13.0,<5" 2>&1 | tee -a "$LOG_FILE"; then
        mkdir -p "$HOME/.local/bin"
        cat > "$HOME/.local/bin/z3" << 'EOF'
#!/usr/bin/env python3
import sys
try:
    import z3
    if len(sys.argv) > 1 and sys.argv[1] == '--version':
        print(f"Z3 {z3.get_version_string()}")
        sys.exit(0)
    else:
        print("Z3 is available as a Python module (import z3)", file=sys.stderr)
        sys.exit(1)
except ImportError:
    print("z3-solver is not installed", file=sys.stderr)
    sys.exit(1)
EOF
        chmod +x "$HOME/.local/bin/z3"
        success "Z3 installed via pip (z3-solver)"
    else
        error "Failed to install z3-solver via pip"
        return 1
    fi
}

install_z3_from_source() {
    local os="$1"
    local arch="$2"
    info "Building Z3 from source..."

    mkdir -p "$TEMP_DIR/z3"
    cd "$TEMP_DIR/z3"

    local z3_version="4.13.0"
    local z3_url="https://github.com/Z3Prover/z3/archive/refs/tags/z3-${z3_version}.tar.gz"

    info "Downloading Z3 v${z3_version}..."
    if curl -sSL "$z3_url" -o z3.tar.gz 2>&1 | tee -a "$LOG_FILE"; then
        tar -xzf z3.tar.gz
        cd "z3-z3-${z3_version}"
        mkdir -p build && cd build
        cmake -DCMAKE_INSTALL_PREFIX="$HOME/.local" -G "Unix Makefiles" .. 2>&1 | tee -a "$LOG_FILE"
        cmake --build . -j"$(nproc 2>/dev/null || echo 4)" 2>&1 | tee -a "$LOG_FILE"
        cmake --install . 2>&1 | tee -a "$LOG_FILE"
    else
        error "Failed to download Z3"
        return 1
    fi
}

check_semgrep() {
    if check_tool "semgrep"; then
        local version
        version=$(semgrep --version 2>/dev/null | head -n1)
        success "Semgrep is already installed: $version"
        return 0
    fi
    return 1
}

install_semgrep() {
    local system_info="$1"
    local os="${system_info%%|*}"
    local pkg_mgr="$2"

    info "Installing Semgrep..."

    if command -v pip3 &>/dev/null; then
        pip3 install --user semgrep 2>&1 | tee -a "$LOG_FILE"
    elif command -v pip &>/dev/null; then
        pip install --user semgrep 2>&1 | tee -a "$LOG_FILE"
    elif command -v brew &>/dev/null; then
        brew install semgrep 2>&1 | tee -a "$LOG_FILE"
    elif [[ "$pkg_mgr" == "apt" ]]; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq semgrep 2>&1 | tee -a "$LOG_FILE"
    else
        error "Cannot install Semgrep: no package manager or pip found"
        error "Please install manually: https://semgrep.dev/docs/getting-started/"
        return 1
    fi
}

check_gcc() {
    if check_tool "gcc"; then
        local version
        version=$(gcc --version 2>/dev/null | head -n1)
        success "GCC is already installed: $version"
        return 0
    fi
    return 1
}

install_gcc() {
    local system_info="$1"
    local os="${system_info%%|*}"
    local pkg_mgr="$2"

    info "Installing GCC..."

    case "$os" in
        linux)
            case "$pkg_mgr" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq gcc g++ build-essential 2>&1 | tee -a "$LOG_FILE"
                    ;;
                brew)
                    brew install gcc 2>&1 | tee -a "$LOG_FILE"
                    ;;
                yum|dnf)
                    sudo $pkg_mgr install -y gcc gcc-c++ make 2>&1 | tee -a "$LOG_FILE"
                    ;;
                pacman)
                    sudo pacman -S --noconfirm gcc make 2>&1 | tee -a "$LOG_FILE"
                    ;;
                apk)
                    sudo apk add gcc g++ make 2>&1 | tee -a "$LOG_FILE"
                    ;;
                *)
                    error "Cannot install GCC: unknown package manager"
                    return 1
                    ;;
            esac
            ;;
        macos)
            if command -v xcode-select &>/dev/null; then
                xcode-select --install 2>&1 | tee -a "$LOG_FILE" || true
            elif command -v brew &>/dev/null; then
                brew install gcc 2>&1 | tee -a "$LOG_FILE"
            fi
            ;;
        *)
            error "Cannot install GCC on this platform"
            return 1
            ;;
    esac
}

check_lcov() {
    if check_tool "lcov"; then
        local version
        version=$(lcov --version 2>/dev/null | head -n1)
        success "lcov is already installed: $version"
        return 0
    fi
    return 1
}

install_lcov() {
    local system_info="$1"
    local os="${system_info%%|*}"
    local pkg_mgr="$2"

    info "Installing lcov..."

    case "$os" in
        linux)
            case "$pkg_mgr" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq lcov 2>&1 | tee -a "$LOG_FILE"
                    ;;
                brew)
                    brew install lcov 2>&1 | tee -a "$LOG_FILE"
                    ;;
                yum|dnf)
                    sudo $pkg_mgr install -y lcov 2>&1 | tee -a "$LOG_FILE"
                    ;;
                *)
                    install_lcov_from_source
                    ;;
            esac
            ;;
        macos)
            if command -v brew &>/dev/null; then
                brew install lcov 2>&1 | tee -a "$LOG_FILE"
            else
                install_lcov_from_source
            fi
            ;;
        *)
            install_lcov_from_source
            ;;
    esac
}

install_lcov_from_source() {
    info "Building lcov from source..."

    mkdir -p "$TEMP_DIR/lcov"
    cd "$TEMP_DIR/lcov"

    local lcov_url="https://github.com/linux-test-project/lcov/archive/refs/tags/v1.16.tar.gz"

    if curl -sSL "$lcov_url" -o lcov.tar.gz 2>&1 | tee -a "$LOG_FILE"; then
        tar -xzf lcov.tar.gz
        cd lcov-*
        make install PREFIX="$HOME/.local" 2>&1 | tee -a "$LOG_FILE"
    else
        error "Failed to download lcov"
        return 1
    fi
}

rollback() {
    if [[ ${#ROLLBACK_LOG[@]} -eq 0 ]]; then
        info "Nothing to rollback"
        return
    fi

    warn "Performing rollback of last installation..."
    for entry in "${ROLLBACK_LOG[@]}"; do
        local action="${entry%%:*}"
        local target="${entry#*:}"
        case "$action" in
            apt-remove)
                info "Removing package: $target"
                sudo apt-get remove -y "$target" 2>/dev/null || true
                ;;
            brew-remove)
                info "Removing brew package: $target"
                brew uninstall "$target" 2>/dev/null || true
                ;;
            pip-remove)
                info "Removing pip package: $target"
                pip3 uninstall -y "$target" 2>/dev/null || true
                ;;
            file-remove)
                info "Removing file: $target"
                rm -f "$target" 2>/dev/null || true
                ;;
        esac
    done
    ROLLBACK_LOG=()
    success "Rollback completed"
}

install_tool() {
    local tool="$1"
    local system_info="$2"
    local pkg_mgr="$3"

    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install: $tool"
        return 0
    fi

    if [[ "$FORCE_INSTALL" == false ]]; then
        case "$tool" in
            cbmc)    check_cbmc    && { SKIPPED_TOOLS+=("$tool"); return 0; } ;;
            z3)      check_z3      && { SKIPPED_TOOLS+=("$tool"); return 0; } ;;
            semgrep) check_semgrep && { SKIPPED_TOOLS+=("$tool"); return 0; } ;;
            gcc)     check_gcc     && { SKIPPED_TOOLS+=("$tool"); return 0; } ;;
            lcov)    check_lcov    && { SKIPPED_TOOLS+=("$tool"); return 0; } ;;
        esac
    fi

    local start_time
    start_time=$(date +%s)

    info "=========================================="
    info "Installing: $tool"
    info "=========================================="

    local install_func="install_${tool}"
    local result=0

    if declare -f "$install_func" &>/dev/null; then
        $install_func "$system_info" "$pkg_mgr" || result=$?
    else
        error "Unknown tool: $tool"
        result=1
    fi

    local end_time elapsed
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    if [[ $result -eq 0 ]]; then
        success "Successfully installed $tool (${elapsed}s)"
        INSTALLED_TOOLS+=("$tool")
    else
        error "Failed to install $tool (${elapsed}s)"
        FAILED_TOOLS+=("$tool")
    fi

    return $result
}

generate_report() {
    local report=""
    report+="SkyForge Tool Installation Report\n"
    report+="=================================\n"
    report+="Date: $(date '+%Y-%m-%d %H:%M:%S')\n"
    report+="System: $(uname -s) $(uname -m)\n"
    report+="Package Manager: $(detect_package_manager)\n\n"

    report+="--- Installation Summary ---\n"

    if [[ ${#INSTALLED_TOOLS[@]} -gt 0 ]]; then
        report+="
${GREEN}Successfully Installed:${NC}\n"
        for tool in "${INSTALLED_TOOLS[@]}"; do
            report+="  ✓ $tool\n"
        done
    fi

    if [[ ${#SKIPPED_TOOLS[@]} -gt 0 ]]; then
        report+="
${YELLOW}Skipped (already installed):${NC}\n"
        for tool in "${SKIPPED_TOOLS[@]}"; do
            report+="  - $tool\n"
        done
    fi

    if [[ ${#FAILED_TOOLS[@]} -gt 0 ]]; then
        report+="
${RED}Failed:${NC}\n"
        for tool in "${FAILED_TOOLS[@]}"; do
            report+="  ✗ $tool\n"
        done
    fi

    report+="
--- Tool Verification ---\n"
    for tool in cbmc z3 semgrep gcc lcov; do
        if command -v "$tool" &>/dev/null; then
            local version
            version=$($tool --version 2>/dev/null | head -n1 || echo "unknown version")
            report+="  ✓ $tool: $version\n"
        else
            report+="  ✗ $tool: NOT INSTALLED\n"
        fi
    done

    report+="
--- Log File ---\n"
    report+="  $LOG_FILE\n"

    echo -e "$report" > "$REPORT_FILE"
    echo -e "$report"
    info "Report saved to: $REPORT_FILE"
}

verify_installation() {
    info ""
    info "Verifying installations..."
    info "=========================="
    export PATH="$HOME/.local/bin:$PATH"
    local all_ok=true

    for tool in cbmc z3 semgrep gcc lcov; do
        if command -v "$tool" &>/dev/null; then
            success "$tool: $(command -v "$tool")"
        elif [[ "$tool" == "z3" ]] && python3 -c "import z3" 2>/dev/null; then
            local z3_ver
            z3_ver=$(python3 -c "import z3; print(z3.get_version_string())" 2>/dev/null)
            success "z3: Python module (z3-solver $z3_ver)"
        else
            error "$tool: NOT FOUND in PATH"
            all_ok=false
        fi
    done

    if [[ "$all_ok" == true ]]; then
        success "All tools verified successfully!"
    else
        warn "Some tools could not be found. Check the report for details."
    fi
}

main() {
    local tools_to_install=()
    local skip_tools=()

    mkdir -p "$LOG_DIR" "$TEMP_DIR"

    log "INFO" "======================================="
    log "INFO" "SkyForge Tool Installer v1.0"
    log "INFO" "======================================="

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)      DRY_RUN=true; shift ;;
            --force)        FORCE_INSTALL=true; shift ;;
            --offline)      OFFLINE_MODE=true; shift ;;
            --only)
                if [[ -n "${2:-}" ]]; then
                    tools_to_install+=("$2")
                    shift 2
                else
                    error "Missing tool name for --only"
                    exit 1
                fi
                ;;
            --skip)
                if [[ -n "${2:-}" ]]; then
                    skip_tools+=("$2")
                    shift 2
                else
                    error "Missing tool name for --skip"
                    exit 1
                fi
                ;;
            --help|-h)      show_help; exit 0 ;;
            --list)         list_tools; exit 0 ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    local system_info
    system_info=$(detect_system)
    local os="${system_info%%|*}"
    local arch="${system_info##*|}"
    local pkg_mgr
    pkg_mgr=$(detect_package_manager)

    info "Detected system: $os ($arch)"
    info "Package manager: $pkg_mgr"
    info "Log file: $LOG_FILE"

    if [[ ${#tools_to_install[@]} -eq 0 ]]; then
        tools_to_install=(cbmc z3 semgrep gcc lcov)
    fi

    local filtered_tools=()
    for tool in "${tools_to_install[@]}"; do
        local skip=false
        for skip_tool in "${skip_tools[@]}"; do
            if [[ "$tool" == "$skip_tool" ]]; then
                skip=true
                break
            fi
        done
        if [[ "$skip" == false ]]; then
            filtered_tools+=("$tool")
        else
            info "Skipping $tool (explicitly excluded)"
        fi
    done

    if [[ "$DRY_RUN" == true ]]; then
        warn "DRY RUN MODE - No changes will be made"
        info ""
        list_tools
        info ""
        info "Tools that would be installed:"
        for tool in "${filtered_tools[@]}"; do
            info "  - $tool"
        done
        exit 0
    fi

    info ""
    info "Installing ${#filtered_tools[@]} tools..."
    info ""

    for tool in "${filtered_tools[@]}"; do
        install_tool "$tool" "$system_info" "$pkg_mgr" || true
        info ""
    done

    verify_installation
    generate_report

    local total=${#filtered_tools[@]}
    local installed=${#INSTALLED_TOOLS[@]}
    local skipped=${#SKIPPED_TOOLS[@]}
    local failed=${#FAILED_TOOLS[@]}

    info ""
    info "========================================"
    info "Installation Complete!"
    info "  Total: $total"
    info "  Installed: $installed"
    info "  Skipped: $skipped"
    info "  Failed: $failed"
    info "========================================"

    if [[ $failed -gt 0 ]]; then
        error "Some tools failed to install. Check the log for details:"
        error "  Log: $LOG_FILE"
        error "  Report: $REPORT_FILE"
        exit 1
    fi

    success "All tools installed successfully!"
    return 0
}

main "$@"
