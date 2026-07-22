"""HIL 检查点 Stage。"""

from __future__ import annotations

import json
from typing import Any

from skyforge_engine.core.protocols import StageResult
from skyforge_engine.core.stages._utils import (
    _normalize_hook,
    _run_hil_checkpoint,
)


class HILCheckpointStage:
    """HIL 人工检查点审批 Stage。"""

    def __init__(
        self,
        checkpoint: str,
        content_key: str,
        task_id_key: str = "task_id",
    ) -> None:
        self._checkpoint = checkpoint
        self._content_key = content_key
        self._task_id_key = task_id_key

    @property
    def name(self) -> str:
        return f"hil_{self._checkpoint}"

    @property
    def description(self) -> str:
        return f"HIL 检查点: {self._checkpoint}"

    async def execute(
        self, artifact: dict[str, Any], context: dict[str, Any] | None = None
    ) -> StageResult:
        context = context or {}
        hook = _normalize_hook(context.get("log_hook"))
        task_id = context.get("task_id", "")

        if self._content_key == "requirement":
            content = json.dumps(
                artifact.get("requirement", {}), ensure_ascii=False, indent=2
            )
        else:
            content = artifact.get(self._content_key, "")

        result = await _run_hil_checkpoint(
            checkpoint=self._checkpoint,
            content=content,
            hook=hook,
            task_id=task_id,
        )

        if "hil_approvals" not in artifact:
            artifact["hil_approvals"] = {}
        artifact["hil_approvals"][self._checkpoint] = result

        if not result.get("approved", False) and not result.get("pipeline_continue", False):
            return StageResult(
                artifact=artifact,
                status="failure",
                errors=(f"{self._checkpoint} rejected",),
            )

        return StageResult(artifact=artifact, status="success")
