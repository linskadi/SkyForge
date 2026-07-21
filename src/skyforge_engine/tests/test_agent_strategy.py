"""Agent 策略分层单元测试。

验证 MockStrategy / LLMStrategy 的分发逻辑与各 Agent 的策略注入。
"""

import pytest

from skyforge_engine.core.protocols import AgentMode
from skyforge_engine.core.strategies import (
    MockStrategy,
    LLMStrategy,
    get_strategy_for_mode,
)


class TestGetStrategyForMode:
    def test_returns_mock_when_mock_mode(self, monkeypatch):
        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        strategy = get_strategy_for_mode()
        assert isinstance(strategy, MockStrategy)
        assert strategy.mode == AgentMode.MOCK

    def test_returns_llm_when_api_mode(self, monkeypatch):
        monkeypatch.setenv("SKYFORGE_LLM_MODE", "api")
        strategy = get_strategy_for_mode()
        assert isinstance(strategy, LLMStrategy)
        assert strategy.mode == AgentMode.LLM

    def test_returns_llm_when_local_mode(self, monkeypatch):
        monkeypatch.setenv("SKYFORGE_LLM_MODE", "local")
        strategy = get_strategy_for_mode()
        assert isinstance(strategy, LLMStrategy)
        assert strategy.mode == AgentMode.LLM


class TestMockStrategy:
    @pytest.fixture
    def strategy(self):
        return MockStrategy()

    @pytest.mark.asyncio
    async def test_requirement(self, strategy):
        requirement = "实现一个低通滤波器"
        result = await strategy.run(
            requirement, req_id="REQ-001", input_type="requirement"
        )
        assert result.success
        assert result.output["type"] == "filter"
        assert result.output["req_id"] == "REQ-001"

    @pytest.mark.asyncio
    async def test_contract(self, strategy):
        req = {"req_id": "REQ-001", "type": "functional", "module_name": "lpf"}
        result = await strategy.run(req, input_type="contract")
        assert result.success
        assert "component" in result.output

    @pytest.mark.asyncio
    async def test_code(self, strategy):
        req = {"req_id": "REQ-001", "type": "functional", "module_name": "lpf"}
        result = await strategy.run(req, input_type="code")
        assert result.success
        assert "void" in result.output

    @pytest.mark.asyncio
    async def test_repair(self, strategy):
        from skyforge_engine.tools.cppcheck_scanner import Violation

        code = "int x;\n"
        violations = [
            Violation(
                file="test.c",
                line=1,
                column=0,
                severity="style",
                rule_id="MISRA-C:2012-Rule-9.1",
                message="未初始化",
            )
        ]
        result = await strategy.run(
            code, violations=violations, req_id="REQ-001", input_type="repair"
        )
        assert result.success
        assert hasattr(result.output, "actions")
        assert hasattr(result.output, "code")

    @pytest.mark.asyncio
    async def test_architecture(self, strategy):
        hlr = [{"req_id": "REQ-001", "description": "低通滤波"}]
        result = await strategy.run(
            hlr, module_name="lpf", safety_level="DAL-C", input_type="architecture"
        )
        assert result.success
        assert len(result.output.modules) > 0

    @pytest.mark.asyncio
    async def test_llr(self, strategy):
        hlr = [{"req_id": "REQ-001", "desc": "低通滤波"}]
        result = await strategy.run(
            hlr, safety_level="DAL-C", module_name="lpf", input_type="llr"
        )
        assert result.success
        assert result.output["hlr_count"] == 1
        assert result.output["llr_count"] == 1

    @pytest.mark.asyncio
    async def test_code_multi(self, strategy):
        req = {"req_id": "REQ-001", "type": "functional"}
        result = await strategy.run(req, language="c", input_type="code_multi")
        assert result.success
        assert "void" in result.output

    @pytest.mark.asyncio
    async def test_unsupported_type(self, strategy):
        result = await strategy.run("data", input_type="unknown")
        assert not result.success
        assert "不支持的 input_type" in str(result.warnings)


class TestLLMStrategy:
    @pytest.fixture
    def strategy(self):
        return LLMStrategy()

    @pytest.mark.asyncio
    async def test_unsupported_type(self, strategy):
        result = await strategy.run("data", input_type="unknown")
        assert not result.success
        assert "不支持的 input_type" in str(result.warnings)


class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_requirement_parser_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.requirement_parser import RequirementParserAgent

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = RequirementParserAgent()
        result = await agent.run("实现一个低通滤波器")
        assert result["type"] == "filter"

    @pytest.mark.asyncio
    async def test_contract_generator_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.contract_generator import ContractGeneratorAgent

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = ContractGeneratorAgent()
        req = {"req_id": "REQ-001", "type": "functional", "module_name": "lpf"}
        result = await agent.run(req)
        assert "component" in result

    @pytest.mark.asyncio
    async def test_code_generator_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.code_generator import CodeGeneratorAgent

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = CodeGeneratorAgent()
        req = {"req_id": "REQ-001", "type": "functional", "module_name": "lpf"}
        result = await agent.run(req, contract="")
        assert "void" in result

    @pytest.mark.asyncio
    async def test_code_repairer_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.code_repairer import CodeRepairerAgent
        from skyforge_engine.tools.cppcheck_scanner import Violation

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = CodeRepairerAgent()
        code = "int x;\n"
        violations = [
            Violation(
                file="test.c",
                line=1,
                column=0,
                severity="style",
                rule_id="MISRA-C:2012-Rule-9.1",
                message="未初始化",
            )
        ]
        result = await agent.repair(code, violations)
        assert result.code != code or len(result.actions) > 0

    @pytest.mark.asyncio
    async def test_llr_generator_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.llr_generator import LLRGeneratorAgent

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = LLRGeneratorAgent()
        hlr = [{"req_id": "REQ-001", "desc": "低通滤波"}]
        result = await agent.generate(hlr)
        assert result["hlr_count"] == 1
        assert result["llr_count"] == 1

    @pytest.mark.asyncio
    async def test_code_generator_multi_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.code_generator_multi import (
            MultiLanguageCodeGenerator,
        )

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        agent = MultiLanguageCodeGenerator()
        req = {"req_id": "REQ-001", "type": "functional"}
        result = await agent.run(req, contract="")
        assert "void" in result

    def test_architecture_designer_uses_strategy(self, monkeypatch):
        from skyforge_engine.agents.architecture_designer import design_architecture

        monkeypatch.setenv("SKYFORGE_LLM_MODE", "mock")
        hlr = [{"req_id": "REQ-001", "description": "低通滤波"}]
        result = design_architecture(hlr, module_name="lpf")
        assert len(result.modules) > 0

    @pytest.mark.asyncio
    async def test_custom_strategy_injection(self):
        from skyforge_engine.agents.requirement_parser import RequirementParserAgent

        custom = MockStrategy()
        agent = RequirementParserAgent(strategy=custom)
        assert agent.strategy is custom
        result = await agent.run("实现一个低通滤波器")
        assert result["type"] == "filter"
