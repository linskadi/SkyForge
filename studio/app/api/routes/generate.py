"""Legacy WebSocket compatibility endpoint (DEPRECATED).

.. deprecated::
    ``/ws/agent-stream`` is deprecated as of V1.0 and will be removed in V2.0.
    New clients should use the V1 TaskService flow:

    1. ``POST /api/v1/tasks`` to create a task and obtain ``task_id``.
    2. ``WS /api/v1/tasks/{task_id}/events`` to subscribe to its event stream.

    This endpoint is preserved for one release to keep existing clients
    working. It still creates a task via the V1 ``TaskService`` (single owner
    of pipeline execution) and streams events through the shared
    ``TaskStreamRegistry``; it just does both in one socket call.

    New clients use POST /api/v1/tasks and the subscribe-only V1 socket.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.streaming import get_task_stream_registry
from app.db import SessionLocal
from app.repositories import task_history_repo, task_repo
from app.services.task_service import get_task_service
from app.utils.log_util import logger
from skyforge_engine.config import settings

router = APIRouter()

DEPRECATION_MIGRATION_URL = "/api/v1/tasks/{task_id}/events"


def _resolve_legacy_profile_id(data: dict) -> str:
    profile_id = data.get("profile_id")
    if profile_id in {"cloud", "local"}:
        return str(profile_id)
    return "cloud" if settings.SKYFORGE_LLM_MODE == "api" else "local"


@router.websocket("/ws/agent-stream")
async def agent_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    # Phase 5: notify legacy clients about the V2 channel so they can migrate.
    # We send a deprecation warning immediately on connect, but still process
    # subsequent messages to preserve the one-release compatibility contract.
    await websocket.send_json({
        "type": "deprecation_warning",
        "level": "warn",
        "agent": "SYSTEM",
        "thought": "/ws/agent-stream is deprecated, use /api/v1/tasks/{task_id}/events instead",
        "message": "/ws/agent-stream is deprecated, use /api/v1/tasks/{task_id}/events instead",
        "time": datetime.now().isoformat(),
        "migration": DEPRECATION_MIGRATION_URL,
    })
    registry = get_task_stream_registry()
    active_subscriptions: set[str] = set()
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                data = {"requirement": str(data)}

            task_id = str(data.get("task_id") or "")
            if data.get("action") == "subscribe" and task_id:
                if await _subscribe_existing(websocket, task_id):
                    active_subscriptions.add(task_id)
                continue

            requirement = str(data.get("requirement") or "")
            scade_file = str(data.get("scade_file") or "")
            if not requirement and not scade_file:
                await websocket.send_json(_message(
                    "error", "必须提供 requirement 或 scade_file 至少一项"
                ))
                continue

            service = get_task_service()
            created = await service.create(
                requirement=requirement or f"SCADE input ({len(scade_file)} bytes)",
                scade_file=scade_file or None,
                language=str(data.get("language") or "c"),
                profile_id=_resolve_legacy_profile_id(data),
                idempotency_key=str(data.get("idempotency_key") or f"legacy-ws-{uuid4().hex}"),
            )
            task_id = created["id"]
            if await registry.add_subscriber(task_id, websocket):
                active_subscriptions.add(task_id)
            # Execution and persistence are owned by TaskService; this await
            # never invokes run_full_pipeline a second time.
            await service.wait(task_id)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(f"legacy agent-stream closed: {exc}")
    finally:
        for task_id in active_subscriptions:
            await registry.remove_subscriber(task_id, websocket)


def _message(level: str, thought: str, **extra):
    return {
        "agent": "SYSTEM",
        "level": level,
        "thought": thought,
        "message": thought,
        "time": datetime.now().isoformat(),
        **extra,
    }


async def _subscribe_existing(websocket: WebSocket, task_id: str) -> bool:
    registry = get_task_stream_registry()
    if await registry.add_subscriber(task_id, websocket):
        return True

    with SessionLocal() as db:
        task = task_repo.get(db, task_id)
        if task is not None:
            if task.status in {"queued", "running"}:
                await websocket.send_json(_message(
                    "warn", f"任务 {task_id} 无活跃执行器，可能已被中断"
                ))
            else:
                detail = task_repo.serialize_task(task)
                await websocket.send_json(_message(
                    "complete", f"任务 {task_id} 已完成（status={task.status}）",
                    type="complete", result=detail.get("result"),
                ))
            return False

        legacy = task_history_repo.get(db, task_id)
        if legacy is not None:
            await websocket.send_json(_message(
                "complete", f"legacy 任务 {task_id} 仅保留摘要",
                type="complete",
                result={"requirement": legacy.requirement, "final_code": ""},
            ))
            return False

    await websocket.send_json(_message("error", f"任务 {task_id} 不存在或已过期"))
    return False
