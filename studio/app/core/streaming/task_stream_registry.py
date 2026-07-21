# -*- coding: utf-8 -*-
"""L3 兼容 shim：转发到 L0 ``skyforge_engine.streaming.task_stream_registry``。

历史上下文：本模块原为 L3 实现（依赖 ``fastapi.WebSocket`` 类型）。
2026-07 L0/L3 分层重构时，将纯逻辑部分提升到 L0
（``src/skyforge_engine/streaming/task_stream_registry.py``），
L0 用 ``WebSocketProtocol`` (Protocol) 替代 ``fastapi.WebSocket`` 类型注解，
从而不硬依赖 fastapi。

本文件保留 ``app.core.streaming.task_stream_registry`` 导入路径，
保证既有 L3 代码（``from app.core.streaming.task_stream_registry import ...``）
无需修改。

模块属性（含私有常量 ``_TASK_HISTORY_TTL_SEC`` / ``_MAX_HISTORY_PER_TASK`` 与
单例 ``_task_stream_registry``）的读写通过自定义 ``__class__`` 透明转发到 L0
模块，使测试的 monkey-patch（如 ``tsr_module._TASK_HISTORY_TTL_SEC = 0.1``）
能影响 L0 实际逻辑。
"""

import sys
import types

from skyforge_engine.streaming.task_stream_registry import (  # noqa: F401
    TaskStreamRegistry,
    WebSocketProtocol,
    get_task_stream_registry,
)

_L0_MODULE_PATH = "skyforge_engine.streaming.task_stream_registry"


class _ForwardingModule(types.ModuleType):
    """把本 shim 模块的属性读写转发到 L0 模块。

    - ``__getattr__``：本 shim 未定义的属性（如 ``_TASK_HISTORY_TTL_SEC``、
      ``_MAX_HISTORY_PER_TASK``、``_task_stream_registry``）回退到 L0 模块读取
    - ``__setattr__``：写入属性时同步到 L0 模块，使测试 monkey-patch 能影响
      L0 的实际逻辑（L0 代码通过模块全局名读取这些常量/单例）
    """

    def __getattr__(self, name):
        l0_mod = sys.modules.get(_L0_MODULE_PATH)
        if l0_mod is not None and hasattr(l0_mod, name):
            return getattr(l0_mod, name)
        raise AttributeError(
            f"module {self.__name__!r} has no attribute {name!r}"
        )

    def __setattr__(self, name, value):
        l0_mod = sys.modules.get(_L0_MODULE_PATH)
        if l0_mod is not None:
            setattr(l0_mod, name, value)
        super().__setattr__(name, value)


# 把本模块的 __class__ 替换为转发类（必须在所有 import 语句之后执行）
sys.modules[__name__].__class__ = _ForwardingModule

__all__ = [
    "TaskStreamRegistry",
    "WebSocketProtocol",
    "get_task_stream_registry",
]
