"""测试 PipelineOrchestrator 与 Stage 分层。"""

from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from skyforge_engine.core.orchestrator import PipelineOrchestrator
from skyforge_engine.core.protocols import PipelineStageProtocol, StageResult
from skyforge_engine.core.stages import (
    ArchitectureDesignStage,
    CodeGenStage,
    ContractGenStage,
    CppcheckStage,
    FormalVerificationStage,
    HILCheckpointStage,
    LLRGenStage,
    RepairLoopStage,
    ReportGenStage,
    RequirementParseStage,
    SimulationStage,
)


# ---------------------------------------------------------------------------
# Dummy Stage 辅助类
# ---------------------------------------------------------------------------

class DummyStage:
    """测试用 dummy stage，可配置名称和行为。"""

    def __init__(self, name: str, description: str = "", return_value: Any = None, fail: bool = False):
        self._name = name
        self._description = description
        self._return_value = return_value
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    async def execute(self, artifact: Any, context: dict[str, Any] | None = None) -> StageResult:
        if self._fail:
            return StageResult(artifact=artifact, status="failure", errors=("failed",))
        if isinstance(artifact, dict) and self._return_value is not None:
            artifact[self._name] = self._return_value
        return StageResult(artifact=artifact, status="success")


class AddStage:
    """向 artifact 的 value 累加的 stage。"""

    def __init__(self, name: str, add: int):
        self._name = name
        self._add = add

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"add {self._add}"

    async def execute(self, artifact: Any, context: dict[str, Any] | None = None) -> StageResult:
        if isinstance(artifact, dict):
            artifact["value"] = artifact.get("value", 0) + self._add
        return StageResult(artifact=artifact, status="success")


# ---------------------------------------------------------------------------
# Orchestrator 基础测试
# ---------------------------------------------------------------------------

class TestPipelineOrchestrator:
    def test_empty_stages(self):
        """空 Stage 列表返回空结果。"""
        orchestrator = PipelineOrchestrator([])
        results = asyncio.run(orchestrator.run({}))
        assert results == []

    def test_serial_execution(self):
        """串行执行并正确传递产物。"""
        stages = [AddStage("a", 1), AddStage("b", 2), AddStage("c", 3)]
        orchestrator = PipelineOrchestrator(stages)
        results = asyncio.run(orchestrator.run({"value": 0}))
        assert len(results) == 3
        assert results[-1].artifact["value"] == 6
        for r in results:
            assert r.status == "success"

    def test_parallel_group_execution(self):
        """并行组内 Stage 同时执行，产物合并。"""

        class SetStage:
            def __init__(self, name, key, value):
                self._name = name
                self._key = key
                self._value = value

            @property
            def name(self):
                return self._name

            @property
            def description(self):
                return f"set {self._key}={self._value}"

            async def execute(self, artifact, context=None):
                artifact[self._key] = self._value
                return StageResult(artifact=artifact, status="success")

        stages = [
            SetStage("parallel_a", "a", 10),
            SetStage("parallel_b", "b", 20),
            AddStage("serial", 1),
        ]
        config = {
            "parallel_groups": [["parallel_a", "parallel_b"]],
        }
        orchestrator = PipelineOrchestrator(stages, config)
        results = asyncio.run(orchestrator.run({"value": 0}))
        # parallel_a 和 parallel_b 并行（修改不同字段），然后 serial +1
        assert len(results) == 3
        final = results[-1].artifact
        assert final.get("a") == 10
        assert final.get("b") == 20
        assert final["value"] == 1

    def test_on_failure_stop(self):
        """失败策略 stop 时遇到 failure 终止。"""
        stages = [
            DummyStage("s1", fail=False),
            DummyStage("s2", fail=True),
            DummyStage("s3", fail=False),
        ]
        orchestrator = PipelineOrchestrator(stages, {"on_stage_failure": "stop"})
        results = asyncio.run(orchestrator.run({}))
        assert len(results) == 2
        assert results[0].status == "success"
        assert results[1].status == "failure"

    def test_on_failure_continue(self):
        """失败策略 continue 时跳过失败继续执行。"""
        stages = [
            DummyStage("s1", fail=False),
            DummyStage("s2", fail=True),
            DummyStage("s3", fail=False),
        ]
        orchestrator = PipelineOrchestrator(stages, {"on_stage_failure": "continue"})
        results = asyncio.run(orchestrator.run({}))
        assert len(results) == 3
        assert results[0].status == "success"
        assert results[1].status == "failure"
        assert results[2].status == "success"

    def test_retry_policy(self):
        """重试策略会多次尝试失败的 stage。"""
        mock_stage = MagicMock(spec=PipelineStageProtocol)
        mock_stage.name = "retry_stage"
        mock_stage.execute = AsyncMock(
            side_effect=[
                StageResult(artifact={}, status="failure", errors=("err",)),
                StageResult(artifact={}, status="success"),
            ]
        )
        orchestrator = PipelineOrchestrator(
            [mock_stage], {"on_stage_failure": "retry", "max_retries": 2}
        )
        results = asyncio.run(orchestrator.run({}))
        assert results[-1].status == "success"
        assert mock_stage.execute.call_count == 2

    def test_stage_exception_raises(self):
        """Stage 抛异常时应包装为 StageExecutionError。"""
        from skyforge_engine.core.protocols import StageExecutionError

        mock_stage = MagicMock(spec=PipelineStageProtocol)
        mock_stage.name = "bad_stage"
        mock_stage.execute = AsyncMock(side_effect=RuntimeError("boom"))
        orchestrator = PipelineOrchestrator([mock_stage])
        with pytest.raises(StageExecutionError, match="bad_stage"):
            asyncio.run(orchestrator.run({}))

    def test_parallel_group_failure_stop(self):
        """并行组中任一失败且策略为 stop 时终止。"""
        stages = [
            DummyStage("p1", fail=False),
            DummyStage("p2", fail=True),
            DummyStage("s3", fail=False),
        ]
        orchestrator = PipelineOrchestrator(
            stages, {"parallel_groups": [["p1", "p2"]], "on_stage_failure": "stop"}
        )
        results = asyncio.run(orchestrator.run({}))
        # 并行组执行后应因失败而停止，s3 不执行
        assert len(results) == 2
        assert any(r.status == "failure" for r in results)


# ---------------------------------------------------------------------------
# Stage 协议合规测试
# ---------------------------------------------------------------------------

class TestStageProtocolCompliance:
    def test_requirement_parse_stage_protocol(self):
        stage = RequirementParseStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "requirement_parse"

    def test_llr_gen_stage_protocol(self):
        stage = LLRGenStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "llr_gen"

    def test_architecture_design_stage_protocol(self):
        stage = ArchitectureDesignStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "architecture_design"

    def test_contract_gen_stage_protocol(self):
        stage = ContractGenStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "contract_gen"

    def test_code_gen_stage_protocol(self):
        stage = CodeGenStage(language="cpp")
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "code_gen"

    def test_cppcheck_stage_protocol(self):
        stage = CppcheckStage(language="cpp")
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "cppcheck"

    def test_hil_checkpoint_stage_protocol(self):
        stage = HILCheckpointStage(checkpoint="requirement_review", content_key="requirement")
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "hil_requirement_review"

    def test_formal_verification_stage_protocol(self):
        stage = FormalVerificationStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "formal_verification"

    def test_repair_loop_stage_protocol(self):
        stage = RepairLoopStage(max_iterations=2)
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "repair_loop"

    def test_simulation_stage_protocol(self):
        stage = SimulationStage(simulate=False)
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "simulation"

    def test_report_gen_stage_protocol(self):
        stage = ReportGenStage()
        assert isinstance(stage, PipelineStageProtocol)
        assert stage.name == "report_gen"


# ---------------------------------------------------------------------------
# HILCheckpointStage 行为测试
# ---------------------------------------------------------------------------

class TestHILCheckpointStage:
    @pytest.mark.asyncio
    async def test_hil_approved(self):
        """HIL 通过时返回 success。"""
        stage = HILCheckpointStage(checkpoint="requirement_review", content_key="requirement")
        artifact = {"requirement": {"req_id": "REQ-001"}, "hil_approvals": {}}
        with patch(
            "skyforge_engine.core.stages.hil_checkpoint_stage._run_hil_checkpoint",
            new=AsyncMock(return_value={"approved": True, "status": "approved"}),
        ):
            result = await stage.execute(artifact, {"log_hook": None, "task_id": "T1"})
        assert result.status == "success"
        assert artifact["hil_approvals"]["requirement_review"]["approved"] is True

    @pytest.mark.asyncio
    async def test_hil_rejected(self):
        """HIL 拒绝时返回 failure。"""
        stage = HILCheckpointStage(checkpoint="contract_review", content_key="contract")
        artifact = {"contract": "test", "hil_approvals": {}}
        with patch(
            "skyforge_engine.core.stages.hil_checkpoint_stage._run_hil_checkpoint",
            new=AsyncMock(return_value={"approved": False, "status": "rejected"}),
        ):
            result = await stage.execute(artifact, {"log_hook": None, "task_id": "T1"})
        assert result.status == "failure"
        assert "contract_review rejected" in result.errors


# ---------------------------------------------------------------------------
# 向后兼容测试
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_run_pipeline_signature_unchanged(self):
        """run_pipeline 函数签名保持不变。"""
        import inspect
        from skyforge_engine.pipeline import run_pipeline

        sig = inspect.signature(run_pipeline)
        params = list(sig.parameters.keys())
        assert params == ["requirement", "scade_file", "language", "log_hook", "task_id"]

    def test_repair_loop_signature_unchanged(self):
        """repair_loop 函数签名保持不变。"""
        import inspect
        from skyforge_engine.pipeline import repair_loop

        sig = inspect.signature(repair_loop)
        params = list(sig.parameters.keys())
        assert params == ["code", "contract", "max_iterations", "req_id", "log_hook"]

    def test_run_full_pipeline_signature_unchanged(self):
        """run_full_pipeline 函数签名保持不变。"""
        import inspect
        from skyforge_engine.pipeline import run_full_pipeline

        sig = inspect.signature(run_full_pipeline)
        params = list(sig.parameters.keys())
        assert params == [
            "requirement",
            "scade_file",
            "log_hook",
            "simulate",
            "language",
            "execution_context",
        ]

    def test_run_pipeline_deprecated_warning(self):
        """run_pipeline 调用时发出 DeprecationWarning。"""
        from skyforge_engine.pipeline import run_pipeline

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # 触发警告（由于内部逻辑复杂，直接调用包装器会触发）
            # 使用一个不会走到内部逻辑的调用
            try:
                asyncio.run(run_pipeline(requirement=""))
            except ValueError:
                pass
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            # 至少有一个 DeprecationWarning（由 @deprecated 触发）
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()


# ---------------------------------------------------------------------------
# Pipeline 集成测试（mock Agent）
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_run_pipeline_mock_mode(self):
        """mock 模式下 run_pipeline 正常完成。"""
        import os
        from skyforge_engine import pipeline as pipeline_module
        from skyforge_engine.pipeline import run_pipeline

        mock_req_json = {
            "req_id": "REQ-001",
            "desc": "test",
            "type": "generic",
            "module_name": "mod",
            "safety_level": "DAL-C",
        }
        mock_contract = "component: mod\n"
        mock_code = "int main(void){return 0;}"

        with patch.dict(os.environ, {"SKYFORGE_LLM_MODE": "mock"}), \
             patch.object(pipeline_module, "RequirementParseStage") as MockParser, \
             patch.object(pipeline_module, "LLRGenStage") as MockLLR, \
             patch.object(pipeline_module, "ArchitectureDesignStage") as MockArch, \
             patch.object(pipeline_module, "HILCheckpointStage") as MockHIL, \
             patch.object(pipeline_module, "ContractGenStage") as MockContract, \
             patch.object(pipeline_module, "FormalVerificationStage") as MockFormal, \
             patch.object(pipeline_module, "CodeGenStage") as MockCode, \
             patch.object(pipeline_module, "CppcheckStage") as MockCppcheck:

            # 配置 mock stages
            def make_mock_stage(name, updates=None, fail=False):
                m = MagicMock()
                m.name = name
                async def _execute(artifact, context=None):
                    if fail:
                        return StageResult(artifact=artifact, status="failure", errors=("fail",))
                    if updates:
                        artifact.update(updates)
                    return StageResult(artifact=artifact, status="success")
                m.execute = _execute
                return m

            MockParser.return_value = make_mock_stage("requirement_parse", {"requirement": mock_req_json})
            MockLLR.return_value = make_mock_stage("llr_gen")
            MockArch.return_value = make_mock_stage("architecture_design")
            MockHIL.side_effect = lambda **kwargs: make_mock_stage(f"hil_{kwargs['checkpoint']}")
            MockContract.return_value = make_mock_stage("contract_gen", {"contract": mock_contract})
            MockFormal.return_value = make_mock_stage("formal_verification")
            MockCode.return_value = make_mock_stage("code_gen", {"code": mock_code})
            MockCppcheck.return_value = make_mock_stage("cppcheck", {"cppcheck_result": []})

            result = asyncio.run(run_pipeline(requirement="test req"))

        assert result["requirement"]["req_id"] == "REQ-001"
        assert result["contract"] == mock_contract
        assert result["code"] == mock_code

    def test_repair_loop_mock_mode(self):
        """mock 模式下 repair_loop 正常完成。"""
        from skyforge_engine.pipeline import repair_loop

        mock_repair_result = {
            "final_code": "int main(){return 0;}",
            "repair_history": [],
            "final_violations": [],
            "contract_check_result": None,
        }

        with patch(
            "skyforge_engine.pipeline.RepairLoopStage.execute",
            new=AsyncMock(
                return_value=StageResult(
                    artifact={"repair_result": mock_repair_result},
                    status="success",
                )
            ),
        ):
            result = asyncio.run(repair_loop(code="int main(){return 0;}", contract=""))

        assert result["final_code"] == "int main(){return 0;}"
