"""V1 task API: one command channel plus subscribe-only WebSocket events."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.auth import require_write_access
from sqlalchemy.orm import Session

from app.core.streaming import get_task_stream_registry
from app.core.hil.hil_manager import get_hil_manager
from app.db import get_db
from app.repositories import task_repo
from app.services.task_service import get_task_service
from skyforge_engine.config import settings


router = APIRouter(prefix="/api/v1", tags=["tasks-v1"])
_RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "recordings"
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_recording_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_path = (path.parent / data["source_log"]).resolve()
    if _REPO_ROOT.resolve() not in source_path.parents:
        raise ValueError("recording source is outside repository")
    actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    data["hash_verified"] = actual_hash == data["source_log_sha256"]
    data["actual_sha256"] = actual_hash
    return data


class CreateTaskRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=20_000)
    language: Literal["c", "cpp", "python"] = "c"
    profile_id: Literal["cloud", "local"] | None = None
    idempotency_key: str = Field(min_length=8, max_length=96)
    scade_file: str | None = None


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comments: str = Field(default="", max_length=2_000)
    reviewer: str = Field(default="reviewer", min_length=1, max_length=128)


def _resolve_profile_id(
    profile_id: Literal["cloud", "local"] | None,
) -> Literal["cloud", "local"]:
    if profile_id is not None:
        return profile_id
    return "cloud" if settings.SKYFORGE_LLM_MODE == "api" else "local"


@router.post("/tasks", status_code=202)
async def create_task(
    req: CreateTaskRequest,
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    profile_id = _resolve_profile_id(req.profile_id)
    task = await get_task_service().create(
        requirement=req.requirement.strip(),
        language=req.language,
        profile_id=profile_id,
        idempotency_key=req.idempotency_key,
        scade_file=req.scade_file,
    )
    task["events_url"] = f"/api/v1/tasks/{task['id']}/events"
    return task


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "tasks": [
            task_repo.serialize_task(task, include_result=False)
            for task in task_repo.list_recent(db, limit=limit)
        ]
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    task = task_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    data = task_repo.serialize_task(task)
    data["events"] = [
        task_repo.serialize_event(event)
        for event in task_repo.events_after(db, task_id)
    ]
    return data


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    if task_repo.get(db, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    cancelled = await get_task_service().cancel(task_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="task is not running")
    return {"ok": True, "task_id": task_id}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    if task_repo.get(db, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    task_repo.delete(db, task_id)
    return {"ok": True, "task_id": task_id}


@router.get("/tasks/{task_id}/reviews")
async def task_reviews(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return only HITL requests belonging to this execution instance."""
    if task_repo.get(db, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    manager = get_hil_manager()
    pending = [
        item
        for item in manager.get_pending_approvals()
        if item.get("task_id") == task_id
    ]
    history = [
        item for item in manager.get_history() if item.get("task_id") == task_id
    ]
    return {"task_id": task_id, "pending": pending, "history": history}


@router.post("/tasks/{task_id}/reviews/{review_id}/decisions")
async def decide_task_review(
    task_id: str,
    review_id: str,
    req: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    _user: str = Depends(require_write_access),
) -> dict[str, Any]:
    if task_repo.get(db, task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    manager = get_hil_manager()
    matching = next(
        (
            item
            for item in manager.get_pending_approvals()
            if item.get("request_id") == review_id and item.get("task_id") == task_id
        ),
        None,
    )
    if matching is None:
        raise HTTPException(status_code=404, detail="review not found for task")
    operation = manager.approve if req.decision == "approved" else manager.reject
    return await operation(review_id, comments=req.comments, reviewer=req.reviewer)


@router.websocket("/tasks/{task_id}/events")
async def task_events(
    websocket: WebSocket,
    task_id: str,
    after_seq: int = Query(0, ge=0),
) -> None:
    await websocket.accept()
    from app.db import SessionLocal

    with SessionLocal() as db:
        task = task_repo.get(db, task_id)
        if task is None:
            await websocket.send_json({"level": "error", "message": "task not found"})
            await websocket.close(code=4404)
            return
        persisted_events = [
            task_repo.serialize_event(event)
            for event in task_repo.events_after(db, task_id, after_seq=after_seq)
        ]
        terminal = task.status in {
            "done", "error", "cancelled", "interrupted", "timeout"
        }

    registry = get_task_stream_registry()
    added = (
        False
        if terminal
        else await registry.add_subscriber(task_id, websocket, after_seq=after_seq)
    )
    if not added:
        for event in persisted_events:
            await websocket.send_json(event)
        with SessionLocal() as db:
            latest = task_repo.get(db, task_id)
            if latest is not None and latest.status in {
                "done", "error", "cancelled", "interrupted", "timeout"
            }:
                await websocket.send_json(
                    {
                        "type": "complete",
                        "level": "complete",
                        "task": task_repo.serialize_task(latest),
                    }
                )
        await websocket.close()
        return

    # Active tasks are replayed by the in-memory registry. Persisted events are
    # only needed when the process has restarted and no registry entry exists.

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await registry.remove_subscriber(task_id, websocket)


@router.get("/execution-profiles")
async def execution_profiles() -> dict[str, Any]:
    return {
        "profiles": [
            {
                "id": "demo",
                "label": "演示模式（模拟）",
                "available": True,
                "source": "simulated",
            },
            {
                "id": "cloud",
                "label": "云 API",
                "available": bool(settings.LLM_API_KEY),
                "source": "live",
                "provider": settings.SKYFORGE_LLM_PROVIDER,
                "model": settings.LLM_MODEL,
            },
            {
                "id": "local",
                "label": "本地模型",
                "available": True,
                "source": "live",
            },
        ]
    }


@router.get("/preflight/{profile_id}")
async def preflight(profile_id: Literal["demo", "cloud", "local"]) -> dict[str, Any]:
    if profile_id == "demo":
        return {
            "profile_id": profile_id,
            "ready": True,
            "source": "simulated",
            "checks": {"browser_demo": True},
        }
    checks = {
        "gcc": shutil.which("gcc") is not None,
        "cppcheck": shutil.which("cppcheck") is not None,
        "api_key": bool(settings.LLM_API_KEY) if profile_id == "cloud" else True,
    }
    return {
        "profile_id": profile_id,
        "ready": all(checks.values()),
        "source": "live",
        "checks": checks,
    }


@router.get("/hardware-hil/preflight")
async def hardware_hil_preflight() -> dict[str, Any]:
    """Hardware-in-the-Loop has a separate namespace from HITL review."""
    return {
        "source": "live",
        "enabled": settings.HIL_ENABLED,
        "status": "observed" if settings.HIL_ENABLED else "unavailable",
        "interface": settings.HIL_INTERFACE,
        "target": settings.HIL_JTAG_TARGET if settings.HIL_INTERFACE == "jtag_swd" else None,
        "serial_port_configured": bool(settings.HIL_SERIAL_PORT)
        if settings.HIL_INTERFACE == "serial"
        else None,
    }


@router.get("/recordings")
async def list_recordings() -> dict[str, Any]:
    recordings = []
    if _RECORDINGS_DIR.exists():
        for path in sorted(_RECORDINGS_DIR.glob("*.manifest.json")):
            try:
                recordings.append(_load_recording_manifest(path))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
    return {"recordings": recordings}


@router.get("/recordings/{recording_id}")
async def get_recording(recording_id: str) -> dict[str, Any]:
    if not recording_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid recording id")
    matches = list(_RECORDINGS_DIR.glob("*.manifest.json"))
    for path in matches:
        manifest = _load_recording_manifest(path)
        if manifest.get("id") != recording_id:
            continue
        source_path = (path.parent / manifest["source_log"]).resolve()
        manifest["run"] = json.loads(source_path.read_text(encoding="utf-8"))
        return manifest
    raise HTTPException(status_code=404, detail="recording not found")
