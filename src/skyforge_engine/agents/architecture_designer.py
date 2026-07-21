"""架构设计 Agent — 从 HLR 自动生成模块划分、接口定义与数据流。

V0.4 P3: 补齐四大智能体（需求/架构/代码/校验）的"架构设计智能体"缺口。
参照机载要求.md §2.2.2 的规范：
  - 模块划分（高内聚、低耦合）
  - 接口定义（输入/输出/数据类型）
  - 数据结构设计（静态内存、嵌入式规范）
  - 支持 SCXML 状态机描述飞行模式

由 ``SKYFORGE_LLM_MODE`` 决定运行方式：
  - ``mock``：规则引擎生成默认架构。
  - ``api`` / ``local``：调用 LLM 生成架构，异常直接抛出，禁止静默降级。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skyforge_engine.core.protocols import AgentMode
from skyforge_engine.utils.log_util import logger

try:
    from skyforge_llm.parser import safe_parse_llm_json
except ImportError:
    def safe_parse_llm_json(x):
        return {}  # type: ignore[assignment]


# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C 航空软件架构师，专职依据高层需求（HLR）与低层需求（LLR）生成软件架构设计。
你必须以适航视角工作，确保模块划分满足高内聚、低耦合原则，接口定义清晰，数据结构设计符合嵌入式规范。

## 可用工具
- design_modules(hlr_list) 按需求关键词推断模块划分
- define_interfaces(module) 定义输入/输出接口与数据类型
- design_data_structures(safety_level) 按 DAL 等级设计全局数据结构
- generate_state_machine(module_name) 生成 SCXML 兼容的飞行模式状态机

## 输出格式（严格 JSON，禁止前后缀文字）
{
  "modules": [
    {
      "name": "module_name",
      "description": "模块描述",
      "inputs": [{"name": "input_name", "type": "double"}],
      "outputs": [{"name": "output_name", "type": "double"}],
      "data_structures": [],
      "dependencies": []
    }
  ],
  "global_data": [
    {"name": "config_struct", "type": "struct", "fields": [
      {"name": "sample_rate", "type": "uint16_t"},
      {"name": "cutoff_freq", "type": "float"}
    ]}
  ],
  "state_machine": {
    "type": "scxml",
    "initial": "init",
    "states": [...],
    "events": [...]
  },
  "interface_spec": {
    "api_version": "1.0",
    "input_interface": {"function": "module_init", "params": ["void"], "returns": "void"},
    "output_interface": {"function": "module_process", "params": [{"name": "raw_input", "type": "double"}], "returns": "double"},
    "memory_model": "static"
  },
  "architecture_diagram": ""
}

## 禁忌
1. 禁止臆造需求中未提及的模块
2. 禁止遗漏接口定义（输入/输出/数据类型）
3. 禁止输出 JSON 以外的任何文字
4. 禁止使用动态内存相关字段
5. DAL-A 必须包含冗余数据结构"""


@dataclass
class ArchitectureModule:
    """单个架构模块。"""

    name: str = ""
    description: str = ""
    inputs: list[dict[str, str]] = field(default_factory=list)
    outputs: list[dict[str, str]] = field(default_factory=list)
    data_structures: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ArchitectureResult:
    """架构设计结果。"""

    modules: list[ArchitectureModule] = field(default_factory=list)
    global_data: list[dict[str, Any]] = field(default_factory=list)
    state_machine: dict[str, Any] = field(default_factory=dict)
    interface_spec: dict[str, Any] = field(default_factory=dict)
    architecture_diagram: str = ""
    generated_by: str = "rule_engine"


def design_architecture(
    hlr_list: list[dict[str, Any]],
    llr_list: list[dict[str, Any]] | None = None,
    module_name: str = "",
    safety_level: str = "DAL-C",
    strategy=None,
) -> ArchitectureResult:
    """根据 HLR + LLR 生成软件架构设计。

    Args:
        hlr_list: 高层需求列表。
        llr_list: 低层需求列表（可选）。
        module_name: 模块名称。
        safety_level: DAL 安全等级。
        strategy: 可选的执行策略。

    Returns:
        ArchitectureResult: 架构设计结果。
    """
    if strategy is None:
        from skyforge_engine.core.strategies import get_strategy_for_mode
        strategy = get_strategy_for_mode()

    if strategy.mode == AgentMode.MOCK:
        result = _design_with_rules(hlr_list, llr_list, module_name, safety_level)
        logger.info(
            f"ArchitectureDesigner:规则引擎生成 {len(result.modules)} 个模块, DAL={safety_level}"
        )
        return result

    result = _llm_design(hlr_list, llr_list, module_name, safety_level)
    logger.info(
        f"ArchitectureDesigner:生成 {len(result.modules)} 个模块, DAL={safety_level}"
    )
    return result


def _llm_design(
    hlr_list: list[dict[str, Any]],
    llr_list: list[dict[str, Any]] | None,
    module_name: str,
    safety_level: str,
) -> ArchitectureResult:
    """LLM 实现：调用 LLM 生成架构设计。"""
    from skyforge_engine.llm_provider import get_llm_client

    client = get_llm_client()
    if client is None:
        raise RuntimeError("ArchitectureDesigner:LLM 客户端不可用")
    prompt = _build_architecture_prompt(hlr_list, llr_list, module_name, safety_level)
    response = client.chat(
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=4096,
    )
    if not response:
        raise RuntimeError("ArchitectureDesigner:LLM 调用返回空响应")

    parsed = safe_parse_llm_json(response)
    if not parsed:
        raise RuntimeError("ArchitectureDesigner:LLM 输出解析失败")

    return _parse_architecture_result(parsed, module_name, safety_level)


def _build_architecture_prompt(
    hlr_list: list[dict[str, Any]],
    llr_list: list[dict[str, Any]] | None,
    module_name: str,
    safety_level: str,
) -> str:
    """构建架构设计 LLM prompt。"""
    parts = [
        "请依据以下需求生成航空软件架构设计（输出严格 JSON）：\n",
        f"模块名称: {module_name or '未指定'}\n",
        f"安全等级: {safety_level}\n",
        "\n高层需求 (HLR):\n",
    ]
    for hlr in hlr_list:
        parts.append(f"- {hlr.get('req_id', 'REQ-???')}: {hlr.get('description', '')}\n")

    if llr_list:
        parts.append("\n低层需求 (LLR):\n")
        for llr in llr_list:
            parts.append(f"- {llr.get('req_id', 'LLR-???')}: {llr.get('description', '')}\n")

    parts.append(
        "\n要求：\n"
        "1. 模块划分满足高内聚、低耦合\n"
        "2. 接口定义包含输入/输出名称和数据类型\n"
        "3. 全局数据结构使用静态内存\n"
        "4. 状态机使用 SCXML 格式描述飞行模式\n"
        "5. 仅输出 JSON，禁止任何解释性文字"
    )
    return "".join(parts)


def _parse_architecture_result(
    parsed: dict[str, Any],
    module_name: str,
    safety_level: str,
) -> ArchitectureResult:
    """将 LLM 解析后的字典转为 ArchitectureResult。"""
    modules: list[ArchitectureModule] = []
    for mod in parsed.get("modules", []):
        if not isinstance(mod, dict):
            continue
        modules.append(
            ArchitectureModule(
                name=mod.get("name", ""),
                description=mod.get("description", ""),
                inputs=mod.get("inputs", []),
                outputs=mod.get("outputs", []),
                data_structures=mod.get("data_structures", []),
                dependencies=mod.get("dependencies", []),
            )
        )

    global_data = parsed.get("global_data", [])
    if not isinstance(global_data, list):
        global_data = []

    state_machine = parsed.get("state_machine", {})
    if not isinstance(state_machine, dict):
        state_machine = {}

    interface_spec = parsed.get("interface_spec", {})
    if not isinstance(interface_spec, dict):
        interface_spec = {}

    # 兜底：确保 interface_spec 包含必要字段
    if "api_version" not in interface_spec:
        interface_spec["api_version"] = "1.0"
    if "input_interface" not in interface_spec:
        interface_spec["input_interface"] = {
            "function": f"{module_name or 'module'}_init",
            "params": ["void"],
            "returns": "void",
        }
    if "output_interface" not in interface_spec:
        interface_spec["output_interface"] = {
            "function": f"{module_name or 'module'}_process",
            "params": [{"name": "raw_input", "type": "double"}],
            "returns": "double",
        }
    if "memory_model" not in interface_spec:
        interface_spec["memory_model"] = (
            "static" if safety_level in ("DAL-A", "DAL-B") else "stack"
        )

    architecture_diagram = str(parsed.get("architecture_diagram", ""))

    return ArchitectureResult(
        modules=modules,
        global_data=global_data,
        state_machine=state_machine,
        interface_spec=interface_spec,
        architecture_diagram=architecture_diagram,
        generated_by="llm",
    )


def _design_with_rules(
    hlr_list: list[dict[str, Any]],
    llr_list: list[dict[str, Any]] | None,
    module_name: str,
    safety_level: str,
) -> ArchitectureResult:
    """规则引擎生成默认架构（仅在 mock 模式下使用）。"""
    modules: list[ArchitectureModule] = []

    module_keywords = {
        "input": ["输入", "读取", "传感器", "采样", "input", "sensor", "adc", "read"],
        "filter": ["滤波", "过滤", "filter", "平滑", "smooth", "降噪", "denoise"],
        "control": ["控制", "调节", "controller", "pid", "反馈", "feedback"],
        "output": ["输出", "写入", "执行", "驱动", "output", "actuator", "write", "send"],
        "monitor": ["监测", "监控", "监测", "检查", "monitor", "check", "watchdog", "告警"],
    }

    for hlr in hlr_list:
        req_text = (hlr.get("description", "") + " " + hlr.get("req_id", "")).lower()

        matched = False
        for mod_type, keywords in module_keywords.items():
            if any(kw in req_text for kw in keywords):
                mod = _find_or_create_module(modules, mod_type)
                mod.inputs.append({"name": f"{mod_type}_input", "type": "double"})
                mod.outputs.append({"name": f"{mod_type}_output", "type": "double"})
                matched = True
                break

        if not matched:
            mod = _find_or_create_module(modules, "core")
            mod.description = "核心处理逻辑"

    global_data = [
        {"name": "config_struct", "type": "struct", "fields": [
            {"name": "sample_rate", "type": "uint16_t"},
            {"name": "cutoff_freq", "type": "float"},
            {"name": "fault_threshold", "type": "float"},
        ]},
        {"name": "state_struct", "type": "struct", "fields": [
            {"name": "mode", "type": "uint8_t"},
            {"name": "error_flag", "type": "bool"},
            {"name": "step_count", "type": "uint32_t"},
        ]},
    ]

    if safety_level in ("DAL-A", "A"):
        global_data.append({
            "name": "redundant_data", "type": "struct",
            "fields": [
                {"name": "primary_value", "type": "double"},
                {"name": "secondary_value", "type": "double"},
                {"name": "voting_result", "type": "double"},
            ],
        })

    for mod in modules:
        if mod.name != "input":
            mod.dependencies.append("input")
        if mod.name == "output":
            mod.dependencies.append("filter")

    state_machine = _generate_state_machine(module_name)

    interface_spec = {
        "api_version": "1.0",
        "input_interface": {
            "function": f"{module_name or 'module'}_init",
            "params": ["void"],
            "returns": "void",
        },
        "output_interface": {
            "function": f"{module_name or 'module'}_process",
            "params": [{"name": "raw_input", "type": "double"}],
            "returns": "double",
        },
        "memory_model": "static" if safety_level in ("DAL-A", "DAL-B") else "stack",
    }

    return ArchitectureResult(
        modules=modules,
        global_data=global_data,
        state_machine=state_machine,
        interface_spec=interface_spec,
        generated_by="rule_engine",
    )


def _find_or_create_module(modules: list[ArchitectureModule], name: str) -> ArchitectureModule:
    """查找或创建模块。"""
    for m in modules:
        if m.name == name:
            return m
    mod = ArchitectureModule(name=name, description=f"{name} 处理模块")
    modules.append(mod)
    return mod


def _generate_state_machine(module_name: str) -> dict[str, Any]:
    """生成飞行模式状态机定义（SCXML 兼容）。"""
    return {
        "type": "scxml",
        "initial": "init",
        "states": [
            {
                "id": "init",
                "description": "初始化状态：加载配置、校验内存",
                "transitions": [{"event": "init_complete", "target": "idle", "guard": "config_valid"}],
            },
            {
                "id": "idle",
                "description": "空闲状态：等待处理请求",
                "transitions": [
                    {"event": "start_processing", "target": "running"},
                    {"event": "fault_detected", "target": "degraded"},
                ],
            },
            {
                "id": "running",
                "description": "运行状态：正常数据处理",
                "transitions": [
                    {"event": "processing_complete", "target": "idle"},
                    {"event": "fault_detected", "target": "degraded"},
                ],
            },
            {
                "id": "degraded",
                "description": "降级状态：使用预测值替代故障传感器",
                "transitions": [
                    {"event": "fault_cleared", "target": "idle"},
                    {"event": "critical_fault", "target": "fail_safe"},
                ],
            },
            {
                "id": "fail_safe",
                "description": "故障安全状态：输出安全默认值",
                "transitions": [{"event": "reset", "target": "init"}],
            },
        ],
        "events": ["init_complete", "start_processing", "processing_complete",
                   "fault_detected", "fault_cleared", "critical_fault", "reset"],
    }


# 便捷函数
def design(hlr_list: list[dict], module_name: str = "", dal: str = "C") -> dict:
    """便捷函数：生成架构并返回字典。"""
    result = design_architecture(hlr_list, module_name=module_name, safety_level=dal)
    return {
        "modules": [
            {
                "name": m.name,
                "description": m.description,
                "inputs": m.inputs,
                "outputs": m.outputs,
                "dependencies": m.dependencies,
            }
            for m in result.modules
        ],
        "state_machine": result.state_machine,
        "interface_spec": result.interface_spec,
        "generated_by": result.generated_by,
    }
