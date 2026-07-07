"""Agent 共享类型定义。

避免 Agent 模块间的循环导入：当多个 Agent 文件需要共享数据类时，
统一在此模块定义，各自从这里导入。
"""

from dataclasses import dataclass


@dataclass
class RepairAction:
    """单条修复动作记录（用于追溯链 + Patch 4 流式推送）。"""

    rule_id: str
    line: int
    description: str
    req_id: str = "REQ-001"
    before: str = ""
    after: str = ""
