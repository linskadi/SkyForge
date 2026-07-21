"""契约生成 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _push_agent_thought,
    _normalize_hook,
)


class ContractGenStage:
    """依据需求生成 DO-178C 契约 YAML。"""

    @property
    def name(self) -> str:
        return "contract_gen"

    @property
    def description(self) -> str:
        return "依据需求生成 DO-178C 契约 YAML"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.agents.contract_generator import ContractGeneratorAgent

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        req_json = artifact["requirement"]

        await _push_agent_thought(
            hook,
            "CON-Gen",
            "契约生成 Agent 启动：依据需求生成 DO-178C 契约 YAML",
        )
        contract_agent = ContractGeneratorAgent()
        contract = await contract_agent.run(req_json)
        artifact["contract"] = contract
        await hook("CON-Gen", "success", "契约生成完成")
        return StageResult(artifact=artifact, status="success")
