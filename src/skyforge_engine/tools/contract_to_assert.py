"""契约→C 断言自动映射器（Patch 2）：读取 .contract YAML，
用 Jinja2 生成 C 断言检查函数。

参考设计文档第 6.4.1 节："契约即测试，违约即崩溃"。
数字孪生仿真时，一旦波形异常，GCC 编译的程序直接 core dump 抛出断言失败。
"""

from typing import Any

import yaml
from jinja2 import Template

from skyforge_engine.utils.log_util import logger

# Jinja2 模板：生成 C 断言检查函数
ASSERT_TEMPLATE = Template("""/* ===== 自动生成的契约断言（请勿手动修改）===== */
/* [{{cid}}] 契约追溯：{{traceability}} */
#include <assert.h>
#include <math.h>

static void __check_contract_step_{{cid}}(double output) {
    {% for post in postconditions %}
    /* [{{post.id}}] {{post.desc}} */
    assert({{post.expr}} && "[{{post.id}}] 违反后置条件: {{post.desc}}");
    {% endfor %}
    /* 检查 NaN/Inf */
    assert(!isnan(output) && "[{{cid}}] 输出为 NaN");
    assert(!isinf(output) && "[{{cid}}] 输出为 Inf");
}
""")


def contract_to_assert(yaml_str: str, cid: str = "CON-001") -> str:
    """读取 YAML 契约字符串，生成 C 断言检查函数。

    Args:
        yaml_str: .contract YAML 文本。
        cid: 契约 ID，用于断言追溯 Tag（默认 CON-001）。

    Returns:
        C 断言检查函数源码字符串。
    """
    contract = yaml.safe_load(yaml_str) or {}
    postconditions = _extract_postconditions(contract, cid)
    traceability = contract.get("traceability", "")

    # 统一替换变量名：将契约中的变量名映射到函数参数名
    for post in postconditions:
        post["expr"] = post["expr"].replace("filtered_output", "output").replace("out_val", "output")

    rendered = ASSERT_TEMPLATE.render(
        cid=cid,
        traceability=traceability,
        postconditions=postconditions,
    )
    logger.info(
        f"ContractToAssert:完成:生成 {len(postconditions)} 条后置条件断言 (cid={cid})"
    )
    return rendered


def _extract_postconditions(contract: dict[str, Any], cid: str) -> list[dict[str, str]]:
    """从契约字典提取后置条件，兼容两种 YAML 布局。

    布局1（文档 6.4.1 示例）：顶层 postconditions 列表
    布局2（文档 6.3 生成的 .contract）：contracts.postconditions 列表
    """
    raw_list: list[Any] = []
    if "postconditions" in contract:
        raw_list = contract.get("postconditions", []) or []
    else:
        contracts_block = contract.get("contracts", {}) or {}
        raw_list = contracts_block.get("postconditions", []) or []

    parsed: list[dict[str, str]] = []
    for i, expr in enumerate(raw_list):
        if isinstance(expr, str):
            parsed.append({"desc": expr, "expr": _to_c_expr(expr)})
        elif isinstance(expr, dict):
            desc = expr.get("desc", "")
            parsed.append({"desc": desc, "expr": _to_c_expr(expr.get("expr", desc))})

    # 统一生成 id（用传入 cid 作前缀，便于追溯）
    return [
        {
            "id": f"{cid}-POST-{i:03d}",
            "desc": post["desc"],
            "expr": post["expr"],
        }
        for i, post in enumerate(parsed)
    ]


def _to_c_expr(expr: str) -> str:
    """将契约表达式转换为合法 C 表达式（简易替换）。"""
    # NULL -> ((void*)0) 以兼容 C
    converted = expr.replace("NULL", "((void *)0)")
    # abs(x) -> fabs(x) 保证浮点取绝对值（需 math.h）
    converted = re_sub_abs(converted)
    return converted


def re_sub_abs(text: str) -> str:
    """将 abs(...) 替换为 fabs(...)，仅处理函数调用形式。"""
    import re

    return re.sub(r"\babs\(", "fabs(", text)
