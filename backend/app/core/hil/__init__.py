# -*- coding: utf-8 -*-
"""HIL（Human-In-The-Loop）人机协作模块。

提供人工审批检查点机制，在 Agent 流水线关键节点
（需求评审 / 契约评审 / 代码评审 / 最终评审）暂停流水线，
等待人工确认或拒绝，超时自动批准。

子模块：
- hil_manager：HIL 管理器，管理审批请求的创建、批准、拒绝与历史

模块导出：
- HILManager / ApprovalRequest / ApprovalResult / get_hil_manager
"""

from app.core.hil.hil_manager import (
    ApprovalRequest,
    ApprovalResult,
    HILManager,
    get_hil_manager,
)

__all__ = [
    "HILManager",
    "ApprovalRequest",
    "ApprovalResult",
    "get_hil_manager",
]
