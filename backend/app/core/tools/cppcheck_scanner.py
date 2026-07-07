"""Cppcheck 查改解耦模块（Patch 1）：扫描与修复分离，支持优雅降级。

scan() 只负责"查"：调用 cppcheck --addon=misra --dump 扫描 C 代码，解析违规列表。
repair() 只负责"改"：调用代码修复 Agent（当前 Mock），返回修复后代码。
若系统未安装 cppcheck，scan() 优雅降级：返回基于代码模式匹配的 mock 违规数据
（用于测试修复闭环）。
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable

from app.utils.log_util import logger

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


def _cppcheck_available() -> bool:
    """检测系统是否安装 cppcheck。"""
    return shutil.which("cppcheck") is not None


def scan(
    code: str,
    log_callback: LogCallback | None = None,
) -> list[Violation]:
    """扫描 C 代码，返回 MISRA-C 违规列表。

    调用 `cppcheck --addon=misra --dump`，解析文本输出。
    若系统未安装 cppcheck，优雅降级：返回基于代码模式匹配的 mock 违规数据
    （用于测试修复闭环）。

    Args:
        code: 待扫描的 C 代码字符串。
        log_callback: 终端日志回调 (agent, level, message)，用于 Patch 4
            WebSocket 流式推送终端命令和输出。为 None 时不推送。

    Returns:
        违规列表（行号 + 规则ID + 描述）。
    """
    if not _cppcheck_available():
        logger.warning(
            "CppcheckScanner:系统未安装 cppcheck，降级为 mock 扫描（基于代码模式匹配）"
        )
        if log_callback:
            log_callback(
                "SYSTEM",
                "warn",
                "系统未安装 cppcheck，降级为基于代码模式匹配的 mock 扫描",
            )
        return _mock_scan(code)

    tmp_dir = tempfile.mkdtemp(prefix="airborne_cppcheck_")
    src_path = os.path.join(tmp_dir, "code.c")
    try:
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 使用管道分隔模板，便于稳定解析
        # {file}|{line}|{column}|{severity}|{id}|{message}
        template = "{file}|{line}|{column}|{severity}|{id}|{message}"
        cmd = [
            "cppcheck",
            "--dump",
            "--addon=misra",
            f"--template={template}",
            "--quiet",
            src_path,
        ]
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
            timeout=60,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        if log_callback and combined.strip():
            # 推送 cppcheck 原始输出（截断过长的输出）
            snippet = combined[:2000]
            level = "warn" if proc.returncode != 0 else "info"
            log_callback("TERMINAL", level, snippet)
        return _parse_output(combined, src_path)
    except subprocess.TimeoutExpired:
        logger.error("CppcheckScanner:扫描超时（60s），返回空列表")
        if log_callback:
            log_callback("TERMINAL", "error", "cppcheck 扫描超时（60s）")
        return []
    except Exception as e:
        logger.error(f"CppcheckScanner:扫描异常: {e}")
        if log_callback:
            log_callback("TERMINAL", "error", f"cppcheck 扫描异常: {e}")
        return []
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _mock_scan(code: str) -> list[Violation]:
    """基于代码模式匹配的 mock 扫描（cppcheck 未安装时使用）。

    识别常见 MISRA-C 违规模式，返回 Violation 列表，用于测试修复闭环：
    - Rule 20.4：malloc/calloc/realloc 动态内存
    - Rule 8.7：非 static 全局变量
    - Rule 17.7：未检查返回值的函数调用
    - Rule 8.1：函数定义缺少原型
    - Rule 11.3：不同类型指针间转换
    - Rule 12.1：运算符优先级混淆
    - Rule 14.2：for 循环计数器未修改
    - Rule 21.6：标准库 I/O 函数使用
    """
    violations: list[Violation] = []
    lines = code.splitlines()
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # 跳过注释行
        if (
            not stripped
            or stripped.startswith("/*")
            or stripped.startswith("//")
            or stripped.startswith("*")
        ):
            continue

        # Rule 20.4：动态内存分配
        if re.search(r"\b(malloc|calloc|realloc)\s*\(", stripped):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="error",
                    rule_id="misra-c2012-20.4",
                    message="动态内存分配不被允许（Rule 20.4）",
                )
            )

        # Rule 8.7：非 static 全局变量（粗暴匹配：行首类型 + 变量名 + 分号，且非 static/extern/const）
        if (
            re.match(
                r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*=\s*.+;",
                stripped,
            )
            and not stripped.startswith("static")
            and not stripped.startswith("extern")
        ):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="style",
                    rule_id="misra-c2012-8.7",
                    message="外部变量应定义为 static（Rule 8.7）",
                )
            )

        # Rule 17.7：函数调用未检查返回值（形如 func(args); 且非控制流）
        m = re.match(r"^(\w+)\s*\(([^)]*)\)\s*;\s*$", stripped)
        if m and m.group(1) not in {
            "if",
            "while",
            "for",
            "switch",
            "return",
            "sizeof",
        }:
            # 排除赋值/函数定义（含 {）
            if "= " not in stripped and "{" not in stripped:
                violations.append(
                    Violation(
                        file="code.c",
                        line=i,
                        column=0,
                        severity="style",
                        rule_id="misra-c2012-17.7",
                        message="函数返回值未被使用（Rule 17.7）",
                    )
                )

        # Rule 8.1：函数定义缺少原型（粗暴匹配：行首类型 函数名(...) {）
        if re.match(
            r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*\([^)]*\)\s*\{",
            stripped,
        ):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="style",
                    rule_id="misra-c2012-8.1",
                    message="函数需要类型声明/原型（Rule 8.1）",
                )
            )

        # Rule 11.3：不同类型指针间转换（粗暴匹配：强制类型转换指针）
        if re.search(r"\(\w+\s*\*\)\s*\w+", stripped) and not stripped.startswith("//"):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="error",
                    rule_id="misra-c2012-11.3",
                    message="不同类型指针间转换需要显式强制类型转换（Rule 11.3）",
                )
            )

        # Rule 12.1：运算符优先级混淆（粗暴匹配：混合算术和位运算、逻辑运算）
        if re.search(r"\w+\s*\+\s*\w+\s*<<\s*\w+", stripped) or re.search(
            r"\w+\s*\|\s*\w+\s*\&\s*\w+", stripped
        ):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="style",
                    rule_id="misra-c2012-12.1",
                    message="运算符优先级需要括号明确（Rule 12.1）",
                )
            )

        # Rule 14.2：for 循环计数器未修改（粗暴匹配：for 循环但循环体内无计数器修改）
        if re.search(r"for\s*\([^;]*;\s*(\w+)\s*[<>=!]+[^;]*;", stripped):
            # 简化检测：如果 for 循环后面几行没有计数器递增，则标记违规
            counter_match = re.search(r"for\s*\([^;]*;\s*(\w+)\s*[<>=!]+[^;]*;", stripped)
            if counter_match:
                counter_var = counter_match.group(1)
                # 检查后续几行是否有计数器修改
                has_increment = False
                for j in range(i, min(i + 10, len(lines) + 1)):
                    if j - 1 < len(lines):
                        next_line = lines[j - 1].strip()
                        if re.search(rf"\b{counter_var}\s*(\+\+|--|[+=]|-=|\*=|/=)", next_line):
                            has_increment = True
                            break
                if not has_increment:
                    violations.append(
                        Violation(
                            file="code.c",
                            line=i,
                            column=0,
                            severity="error",
                            rule_id="misra-c2012-14.2",
                            message="for 循环计数器未在循环体内修改（Rule 14.2）",
                        )
                    )

        # Rule 21.6：标准库 I/O 函数使用（printf/scanf）
        if re.search(r"\b(printf|fprintf|scanf|fscanf)\s*\(", stripped):
            violations.append(
                Violation(
                    file="code.c",
                    line=i,
                    column=0,
                    severity="error",
                    rule_id="misra-c2012-21.6",
                    message="标准库 I/O 函数在嵌入式系统中不允许使用（Rule 21.6）",
                )
            )

    logger.info(f"CppcheckScanner:mock 扫描完成:检出 {len(violations)} 条违规")
    return violations


def _parse_output(output: str, src_path: str) -> list[Violation]:
    """解析 cppcheck 模板化输出为 Violation 列表。"""
    violations: list[Violation] = []
    basename = os.path.basename(src_path)
    for line in output.splitlines():
        # 期望格式: file|line|column|severity|id|message
        if "|" not in line:
            continue
        parts = line.split("|", 5)
        if len(parts) < 6:
            continue
        fpath, line_no, col, sev, rid, msg = parts
        # 仅保留针对本文件的违规（misra addon 可能输出 dump 路径）
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
    logger.info(f"CppcheckScanner:完成:检出 {len(violations)} 条违规")
    return violations


def repair(code: str, violations: list[Violation]) -> str:
    """修复代码（当前 Mock 实现，已被 code_repairer_agent 取代，保留向后兼容）。

    查改解耦：scan() 只查不修，repair() 只修不查。
    当前 Mock 行为：在原代码顶部插入违规修复注释，原代码语义不变。
    真实修复闭环请使用 code_repairer_agent.CodeRepairerAgent.repair()。

    Args:
        code: 原始 C 代码字符串。
        violations: scan() 返回的违规列表。

    Returns:
        修复后的 C 代码字符串。
    """
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
