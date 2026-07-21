"""Python 军工软件编程安全规范编码标准协议实现。"""

from __future__ import annotations

import re
from typing import Any

from skyforge_engine.core.protocols import Violation


class PythonSafetyStandard:
    """军工软件Python编程规范 (T/ZASDI 0002-2023) 协议实现。

    实现 CodingStandardProtocol，支持基于正则的 Mock 扫描。
    """

    @property
    def standard_name(self) -> str:
        return "军工软件Python编程规范 (T/ZASDI 0002-2023)"

    @property
    def language(self) -> str:
        return "python"

    def get_mock_scan_patterns(self) -> list[dict[str, Any]]:
        return [
            {
                "pattern": r"\beval\s*\(",
                "rule_id": "python-P-01",
                "severity": "error",
                "message": "禁止使用 eval（P-01）",
            },
            {
                "pattern": r"\bexec\s*\(",
                "rule_id": "python-P-01",
                "severity": "error",
                "message": "禁止使用 exec（P-01）",
            },
            {
                "pattern": r"\bglobal\s+\w+",
                "rule_id": "python-P-02",
                "severity": "warning",
                "message": "禁止使用 global 声明（P-02）",
            },
            {
                "pattern": r"\bnonlocal\s+\w+",
                "rule_id": "python-P-02",
                "severity": "warning",
                "message": "禁止使用 nonlocal 声明（P-02）",
            },
        ]

    def scan(self, code: str) -> list[Violation]:
        violations: list[Violation] = []
        patterns = self.get_mock_scan_patterns()

        for line_no, line in enumerate(code.splitlines(), start=1):
            for pat in patterns:
                regex = pat["pattern"]
                if re.search(regex, line):
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
