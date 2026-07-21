# -*- coding: utf-8 -*-
"""HIL Manager Provider — L0 依赖反转接口。

设计动机
--------
L0 (skyforge_engine.pipeline) 历史上通过
``try: from studio.app.core.hil... / from app.core.hil...`` 反向 import L3 的
``get_hil_manager``，违反 L0→L3 不可依赖的分层约束。本模块通过 provider
模式反转依赖：

- L0 仅定义 ``HILManagerProtocol``（最小接口）+ ``set_hil_manager_provider``
  注入点
- L0 ``pipeline.run_pipeline`` 调用 ``get_hil_manager()`` 获取管理器
- L3 启动时（``studio/app/core/hil/__init__.py`` 加载时）调用
  ``set_hil_manager_provider(get_hil_manager)`` 注入自己的实现
- L0 独立运行（无 L3）时返回空实现 ``_NoopHILManager``，所有审批请求自动
  返回 ``approved=True / status=skipped``，流水线不阻塞。
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class HILManagerProtocol(Protocol):
    """HIL 管理器最小接口（duck typing）。"""

    enabled: bool

    async def request_approval(self, **kwargs: Any) -> dict[str, Any]: ...


# Provider 函数类型：返回 HIL 管理器实例
HILManagerProvider = Callable[[], HILManagerProtocol]


class _NoopHILManager:
    """引擎独立运行时 HIL 不可用的空实现。

    所有 ``request_approval`` 直接返回 ``approved=True / status=skipped``，
    流水线不阻塞（与原 ``pipeline.py`` 中的内联 fallback 行为一致）。
    """

    enabled = False

    async def request_approval(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "approved": True,
            "status": "skipped",
            "comments": "HIL unavailable (engine standalone)",
        }


def _default_provider() -> HILManagerProtocol:
    """默认 provider：返回空实现（L0 独立运行时）。"""
    return _NoopHILManager()


# 模块级 provider 句柄（默认空实现；L3 启动时通过 set_hil_manager_provider 覆盖）
_provider: HILManagerProvider = _default_provider


def set_hil_manager_provider(provider: HILManagerProvider) -> None:
    """注入 HIL 管理器 provider（由 L3 启动时调用）。

    Args:
        provider: 零参函数，返回 HIL 管理器实例。
    """
    global _provider
    _provider = provider


def get_hil_manager() -> HILManagerProtocol:
    """获取 HIL 管理器（通过当前 provider）。

    Returns:
        HIL 管理器实例（默认为空实现，L3 注入后为真实管理器）。
    """
    return _provider()


__all__ = [
    "HILManagerProtocol",
    "HILManagerProvider",
    "set_hil_manager_provider",
    "get_hil_manager",
]
