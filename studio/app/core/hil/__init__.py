# -*- coding: utf-8 -*-
"""HIL（Human-In-The-Loop）人机协作模块。

提供人工审批检查点机制，在 Agent 流水线关键节点
（需求评审 / 契约评审 / 代码评审 / 最终评审）暂停流水线，
等待人工确认或拒绝，超时自动批准。

子模块：
- hil_manager：HIL 管理器，管理审批请求的创建、批准、拒绝与历史

模块导出：
- HILManager / ApprovalRequest / ApprovalResult / get_hil_manager

L0→L3 反向依赖修复：本模块加载时通过
``skyforge_engine.hil_provider.set_hil_manager_provider`` 把 L3 的
``get_hil_manager`` 注册为 L0 pipeline 的 HIL provider，使 L0 不再
反向 import L3。
"""

from app.core.hil.hil_manager import (
    ApprovalRequest,
    ApprovalResult,
    HILManager,
    get_hil_manager,
)
from skyforge_engine.hil_provider import set_hil_manager_provider

# 注册 L3 HIL 管理器为 L0 pipeline 的 HIL provider（覆盖 L0 默认的空实现）
set_hil_manager_provider(get_hil_manager)

__all__ = [
    "HILManager",
    "ApprovalRequest",
    "ApprovalResult",
    "get_hil_manager",
]
