"""架构设计 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _push_agent_thought,
    _normalize_hook,
)
from skyforge_engine.utils.log_util import logger


class ArchitectureDesignStage:
    """模块划分 + 接口定义 + 状态机设计。"""

    @property
    def name(self) -> str:
        return "architecture_design"

    @property
    def description(self) -> str:
        return "模块划分 + 接口定义 + 状态机设计"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        req_json = artifact["requirement"]

        await _push_agent_thought(
            hook,
            "ARCH-Designer",
            "架构设计 Agent 启动：模块划分 + 接口定义 + 状态机设计",
        )
        try:
            from skyforge_engine.agents.architecture_designer import design_architecture

            hlr_list = [req_json]
            llr_result = req_json.get("llr_result", {})
            module_name = req_json.get("module_name", "")
            safety_level = req_json.get("safety_level", "DAL-C")
            arch_result = design_architecture(
                hlr_list,
                llr_list=llr_result.get("llr_list", []),
                module_name=module_name,
                safety_level=safety_level,
            )
            req_json["architecture"] = {
                "modules": len(arch_result.modules),
                "state_machine": arch_result.state_machine,
                "interface_spec": arch_result.interface_spec,
                "generated_by": arch_result.generated_by,
            }
            await hook(
                "ARCH-Designer",
                "success",
                f"架构设计完成 {len(arch_result.modules)} 模块，"
                f"状态机 {len(arch_result.state_machine.get('states', []))} 状态",
            )
        except ImportError:
            await hook("ARCH-Designer", "info", "架构设计 Agent 跳过")
        except Exception as e:
            logger.warning(f"Pipeline:架构设计失败: {e}")

        return StageResult(artifact=artifact, status="success")
