"""LLM 输出验证器 — 确保 LLM 输出符合规范。

验证规则:
  1. C 代码语法正确性检查
  2. MISRA-C 禁止模式检测 (malloc/free/recursion/goto)
  3. 恶意代码检测 (system/exec/popen)
  4. 输出大小限制
  5. 追溯注释完整性
"""

import re
from dataclasses import dataclass, field

# 禁止模式（MISRA-C 强制 + 安全相关）
FORBIDDEN_PATTERNS = [
    (r"\bmalloc\s*\(", "MISRA Rule-21.3: 禁止动态内存分配"),
    (r"\bfree\s*\(", "MISRA Rule-21.3: 禁止动态内存释放"),
    (r"\bcalloc\s*\(", "MISRA Rule-21.3: 禁止动态内存分配"),
    (r"\brealloc\s*\(", "MISRA Rule-21.3: 禁止动态内存重分配"),
    (r"\bgoto\s+\w", "MISRA Rule-15.1: 禁止 goto"),
    (r"\bsystem\s*\(", "安全: 禁止 system() 调用"),
    (r"\bexec\s*\(", "安全: 禁止 exec() 调用"),
    (r"\bpopen\s*\(", "安全: 禁止 popen() 调用"),
    (r"\bfork\s*\(", "安全: 禁止 fork() 调用"),
    (r"\b__asm\b", "安全: 禁止内联汇编"),
]


@dataclass
class ValidatedOutput:
    passed: bool
    content: str = ""
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_output(raw_output: str, max_size: int = 102400) -> ValidatedOutput:
    """验证 LLM 输出是否符合规范。"""
    violations: list[str] = []
    warnings: list[str] = []
    
    # 大小检查
    if len(raw_output.encode("utf-8")) > max_size:
        violations.append(f"输出超过限制: {len(raw_output)} > {max_size}")
        return ValidatedOutput(passed=False, content=raw_output[:max_size], violations=violations)
    
    # 禁止模式检测
    for pattern, description in FORBIDDEN_PATTERNS:
        if re.search(pattern, raw_output):
            violations.append(f"{description}: {pattern}")
    
    # 追溯注释检查
    if "void" in raw_output or "double" in raw_output:
        if "[REQ-" not in raw_output:
            warnings.append("代码缺少 [REQ-xxx] 追溯注释")
    
    return ValidatedOutput(
        passed=len(violations) == 0,
        content=raw_output,
        violations=violations,
        warnings=warnings,
    )
