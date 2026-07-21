"""MISRA-C:2012 编码标准协议实现。"""

from __future__ import annotations

import re
from typing import Any

from skyforge_engine.core.protocols import Violation


class MISRACStandard:
    """MISRA-C:2012 编码标准协议实现。

    实现 CodingStandardProtocol，支持基于正则的 Mock 扫描。
    """

    @property
    def standard_name(self) -> str:
        return "MISRA-C:2012"

    @property
    def language(self) -> str:
        return "c"

    def get_mock_scan_patterns(self) -> list[dict[str, Any]]:
        return [
            {
                "pattern": r"\b(malloc|calloc|realloc)\s*\(",
                "rule_id": "misra-c2012-20.4",
                "severity": "error",
                "message": "动态内存分配不被允许（Rule 20.4）",
            },
            {
                "pattern": r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*=\s*.*;",
                "rule_id": "misra-c2012-8.7",
                "severity": "style",
                "message": "外部变量应定义为 static（Rule 8.7）",
                "exclude_starts": ["static", "extern"],
            },
            {
                "pattern": r"^(\w+)\s*\(([^)]*)\)\s*;\s*$",
                "rule_id": "misra-c2012-17.7",
                "severity": "style",
                "message": "函数返回值未被使用（Rule 17.7）",
                "exclude_names": ["if", "while", "for", "switch", "return", "sizeof"],
                "exclude_contains": ["= ", "{"],
            },
            {
                "pattern": r"^(void|int|double|float|char|short|long|unsigned)\s+\w+\s*\([^)]*\)\s*\{",
                "rule_id": "misra-c2012-8.1",
                "severity": "style",
                "message": "函数需要类型声明/原型（Rule 8.1）",
            },
            {
                "pattern": r"\(\w+\s*\*\)\s*\w+",
                "rule_id": "misra-c2012-11.3",
                "severity": "error",
                "message": "不同类型指针间转换需要显式强制类型转换（Rule 11.3）",
            },
            {
                "pattern": r"\w+\s*\+\s*\w+\s*<<\s*\w+",
                "rule_id": "misra-c2012-12.1",
                "severity": "style",
                "message": "运算符优先级需要括号明确（Rule 12.1）",
            },
            {
                "pattern": r"\w+\s*\|\s*\w+\s*\&\s*\w+",
                "rule_id": "misra-c2012-12.1",
                "severity": "style",
                "message": "运算符优先级需要括号明确（Rule 12.1）",
            },
            {
                "pattern": r"\b(printf|fprintf|scanf|fscanf)\s*\(",
                "rule_id": "misra-c2012-21.6",
                "severity": "error",
                "message": "标准库 I/O 函数在嵌入式系统中不允许使用（Rule 21.6）",
            },
        ]

    def scan(self, code: str) -> list[Violation]:
        violations: list[Violation] = []
        patterns = self.get_mock_scan_patterns()

        for line_no, line in enumerate(code.splitlines(), start=1):
            stripped = line.lstrip()
            for pat in patterns:
                regex = pat["pattern"]
                if not re.search(regex, line):
                    continue

                # 排除规则
                exclude_starts = pat.get("exclude_starts", [])
                if any(stripped.startswith(es) for es in exclude_starts):
                    continue

                exclude_names = pat.get("exclude_names", [])
                first_token = stripped.split()[0] if stripped.split() else ""
                if first_token in exclude_names:
                    continue

                exclude_contains = pat.get("exclude_contains", [])
                if any(ec in line for ec in exclude_contains):
                    continue

                violations.append(
                    Violation(
                        file="",
                        line=line_no,
                        column=0,
                        severity=pat["severity"],
                        rule_id=pat["rule_id"],
                        message=pat["message"],
                    )
                )

        return violations
