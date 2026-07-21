"""代码生成 Stage。"""

from __future__ import annotations

from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _push_agent_thought,
    _normalize_hook,
)


class CodeGenStage:
    """依据需求和契约生成 MISRA-C 合规代码。"""

    def __init__(self, language: str = "c") -> None:
        self._language = language

    @property
    def name(self) -> str:
        return "code_gen"

    @property
    def description(self) -> str:
        return "依据需求和契约生成 MISRA-C 合规代码"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        from skyforge_engine.agents.code_generator_multi import MultiLanguageCodeGenerator

        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        req_json = artifact["requirement"]
        contract = artifact.get("contract", "")

        await _push_agent_thought(
            hook,
            "CODE-Gen",
            "代码生成 Agent 启动：依据需求和契约生成 MISRA-C 合规代码",
        )
        code_agent = MultiLanguageCodeGenerator()
        code = await code_agent.run(req_json, contract, language=self._language)
        artifact["code"] = code
        await hook("CODE-Gen", "success", "C 代码生成完成")
        return StageResult(artifact=artifact, status="success")
