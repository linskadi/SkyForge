"""测试 skyforge_engine.core.protocols 协议接口。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


from skyforge_engine.core.protocols import (
    AgentMode,
    AgentResult,
    AgentStrategyProtocol,
    CodingStandardProtocol,
    HILAdapterProtocol,
    HILConnectionState,
    PipelineStageProtocol,
    ReportRendererProtocol,
    StageExecutionError,
    StageResult,
    ToolNotFoundError,
    VerificationError,
    VerificationResult,
    VerifierProtocol,
    Violation,
)


class DummyStage:
    """实现 PipelineStageProtocol 的 dummy 阶段。"""

    @property
    def name(self) -> str:
        return "dummy_stage"

    @property
    def description(self) -> str:
        return "A dummy stage for testing"

    async def execute(self, artifact, context=None):
        return StageResult(artifact=artifact, status="success")


class DummyVerifier:
    """实现 VerifierProtocol 的 dummy 验证器。"""

    @property
    def tool_name(self) -> str:
        return "dummy_verifier"

    def is_available(self) -> bool:
        return True

    def verify(self, code, contract=None, **kwargs):
        return VerificationResult(passed=True, tool_name=self.tool_name, tool_available=True)


class DummyHILAdapter:
    """实现 HILAdapterProtocol 的 dummy 适配器。"""

    @property
    def adapter_type(self) -> str:
        return "dummy"

    def is_available(self) -> bool:
        return True

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def send(self, data: bytes) -> None:
        pass

    def receive(self, timeout_ms: int = 5000) -> bytes:
        return b""


class DummyRenderer:
    """实现 ReportRendererProtocol 的 dummy 渲染器。"""

    @property
    def mime_type(self) -> str:
        return "text/html"

    @property
    def format_name(self) -> str:
        return "html"

    def render(self, data):
        return "<html></html>"


class DummyCodingStandard:
    """实现 CodingStandardProtocol 的 dummy 编码标准。"""

    @property
    def standard_name(self) -> str:
        return "DUMMY-STD"

    @property
    def language(self) -> str:
        return "c"

    def scan(self, code):
        return []

    def get_mock_scan_patterns(self):
        return []


class DummyStrategy:
    """实现 AgentStrategyProtocol 的 dummy 策略。"""

    @property
    def mode(self) -> AgentMode:
        return AgentMode.MOCK

    def supports(self, input_type: str) -> bool:
        return True

    async def run(self, input_data, **kwargs):
        return AgentResult(output=input_data)


class TestProtocolCompliance:
    """测试各协议接口的合规性。"""

    def test_pipeline_stage_protocol(self):
        stage = DummyStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "dummy_stage"
        assert stage.description == "A dummy stage for testing"

    def test_verifier_protocol(self):
        verifier = DummyVerifier()
        assert isinstance(verifier, VerifierProtocol)
        assert verifier.tool_name == "dummy_verifier"
        assert verifier.is_available() is True
        result = verifier.verify("int main() {}")
        assert isinstance(result, VerificationResult)
        assert result.passed is True

    def test_hil_adapter_protocol(self):
        adapter = DummyHILAdapter()
        assert isinstance(adapter, HILAdapterProtocol)
        assert adapter.adapter_type == "dummy"
        adapter.connect()
        adapter.send(b"test")
        data = adapter.receive()
        assert data == b""
        adapter.disconnect()

    def test_report_renderer_protocol(self):
        renderer = DummyRenderer()
        assert isinstance(renderer, ReportRendererProtocol)
        assert renderer.mime_type == "text/html"
        assert renderer.format_name == "html"
        assert renderer.render({}) == "<html></html>"

    def test_coding_standard_protocol(self):
        standard = DummyCodingStandard()
        assert isinstance(standard, CodingStandardProtocol)
        assert standard.standard_name == "DUMMY-STD"
        assert standard.language == "c"
        assert standard.scan("code") == []

    def test_agent_strategy_protocol(self):
        strategy = DummyStrategy()
        assert isinstance(strategy, AgentStrategyProtocol)
        assert strategy.mode == AgentMode.MOCK
        assert strategy.supports("anything") is True


class TestDataClasses:
    """测试数据类。"""

    def test_stage_result_defaults(self):
        result = StageResult(artifact="test")
        assert result.artifact == "test"
        assert result.status == "success"
        assert result.duration_ms == 0.0
        assert result.provenance == {}

    def test_verification_result_defaults(self):
        result = VerificationResult()
        assert result.passed is False
        assert result.tool_available is False

    def test_violation_defaults(self):
        v = Violation()
        assert v.file == ""
        assert v.line == 0
        assert v.rule_id == ""


class TestExceptions:
    """测试异常类。"""

    def test_tool_not_found_error(self):
        err = ToolNotFoundError("z3")
        assert err.tool_name == "z3"
        assert "z3" in str(err)

    def test_tool_not_found_custom_message(self):
        err = ToolNotFoundError("cbmc", "CBMC is required but not installed")
        assert "CBMC is required" in str(err)

    def test_stage_execution_error(self):
        err = StageExecutionError("compile", "gcc not found")
        assert err.stage_name == "compile"
        assert "compile" in str(err)

    def test_verification_error(self):
        err = VerificationError("z3", "solver timeout")
        assert err.tool_name == "z3"
        assert "z3" in str(err)


class TestEnums:
    """测试枚举类。"""

    def test_agent_mode_values(self):
        assert AgentMode.MOCK.name == "MOCK"
        assert AgentMode.LLM.name == "LLM"

    def test_hil_connection_state_values(self):
        assert HILConnectionState.DISCONNECTED.name == "DISCONNECTED"
        assert HILConnectionState.CONNECTED.name == "CONNECTED"
