"""LLR 生成 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _push_agent_thought,
    _normalize_hook,
)


class LLRGenStage:
    """从高层需求推导低层需求。"""

    @property
    def name(self) -> str:
        return "llr_gen"

    @property
    def description(self) -> str:
        return "从高层需求推导低层需求"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.agents.llr_generator import LLRGeneratorAgent

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        req_json = artifact["requirement"]

        await _push_agent_thought(
            hook,
            "LLR-Gen",
            "LLR 生成 Agent 启动：从高层需求推导低层需求",
        )
        llr_agent = LLRGeneratorAgent()
        hlr_list = [req_json]
        safety_level = req_json.get("safety_level", "DAL-C")
        module_name = req_json.get("module_name", "")
        llr_result = await llr_agent.generate(hlr_list, safety_level, module_name)
        await hook(
            "LLR-Gen",
            "success",
            f"LLR 生成完成 HLR {llr_result['hlr_count']} 条 → LLR {llr_result['llr_count']} 条",
        )
        req_json["llr_result"] = llr_result
        return StageResult(artifact=artifact, status="success")
