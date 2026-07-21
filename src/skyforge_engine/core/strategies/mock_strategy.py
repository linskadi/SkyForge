"""Mock 策略实现。

统一处理各 Agent 的 mock 逻辑，确保输出格式与现有实现一致。
"""

from typing import Any

from skyforge_engine.core.protocols import AgentMode, AgentResult
from skyforge_engine.utils.log_util import logger


class MockStrategy:
    """Mock 策略：复用现有 Agent 的 mock 方法，返回 AgentResult。"""

    @property
    def mode(self) -> AgentMode:
        return AgentMode.MOCK

    def supports(self, input_type: str) -> bool:
        return input_type in (
            "requirement",
            "contract",
            "code",
            "repair",
            "architecture",
            "llr",
            "code_multi",
        )

    async def run(self, input_data: Any, **kwargs: Any) -> AgentResult:
        input_type = kwargs.get("input_type", "")
        try:
            if input_type == "requirement":
                from skyforge_engine.agents.requirement_parser import (
                    RequirementParserAgent,
                )

                agent = RequirementParserAgent()
                req_id = kwargs.get("req_id", "REQ-001")
                output = agent._mock_run(input_data, req_id)
                return AgentResult(output=output)

            elif input_type == "contract":
                from skyforge_engine.agents.contract_generator import (
                    ContractGeneratorAgent,
                )

                agent = ContractGeneratorAgent()
                output = agent._mock_run(input_data)
                return AgentResult(output=output)

            elif input_type == "code":
                from skyforge_engine.agents.code_generator import CodeGeneratorAgent

                agent = CodeGeneratorAgent()
                output = agent._mock_run(input_data)
                return AgentResult(output=output)

            elif input_type == "repair":
                from skyforge_engine.agents.code_repairer import CodeRepairerAgent

                agent = CodeRepairerAgent()
                violations = kwargs.get("violations", [])
                req_id = kwargs.get("req_id", "REQ-001")
                output = agent._mock_repair(input_data, violations, req_id)
                return AgentResult(output=output)

            elif input_type == "architecture":
                from skyforge_engine.agents.architecture_designer import (
                    _design_with_rules,
                )

                hlr_list = input_data
                llr_list = kwargs.get("llr_list")
                module_name = kwargs.get("module_name", "")
                safety_level = kwargs.get("safety_level", "DAL-C")
                output = _design_with_rules(
                    hlr_list, llr_list, module_name, safety_level
                )
                return AgentResult(output=output)

            elif input_type == "llr":
                from skyforge_engine.agents.llr_generator import LLRGeneratorAgent

                agent = LLRGeneratorAgent()
                safety_level = kwargs.get("safety_level", "DAL-C")
                module_name = kwargs.get("module_name", "")
                output = agent._fallback_generate(
                    input_data, safety_level, module_name
                )
                return AgentResult(output=output)

            elif input_type == "code_multi":
                from skyforge_engine.agents.code_generator_multi import (
                    MultiLanguageCodeGenerator,
                )

                agent = MultiLanguageCodeGenerator()
                language = kwargs.get("language", "c")
                output = agent._mock_run(input_data, language)
                return AgentResult(output=output)

            else:
                return AgentResult(
                    output=None,
                    success=False,
                    warnings=(f"不支持的 input_type: {input_type}",),
                )
        except Exception as e:
            logger.error(f"MockStrategy 执行失败 [{input_type}]: {e}")
            return AgentResult(output=None, success=False, warnings=(str(e),))
