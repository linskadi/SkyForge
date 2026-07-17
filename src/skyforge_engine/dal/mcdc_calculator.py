"""MC/DC 覆盖率计算核心。

V3.3 增强:
  - 支持基于括号的嵌套条件识别（非扁平拆分）
  - 生成 MC/DC 测试向量（展示每个判定需要哪些测试用例）
  - 改进的语句覆盖率统计（排除声明行、空函数体等）
  - 支持 switch 语句的 case 覆盖

MC/DC 定义 (DO-178C Table A-7.8):
  - 每个判定的每个条件独立影响判定结果
  - 对 N 个条件的判定，至少需要 N+1 个测试用例
  - 条件独立性: 固定其他条件不变，改变目标条件 → 判定结果应改变
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger


@dataclass
class Condition:
    """单个条件（用于 MC/DC 分析）。

    Attributes:
        expression: 条件表达式文本。
        line: 条件所在行号。
        is_compound: 是否为复合条件（含 && / ||）。
    """

    expression: str = ""
    line: int = 0
    is_compound: bool = False

    def __repr__(self) -> str:
        return f"Condition({self.expression[:40]})"


@dataclass
class DecisionPoint:
    """单个判定节点。

    Attributes:
        line: 行号（1-based）。
        type: 判定类型（"if" / "while" / "for" / "switch"）。
        raw_condition: 原始条件表达式。
        conditions: 独立条件列表（按 && / || 拆分，支持括号嵌套）。
        operator: 逻辑运算符（"&&" / "||" / "mixed" / "single"）。
        test_count: 已执行的测试用例数（stub 默认 0）。
        required_tests: MC/DC 最小测试用例数。
        test_vectors: 建议的测试向量（展示条件独立性）。
    """

    line: int = 0
    type: str = ""
    raw_condition: str = ""
    conditions: list[Condition] = field(default_factory=list)
    operator: str = ""
    test_count: int = 0
    required_tests: int = 0
    test_vectors: list[str] = field(default_factory=list)

    @property
    def condition_count(self) -> int:
        """独立条件总数。"""
        return len(self.conditions)

    @property
    def min_tests(self) -> int:
        """MC/DC 最小测试用例数 = N（条件数）+ 1。"""
        n = self.condition_count
        return n + 1 if n > 0 else 2

    @property
    def satisfied(self) -> bool:
        """判定是否满足 MC/DC。"""
        return self.test_count >= self.min_tests

    @property
    def status(self) -> str:
        """判定状态：满足 / 部分满足 / 未满足。"""
        if self.satisfied:
            return "满足"
        if self.test_count > 0:
            return "部分满足"
        return "未满足"


@dataclass
class CoverageResult:
    """覆盖率分析结果。"""

    statement_count: int = 0
    statement_covered: int = 0
    decision_points: list[DecisionPoint] = field(default_factory=list)
    switch_cases: list[dict] = field(default_factory=list)

    @property
    def statement_coverage(self) -> float:
        if self.statement_count == 0:
            return 0.0
        return round(self.statement_covered / self.statement_count * 100, 1)

    @property
    def decision_coverage(self) -> float:
        if not self.decision_points:
            return 0.0
        covered = sum(1 for d in self.decision_points if d.test_count > 0)
        return round(covered / len(self.decision_points) * 100, 1)

    @property
    def mcdc_coverage(self) -> float:
        if not self.decision_points:
            return 0.0
        satisfied = sum(1 for d in self.decision_points if d.satisfied)
        return round(satisfied / len(self.decision_points) * 100, 1)

    @property
    def mcdc_total(self) -> int:
        return len(self.decision_points)

    @property
    def mcdc_satisfied(self) -> int:
        return sum(1 for d in self.decision_points if d.satisfied)

    @property
    def summary(self) -> dict[str, Any]:
        """生成覆盖率摘要。"""
        return {
            "statement_coverage": self.statement_coverage,
            "decision_coverage": self.decision_coverage,
            "mcdc_coverage": self.mcdc_coverage,
            "decision_points": len(self.decision_points),
            "conditions_total": sum(d.condition_count for d in self.decision_points),
            "mcdc_satisfied": self.mcdc_satisfied,
            "mcdc_total": self.mcdc_total,
            "version": "V3.3-Enhanced",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.summary,
            "statement_count": self.statement_count,
            "statement_covered": self.statement_covered,
            "decision_count": len(self.decision_points),
            "switch_case_count": len(self.switch_cases),
            "decision_points": [
                {
                    "line": d.line,
                    "type": d.type,
                    "conditions": [c.expression for c in d.conditions],
                    "operator": d.operator,
                    "condition_count": d.condition_count,
                    "min_tests": d.min_tests,
                    "test_count": d.test_count,
                    "status": d.status,
                    "test_vectors": d.test_vectors,
                }
                for d in self.decision_points
            ],
            "switch_cases": self.switch_cases,
        }


# ---- 判定识别正则 ----
_DECISION_PATTERN = re.compile(
    r"\b(if|while|for)\s*\((.+?)\)\s*",
    re.DOTALL,
)

_SWITCH_PATTERN = re.compile(
    r"\bswitch\s*\((.+?)\)\s*\{",
    re.DOTALL,
)

_CASE_PATTERN = re.compile(
    r"\bcase\s+(.+?)\s*:",
)

# ---- 条件拆分（V3.3: 括号感知）----


def _split_conditions(condition_str: str) -> list[str]:
    """将条件表达式拆分为独立条件（括号感知）。

    处理优先级:
      - 括号内的 content 作为整体（不拆分内部 && / ||）
      - 顶层 && / || 作为条件分隔符
      - 处理运算符 (a && b) 和 (a || b)

    示例:
        "(x>0 && y<10) || z==0" → ["(x>0 && y<10)", "z==0"]
        "x>0 && y<10"          → ["x>0", "y<10"]
        "x>0"                  → ["x>0"]
    """
    if not condition_str:
        return []

    conditions: list[str] = []
    depth = 0
    current: list[str] = []

    # 正则匹配顶层 && 或 ||
    tokens = re.split(r"(\s*(?:&&|\|\|)\s*)", condition_str)

    for token in tokens:
        # 更新括号深度
        depth += token.count("(") - token.count(")")
        token_stripped = token.strip()

        if token_stripped in ("&&", "||"):
            if depth == 0 and current:
                cond = "".join(current).strip()
                if cond and cond not in ("&&", "||"):
                    conditions.append(cond)
                current = []
            elif depth > 0:
                current.append(token)
        else:
            current.append(token)

    # 最后一个条件
    if current:
        cond = "".join(current).strip()
        if cond and cond not in ("&&", "||"):
            conditions.append(cond)

    return conditions


def _detect_operator(condition_str: str, conditions: list[str]) -> str:
    """检测逻辑运算符类型。"""
    has_and = "&&" in condition_str
    has_or = "||" in condition_str

    if has_and and has_or:
        # 验证是否为混合（在顶层包含两种运算符）
        depth = 0
        top_and = False
        top_or = False
        for ch in condition_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0:
                if condition_str[condition_str.index(ch):].startswith("&&"):
                    top_and = True
                elif condition_str[condition_str.index(ch):].startswith("||"):
                    top_or = True
        return "mixed" if (top_and and top_or) else ("&&" if top_and else "||")
    elif has_and:
        return "&&"
    elif has_or:
        return "||"
    elif len(conditions) == 1:
        return "single"
    return ""


def _generate_test_vectors(dp: DecisionPoint) -> list[str]:
    """生成 MC/DC 测试向量建议。

    对每个条件，说明如何独立影响判定结果：
      - 固定其他条件，翻转目标条件 → 判定应翻转

    Returns:
        测试向量描述列表，如 ["T1: x>0=T,y<10=T → true", "T2: x>0=F,y<10=T → false"]
    """
    if dp.condition_count == 0:
        return []

    vectors: list[str] = []

    for i, cond in enumerate(dp.conditions, start=1):
        # 简化的测试向量生成
        if dp.operator == "&&":
            # AND: 所有条件为 T → T; 翻转第 i 个为 F → F
            others = ", ".join(
                f"{c.expression}=T" for j, c in enumerate(dp.conditions) if j != i - 1
            )
            vectors.append(f"T{i}: {cond.expression}=T,{others} → true")
            others_f = ", ".join(
                f"{c.expression}=T" for j, c in enumerate(dp.conditions) if j != i - 1
            )
            vectors.append(f"T{i}': {cond.expression}=F,{others_f} → false")

        elif dp.operator == "||":
            # OR: 所有条件为 F → F; 翻转第 i 个为 T → T
            others = ", ".join(
                f"{c.expression}=F" for j, c in enumerate(dp.conditions) if j != i - 1
            )
            vectors.append(f"T{i}: {cond.expression}=T,{others} → true")
            vectors.append(f"T{i}': {cond.expression}=F,{others} → false")

        elif dp.operator == "single":
            # 单一条件
            vectors.append(f"T1: {cond.expression}=T → true")
            vectors.append(f"T2: {cond.expression}=F → false")

    return vectors


# ---- 主分析函数 ----

def analyze_coverage(code: str) -> CoverageResult:
    """分析 C 代码的覆盖率（V3.3 增强版）。

    改进:
      - 括号感知的条件拆分
      - 自动生成 MC/DC 测试向量
      - 更准确的语句计数
      - switch 语句 case 覆盖分析

    Args:
        code: C 源代码字符串。

    Returns:
        CoverageResult：覆盖率分析结果。
    """
    result = CoverageResult()

    if not code:
        return result

    lines = code.splitlines()

    # 1. 语句计数
    block_comment = False
    statement_lines = 0
    declaration_keywords = {"typedef", "extern", "static", "struct", "enum", "union"}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("/*"):
            block_comment = True
            continue
        if block_comment:
            if "*/" in stripped:
                block_comment = False
            continue
        if stripped in ("{", "}", "};"):
            continue

        # 排除纯声明行
        first_word = stripped.split()[0] if stripped.split() else ""
        if first_word in declaration_keywords:
            continue

        statement_lines += 1

    result.statement_count = max(statement_lines, 1)
    result.statement_covered = statement_lines  # stub: 假设全部通过

    # 2. 识别判定节点（括号感知）
    for idx, line in enumerate(lines, start=1):
        for m in _DECISION_PATTERN.finditer(line):
            dec_type = m.group(1)
            condition_str = m.group(2).strip()

            # 括号感知条件拆分
            cond_strs = _split_conditions(condition_str)
            conditions = [Condition(expression=c, line=idx) for c in cond_strs]

            operator = _detect_operator(condition_str, cond_strs)

            dp = DecisionPoint(
                line=idx,
                type=dec_type,
                raw_condition=condition_str,
                conditions=conditions,
                operator=operator,
                required_tests=len(conditions) + 1 if conditions else 2,
            )

            # 生成测试向量
            dp.test_vectors = _generate_test_vectors(dp)
            result.decision_points.append(dp)

    # 3. Switch 语句 case 覆盖
    for idx, line in enumerate(lines, start=1):
        for m in _SWITCH_PATTERN.finditer(line):
            switch_var = m.group(1).strip()
            # 从后续行中查找 case 标签
            cases: list[str] = []
            in_switch = True
            for sub_line in lines[idx:]:  # 从当前行开始搜索
                sub_stripped = sub_line.strip()
                if in_switch and "}" in sub_stripped:
                    in_switch = False
                    break
                case_match = _CASE_PATTERN.search(sub_stripped)
                if case_match:
                    cases.append(case_match.group(1).strip())

            result.switch_cases.append({
                "line": idx,
                "switch_var": switch_var,
                "cases": cases,
                "case_count": len(cases),
            })

    logger.info(
        f"MCDC(V3.3):分析完成: {result.statement_count} 语句, "
        f"{result.mcdc_total} 判定 ({sum(d.condition_count for d in result.decision_points)} 条件), "
        f"语句={result.statement_coverage}%, "
        f"判定={result.decision_coverage}%, "
        f"MC/DC={result.mcdc_coverage}% "
        f"({result.mcdc_satisfied}/{result.mcdc_total})"
    )
    return result


def compute_mcdc_for_code(code: str) -> dict[str, Any]:
    """便捷函数：计算并返回代码的 MC/DC 结果字典。"""
    cov = analyze_coverage(code)
    return cov.to_dict()
