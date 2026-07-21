"""编码标准协议层注册表。

支持 CodingStandardProtocol 实现类的注册与查找。
"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import CodingStandardProtocol


class CodingStandardRegistry:
    """编码标准协议注册表。

    管理 CodingStandardProtocol 实现实例的注册、查询与迭代。
    """

    def __init__(self) -> None:
        self._standards: dict[str, CodingStandardProtocol] = {}

    def register(self, standard: CodingStandardProtocol) -> None:
        """注册一个编码标准实现。"""
        self._standards[standard.standard_name] = standard

    def unregister(self, standard_name: str) -> None:
        """注销指定名称的编码标准。"""
        self._standards.pop(standard_name, None)

    def get(self, standard_name: str) -> CodingStandardProtocol | None:
        """按标准名称获取编码标准实现。"""
        return self._standards.get(standard_name)

    def get_for_language(self, language: str) -> list[CodingStandardProtocol]:
        """按目标语言获取所有适用的编码标准。"""
        return [
            s for s in self._standards.values() if s.language == language
        ]

    def get_all(self) -> list[CodingStandardProtocol]:
        """获取所有已注册的编码标准。"""
        return list(self._standards.values())

    def get_mock_scan_patterns(
        self, language: str
    ) -> list[dict[str, Any]]:
        """获取指定语言下所有标准的 Mock 扫描模式（合并）。"""
        patterns: list[dict[str, Any]] = []
        for std in self.get_for_language(language):
            patterns.extend(std.get_mock_scan_patterns())
        return patterns


_registry: CodingStandardRegistry | None = None


def get_registry() -> CodingStandardRegistry:
    """获取全局编码标准协议注册表单例。"""
    global _registry
    if _registry is None:
        _registry = CodingStandardRegistry()
    return _registry
