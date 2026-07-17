"""DAL 自适应目标数据结构：定义 DO-178C 各 DAL 等级的目标清单与判定逻辑。

根据 DO-178C Table A-2 ~ A-7，不同安全等级的软件需要满足不同数量的目标。

目标映射（修正为 DO-178C 官方值，参考 DO-178C/ED-12C Table A-1）：
  DAL-A: 71 目标 — MC/DC + 独立验证 + 全部目标（灾难性失效）
  DAL-B: 69 目标 — Decision Coverage + 独立验证（危险/严重重大失效）
  DAL-C: 62 目标 — Statement Coverage（重大失效）
  DAL-D: 26 目标 — 基础验证（轻微失效）
  DAL-E: 0  目标 — 无特殊要求（无安全影响）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DAL(Enum):
    """Design Assurance Level — 软件安全等级。

    Attributes:
        A: 灾难性 (Catastrophic) — 失效导致机毁人亡。
        B: 危险 (Hazardous) — 失效导致严重伤害或飞机严重损坏。
        C: 重大 (Major) — 失效导致人员不适或飞机性能降低。
        D: 轻微 (Minor) — 失效导致轻微不便。
        E: 无影响 (No Effect) — 失效不影响安全。
    """

    A = "DAL-A"
    B = "DAL-B"
    C = "DAL-C"
    D = "DAL-D"
    E = "DAL-E"

    @classmethod
    def from_string(cls, value: str) -> "DAL":
        """从字符串解析 DAL 等级。

        支持格式: "DAL-A", "A", "a", "Level A", etc.
        """
        v = value.upper().strip()
        # 尝试直接匹配
        for level in cls:
            if v == level.value.upper():
                return level
            # 尝试匹配短名
            if v == level.name:
                return level
            # 尝试匹配 "DAL-A", "LEVEL A" 等变体
            if v.endswith(level.name):
                return level
        # 默认 DAL-C（最常用等级）
        return cls.C

    @property
    def objective_count(self) -> int:
        """该等级需要满足的目标总数。"""
        return DAL_OBJECTIVE_COUNTS.get(self, 0)

    @property
    def requires_mcdc(self) -> bool:
        """是否需要 MC/DC 覆盖。"""
        return self == DAL.A

    @property
    def requires_decision_coverage(self) -> bool:
        """是否需要判定覆盖。"""
        return self in (DAL.A, DAL.B)

    @property
    def requires_statement_coverage(self) -> bool:
        """是否需要语句覆盖。"""
        return self in (DAL.A, DAL.B, DAL.C)

    @property
    def requires_independent_verification(self) -> bool:
        """是否需要独立验证。"""
        return self in (DAL.A, DAL.B)


# DAL 等级 → 目标总数映射
# DAL 等级 → 目标总数映射（DO-178C 官方值，多源交叉校验）
# 来源: DO-178C/ED-12C Annex A / legalclarity.org / do178.org / Wikipedia
DAL_OBJECTIVE_COUNTS: dict[DAL, int] = {
    DAL.A: 71,  # 灾难性 — 最高严格度
    DAL.B: 69,  # 危险/严重重大
    DAL.C: 62,  # 重大
    DAL.D: 26,  # 轻微
    DAL.E: 0,   # 无影响
}

# DAL 等级 → 需独立验证目标数（多源交叉校验）
DAL_INDEPENDENCE_COUNTS: dict[DAL, int] = {
    DAL.A: 30,  # 30 项目标需独立验证
    DAL.B: 18,
    DAL.C: 5,
    DAL.D: 2,
    DAL.E: 0,
}


# DAL 等级 → 适用目标 ID 列表
DAL_OBJECTIVE_IDS: dict[DAL, list[str]] = {
    DAL.A: [
        "OBJ-1", "OBJ-2", "OBJ-3", "OBJ-4", "OBJ-5", "OBJ-6",
        "OBJ-7", "OBJ-8", "OBJ-9", "OBJ-10", "OBJ-11", "OBJ-12",
        "OBJ-13", "OBJ-14", "OBJ-15", "OBJ-16", "OBJ-17", "OBJ-18", "OBJ-19",
    ],
    DAL.B: [
        "OBJ-1", "OBJ-2", "OBJ-3", "OBJ-4", "OBJ-5", "OBJ-6",
        "OBJ-7", "OBJ-8", "OBJ-9", "OBJ-10", "OBJ-11", "OBJ-12",
        "OBJ-13", "OBJ-14", "OBJ-16", "OBJ-17", "OBJ-18",
    ],
    DAL.C: [
        "OBJ-1", "OBJ-2", "OBJ-3", "OBJ-4", "OBJ-5", "OBJ-6",
        "OBJ-7", "OBJ-8", "OBJ-9", "OBJ-10", "OBJ-11", "OBJ-12",
        "OBJ-13", "OBJ-16", "OBJ-18",
    ],
    DAL.D: [
        "OBJ-1", "OBJ-2", "OBJ-3", "OBJ-5", "OBJ-7",
        "OBJ-8", "OBJ-9", "OBJ-11", "OBJ-13", "OBJ-16", "OBJ-18",
    ],
    DAL.E: [],
}


@dataclass
class DALObjectiveDefinition:
    """DO-178C 单项目标定义。

    Attributes:
        obj_id: 目标 ID（如 OBJ-1）。
        name: 目标名称。
        description: 目标描述。
        do178_table: 引用的 DO-178C 附录表。
        applicable_dals: 适用的 DAL 等级集合。
    """

    obj_id: str
    name: str
    description: str
    do178_table: str = ""
    applicable_dals: set[DAL] = field(default_factory=lambda: set(DAL))


# 全部 19 项目标定义
ALL_OBJECTIVES: list[DALObjectiveDefinition] = [
    DALObjectiveDefinition(
        obj_id="OBJ-1",
        name="需求可追溯性",
        description="高级需求到低级需求、代码、测试的可追溯链完整",
        do178_table="A-7.6",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-2",
        name="契约式设计验证",
        description="前置/后置/不变式/故障处理契约均被验证",
        do178_table="A-3.1",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-3",
        name="源代码合规性",
        description="MISRA-C:2012 强制规则无残留违规",
        do178_table="A-5.1",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-4",
        name="静态分析",
        description="Cppcheck --addon=misra 已执行",
        do178_table="A-5.2",
        applicable_dals={DAL.A, DAL.B, DAL.C},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-5",
        name="仿真测试覆盖",
        description="数字孪生仿真步数 >= 100",
        do178_table="A-6.2",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-6",
        name="故障注入测试",
        description="数字孪生仿真含故障注入场景",
        do178_table="A-6.6",
        applicable_dals={DAL.A, DAL.B, DAL.C},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-7",
        name="代码审查",
        description="代码修复历史完整，每处违规均有修复动作",
        do178_table="A-7.1",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-8",
        name="配置管理",
        description="软件版本号可追溯",
        do178_table="A-8.1",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-9",
        name="问题报告",
        description="违规与修复历史均被记录可查",
        do178_table="A-8.3",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-10",
        name="独立性",
        description="AI 生成 + 自动化验证双重独立",
        do178_table="A-9.1",
        applicable_dals={DAL.A, DAL.B, DAL.C},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-11",
        name="编译验证",
        description="C 代码经 GCC 真实编译通过",
        do178_table="A-5.3",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-12",
        name="契约违约处理",
        description="数字孪生仿真契约断言被注入并可触发违约检测",
        do178_table="—",
        applicable_dals={DAL.A, DAL.B, DAL.C},
    ),
    # ---- Phase 3 新增 ----
    DALObjectiveDefinition(
        obj_id="OBJ-13",
        name="语句覆盖率",
        description="语句覆盖率 100%",
        do178_table="A-7.5",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-14",
        name="判定覆盖率",
        description="判定覆盖率 100%",
        do178_table="A-7.7",
        applicable_dals={DAL.A, DAL.B},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-15",
        name="MC/DC 覆盖率",
        description="MC/DC 覆盖率 100%",
        do178_table="A-7.8",
        applicable_dals={DAL.A},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-16",
        name="HLR/LLR 追溯",
        description="高层需求到低层需求双向追溯",
        do178_table="A-2.1",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-17",
        name="独立验证",
        description="验证由独立于开发的人员执行",
        do178_table="A-9.2",
        applicable_dals={DAL.A, DAL.B},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-18",
        name="正式 PR 系统",
        description="问题报告通过正式 PR 系统管理",
        do178_table="A-8.2",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
    DALObjectiveDefinition(
        obj_id="OBJ-19",
        name="工具鉴定",
        description="开发工具经鉴定满足 DO-330 要求",
        do178_table="§12.2",
        applicable_dals={DAL.A, DAL.B, DAL.C, DAL.D},
    ),
]


def get_objectives_for_dal(dal: DAL) -> list[DALObjectiveDefinition]:
    """根据 DAL 等级返回适用的目标清单。

    Args:
        dal: 软件安全等级。

    Returns:
        适用的目标定义列表。
    """
    applicable_ids = DAL_OBJECTIVE_IDS.get(dal, [])
    obj_map = {o.obj_id: o for o in ALL_OBJECTIVES}
    return [obj_map[oid] for oid in applicable_ids if oid in obj_map]
