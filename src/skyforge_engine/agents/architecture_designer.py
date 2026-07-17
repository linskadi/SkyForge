"""架构设计 Agent — 从 HLR 自动生成模块划分、接口定义与数据流。

V0.4 P3: 补齐四大智能体（需求/架构/代码/校验）的"架构设计智能体"缺口。
参照机载要求.md §2.2.2 的规范：
  - 模块划分（高内聚、低耦合）
  - 接口定义（输入/输出/数据类型）
  - 数据结构设计（静态内存、嵌入式规范）
  - 支持 SCXML 状态机描述飞行模式

降级策略: LLM 不可用时使用规则引擎生成默认架构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger

# 可选：LLM 增强
try:
    from skyforge_llm.client import get_lmstudio_client
except ImportError:
    get_lmstudio_client = None  # type: ignore[assignment]

try:
    from skyforge_llm.parser import safe_parse_llm_json
except ImportError:
    safe_parse_llm_json = lambda x: {}  # type: ignore[assignment]


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
) -> ArchitectureResult:
    """根据 HLR + LLR 生成软件架构设计。

    Args:
        hlr_list: 高层需求列表。
        llr_list: 低层需求列表（可选）。
        module_name: 模块名称。
        safety_level: DAL 安全等级。

    Returns:
        ArchitectureResult: 架构设计结果。
    """
    # 优先使用 LLM
    client = None
    if get_lmstudio_client:
        client = get_lmstudio_client()

    if client and client.is_available() if hasattr(client, 'is_available') else False:
        return _design_with_llm(hlr_list, llr_list, module_name, safety_level, client)

    return _design_with_rules(hlr_list, llr_list, module_name, safety_level)


def _design_with_rules(
    hlr_list: list[dict[str, Any]],
    llr_list: list[dict[str, Any]] | None,
    module_name: str,
    safety_level: str,
) -> ArchitectureResult:
    """规则引擎生成默认架构。"""
    modules: list[ArchitectureModule] = []

    # 按需求关键词推断模块划分
    module_keywords = {
        "input": ["输入", "读取", "传感器", "采样", "input", "sensor", "adc", "read"],
        "filter": ["滤波", "过滤", "filter", "平滑", "smooth", "降噪", "denoise"],
        "control": ["控制", "调节", "controller", "pid", "反馈", "feedback"],
        "output": ["输出", "写入", "执行", "驱动", "output", "actuator", "write", "send"],
        "monitor": ["监测", "监控", "监测", "检查", "monitor", "check", "watchdog", "告警"],
    }

    for hlr in hlr_list:
        req_text = (hlr.get("description", "") + " " + hlr.get("req_id", "")).lower()

        # 匹配模块类型
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

    # 全局数据结构
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

    # DAL-A 额外安全检查
    if safety_level in ("DAL-A", "A"):
        global_data.append({
            "name": "redundant_data", "type": "struct",
            "fields": [
                {"name": "primary_value", "type": "double"},
                {"name": "secondary_value", "type": "double"},
                {"name": "voting_result", "type": "double"},
            ],
        })

    # 模块依赖关系
    for mod in modules:
        if mod.name != "input":
            mod.dependencies.append("input")
        if mod.name == "output":
            mod.dependencies.append("filter")

    # 状态机（飞行模式）
    state_machine = _generate_state_machine(module_name)

    # 接口规范
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

    logger.info(
        f"ArchitectureDesigner:规则引擎生成 {len(modules)} 个模块, "
        f"DAL={safety_level}"
    )

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
    mod = ArchitectureModule(
        name=name,
        description=f"{name} 处理模块",
    )
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
                "transitions": [
                    {"event": "init_complete", "target": "idle", "guard": "config_valid"}
                ],
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
                "transitions": [
                    {"event": "reset", "target": "init"},
                ],
            },
        ],
        "events": [
            "init_complete", "start_processing", "processing_complete",
            "fault_detected", "fault_cleared", "critical_fault", "reset",
        ],
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
