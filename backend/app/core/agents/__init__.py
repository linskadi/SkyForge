"""Pipeline Agents 模块。

每个 Agent 独立实现（不继承共同基类），原因：
1. 底层 LLM 客户端不同：pipeline agents 使用 LMStudioClient（本地直连），
   而基类 Agent 设计为使用 LLM（多 Provider 抽象层 + Redis 流式推送）。
2. 调用模式不同：pipeline agents 是单轮 prompt 调用 + Mock 降级，
   基类 Agent 是多轮对话 + 历史管理 + token 压缩。
3. 强行统一会引入不必要的耦合，保持独立更清晰。
"""

from .requirement_parser_agent import RequirementParserAgent
from .contract_generator_agent import ContractGeneratorAgent
from .code_generator_agent import CodeGeneratorAgent
from .code_repairer_agent import CodeRepairerAgent

__all__ = [
    "RequirementParserAgent",
    "ContractGeneratorAgent",
    "CodeGeneratorAgent",
    "CodeRepairerAgent",
]
