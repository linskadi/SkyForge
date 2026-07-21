"""V1 task persistence models.

The task identifier is deliberately independent from requirement identifiers such
as ``REQ-001``.  A task is an execution instance; requirements are artifacts
inside that execution.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Task(Base):
    """Durable execution record for demo, cloud, and local profiles."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    requirement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requirement: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="c")
    profile_id: Mapped[str] = mapped_column(String(16), default="local")
    source: Mapped[str] = mapped_column(String(16), default="live")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    current_stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    events: Mapped[list["TaskEvent"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_tasks_created_at", "created_at"),
        Index("idx_tasks_status", "status"),
    )


class TaskEvent(Base):
    """Ordered, replayable task event."""

    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(32), default="system")
    level: Mapped[str] = mapped_column(String(16), default="info")
    agent: Mapped[str] = mapped_column(String(32), default="SYSTEM")
    message: Mapped[str] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(16), default="observed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped[Task] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_task_events_task_seq"),
        Index("idx_task_events_task_seq", "task_id", "seq"),
    )
