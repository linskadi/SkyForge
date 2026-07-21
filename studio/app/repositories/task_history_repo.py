"""task_history 仓储层：封装 TaskHistory 的 CRUD 与聚合查询。"""

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task_history import TaskHistory


def _truncate_requirement(text: str, max_len: int = 200) -> str:
    """截断需求文本到指定长度。"""
    if not text:
        return ""
    return text[:max_len]


def _compute_code_hash(code: str) -> str:
    """计算代码 SHA256 前 8 位。"""
    if not code:
        return ""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:8]


def _count_violations_by_category(violations: list[Any]) -> tuple[int, int, int]:
    """从 violations 列表统计 Mandatory/Required/Advisory 数量。

    violations 是 list[dict]，每个 dict 可能含 `category` 或 `severity` 字段，
    字段值不区分大小写。无法归类的违规计入 Advisory。
    """
    mandatory = 0
    required = 0
    advisory = 0
    for v in violations or []:
        if not isinstance(v, dict):
            advisory += 1
            continue
        raw = v.get("category") or v.get("severity") or ""
        key = str(raw).strip().lower()
        if "mandatory" in key or "error" in key or "high" in key:
            mandatory += 1
        elif "required" in key or "warning" in key or "warn" in key or "medium" in key:
            required += 1
        else:
            advisory += 1
    return mandatory, required, advisory


def create(db: Session, **fields: Any) -> TaskHistory:
    """插入一条 task_history 记录，commit 后返回。"""
    record = TaskHistory(**fields)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update(db: Session, task_id: str, **fields: Any) -> TaskHistory | None:
    """按主键更新字段，commit 后返回记录。不存在则返回 None。"""
    record = db.get(TaskHistory, task_id)
    if not record:
        return None
    for key, value in fields.items():
        if hasattr(record, key):
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


def create_or_update(db: Session, task_id: str, **fields: Any) -> TaskHistory:
    """存在则更新，不存在则创建，commit 后返回。"""
    existing = db.get(TaskHistory, task_id)
    if existing:
        for key, value in fields.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    record = TaskHistory(id=task_id, **fields)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_recent(db: Session, limit: int = 20) -> list[TaskHistory]:
    """按 created_at DESC 取最近 N 条。"""
    stmt = (
        select(TaskHistory)
        .order_by(TaskHistory.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get(db: Session, task_id: str) -> TaskHistory | None:
    """按主键查询。"""
    return db.get(TaskHistory, task_id)


def count_today(db: Session) -> int:
    """今日 UTC 0 点之后的记录数。"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count()).select_from(TaskHistory).where(
        TaskHistory.created_at >= today_start
    )
    return int(db.execute(stmt).scalar() or 0)


def count_today_done(db: Session) -> int:
    """今日 status='done' 的记录数。"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count()).select_from(TaskHistory).where(
        TaskHistory.created_at >= today_start,
        TaskHistory.status == "done",
    )
    return int(db.execute(stmt).scalar() or 0)


def total_count(db: Session) -> int:
    """总记录数。"""
    stmt = select(func.count()).select_from(TaskHistory)
    return int(db.execute(stmt).scalar() or 0)


def compliance_trend(db: Session, limit: int = 20) -> list[dict]:
    """最近 N 条记录的违规数列表。

    返回格式：
        [{"ts": iso_string, "mandatory": int, "required": int,
          "advisory": int, "total": int}, ...]
    按时间正序（旧到新）。
    """
    records = list_recent(db, limit=limit)
    items: list[dict] = []
    for t in reversed(records):
        ts = t.created_at.isoformat() if t.created_at else None
        items.append(
            {
                "ts": ts,
                "mandatory": int(t.mandatory_count or 0),
                "required": int(t.required_count or 0),
                "advisory": int(t.advisory_count or 0),
                "total": int(t.violation_count or 0),
            }
        )
    return items
