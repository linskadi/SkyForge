"""Cppcheck 查改解耦模块（Patch 1 + P1-5）：扫描与修复分离。

scan() 只负责"查"：调用 cppcheck --addon=misra --dump 扫描 C 代码，解析违规列表。
repair() 只负责"改"：调用代码修复 Agent（当前 Mock），返回修复后代码。

扫描模式由 settings.USE_REAL_CPPCHECK 控制：
- True（默认）：调用真实 cppcheck --addon=misra --dump；当系统未安装 cppcheck 或
  执行失败时，抛出异常。
- False：使用基于代码模式匹配的 Mock 扫描，不依赖系统 cppcheck。

P1-5 修复：默认使用真实 Cppcheck，扫描结果明确标识扫描引擎类型。
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from skyforge_engine.config import settings
from skyforge_engine.utils.log_util import logger
from skyforge_engine.utils.cleanup_util import safe_tempdir
from skyforge_engine.tools.base_scanner import MultiLanguageScanner
from skyforge_engine.tools.base_scanner import Violation as BaseViolation

import warnings

# 终端日志回调类型（Patch 4 流式推送）
# 签名：(agent: str, level: str, message: str) -> None
# - agent：TERMINAL / SYSTEM（与前端 AgentType 对齐）
# - level：info / success / warn / error
LogCallback = Callable[[str, str, str], None]


@dataclass
class Violation:
    """单条 MISRA-C 违规记录。"""

    file: str
    line: int
    column: int = 0
    severity: str = "style"
    rule_id: str = ""
    message: str = ""


@dataclass
class ScanResult:
    """扫描结果包装，包含违规列表和扫描引擎元信息。"""

    violations: list[Violation]
    engine: str  # "cppcheck" | "mock"
    cppcheck_version: str | None = None
    degraded: bool = False  # 保留字段，兼容旧数据
    degradation_reason: str = ""  # 保留字段，兼容旧数据


def _find_cppcheck() -> str | None:
    """查找可用的 cppcheck 可执行文件。

    优先使用 MSYS2 ucrt64 的 cppcheck（版本更新且 cfg 路径正确），
    避免使用编译时 FILESDIR 错误的 Strawberry cppcheck。
    """
    import sys
    if sys.platform == "win32":
        # 优先查找 MSYS2 ucrt64
        msys2_paths = [
            r"C:\msys64\ucrt64\bin\cppcheck.exe",
            r"C:\msys64\mingw64\bin\cppcheck.exe",
        ]
        for p in msys2_paths:
            if os.path.isfile(p):
                return p
    # 回退到系统 PATH 中的 cppcheck
    return shutil.which("cppcheck")


def _cppcheck_available() -> bool:
    """检测系统是否安装 cppcheck。"""
    return _find_cppcheck() is not None


def _cppcheck_version() -> str | None:
    """获取 cppcheck 版本号，不可用时返回 None。"""
    cppcheck_path = _find_cppcheck()
    if not cppcheck_path:
        return None
    try:
        proc = subprocess.run(
            [cppcheck_path, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        version = (proc.stdout or proc.stderr or "").strip()
        return version if version else None
    except Exception:
        return None


def _cppcheck_installation_hint() -> str:
    """返回 Cppcheck 安装指导信息。"""
    return (
        "Cppcheck 未安装或配置错误。请根据您的操作系统安装 Cppcheck：\n"
        "  - Ubuntu/Debian: sudo apt-get install cppcheck\n"
        "  - macOS: brew install cppcheck\n"
        "  - Windows: 通过 MSYS2 安装 pacman -S mingw-w64-ucrt-x86_64-cppcheck\n"
        "  - CentOS/RHEL: sudo yum install cppcheck 或 sudo dnf install cppcheck\n"
        "如需使用 Mock 扫描，请将 USE_REAL_CPPCHECK 设为 false。"
    )


def scan(
    code: str,
    log_callback: LogCallback | None = None,
) -> list[Violation]:
    """扫描 C 代码，返回 MISRA-C 违规列表（向后兼容接口）。

    .. deprecated::
        使用 ``CppcheckVerifier().verify(code)`` 替代（真实 Cppcheck 模式）。

    内部委托 scan_with_result() 获取完整 ScanResult，此处仅返回 violations 列表
    以保持向后兼容。新代码应优先使用 scan_with_result()。

    扫描模式由 settings.USE_REAL_CPPCHECK 控制：
    - True（默认）：调用真实 `cppcheck --addon=misra --dump`。当系统未安装 cppcheck 或
      执行失败时，抛出异常。
    - False：使用 Mock 扫描（基于代码模式匹配），不依赖系统 cppcheck。

    Args:
        code: 待扫描的 C 代码字符串。
        log_callback: 终端日志回调 (agent, level, message)，用于 Patch 4
            WebSocket 流式推送终端命令和输出。为 None 时不推送。

    Returns:
        违规列表（行号 + 规则ID + 描述）。
    """
    warnings.warn(
        "scan is deprecated, use CppcheckVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    result = scan_with_result(code, log_callback)
    return result.violations


def scan_with_result(
    code: str,
    log_callback: LogCallback | None = None,
) -> ScanResult:
    """扫描 C 代码，返回包含引擎元信息的完整 ScanResult。

    .. deprecated::
        使用 ``CppcheckVerifier().verify(code)`` 替代（真实 Cppcheck 模式）。

    与 scan() 的区别：返回 ScanResult 包含 engine、cppcheck_version、
    degraded 等元信息，用于合规审计和日志追溯。

    扫描模式由 settings.USE_REAL_CPPCHECK 控制：
    - True（默认）：调用真实 `cppcheck --addon=misra --dump`。
    - False：使用 Mock 扫描（基于代码模式匹配）。

    Args:
        code: 待扫描的 C 代码字符串。
        log_callback: 终端日志回调。

    Returns:
        ScanResult 包含违规列表和扫描引擎元信息。
    """
    warnings.warn(
        "scan_with_result is deprecated, use CppcheckVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    # Mock 模式：直接使用 Mock 扫描
    if not settings.USE_REAL_CPPCHECK:
        logger.info("CppcheckScanner:USE_REAL_CPPCHECK=false，使用 Mock 扫描")
        if log_callback:
            log_callback(
                "SYSTEM",
                "info",
                "扫描模式: Mock（USE_REAL_CPPCHECK=false）",
            )
        violations = _scan_mock(code, log_callback)
        return ScanResult(
            violations=violations,
            engine="mock",
            degraded=False,
        )

    # 真实 Cppcheck 模式
    cppcheck_ver = _cppcheck_version()
    if not _cppcheck_available():
        hint = _cppcheck_installation_hint()
        logger.error(f"CppcheckScanner:{hint}")
        if log_callback:
            log_callback("SYSTEM", "error", hint)
        raise RuntimeError(hint)

    violations = _scan_real_cppcheck(code, log_callback)
    logger.info(f"CppcheckScanner:真实 Cppcheck 扫描完成，版本: {cppcheck_ver}")
    return ScanResult(
        violations=violations,
        engine="cppcheck",
        cppcheck_version=cppcheck_ver,
        degraded=False,
    )


def _find_cppcheck_cfg_dir() -> str | None:
    """在 Windows 上搜索 Cppcheck 的 cfg 目录（含 std.cfg）。

    Cppcheck 二进制在 Windows 上可能将 FILESDIR 硬编码为构建机器路径，
    导致运行时找不到 std.cfg。本函数搜索实际安装路径。
    """
    import sys
    if sys.platform != "win32":
        return None
    from pathlib import Path

    candidates: list[str] = []
    # 通过 cppcheck 可执行文件相对路径推导（最可靠）
    cppcheck_path = _find_cppcheck() or shutil.which("cppcheck")
    if cppcheck_path:
        cppcheck_dir = Path(cppcheck_path).resolve().parent
        candidates.append(str(cppcheck_dir / ".." / "share" / "cppcheck" / "cfg"))
        candidates.append(str(cppcheck_dir / "cfg"))
    # MSYS2 ucrt64 / mingw64
    candidates.append(r"C:\msys64\ucrt64\share\cppcheck\cfg")
    candidates.append(r"C:\msys64\mingw64\share\cppcheck\cfg")
    # 标准安装路径
    candidates.append(r"C:\Program Files\cppcheck\cfg")
    candidates.append(r"C:\Program Files (x86)\cppcheck\cfg")

    for path in candidates:
        if Path(path).exists() and (Path(path) / "std.cfg").exists():
            return path
    return None


def _find_misra_addon() -> str | None:
    """在 Windows 上搜索 misra.py addon 的完整路径。"""
    import sys
    if sys.platform != "win32":
        return None
    # 常见安装路径
    candidates = []
    # MSYS2 ucrt64
    candidates.append(r"C:\msys64\ucrt64\share\cppcheck\addons\misra.py")
    # MSYS2 mingw64
    candidates.append(r"C:\msys64\mingw64\share\cppcheck\addons\misra.py")
    # 标准安装路径
    candidates.append(r"C:\Program Files\cppcheck\addons\misra.py")
    candidates.append(r"C:\Program Files (x86)\cppcheck\addons\misra.py")
    # 通过 cppcheck 可执行文件定位
    import shutil
    cppcheck_path = shutil.which("cppcheck")
    if cppcheck_path:
        from pathlib import Path
        cppcheck_dir = Path(cppcheck_path).parent
        candidates.append(str(cppcheck_dir / ".." / "share" / "cppcheck" / "addons" / "misra.py"))
        candidates.append(str(cppcheck_dir / "addons" / "misra.py"))
    for path in candidates:
        from pathlib import Path
        if Path(path).exists():
            return path
    return None


def _scan_real_cppcheck(
    code: str,
    log_callback: LogCallback | None = None,
) -> list[Violation]:
    """真实 Cppcheck 扫描路径：调用 `cppcheck --addon=misra --dump`。

    将 C 代码写入临时文件，执行 cppcheck 命令，解析模板化文本输出为 Violation
    列表。临时文件用完即删。

    异常（如 subprocess.TimeoutExpired、文件系统错误）会向上抛出。

    Args:
        code: 待扫描的 C 代码字符串。
        log_callback: 终端日志回调。

    Returns:
        违规列表。
    """
    with safe_tempdir(prefix="skyforge_cppcheck_") as tmp_dir:
        src_path = os.path.join(tmp_dir, "code.c")
        # Cppcheck 不支持非 ASCII 字符（如中文注释），
        # 将非 ASCII 字符替换为 '?' 以避免 unhandledChar 错误
        ascii_code = code.encode("ascii", errors="replace").decode("ascii")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(ascii_code)

        # 使用管道分隔模板，便于稳定解析
        # {file}|{line}|{column}|{severity}|{id}|{message}
        template = "{file}|{line}|{column}|{severity}|{id}|{message}"
        cppcheck_path = _find_cppcheck() or "cppcheck"
        cmd = [
            cppcheck_path,
            "--dump",
            f"--template={template}",
            "--quiet",
        ]
        # Windows 特殊处理：FILESDIR 硬编码 + addon 路径
        import sys
        if sys.platform == "win32":
            # 优先用当前 Python 解释器（venv 内），避免 Windows Store 的 python stub（exitcode 9009）
            python_path = sys.executable
            if not python_path or "WindowsApps" in python_path:
                python_path = shutil.which("python3") or shutil.which("python")
            if python_path:
                cmd.append(f"--addon-python={python_path}")
            # 搜索 misra.py addon 的完整路径
            misra_path = _find_misra_addon()
            if misra_path:
                cmd.append(f"--addon={misra_path}")
            else:
                cmd.append("--addon=misra")
        else:
            cmd.append("--addon=misra")
        cmd.append(src_path)
        cmd_str = " ".join(cmd)
        logger.info(f"CppcheckScanner:执行: {cmd_str}")
        if log_callback:
            log_callback("TERMINAL", "info", f"$ {cmd_str}")
        # misra addon 会先生成 code.c.dump，再扫描该 dump
        proc = subprocess.run(
            cmd,
            cwd=tmp_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")

        # Windows 上 Cppcheck 可能找不到 misra addon，手动运行 MISRA 扫描
        if sys.platform == "win32":
            from pathlib import Path as _Path
            dump_path = _Path(tmp_dir) / (os.path.basename(src_path).replace(".c", "") + ".c.dump")
            if dump_path.exists():
                misra_path = _find_misra_addon()
                # 优先用当前 Python 解释器（venv 内），避免 Windows Store stub
                python_path = sys.executable
                if not python_path or "WindowsApps" in python_path:
                    python_path = shutil.which("python3") or shutil.which("python")
                if misra_path and python_path:
                    misra_proc = subprocess.run(
                        [python_path, misra_path, str(dump_path)],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=60,
                        check=False,
                    )
                    misra_output = (misra_proc.stdout or "") + (misra_proc.stderr or "")
                    if misra_output:
                        combined += "\n" + misra_output
                    logger.info(f"CppcheckScanner:手动 MISRA 扫描完成, 输出长度={len(misra_output)}")
        if log_callback and combined.strip():
            # 推送 cppcheck 原始输出（截断过长的输出）
            snippet = combined[:2000]
            level = "warn" if proc.returncode != 0 else "info"
            log_callback("TERMINAL", level, snippet)
        return _parse_output(combined, src_path)


def _scan_mock(
    code: str,
    log_callback: LogCallback | None = None,
    language: str = "c",
) -> list[Violation]:
    """Mock 扫描路径（基于编码标准注册表的模式匹配）。

    从编码标准注册表获取指定语言的 mock 扫描模式。
    """
    logger.info("CppcheckScanner:使用 mock 扫描（基于编码标准注册表）")
    if log_callback:
        log_callback(
            "SYSTEM",
            "info",
            "使用基于编码标准注册表的 mock 扫描",
        )
    return _mock_scan(code, language=language)


def _mock_scan(code: str, language: str = "c") -> list[Violation]:
    """基于编码标准注册表的 mock 扫描。

    从编码标准注册表获取指定语言的 mock 扫描模式，
    按模式匹配代码并返回 Violation 列表。
    """
    from skyforge_engine.coding_standards.base import get_registry

    violations: list[Violation] = []
    patterns = get_registry().get_mock_scan_patterns(language)

    lines = code.splitlines()
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("/*")
            or stripped.startswith("//")
            or stripped.startswith("*")
        ):
            continue

        for pat_def in patterns:
            if not re.search(pat_def["pattern"], stripped):
                continue

            # 排除条件
            exclude = False

            exclude_starts = pat_def.get("exclude_starts", [])
            if exclude_starts and any(stripped.startswith(s) for s in exclude_starts):
                exclude = True

            exclude_names = pat_def.get("exclude_names", [])
            m_match = re.match(r"^(\w+)\s*\(", stripped)
            if exclude_names and m_match and m_match.group(1) in exclude_names:
                exclude = True

            exclude_contains = pat_def.get("exclude_contains", [])
            if exclude_contains and any(s in stripped for s in exclude_contains):
                exclude = True

            if not exclude:
                violations.append(
                    Violation(
                        file="code.c",
                        line=i,
                        column=0,
                        severity=pat_def.get("severity", "style"),
                        rule_id=pat_def["rule_id"],
                        message=pat_def["message"],
                    )
                )

    logger.info(f"CppcheckScanner:mock 扫描完成:检出 {len(violations)} 条违规")
    return violations


def _parse_output(output: str, src_path: str) -> list[Violation]:
    """解析 cppcheck 模板化输出为 Violation 列表。

    支持两种格式：
    1. 模板格式: file|line|column|severity|id|message
    2. MISRA addon stderr 格式: [file:line] (severity) ... [rule-id]
    """
    import re
    violations: list[Violation] = []
    basename = os.path.basename(src_path)
    for line in output.splitlines():
        # 格式 1: 模板格式 file|line|column|severity|id|message
        if "|" in line:
            parts = line.split("|", 5)
            if len(parts) >= 6:
                fpath, line_no, col, sev, rid, msg = parts
                if basename not in fpath and src_path not in fpath:
                    continue
                try:
                    line_int = int(line_no)
                except ValueError:
                    continue
                violations.append(
                    Violation(
                        file=fpath,
                        line=line_int,
                        column=int(col) if col.isdigit() else 0,
                        severity=sev,
                        rule_id=rid,
                        message=msg,
                    )
                )
                continue

        # 格式 2: MISRA addon stderr 格式 [file:line] (severity) ... [rule-id]
        # 例如: [C:/path/to/file.c:1] (style) misra violation ... [misra-c2012-8.4]
        match = re.match(
            r'\[(.+?):(\d+)\]\s*\((\w+)\).*\[(misra-c2012-[\d.]+)\]',
            line,
        )
        if match:
            fpath, line_no, sev, rid = match.groups()
            if basename not in fpath and src_path not in fpath:
                continue
            try:
                line_int = int(line_no)
            except ValueError:
                continue
            violations.append(
                Violation(
                    file=fpath,
                    line=line_int,
                    column=0,
                    severity=sev,
                    rule_id=rid,
                    message=f"MISRA violation: {rid}",
                )
            )
            continue
    logger.info(f"CppcheckScanner:完成:检出 {len(violations)} 条违规")
    return violations


def repair(code: str, violations: list[Violation]) -> str:
    """修复代码（当前 Mock 实现，已被 code_repairer_agent 取代，保留向后兼容）。

    .. deprecated::
        使用 ``code_repairer_agent.CodeRepairerAgent.repair()`` 替代。

    查改解耦：scan() 只查不修，repair() 只修不查。
    当前 Mock 行为：在原代码顶部插入违规修复注释，原代码语义不变。
    真实修复闭环请使用 code_repairer_agent.CodeRepairerAgent.repair()。

    Args:
        code: 原始 C 代码字符串。
        violations: scan() 返回的违规列表。

    Returns:
        修复后的 C 代码字符串。
    """
    warnings.warn(
        "repair is deprecated, use CodeRepairerAgent instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if not violations:
        logger.info("CppcheckRepair:无违规，跳过修复")
        return code

    logger.info(f"CppcheckRepair:开始:Mock 修复 {len(violations)} 条违规")
    lines = [
        "/* ===== Cppcheck 自动修复说明（Mock） =====",
        f" * 共检出 {len(violations)} 条 MISRA 违规，待修复项：",
    ]
    for v in violations[:20]:  # 仅列前 20 条，避免注释爆炸
        lines.append(f" *   L{v.line}:{v.column} [{v.rule_id}] {v.message}")
    if len(violations) > 20:
        lines.append(f" *   ... 其余 {len(violations) - 20} 条略")
    lines.append(" * TODO: 接通代码修复 Agent（LLM + MISRA RAG）做定向重写")
    lines.append(" */")
    lines.append("")
    repaired = "\n".join(lines) + code
    logger.info("CppcheckRepair:完成:Mock 修复（注入修复注释）")
    return repaired

# 多语言扫描器实例
multi_scanner = MultiLanguageScanner()

def scan_multi(code: str, language: str = "c", **kwargs) -> list[BaseViolation]:
    """多语言静态分析扫描。

    .. deprecated::
        使用 ``MultiLanguageScanner.scan()`` 直接替代。
    """
    warnings.warn(
        "scan_multi is deprecated, use MultiLanguageScanner directly",
        DeprecationWarning,
        stacklevel=2,
    )
    return multi_scanner.scan(code, language=language, **kwargs)
