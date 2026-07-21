"""TaskHistory 模型：每次 /api/generate 完成后写入一条记录。"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaskHistory(Base):
    """任务历史记录表。每次 /api/generate 完成后写入一条。"""

    __tablename__ = "task_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement: Mapped[str] = mapped_column(String(500))  # 前 200 字 + 余量
    language: Mapped[str] = mapped_column(String(16))  # c / c++ / python
    status: Mapped[str] = mapped_column(String(16))  # done / error
    code_hash: Mapped[str] = mapped_column(String(16))  # SHA256 前 8 位
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    mandatory_count: Mapped[int] = mapped_column(Integer, default=0)
    required_count: Mapped[int] = mapped_column(Integer, default=0)
    advisory_count: Mapped[int] = mapped_column(Integer, default=0)
    stage_reached: Mapped[str] = mapped_column(String(16))  # req/con/code/repair/sim/done
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_task_history_created_at", "created_at"),  # 用于 ORDER BY DESC
    )
