"""枚举类型定义模块。"""

from enum import Enum


class AgentType(str, Enum):
    """Agent 类型标识。"""

    REQUIREMENT_PARSER = "RequirementParserAgent"
    CONTRACT_GENERATOR = "ContractGeneratorAgent"
    CODE_GENERATOR = "CodeGeneratorAgent"
    CODE_REPAIRER = "CodeRepairerAgent"
    SIMULATION_ENGINE = "SimulationEngine"
    REPORT_GENERATOR = "ReportGenerator"


class AgentStatus(str, Enum):
    """Agent 执行状态。"""

    START = "start"
    WORKING = "working"
    DONE = "done"
    ERROR = "error"
    SUCCESS = "success"
