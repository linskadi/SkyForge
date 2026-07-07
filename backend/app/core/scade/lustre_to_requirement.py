"""Lustre → 需求转换器：将 G-Lustre 解析结果转换为自然语言需求 + 契约 YAML。

输入：ParsedLustre（来自 lustre_parser.parse_glustre）
输出：
- convert() 返回自然语言需求字符串（含 [REQ-xxx] 追溯 Tag）
- convert_to_contract() 返回对应 .contract YAML（preconditions/postconditions/invariants）
"""

from app.core.scade.lustre_parser import ParsedLustre, Variable
from app.utils.log_util import logger

# G-Lustre 类型 → C 类型映射
_TYPE_MAP: dict[str, str] = {
    "real": "double",
    "int": "int",
    "bool": "bool",
    "uint8": "uint8_t",
    "int8": "int8_t",
    "uint16": "uint16_t",
    "int16": "int16_t",
    "uint32": "uint32_t",
    "int32": "int32_t",
    "float": "float",
    "double": "double",
}


def convert(parsed: ParsedLustre, req_id: str = "REQ-001") -> str:
    """将 G-Lustre 解析结果转换为自然语言需求。

    生成格式：
        [REQ-xxx] 实现一个 {node_name}，输入为 {inputs}，输出为 {outputs}。
        功能描述：{equations}。
        约束条件：{range_constraints}。

    Args:
        parsed: G-Lustre 解析结果。
        req_id: 需求 ID（用于追溯 Tag）。

    Returns:
        自然语言需求字符串。
    """
    logger.info(f"LustreToReq:开始转换 node={parsed.node_name} req_id={req_id}")

    inputs_desc = ", ".join(f"{v.name}({v.type})" for v in parsed.inputs) or "无"
    outputs_desc = ", ".join(f"{v.name}({v.type})" for v in parsed.outputs) or "无"

    # 等式 → 功能描述
    if parsed.equations:
        eq_desc = "; ".join(f"{eq.output} = {eq.expression}" for eq in parsed.equations)
    else:
        eq_desc = "无显式等式"

    # 范围约束
    constraints: list[str] = []
    for v in parsed.inputs:
        if v.range and len(v.range) >= 2:
            constraints.append(f"{v.name} 范围 [{v.range[0]}, {v.range[1]}]")
    for v in parsed.outputs:
        if v.range and len(v.range) >= 2:
            constraints.append(f"{v.name} 范围 [{v.range[0]}, {v.range[1]}]")
    constraint_str = "; ".join(constraints) if constraints else "无显式范围约束"

    # 局部变量信息
    if parsed.locals:
        locals_desc = ", ".join(f"{v.name}({v.type})" for v in parsed.locals)
        locals_line = f"局部变量：{locals_desc}。"
    else:
        locals_line = ""

    requirement = (
        f"[{req_id}] 实现一个 {parsed.node_name}，"
        f"输入为 {inputs_desc}，输出为 {outputs_desc}。"
        f"{locals_line}"
        f"功能描述：{eq_desc}。"
        f"约束条件：{constraint_str}。"
    )

    logger.info(f"LustreToReq:完成需求转换 ({len(requirement)} 字符)")
    return requirement


def convert_to_contract(parsed: ParsedLustre, req_id: str = "REQ-001") -> str:
    """将 G-Lustre 解析结果转换为契约 YAML。

    生成 .contract 格式（参考设计文档 6.3 节）：
    - preconditions：输入范围约束
    - postconditions：输出范围约束
    - invariants：类型约束
    - fault_handling：默认故障处理

    Args:
        parsed: G-Lustre 解析结果。
        req_id: 需求 ID（用于 traceability 字段）。

    Returns:
        .contract YAML 文本。
    """
    logger.info(f"LustreToReq:开始生成契约 node={parsed.node_name} req_id={req_id}")

    # 构建 preconditions（输入范围）
    preconditions: list[str] = []
    for v in parsed.inputs:
        preconditions.append(f"{v.name} != NULL")
        if v.range and len(v.range) >= 2:
            preconditions.append(
                f"{v.name} >= {v.range[0]} && {v.name} <= {v.range[1]}"
            )

    # 构建 postconditions（输出范围）
    postconditions: list[str] = []
    for v in parsed.outputs:
        postconditions.append(f"{v.name} != NULL")
        if v.range and len(v.range) >= 2:
            postconditions.append(
                f"{v.name} >= {v.range[0]} && {v.name} <= {v.range[1]}"
            )

    # 构建 invariants（类型约束）
    invariants: list[str] = []
    for v in parsed.inputs + parsed.outputs:
        c_type = _to_c_type(v.type)
        invariants.append(f"{v.name} 类型为 {c_type}")
    # 加入等式作为不变式
    for eq in parsed.equations:
        invariants.append(f"{eq.output} 满足数据流等式: {eq.output} = {eq.expression}")

    # 接口 YAML
    inputs_yaml = _build_interface_yaml(parsed.inputs)
    outputs_yaml = _build_interface_yaml(parsed.outputs)

    pre_yaml = _build_list_yaml(preconditions)
    post_yaml = _build_list_yaml(postconditions)
    inv_yaml = _build_list_yaml(invariants)

    contract = f"""component: {parsed.node_name}
version: 1.0.0
safety_level: DAL-B
traceability: [{req_id}]

interface:
  inputs:
{inputs_yaml}
  outputs:
{outputs_yaml}

contracts:
  preconditions:
{pre_yaml}
  postconditions:
{post_yaml}
  invariants:
{inv_yaml}
  fault_handling:
    - "if 输入异常: set fault_detected = true"
    - "if |delta| 超出范围: 拒绝采样并使用预测值"

composability:
  depends_on: []
  provides: []
  consumes: []
  timing:
    wcet: 1ms
    period: 10ms
"""

    logger.info(f"LustreToReq:完成契约生成 ({len(contract)} 字符)")
    return contract


def _to_c_type(lustre_type: str) -> str:
    """将 Lustre 类型映射为 C 类型。"""
    return _TYPE_MAP.get(lustre_type.lower(), lustre_type)


def _build_interface_yaml(variables: list[Variable]) -> str:
    """构建接口 YAML 片段（inputs/outputs 列表）。"""
    if not variables:
        return "    []"
    lines: list[str] = []
    for v in variables:
        c_type = _to_c_type(v.type)
        line = f"    - name: {v.name}\n      type: {c_type}"
        if v.range and len(v.range) >= 2:
            line += f"\n      range: [{v.range[0]}, {v.range[1]}]"
        lines.append(line)
    return "\n".join(lines)


def _build_list_yaml(items: list[str]) -> str:
    """构建 YAML 列表片段（preconditions/postconditions/invariants）。"""
    if not items:
        return "    []"
    return "\n".join(f'    - "{item}"' for item in items)
