"""证据链追溯数据模型。

定义航空软件生成过程中产物间的追溯关系，
支持需求→契约→代码→验证→证据的完整链路追溯。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProvenanceNode(BaseModel):
    """追溯链节点：单个产物的追溯信息。"""

    id: str = Field(description="节点唯一标识（如 req_001 / contract_001 / code_hash）")
    type: str = Field(description="节点类型：requirement / contract / code / verification / evidence")
    description: str = Field(default="", description="节点描述")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class EvidenceChain(BaseModel):
    """完整证据链：从需求到证据的追溯链路。"""

    task_id: str = Field(description="关联的任务ID")
    nodes: list[ProvenanceNode] = Field(default_factory=list, description="追溯链上的所有节点")
    edges: list[tuple[str, str]] = Field(default_factory=list, description="节点间的有向边 (from_id, to_id)")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def add_node(self, node: ProvenanceNode) -> None:
        """添加一个追溯节点。"""
        self.nodes.append(node)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """添加一条有向追溯关系。"""
        self.edges.append((from_id, to_id))


class DO178CObjective(BaseModel):
    """DO-178C 单个目标的映射状态。"""

    objective_id: str = Field(description="目标编号，如 PSAC.01.01")
    objective_name: str = Field(description="目标名称")
    category: str = Field(description="类别：PSAC / SDP / SVP 等")
    status: str = Field(default="not_met", description="状态：met / partially_met / not_met")
    evidence_refs: list[str] = Field(default_factory=list, description="关联的证据节点ID")
    notes: str = Field(default="", description="备注")


class DO178CMapping(BaseModel):
    """DO-178C 目标矩阵映射。"""

    task_id: str = Field(description="关联的任务ID")
    objectives: list[DO178CObjective] = Field(default_factory=list)
    summary: dict[str, int] = Field(
        default_factory=lambda: {"met": 0, "partially_met": 0, "not_met": 0, "total": 0}
    )
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
