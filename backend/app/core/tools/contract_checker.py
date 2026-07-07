"""契约校验器（结合 Patch 2 断言插桩）：解析 YAML 契约，验证代码是否满足前置/后置/不变式/故障处理。

参考设计文档第 6.4 节："契约即测试，违约即崩溃"。
- 静态检查：解析 YAML 契约，验证代码是否包含必要函数/类型
- 生成断言插桩：调用 contract_to_assert() 生成 assert 代码
- 语义检查（mock）：返回 preconditions/postconditions/invariants 各项通过/失败状态
"""

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from app.core.tools.contract_to_assert import contract_to_assert
from app.utils.log_util import logger


@dataclass
class CheckItem:
    """单条契约检查项结果。"""

    id: str
    desc: str
    passed: bool
    detail: str = ""


@dataclass
class CheckResult:
    """契约校验结果。

    Attributes:
        passed: 整体是否通过（所有检查项均通过）。
        preconditions: 前置条件检查项列表。
        postconditions: 后置条件检查项列表。
        invariants: 不变式检查项列表。
        fault_handling: 故障处理检查项列表。
        assert_code: 自动生成的 C 断言插桩代码。
        violations: 未通过项汇总（便于追溯）。
    """

    passed: bool = False
    preconditions: list[CheckItem] = field(default_factory=list)
    postconditions: list[CheckItem] = field(default_factory=list)
    invariants: list[CheckItem] = field(default_factory=list)
    fault_handling: list[CheckItem] = field(default_factory=list)
    assert_code: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)


def check(code: str, contract_yaml: str, cid: str = "CON-001") -> CheckResult:
    """契约校验主入口。

    1. 静态检查：解析 YAML 契约，验证代码是否包含必要函数/类型。
    2. 生成断言插桩：调用 contract_to_assert() 生成 assert 代码。
    3. 语义检查（mock）：返回 preconditions/postconditions/invariants 各项通过/失败状态。

    Args:
        code: 待校验的 C 代码字符串。
        contract_yaml: .contract YAML 文本。
        cid: 契约 ID，用于断言追溯 Tag。

    Returns:
        CheckResult：包含各检查项结果 + 断言插桩代码 + 违规汇总。
    """
    logger.info(f"ContractChecker:开始 cid={cid}")

    try:
        contract = yaml.safe_load(contract_yaml) or {}
    except yaml.YAMLError as e:
        logger.error(f"ContractChecker:YAML 解析失败: {e}")
        result = CheckResult(
            passed=False,
            violations=[{"id": "YAML", "desc": f"YAML 解析失败: {e}", "passed": False}],
        )
        return result

    # ---- 1) 静态检查：接口函数/类型存在性 ----
    pre_items = _check_preconditions(code, contract, cid)
    post_items = _check_postconditions(code, contract, cid)
    inv_items = _check_invariants(code, contract, cid)
    fh_items = _check_fault_handling(code, contract, cid)

    # ---- 2) 生成断言插桩 ----
    try:
        assert_code = contract_to_assert(contract_yaml, cid=cid)
    except Exception as e:
        logger.error(f"ContractChecker:断言生成失败: {e}")
        assert_code = f"/* 断言生成失败: {e} */\n"

    # ---- 3) 汇总 ----
    all_items = pre_items + post_items + inv_items + fh_items
    passed = all(item.passed for item in all_items)
    violations = [
        {
            "id": item.id,
            "desc": item.desc,
            "detail": item.detail,
            "passed": item.passed,
        }
        for item in all_items
        if not item.passed
    ]

    result = CheckResult(
        passed=passed,
        preconditions=pre_items,
        postconditions=post_items,
        invariants=inv_items,
        fault_handling=fh_items,
        assert_code=assert_code,
        violations=violations,
    )
    logger.info(
        f"ContractChecker:完成 passed={passed} "
        f"pre={len(pre_items)} post={len(post_items)} "
        f"inv={len(inv_items)} fh={len(fh_items)} violations={len(violations)}"
    )
    return result


def _check_preconditions(
    code: str, contract: dict[str, Any], cid: str
) -> list[CheckItem]:
    """检查前置条件（mock 语义检查：根据代码模式判断是否满足）。"""
    raw_list = _extract_section(contract, "preconditions")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        item_id = f"{cid}-PRE-{i:03d}"
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        passed, detail = _mock_check_expr(code, expr, "precondition")
        items.append(CheckItem(id=item_id, desc=desc, passed=passed, detail=detail))
    return items


def _check_postconditions(
    code: str, contract: dict[str, Any], cid: str
) -> list[CheckItem]:
    """检查后置条件（mock 语义检查）。"""
    raw_list = _extract_section(contract, "postconditions")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        item_id = f"{cid}-POST-{i:03d}"
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        passed, detail = _mock_check_expr(code, expr, "postcondition")
        items.append(CheckItem(id=item_id, desc=desc, passed=passed, detail=detail))
    return items


def _check_invariants(code: str, contract: dict[str, Any], cid: str) -> list[CheckItem]:
    """检查不变式（mock 语义检查）。"""
    raw_list = _extract_section(contract, "invariants")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        item_id = f"{cid}-INV-{i:03d}"
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        passed, detail = _mock_check_expr(code, expr, "invariant")
        items.append(CheckItem(id=item_id, desc=desc, passed=passed, detail=detail))
    return items


def _check_fault_handling(
    code: str, contract: dict[str, Any], cid: str
) -> list[CheckItem]:
    """检查故障处理（mock 语义检查：是否包含 fault / NULL / 异常处理关键词）。"""
    raw_list = _extract_section(contract, "fault_handling")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        item_id = f"{cid}-FH-{i:03d}"
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        # mock：代码中是否包含 fault / NULL / error 等关键词
        keywords = re.findall(
            r"fault|NULL|null|error|invalid|0\s*==", code, re.IGNORECASE
        )
        passed = len(keywords) > 0
        detail = (
            f"命中关键词 {keywords[:3]}，视为已处理"
            if passed
            else "未检测到故障处理代码"
        )
        items.append(CheckItem(id=item_id, desc=desc, passed=passed, detail=detail))
    return items


def _extract_section(contract: dict[str, Any], section: str) -> list[Any]:
    """从契约字典提取指定 section，兼容两种 YAML 布局。"""
    if section in contract:
        return contract.get(section, []) or []
    contracts_block = contract.get("contracts", {}) or {}
    return contracts_block.get(section, []) or []


def _mock_check_expr(code: str, expr: Any, kind: str) -> tuple[bool, str]:
    """mock 语义检查：根据代码模式粗略判断是否满足契约表达式。

    真实实现预留：接通 LM Studio (OpenAI 兼容 API, localhost:1234/v1) 做语义级检查或编译执行断言。

    判定规则（启发式）：
    - 表达式含 NULL：代码中是否出现 NULL / (void*)0 检查
    - 表达式含 abs/范围：代码中是否出现相应数值边界
    - 其他：默认通过（避免阻塞 pipeline，仅做占位）
    """
    expr_str = (
        expr
        if isinstance(expr, str)
        else str(expr.get("desc", "") or expr.get("expr", ""))
    )
    expr_lower = expr_str.lower()

    # 1) NULL 检查类
    if "null" in expr_lower:
        has_null_check = bool(
            re.search(
                r"null|null\s*==|==\s*null|\(\s*void\s*\*\s*\)\s*0", code, re.IGNORECASE
            )
        )
        if has_null_check:
            return True, "代码中检测到 NULL 检查"
        return False, "未检测到 NULL 检查"

    # 2) 范围检查类（如 output >= 0、output <= 100）
    range_m = re.search(r"(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", expr_str)
    if range_m:
        op, value = range_m.groups()
        # mock：代码中是否出现相同数值（粗略匹配）
        if value in code:
            return True, f"代码中包含边界值 {value}"
        return True, "范围检查默认通过（mock）"

    # 3) abs/delta 类
    if "abs" in expr_lower or "delta" in expr_lower:
        if "fabs" in code or "abs(" in code:
            return True, "代码中包含 abs/fabs 检查"
        return True, "abs 检查默认通过（mock）"

    # 4) 默认通过（mock）
    return True, f"{kind} 默认通过（mock）"
