"""MISRA-C++ / JSF AV C++ 编码标准协议实现。"""

from __future__ import annotations

import re
from typing import Any

from skyforge_engine.core.protocols import Violation


class MISRA_CPPStandard:
    """MISRA-C++/JSF AV C++/CERT C++ 编码标准协议实现。

    实现 CodingStandardProtocol，支持基于正则的 Mock 扫描。
    """

    @property
    def standard_name(self) -> str:
        return "MISRA-C++/JSF AV C++/CERT C++"

    @property
    def language(self) -> str:
        return "cpp"

    def get_mock_scan_patterns(self) -> list[dict[str, Any]]:
        return [
            {
                "pattern": r"\bnew\s+\w+[\[\(]",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 new/delete，应使用智能指针（Rule 18-4-1）",
            },
            {
                "pattern": r"\bdelete\s+",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 new/delete，应使用智能指针（Rule 18-4-1）",
            },
            {
                "pattern": r"\bmalloc\s*\(",
                "rule_id": "jsf-av-cpp-18-4-1",
                "severity": "error",
                "message": "禁止使用 malloc/free（Rule 18-4-1）",
            },
            {
                "pattern": r"\bgoto\s+",
                "rule_id": "jsf-av-cpp-6-6-1",
                "severity": "error",
                "message": "禁止使用 goto（Rule 6-6-1）",
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
