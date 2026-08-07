"""HITL（人在回路）审查数据模型。

定义审查模板、审查意见、审查统计等数据结构。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewTemplateItem(BaseModel):
    """单个审查项。"""

    id: str = Field(description="审查项唯一标识")
    title: str = Field(description="审查项标题")
    description: str = Field(default="", description="审查项详细描述")
    category: str = Field(default="general", description="分类：mandatory/required/advisory/general")
    guideline_ref: str = Field(default="", description="参考标准条款，如 DO-178C/PSAC.01")


class ReviewTemplate(BaseModel):
    """审查模板：某类检查点的标准审查项集合。"""

    checkpoint: str = Field(description="检查点类型：requirement_review / contract_review / code_review / final_review")
    items: list[ReviewTemplateItem] = Field(default_factory=list)
    version: str = Field(default="1.0", description="模板版本")


class ReviewComment(BaseModel):
    """单条审查意见。"""

    id: str = Field(description="意见唯一标识")
    item_id: str = Field(default="", description="关联的审查项ID（可选）")
    content: str = Field(description="意见内容")
    author: str = Field(default="reviewer", description="意见提交者")
    status: str = Field(default="open", description="状态：open / addressed / resolved")
    code_ref: str = Field(default="", description="关联的代码引用，如 file.c:42")
    contract_ref: str = Field(default="", description="关联的契约条件引用")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReviewCommentsBundle(BaseModel):
    """某审批请求的所有意见。"""

    request_id: str = Field(description="审批请求ID")
    comments: list[ReviewComment] = Field(default_factory=list)


class HITLStats(BaseModel):
    """HITL 审查统计指标。"""

    total_requests: int = Field(default=0, description="总审批请求数")
    pending_count: int = Field(default=0, description="待审批数")
    approved_count: int = Field(default=0, description="已通过数")
    rejected_count: int = Field(default=0, description="已拒绝数")
    timeout_count: int = Field(default=0, description="超时自动批准数")
    approval_rate: float = Field(default=0.0, description="通过率（0-100）")
    avg_review_time_sec: float = Field(default=0.0, description="平均审查时间（秒）")
    by_checkpoint: dict[str, dict[str, int]] = Field(default_factory=dict, description="按检查点分类的统计")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
