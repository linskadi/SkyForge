"""需求解析 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _push_agent_thought,
    _normalize_hook,
)


class RequirementParseStage:
    """解析自然语言需求并生成结构化需求标签。"""

    @property
    def name(self) -> str:
        return "requirement_parse"

    @property
    def description(self) -> str:
        return "解析自然语言需求并生成结构化需求标签"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.agents.requirement_parser import RequirementParserAgent

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))

        await _push_agent_thought(
            hook,
            "REQ-Parser",
            "需求解析 Agent 启动：解析自然语言需求并生成结构化需求标签",
        )
        parser = RequirementParserAgent()
        req_json = await parser.run(artifact["requirement"])
        await hook(
            "REQ-Parser",
            "success",
            f"需求解析完成 req_id={req_json['req_id']}",
        )
        artifact["requirement"] = req_json
        return StageResult(artifact=artifact, status="success")
