"""Pipeline Orchestrator。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from skyforge_engine.core.protocols import PipelineStageProtocol, StageResult, StageExecutionError
from skyforge_engine.utils.log_util import logger


class PipelineOrchestrator:
    """Pipeline 编排器。

    支持串行执行、并行组、失败策略和产物传递。
    """

    def __init__(
        self,
        stages: list[PipelineStageProtocol],
        config: dict[str, Any] | None = None,
    ) -> None:
        self.stages = stages
        self.config = config or {}

    async def run(
        self,
        initial_artifact: Any,
        context: dict[str, Any] | None = None,
    ) -> list[StageResult]:
        """执行所有 Stage，返回结果列表。

        Args:
            initial_artifact: 初始产物。
            context: 执行上下文。

        Returns:
            每个 Stage 的 StageResult 列表。
        """
        context = context or {}
        artifact = initial_artifact
        results: list[StageResult] = []

        parallel_groups: list[list[str]] = self.config.get("parallel_groups", [])
        on_failure: str = self.config.get("on_stage_failure", "stop")
        max_retries: int = self.config.get("max_retries", 1)

        # 构建并行组映射：stage name -> group index
        stage_to_group: dict[str, int] = {}
        for group_idx, group in enumerate(parallel_groups):
            for stage_name in group:
                stage_to_group[stage_name] = group_idx

        executed_group_indices: set[int] = set()
        i = 0
        while i < len(self.stages):
            stage = self.stages[i]
            group_idx = stage_to_group.get(stage.name)

            if group_idx is not None:
                if group_idx not in executed_group_indices:
                    # 执行整个并行组
                    group_names = parallel_groups[group_idx]
                    group_stages = [s for s in self.stages if s.name in group_names]
                    group_results = await self._run_parallel_group(
                        group_stages, artifact, context, on_failure, max_retries
                    )
                    results.extend(group_results)

                    # 更新 artifact 为最后一个成功/失败 stage 的产物
                    if group_results:
                        artifact = group_results[-1].artifact

                    # 检查是否有失败
                    if any(r.status == "failure" for r in group_results):
                        if on_failure == "stop":
                            executed_group_indices.add(group_idx)
                            break

                    executed_group_indices.add(group_idx)
                # 无论是否刚执行完，属于已执行并行组的 stage 都跳过单独执行
                i += 1
                continue

            # 串行执行单个 stage
            result = await self._run_stage_with_retry(
                stage, artifact, context, on_failure, max_retries
            )
            results.append(result)
            artifact = result.artifact

            if result.status == "failure" and on_failure == "stop":
                break

            i += 1

        return results

    async def _run_parallel_group(
        self,
        stages: list[PipelineStageProtocol],
        artifact: Any,
        context: dict[str, Any],
        on_failure: str,
        max_retries: int,
    ) -> list[StageResult]:
        """并行执行一组 Stage。"""
        # 每个并行 stage 拿到同一个 artifact 副本
        tasks = []
        for stage in stages:
            # 深拷贝 artifact 避免并发修改冲突（简单 dict 复制）
            import copy

            artifact_copy = copy.deepcopy(artifact)
            tasks.append(
                self._run_single_stage(stage, artifact_copy, context)
            )

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果并合并产物
        results: list[StageResult] = []
        merged_artifact = artifact
        for stage, raw in zip(stages, raw_results):
            if isinstance(raw, Exception):
                result = StageResult(
                    artifact=artifact,
                    status="failure",
                    errors=(str(raw),),
                )
            else:
                result = raw
                # 合并产物：用当前 stage 的产物更新 merged_artifact
                if isinstance(result.artifact, dict):
                    merged_artifact = self._merge_artifacts(
                        merged_artifact, result.artifact
                    )
            results.append(result)

        # 用合并后的产物更新所有结果的 artifact（保持一致性）
        updated_results = []
        for result in results:
            updated_results.append(
                StageResult(
                    artifact=merged_artifact,
                    status=result.status,
                    duration_ms=result.duration_ms,
                    provenance=result.provenance,
                    warnings=result.warnings,
                    errors=result.errors,
                )
            )

        return updated_results

    async def _run_stage_with_retry(
        self,
        stage: PipelineStageProtocol,
        artifact: Any,
        context: dict[str, Any],
        on_failure: str,
        max_retries: int,
    ) -> StageResult:
        """执行单个 Stage，支持重试。"""
        last_result: StageResult | None = None
        for attempt in range(max_retries):
            try:
                result = await self._run_single_stage(stage, artifact, context)
                last_result = result
                if result.status != "failure":
                    return result
                if on_failure != "retry":
                    return result
            except Exception as e:
                logger.warning(f"Stage {stage.name} attempt {attempt + 1} failed: {e}")
                last_result = StageResult(
                    artifact=artifact,
                    status="failure",
                    errors=(str(e),),
                )
                if on_failure != "retry":
                    raise

        return last_result or StageResult(
            artifact=artifact, status="failure", errors=("No result",)
        )

    async def _run_single_stage(
        self,
        stage: PipelineStageProtocol,
        artifact: Any,
        context: dict[str, Any],
    ) -> StageResult:
        """执行单个 Stage 并记录耗时。"""
        start = time.perf_counter()
        try:
            result = await stage.execute(artifact, context)
            duration_ms = (time.perf_counter() - start) * 1000
            return StageResult(
                artifact=result.artifact,
                status=result.status,
                duration_ms=duration_ms,
                provenance=result.provenance,
                warnings=result.warnings,
                errors=result.errors,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Stage {stage.name} execution error: {e}")
            raise StageExecutionError(stage.name, str(e), cause=e) from e

    @staticmethod
    def _merge_artifacts(base: Any, override: Any) -> Any:
        """合并产物字典。"""
        if isinstance(base, dict) and isinstance(override, dict):
            merged = dict(base)
            merged.update(override)
            return merged
        return override
