"""Single-entry task orchestration service used by the V1 API.

Creating a task and subscribing to it are intentionally separate operations.
WebSocket connections can only observe an existing task and therefore cannot
accidentally start duplicate LLM pipelines.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
from uuid import uuid4

from app.core.llm.local_llm_client import get_local_llm_client
from app.core.streaming import get_task_stream_registry
from app.db import SessionLocal
from app.repositories import task_repo
from skyforge_engine.config import settings
from skyforge_engine.execution import ExecutionContext, ToolPolicy
from skyforge_engine.pipeline import run_full_pipeline
from skyforge_engine.utils.log_util import logger


_STAGE_PROGRESS: dict[str, tuple[str, int]] = {
    "REQ-Parser": ("requirement", 14),
    "LLR-Gen": ("llr", 28),
    "ARCH-Designer": ("architecture", 36),
    "CON-Gen": ("contract", 45),
    "CODE-Gen": ("code", 60),
    "REPAIR": ("repair", 75),
    "TERMINAL": ("verification", 86),
    "SYSTEM": ("verification", 86),
}


_LLM_ENV_KEYS = (
    "SKYFORGE_LLM_MODE",
    "SKYFORGE_LLM_PROVIDER",
    "USE_LLM",
    "LLM_API_KEY",
    "LOCAL_LLM_BASE_URL",
    "LMSTUDIO_BASE_URL",
    "LLM_MODEL",
)


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _build_provenance(
    result: dict[str, Any], context: ExecutionContext
) -> dict[str, Any]:
    return {
        "profile_id": context.profile_id,
        "source": "live",
        "llm": {
            "status": "observed",
            "engine": context.provider,
            "model": context.model,
        },
        "tools": result.get("tool_evidence", {}),
        "execution_context": dataclasses.asdict(context),
        "disclaimer": (
            "SkyForge 输出为 DO-178C 工程辅助证据，不代表工具已完成适航鉴定。"
        ),
    }


def _task_llm_config(profile_id: str) -> dict[str, str | None]:
    if not settings.USE_LLM or settings.SKYFORGE_LLM_MODE == "mock":
        return {
            "mode": "mock",
            "provider": None,
            "api_key": None,
            "base_url": settings.LOCAL_LLM_BASE_URL or settings.LMSTUDIO_BASE_URL,
            "model": settings.LLM_MODEL,
        }

    mode = "local" if profile_id == "local" else "api"
    base_url = settings.LOCAL_LLM_BASE_URL or settings.LMSTUDIO_BASE_URL
    model = settings.LLM_MODEL
    if mode == "local" and settings.SKYFORGE_LLM_MODE != "local":
        base_url = "http://localhost:11434/v1"
        model = None
    return {
        "mode": mode,
        "provider": settings.SKYFORGE_LLM_PROVIDER if mode == "api" else "local",
        "api_key": settings.LLM_API_KEY if mode == "api" else None,
        "base_url": base_url,
        "model": model,
    }


def _display_model(config: dict[str, str | None]) -> str | None:
    if config["mode"] == "local":
        return config["model"] or os.environ.get("LMSTUDIO_MODEL", "qwen3:8b")
    return config["model"]


@contextmanager
def _apply_task_llm_profile(profile_id: str) -> Iterator[dict[str, str | None]]:
    config = _task_llm_config(profile_id)
    old_env = {key: os.environ.get(key) for key in _LLM_ENV_KEYS}
    old_settings = {
        "SKYFORGE_LLM_MODE": settings.SKYFORGE_LLM_MODE,
        "SKYFORGE_LLM_PROVIDER": settings.SKYFORGE_LLM_PROVIDER,
        "USE_LLM": settings.USE_LLM,
        "LLM_API_KEY": settings.LLM_API_KEY,
        "LOCAL_LLM_BASE_URL": settings.LOCAL_LLM_BASE_URL,
        "LMSTUDIO_BASE_URL": settings.LMSTUDIO_BASE_URL,
        "LLM_MODEL": settings.LLM_MODEL,
    }

    try:
        mode = str(config["mode"])
        os.environ["SKYFORGE_LLM_MODE"] = mode
        os.environ["USE_LLM"] = "false" if mode == "mock" else "true"
        settings.SKYFORGE_LLM_MODE = mode
        settings.USE_LLM = mode != "mock"

        provider = config["provider"]
        if provider:
            os.environ["SKYFORGE_LLM_PROVIDER"] = provider
        else:
            os.environ.pop("SKYFORGE_LLM_PROVIDER", None)
        settings.SKYFORGE_LLM_PROVIDER = provider

        api_key = config["api_key"]
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
        else:
            os.environ.pop("LLM_API_KEY", None)
        settings.LLM_API_KEY = api_key

        base_url = config["base_url"]
        if base_url:
            os.environ["LOCAL_LLM_BASE_URL"] = base_url
            os.environ["LMSTUDIO_BASE_URL"] = base_url
            settings.LOCAL_LLM_BASE_URL = base_url
            settings.LMSTUDIO_BASE_URL = base_url

        model = config["model"]
        if model:
            os.environ["LLM_MODEL"] = model
        else:
            os.environ.pop("LLM_MODEL", None)
        settings.LLM_MODEL = model

        get_local_llm_client().apply_config(
            mode=mode,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        yield config
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in old_settings.items():
            setattr(settings, key, value)
        get_local_llm_client().apply_config(
            mode=str(old_settings["SKYFORGE_LLM_MODE"]),
            provider=old_settings["SKYFORGE_LLM_PROVIDER"],
            api_key=old_settings["LLM_API_KEY"],
            base_url=old_settings["LOCAL_LLM_BASE_URL"],
            model=old_settings["LLM_MODEL"],
        )


class TaskService:
    """Owns task creation, execution, cancellation, and event publication."""

    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task[None]] = {}
        self._create_lock = asyncio.Lock()
        self._event_locks: dict[str, asyncio.Lock] = {}
        self._local_slots = asyncio.Semaphore(1)
        self._cloud_slots = asyncio.Semaphore(2)
        self._llm_config_lock = asyncio.Lock()

    async def create(
        self,
        *,
        requirement: str,
        language: str,
        profile_id: str,
        idempotency_key: str,
        scade_file: str | None = None,
    ) -> dict[str, Any]:
        # Serialize the check-and-create section so concurrent duplicate clicks
        # cannot both pass the idempotency lookup before the unique constraint.
        async with self._create_lock:
            with SessionLocal() as db:
                existing = task_repo.get_by_idempotency(db, idempotency_key)
                if existing is not None:
                    return task_repo.serialize_task(existing, include_result=False)

                task_id = f"TASK-{uuid4().hex[:16].upper()}"
                task = task_repo.create_task(
                    db,
                    task_id=task_id,
                    idempotency_key=idempotency_key,
                    requirement=requirement,
                    language=language,
                    profile_id=profile_id,
                )
                payload = task_repo.serialize_task(task, include_result=False)

            registry = get_task_stream_registry()
            await registry.register_task(task_id)
            self._event_locks[task_id] = asyncio.Lock()
            runner = asyncio.create_task(
                self._run(
                    task_id=task_id,
                    requirement=requirement,
                    language=language,
                    profile_id=profile_id,
                    scade_file=scade_file,
                ),
                name=f"skyforge-{task_id}",
            )
            self._running[task_id] = runner
            runner.add_done_callback(lambda _done: self._running.pop(task_id, None))
            return payload

    async def cancel(self, task_id: str) -> bool:
        runner = self._running.get(task_id)
        if runner is None:
            return False
        runner.cancel()
        return True

    async def wait(self, task_id: str) -> dict[str, Any] | None:
        """Wait for an existing task without creating another execution."""
        runner = self._running.get(task_id)
        if runner is not None:
            await runner
        with SessionLocal() as db:
            task = task_repo.get(db, task_id)
            return task_repo.serialize_task(task) if task is not None else None

    async def _publish(
        self,
        task_id: str,
        *,
        agent: str,
        level: str,
        message: str,
        evidence_status: str = "observed",
    ) -> dict[str, Any]:
        stage, progress = _STAGE_PROGRESS.get(agent, ("verification", 86))
        if "仿真" in message:
            stage, progress = "simulation", 92
        if "证据" in message or level == "complete":
            stage, progress = "evidence", 98
        event_lock = self._event_locks.setdefault(task_id, asyncio.Lock())
        async with event_lock:
            with SessionLocal() as db:
                event = task_repo.append_event(
                    db,
                    task_id=task_id,
                    stage=stage,
                    level=level,
                    agent=agent,
                    message=message,
                    evidence_status=evidence_status,
                )
                task_repo.update_task(
                    db,
                    task_id,
                    current_stage=stage,
                    progress=progress,
                    status="running",
                )
                data = task_repo.serialize_event(event)
        await get_task_stream_registry().broadcast(task_id, data)
        return data

    async def _run(
        self,
        *,
        task_id: str,
        requirement: str,
        language: str,
        profile_id: str,
        scade_file: str | None,
    ) -> None:
        started = time.perf_counter()
        semaphore = self._local_slots if profile_id == "local" else self._cloud_slots
        task_llm_config = _task_llm_config(profile_id)
        context = ExecutionContext(
            profile_id=profile_id,
            provider=(
                task_llm_config["provider"]
                or ("openai-compatible-local" if profile_id == "local" else "cloud-api")
            ),
            model=_display_model(task_llm_config),
            task_id=task_id,
            timeout_seconds=600 if profile_id == "local" else 120,
            max_concurrency=1 if profile_id == "local" else 2,
            tool_policy=ToolPolicy(
                use_real_gcc=settings.USE_REAL_GCC,
                use_real_cppcheck=settings.USE_REAL_CPPCHECK,
            ),
        )

        async def log_hook(agent: str, level: str, message: str) -> None:
            evidence_status = "observed"
            if "Mock" in message or "mock" in message or "降级" in message:
                evidence_status = "simulated"
            await self._publish(
                task_id,
                agent=agent,
                level=level,
                message=message,
                evidence_status=evidence_status,
            )

        try:
            async with semaphore:
                with SessionLocal() as db:
                    task_repo.update_task(
                        db,
                        task_id,
                        provenance_json=json.dumps(
                            {
                                "profile_id": profile_id,
                                "source": "live",
                                "execution_context": dataclasses.asdict(context),
                            },
                            ensure_ascii=False,
                        ),
                    )
                await self._publish(
                    task_id,
                    agent="SYSTEM",
                    level="info",
                    message=f"任务已创建，执行配置：{profile_id}",
                )
                async with self._llm_config_lock:
                    with _apply_task_llm_profile(profile_id):
                        raw_result = await asyncio.wait_for(
                            run_full_pipeline(
                                requirement=requirement,
                                scade_file=scade_file,
                                language=language,
                                log_hook=log_hook,
                                execution_context=context,
                            ),
                            timeout=context.timeout_seconds,
                        )
                result = _jsonable(raw_result)
                if "code" not in result and "final_code" in result:
                    result["code"] = result["final_code"]
                if "violations" not in result and "final_violations" in result:
                    result["violations"] = result["final_violations"]
                if "traceability" not in result:
                    req_id = (result.get("requirement") or {}).get("req_id", "REQ-001")
                    result["traceability"] = {req_id: []}
                requirement_data = result.get("requirement") or {}
                requirement_id = (
                    requirement_data.get("req_id")
                    if isinstance(requirement_data, dict)
                    else None
                )
                provenance = _build_provenance(result, context)
                duration_ms = int((time.perf_counter() - started) * 1000)
                with SessionLocal() as db:
                    task_repo.update_task(
                        db,
                        task_id,
                        requirement_id=requirement_id,
                        status="done",
                        current_stage="done",
                        progress=100,
                        result_json=json.dumps(result, ensure_ascii=False),
                        provenance_json=json.dumps(provenance, ensure_ascii=False),
                        duration_ms=duration_ms,
                    )
                    event = task_repo.append_event(
                        db,
                        task_id=task_id,
                        stage="done",
                        level="complete",
                        agent="SYSTEM",
                        message="全流程完成",
                        evidence_status="observed",
                    )
                    complete = task_repo.serialize_event(event)
                complete["type"] = "complete"
                complete["result"] = result
                complete["provenance"] = provenance
                await get_task_stream_registry().broadcast(task_id, complete)
        except asyncio.CancelledError:
            await self._publish(
                task_id,
                agent="SYSTEM",
                level="warn",
                message="任务已取消",
            )
            with SessionLocal() as db:
                task_repo.update_task(
                    db,
                    task_id,
                    status="cancelled",
                    current_stage="cancelled",
                    error="任务已由用户取消",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            await get_task_stream_registry().broadcast(
                task_id,
                {
                    "type": "complete",
                    "level": "complete",
                    "status": "cancelled",
                    "message": "任务已取消",
                    "result": None,
                    "time": datetime.now().isoformat(),
                },
            )
        except TimeoutError:
            await self._publish(
                task_id,
                agent="SYSTEM",
                level="error",
                message=f"任务超过 {context.timeout_seconds}s 超时限制",
            )
            with SessionLocal() as db:
                task_repo.update_task(
                    db,
                    task_id,
                    status="timeout",
                    current_stage="timeout",
                    error=f"execution timeout after {context.timeout_seconds}s",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            await get_task_stream_registry().broadcast(
                task_id,
                {
                    "type": "complete",
                    "level": "complete",
                    "status": "timeout",
                    "message": "任务已超时",
                    "result": None,
                    "time": datetime.now().isoformat(),
                },
            )
        except Exception as exc:
            logger.exception(f"TaskService: task {task_id} failed: {exc}")
            await self._publish(
                task_id,
                agent="SYSTEM",
                level="error",
                message=f"流水线异常：{exc}",
            )
            with SessionLocal() as db:
                task_repo.update_task(
                    db,
                    task_id,
                    status="error",
                    current_stage="error",
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            await get_task_stream_registry().broadcast(
                task_id,
                {
                    "type": "complete",
                    "level": "complete",
                    "agent": "SYSTEM",
                    "message": "任务以失败状态结束",
                    "thought": "任务以失败状态结束",
                    "status": "error",
                    "result": None,
                    "time": datetime.now().isoformat(),
                },
            )
        finally:
            await get_task_stream_registry().finish_task(task_id)


_task_service: TaskService | None = None


def get_task_service() -> TaskService:
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
