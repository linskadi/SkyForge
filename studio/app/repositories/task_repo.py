"""Repository helpers for V1 task lifecycle persistence."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.task import Task, TaskEvent
from app.models.task_history import TaskHistory


def create_task(
    db: Session,
    *,
    task_id: str,
    idempotency_key: str,
    requirement: str,
    language: str,
    profile_id: str,
    source: str = "live",
) -> Task:
    task = Task(
        id=task_id,
        idempotency_key=idempotency_key,
        requirement=requirement,
        language=language,
        profile_id=profile_id,
        source=source,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_by_idempotency(db: Session, key: str) -> Task | None:
    return db.execute(select(Task).where(Task.idempotency_key == key)).scalar_one_or_none()


def get(db: Session, task_id: str) -> Task | None:
    return db.get(Task, task_id)


def delete(db: Session, task_id: str) -> None:
    task = db.get(Task, task_id)
    if task is not None:
        db.delete(task)
        db.commit()


def list_recent(db: Session, limit: int = 20) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_task(db: Session, task_id: str, **fields: Any) -> Task | None:
    task = db.get(Task, task_id)
    if task is None:
        return None
    for key, value in fields.items():
        if hasattr(task, key):
            setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def append_event(
    db: Session,
    *,
    task_id: str,
    stage: str,
    level: str,
    agent: str,
    message: str,
    evidence_status: str = "observed",
) -> TaskEvent:
    current = db.execute(
        select(func.max(TaskEvent.seq)).where(TaskEvent.task_id == task_id)
    ).scalar()
    event = TaskEvent(
        task_id=task_id,
        seq=int(current or 0) + 1,
        stage=stage,
        level=level,
        agent=agent,
        message=message,
        evidence_status=evidence_status,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def events_after(db: Session, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
    stmt = (
        select(TaskEvent)
        .where(TaskEvent.task_id == task_id, TaskEvent.seq > after_seq)
        .order_by(TaskEvent.seq.asc())
    )
    return list(db.execute(stmt).scalars().all())


def mark_running_interrupted(db: Session) -> int:
    result = db.execute(
        update(Task)
        .where(Task.status.in_(["queued", "running"]))
        .values(
            status="interrupted",
            error="服务重启导致任务中断，可从原需求重新运行",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def migrate_legacy_history(db: Session) -> int:
    """Copy old summaries into read-only legacy task rows without deleting data."""
    migrated = 0
    records = list(db.execute(select(TaskHistory)).scalars().all())
    for record in records:
        stamp = record.created_at.isoformat() if record.created_at else "unknown"
        legacy_source = f"{record.id}:{stamp}"
        legacy_key = f"legacy:{hashlib.sha256(legacy_source.encode('utf-8')).hexdigest()}"
        if get_by_idempotency(db, legacy_key) is not None:
            continue
        digest = hashlib.sha256(legacy_source.encode("utf-8")).hexdigest()[:16].upper()
        summary = {
            "legacy": True,
            "code_hash": record.code_hash,
            "violation_count": record.violation_count,
            "stage_reached": record.stage_reached,
            "notice": "旧 task_history 仅保存摘要，完整产物在旧版本中未持久化。",
        }
        task = Task(
            id=f"LEGACY-{digest}",
            idempotency_key=legacy_key,
            requirement_id=(record.id if str(record.id).startswith("REQ-") else None),
            requirement=record.requirement,
            language=record.language,
            profile_id="legacy",
            source="replay",
            status="legacy",
            current_stage=record.stage_reached,
            progress=100,
            result_json=json.dumps(summary, ensure_ascii=False),
            provenance_json=json.dumps({
                "source": "legacy",
                "evidence_status": "unavailable",
                "warning": "旧记录缺少逐阶段 provenance，不能视为已验证运行包。",
            }, ensure_ascii=False),
            duration_ms=record.duration_ms,
            created_at=record.created_at,
            updated_at=record.created_at,
        )
        db.add(task)
        migrated += 1
    db.commit()
    return migrated


def serialize_task(task: Task, *, include_result: bool = True) -> dict[str, Any]:
    result = None
    provenance = None
    if include_result and task.result_json:
        try:
            result = json.loads(task.result_json)
        except json.JSONDecodeError:
            result = None
    if task.provenance_json:
        try:
            provenance = json.loads(task.provenance_json)
        except json.JSONDecodeError:
            provenance = None
    return {
        "id": task.id,
        "requirement_id": task.requirement_id,
        "requirement": task.requirement,
        "language": task.language,
        "profile_id": task.profile_id,
        "source": task.source,
        "status": task.status,
        "current_stage": task.current_stage,
        "progress": task.progress,
        "result": result,
        "provenance": provenance,
        "error": task.error,
        "duration_ms": task.duration_ms,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def serialize_event(event: TaskEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "task_id": event.task_id,
        "stage": event.stage,
        "level": event.level,
        "agent": event.agent,
        "message": event.message,
        "thought": event.message,
        "evidence_status": event.evidence_status,
        "time": event.created_at.isoformat() if event.created_at else None,
    }
