"""组件可组合性验证（DO-178C 次级功能）。

参考设计文档第 6.5 节"可组合性验证"：
契约式设计的一个核心价值是"组件可组合性"——多个组件组合后，
契约仍然满足。本模块提供三类组合（顺序 / 并行 / 反馈）的代码拼接、
契约兼容性检查与组合后仿真验证。

子模块：
- compatibility_checker：契约兼容性检查器（A.postconditions → B.preconditions）
- component_combinator：组件组合器（生成组合后的 C 代码 + 组合契约）
- composition_simulator：组合仿真验证（复用 Day 3 SimulationEngine）

模块导出：
- compose / ComponentCombinator / CompositionResult
- check_compatibility / CompatibilityChecker / CompatibilityResult
- simulate_composition / CompositionSimulator
"""

from app.core.composable.compatibility_checker import (
    CheckedPair,
    CompatibilityChecker,
    CompatibilityResult,
    check_compatibility,
)
from app.core.composable.component_combinator import (
    ComponentCombinator,
    CompositionResult,
    compose,
)
from app.core.composable.composition_simulator import (
    CompositionSimulator,
    simulate_composition,
)

__all__ = [
    # 组件组合器
    "ComponentCombinator",
    "CompositionResult",
    "compose",
    # 兼容性检查器
    "CompatibilityChecker",
    "CompatibilityResult",
    "CheckedPair",
    "check_compatibility",
    # 组合仿真器
    "CompositionSimulator",
    "simulate_composition",
]
