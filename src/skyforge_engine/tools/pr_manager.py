"""正式问题报告管理系统（Problem Report Manager）。

根据 DO-178C Table A-8.2/A-8.3，所有验证活动中发现的问题必须通过正式
PR 系统记录、追踪和关闭。

PR 生命周期:
  open → in_progress → resolved → closed
   (可驳回)  ←   ←   ←

字段设计:
  - pr_id: 唯一标识 PR-YYYY-NNNN（年度编号）
  - severity: critical / major / minor
  - source: cppcheck / contract_check / simulation / manual_review
  - status: 状态流转
  - verified_by: 验证人（满足 DO-178C 独立性要求）
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from skyforge_engine.utils.log_util import logger


class PRSeverity(Enum):
    """问题严重级别。"""

    CRITICAL = "critical"  # 工具无法运行 / 安全漏洞
    MAJOR = "major"        # 核心功能异常
    MINOR = "minor"        # 非核心功能异常


class PRStatus(Enum):
    """问题报告状态。"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class PRSource(Enum):
    """问题来源。"""

    CPPCHECK = "cppcheck"
    CONTRACT_CHECK = "contract_check"
    SIMULATION = "simulation"
    MANUAL_REVIEW = "manual_review"
    COVERAGE = "coverage"  # Phase 3 新增


# 状态流转规则
_VALID_TRANSITIONS: dict[PRStatus, set[PRStatus]] = {
    PRStatus.OPEN: {PRStatus.IN_PROGRESS},
    PRStatus.IN_PROGRESS: {PRStatus.RESOLVED, PRStatus.OPEN},
    PRStatus.RESOLVED: {PRStatus.CLOSED, PRStatus.IN_PROGRESS},
    PRStatus.CLOSED: {PRStatus.OPEN},  # 重新打开
}


@dataclass
class ProblemReport:
    """DO-178C 正式问题报告。

    Attributes:
        pr_id: 唯一标识（PR-YYYY-NNNN）。
        severity: 严重级别。
        source: 问题来源。
        rule_id: MISRA-C 规则 ID 或契约 ID。
        location: 问题位置（文件名:行号）。
        description: 问题描述。
        status: 当前状态。
        resolution: 解决方案描述。
        verified_by: 验证人/工具。
        created_at: 创建时间戳。
        updated_at: 更新时间戳。
    """

    pr_id: str = ""
    severity: str = ""
    source: str = ""
    rule_id: str = ""
    location: str = ""
    description: str = ""
    status: str = "open"
    resolution: str = ""
    verified_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    def transition_to(self, new_status: str) -> bool:
        """尝试状态流转。

        Args:
            new_status: 目标状态。

        Returns:
            True 如果流转成功。
        """
        current = PRStatus(self.status)
        try:
            target = PRStatus(new_status)
        except ValueError:
            logger.warning(f"PRManager:无效状态: {new_status}")
            return False

        if target not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(
                f"PRManager:状态流转拒绝: {self.pr_id} "
                f"{self.status} → {new_status}"
            )
            return False

        self.status = new_status
        self.updated_at = datetime.now().isoformat()
        logger.info(
            f"PRManager:状态流转完成: {self.pr_id} "
            f"{current.value} → {new_status}"
        )
        return True

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


class PRManager:
    """问题报告管理器。

    使用方式::

        manager = PRManager()
        pr = manager.create_report(
            severity="major",
            source="cppcheck",
            rule_id="MISRA-C:2012-Rule-8.13",
            location="filter.c:24",
            description="指针参数未声明为 const",
        )
        manager.resolve(pr.pr_id, "已添加 const 修饰符")
        manager.close(pr.pr_id, verified_by="HIL Reviewer")
    """

    def __init__(self) -> None:
        # 年度计数器: {year: counter}
        self._counters: dict[int, int] = {}
        # PR 存储: {pr_id: ProblemReport}
        self._reports: dict[str, ProblemReport] = {}
        # 初始化当年计数器
        current_year = datetime.now().year
        self._counters[current_year] = 0

    def create_report(
        self,
        description: str,
        severity: str = "minor",
        source: str = "manual_review",
        rule_id: str = "",
        location: str = "",
    ) -> ProblemReport:
        """创建新的问题报告。

        Args:
            description: 问题描述。
            severity: 严重级别。
            source: 问题来源。
            rule_id: 相关规则 ID。
            location: 问题位置。

        Returns:
            新的 ProblemReport 实例。
        """
        year = datetime.now().year
        if year not in self._counters:
            self._counters[year] = 0
        self._counters[year] += 1
        pr_id = f"PR-{year}-{self._counters[year]:04d}"

        now = datetime.now().isoformat()
        pr = ProblemReport(
            pr_id=pr_id,
            severity=severity,
            source=source,
            rule_id=rule_id,
            location=location,
            description=description,
            status="open",
            created_at=now,
            updated_at=now,
        )
        self._reports[pr_id] = pr
        logger.info(f"PRManager:创建报告: {pr_id} [{severity}] {description[:80]}")
        return pr

    def get_report(self, pr_id: str) -> ProblemReport | None:
        """获取问题报告。"""
        return self._reports.get(pr_id)

    def resolve(self, pr_id: str, resolution: str) -> bool:
        """标记问题为已解决。

        Args:
            pr_id: 问题 ID。
            resolution: 解决方案描述。

        Returns:
            True 如果操作成功。
        """
        pr = self._reports.get(pr_id)
        if pr is None:
            logger.warning(f"PRManager:报告不存在: {pr_id}")
            return False
        if not pr.transition_to("resolved"):
            return False
        pr.resolution = resolution
        return True

    def close(self, pr_id: str, verified_by: str = "") -> bool:
        """关闭问题报告（验证后关闭）。

        Args:
            pr_id: 问题 ID。
            verified_by: 验证人。

        Returns:
            True 如果操作成功。
        """
        pr = self._reports.get(pr_id)
        if pr is None:
            return False
        if not pr.transition_to("closed"):
            return False
        pr.verified_by = verified_by
        return True

    def reopen(self, pr_id: str, reason: str = "") -> bool:
        """重新打开已关闭的问题。

        Args:
            pr_id: 问题 ID。
            reason: 重新打开原因。

        Returns:
            True 如果操作成功。
        """
        pr = self._reports.get(pr_id)
        if pr is None:
            return False
        if not pr.transition_to("open"):
            return False
        pr.description += f" [重新打开: {reason}]" if reason else " [重新打开]"
        return True

    def list_by_status(self, status: str) -> list[ProblemReport]:
        """按状态列出问题报告。"""
        return [pr for pr in self._reports.values() if pr.status == status]

    def list_all(self) -> list[ProblemReport]:
        """列出所有问题报告。"""
        return list(self._reports.values())

    def get_statistics(self) -> dict[str, int]:
        """获取问题统计。

        Returns:
            {"open": N, "in_progress": N, "resolved": N, "closed": N, "total": N}
        """
        stats = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0, "total": 0}
        for pr in self._reports.values():
            stats[pr.status] = stats.get(pr.status, 0) + 1
            stats["total"] += 1
        return stats

    def to_list(self) -> list[dict[str, Any]]:
        """转为问题报告列表（用于注入 pipeline_result）。"""
        return [pr.to_dict() for pr in self._reports.values()]


# 全局单例（模块级别，支持跨 pipeline 调用共享状态）
_pr_manager: PRManager | None = None


def get_pr_manager() -> PRManager:
    """获取全局 PRManager 实例。"""
    global _pr_manager
    if _pr_manager is None:
        _pr_manager = PRManager()
    return _pr_manager


def create_pr_from_violation(
    violation: dict[str, Any],
    source: str = "cppcheck",
) -> ProblemReport:
    """从违规记录创建问题报告。

    Args:
        violation: 违规字典，含 rule_id / line / description 等字段。
        source: 问题来源。

    Returns:
        ProblemReport 实例。
    """
    manager = get_pr_manager()
    return manager.create_report(
        description=str(violation.get("description", violation.get("message", ""))),
        severity="major",
        source=source,
        rule_id=str(violation.get("rule_id", "")),
        location=f"code.c:{violation.get('line', '?')}",
    )
