# -*- coding: utf-8 -*-
"""Dashboard 后端 API 单元测试（阶段 C1）。

测试覆盖：
- task_history_repo 仓储层 CRUD + 聚合 + 辅助函数
- /api/dashboard/recent-tasks 空态/有数据/limit
- /api/dashboard/system-status 各字段
- /api/dashboard/compliance-trend 聚合
- /api/dashboard/stats 聚合
- /api/dashboard/tasks/{task_id} 详情
- /api/health 容错（redis_manager 导入失败时返回 degraded）

使用内存 SQLite（StaticPool 共享连接）隔离测试，不污染 studio/data/skyforge.db。
"""

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.repositories import task_history_repo
from app.repositories.task_history_repo import (
    _compute_code_hash,
    _count_violations_by_category,
    _truncate_requirement,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def db_engine():
    """内存 SQLite engine。

    使用 StaticPool 让所有连接共享同一 in-memory DB，
    这样 db_session 写入的数据可以被 client 的请求读取到。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """内存 SQLite session，每个测试独立。"""
    SessionLocal = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    """TestClient + 内存 SQLite override get_db。

    通过 dependency_overrides 让请求使用与 db_session 同一 in-memory engine，
    实现「先 db_session 写数据 → client 读数据」的测试模式。

    使用 `with TestClient(app)` 触发 lifespan（必需，否则 portal 未启动）。
    lifespan 会调用 Base.metadata.create_all(real_engine)，但由于 checkfirst=True
    且表已存在，不会破坏 studio/data/skyforge.db。
    """
    SessionLocal = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #


def _make_task(
    *,
    id: str,
    requirement: str = "测试需求",
    language: str = "c",
    status: str = "done",
    code_hash: str = "abcd1234",
    violation_count: int = 0,
    mandatory_count: int = 0,
    required_count: int = 0,
    advisory_count: int = 0,
    stage_reached: str = "done",
    duration_ms: int = 100,
    created_at: datetime | None = None,
) -> dict:
    """构造 task_history 字段字典（用于 task_history_repo.create）。"""
    fields: dict = {
        "id": id,
        "requirement": requirement,
        "language": language,
        "status": status,
        "code_hash": code_hash,
        "violation_count": violation_count,
        "mandatory_count": mandatory_count,
        "required_count": required_count,
        "advisory_count": advisory_count,
        "stage_reached": stage_reached,
        "duration_ms": duration_ms,
    }
    if created_at is not None:
        fields["created_at"] = created_at
    return fields


# --------------------------------------------------------------------------- #
# task_history_repo 仓储层测试
# --------------------------------------------------------------------------- #


class TestTaskHistoryRepo:
    """task_history_repo CRUD + 聚合函数测试。"""

    def test_create_task_history(self, db_session):
        """create 写入后返回的 TaskHistory 字段正确。"""
        now = datetime.now(timezone.utc)
        record = task_history_repo.create(
            db_session,
            **_make_task(id="REQ-001", requirement="实现滤波器", created_at=now),
        )
        assert record.id == "REQ-001"
        assert record.requirement == "实现滤波器"
        assert record.language == "c"
        assert record.status == "done"
        assert record.code_hash == "abcd1234"
        assert record.violation_count == 0
        assert record.mandatory_count == 0
        assert record.required_count == 0
        assert record.advisory_count == 0
        assert record.stage_reached == "done"
        assert record.duration_ms == 100
        # SQLite 不存储 tzinfo，从 DB 读回的 datetime 是 naive；
        # 仅比较时间字段（去掉 tzinfo 后应相等）
        assert record.created_at.replace(tzinfo=None) == now.replace(tzinfo=None)

    def test_list_recent_empty(self, db_session):
        """空表时 list_recent 返回 []。"""
        assert task_history_repo.list_recent(db_session, limit=20) == []

    def test_list_recent_with_data(self, db_session):
        """写入 3 条记录后 list_recent 返回 3 条且按 created_at DESC 排序。"""
        now = datetime.now(timezone.utc)
        # 三条记录时间递增：REQ-000 最旧，REQ-002 最新
        for i, offset in enumerate([2, 1, 0]):
            task_history_repo.create(
                db_session,
                **_make_task(
                    id=f"REQ-{i:03d}",
                    created_at=now - timedelta(seconds=offset),
                ),
            )
        records = task_history_repo.list_recent(db_session, limit=20)
        assert len(records) == 3
        # DESC 排序：最新的（offset=0，id=REQ-002）在最前
        assert records[0].id == "REQ-002"
        assert records[1].id == "REQ-001"
        assert records[2].id == "REQ-000"

    def test_list_recent_limit(self, db_session):
        """list_recent(limit=2) 写入 5 条后返回 2 条。"""
        now = datetime.now(timezone.utc)
        for i in range(5):
            task_history_repo.create(
                db_session,
                **_make_task(
                    id=f"REQ-{i:03d}",
                    created_at=now - timedelta(seconds=i),
                ),
            )
        records = task_history_repo.list_recent(db_session, limit=2)
        assert len(records) == 2
        # 最新的 2 条：REQ-000（offset=0）和 REQ-001（offset=1）
        assert records[0].id == "REQ-000"
        assert records[1].id == "REQ-001"

    def test_get_by_id(self, db_session):
        """get 查询存在的 id 返回记录，不存在的返回 None。"""
        now = datetime.now(timezone.utc)
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-001", created_at=now),
        )
        found = task_history_repo.get(db_session, "REQ-001")
        assert found is not None
        assert found.id == "REQ-001"
        assert found.requirement == "测试需求"
        assert task_history_repo.get(db_session, "NOT-EXIST") is None

    def test_count_today_empty(self, db_session):
        """空表 count_today 返回 0。"""
        assert task_history_repo.count_today(db_session) == 0

    def test_count_today_with_data(self, db_session):
        """写入 1 条今日 + 1 条昨日，count_today 返回 1。"""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-TODAY", created_at=now),
        )
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-YESTERDAY", created_at=yesterday),
        )
        assert task_history_repo.count_today(db_session) == 1

    def test_count_today_done(self, db_session):
        """count_today_done 只统计今日 status='done' 的记录。"""
        now = datetime.now(timezone.utc)
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-DONE", status="done", created_at=now),
        )
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-ERROR", status="error", created_at=now),
        )
        assert task_history_repo.count_today_done(db_session) == 1

    def test_total_count(self, db_session):
        """total_count 返回总记录数。"""
        now = datetime.now(timezone.utc)
        for i in range(3):
            task_history_repo.create(
                db_session,
                **_make_task(id=f"REQ-{i:03d}", created_at=now),
            )
        assert task_history_repo.total_count(db_session) == 3

    def test_compliance_trend_empty(self, db_session):
        """空表 compliance_trend 返回 []。"""
        assert task_history_repo.compliance_trend(db_session) == []

    def test_compliance_trend_with_data(self, db_session):
        """compliance_trend 返回 [{ts, mandatory, required, advisory, total}] 按时间正序。"""
        base = datetime.now(timezone.utc)
        # (id, mandatory, required, advisory, total, offset_seconds)
        # offset=0 最新，offset=20 最旧
        records_data = [
            ("REQ-A", 1, 2, 0, 3, 0),    # 最新
            ("REQ-B", 0, 1, 1, 2, 10),
            ("REQ-C", 2, 0, 0, 2, 20),  # 最旧
        ]
        for rid, m, r, a, total, off in records_data:
            task_history_repo.create(
                db_session,
                **_make_task(
                    id=rid,
                    mandatory_count=m,
                    required_count=r,
                    advisory_count=a,
                    violation_count=total,
                    created_at=base - timedelta(seconds=off),
                ),
            )
        trend = task_history_repo.compliance_trend(db_session, limit=20)
        assert len(trend) == 3
        # 按时间正序（旧到新）：REQ-C, REQ-B, REQ-A
        assert trend[0]["total"] == 2  # REQ-C
        assert trend[1]["total"] == 2  # REQ-B
        assert trend[2]["total"] == 3  # REQ-A
        # 验证字段完整性
        for item in trend:
            assert set(item.keys()) == {
                "ts", "mandatory", "required", "advisory", "total"
            }
        # 验证首尾字段值（ts 在 SQLite 中不存储 tzinfo，故 isoformat 无 +00:00 后缀）
        oldest_ts = (base - timedelta(seconds=20)).replace(tzinfo=None).isoformat()
        newest_ts = base.replace(tzinfo=None).isoformat()
        assert trend[0] == {
            "ts": oldest_ts,
            "mandatory": 2,
            "required": 0,
            "advisory": 0,
            "total": 2,
        }
        assert trend[2] == {
            "ts": newest_ts,
            "mandatory": 1,
            "required": 2,
            "advisory": 0,
            "total": 3,
        }


# --------------------------------------------------------------------------- #
# task_history_repo 辅助函数测试
# --------------------------------------------------------------------------- #


class TestTaskHistoryRepoHelpers:
    """task_history_repo 内部辅助函数测试。"""

    def test_truncate_requirement(self):
        """_truncate_requirement 截断到 200 字。"""
        long_text = "a" * 300
        result = _truncate_requirement(long_text, max_len=200)
        assert len(result) == 200
        assert result == "a" * 200

    def test_compute_code_hash(self):
        """_compute_code_hash 返回 8 字符 SHA256 前缀。"""
        result = _compute_code_hash("abc")
        expected = hashlib.sha256(b"abc").hexdigest()[:8]
        assert len(result) == 8
        assert result == expected

    def test_count_violations_by_category(self):
        """_count_violations_by_category 不区分大小写分类，返回 (mandatory, required, advisory)。"""
        violations = [
            {"category": "Mandatory"},
            {"category": "Required"},
            {"category": "required"},  # 小写，应归入 required
            {"category": "Advisory"},
        ]
        m, r, a = _count_violations_by_category(violations)
        assert (m, r, a) == (1, 2, 1)


# --------------------------------------------------------------------------- #
# /api/dashboard/* API 端点测试
# --------------------------------------------------------------------------- #


class TestDashboardAPI:
    """/api/dashboard/* 端点测试。"""

    def test_get_recent_tasks_empty(self, client):
        """空表 GET /api/dashboard/recent-tasks 返回 200 + []。"""
        response = client.get("/api/dashboard/recent-tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_recent_tasks_with_data(self, client, db_session):
        """写入 2 条后 GET 返回 2 条，包含 id/requirement/language/status 等字段。"""
        now = datetime.now(timezone.utc)
        task_history_repo.create(
            db_session,
            **_make_task(
                id="REQ-001",
                requirement="实现滤波器",
                created_at=now - timedelta(seconds=1),
            ),
        )
        task_history_repo.create(
            db_session,
            **_make_task(
                id="REQ-002",
                requirement="实现 PID 控制",
                created_at=now,
            ),
        )
        response = client.get("/api/dashboard/recent-tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # DESC 排序：REQ-002 在前（最新）
        assert data[0]["id"] == "REQ-002"
        assert data[1]["id"] == "REQ-001"
        # 字段完整性
        item = data[0]
        assert set(item.keys()) >= {
            "id", "requirement", "language", "status",
            "violation_count", "stage_reached",
            "duration_ms", "created_at",
        }
        assert item["requirement"] == "实现 PID 控制"
        assert item["language"] == "c"
        assert item["status"] == "done"

    def test_get_recent_tasks_limit(self, client, db_session):
        """写入 5 条后 GET /api/dashboard/recent-tasks?limit=2 返回 2 条。"""
        now = datetime.now(timezone.utc)
        for i in range(5):
            task_history_repo.create(
                db_session,
                **_make_task(
                    id=f"REQ-{i:03d}",
                    created_at=now - timedelta(seconds=i),
                ),
            )
        response = client.get("/api/dashboard/recent-tasks?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # 最新的 2 条
        assert data[0]["id"] == "REQ-000"
        assert data[1]["id"] == "REQ-001"

    def test_get_system_status(self, client):
        """GET /api/dashboard/system-status 返回 200，字段含 backend/llm/tools/persistence。"""
        response = client.get("/api/dashboard/system-status")
        assert response.status_code == 200
        data = response.json()
        # 顶层字段
        assert data["backend"] == "online"
        assert "llm" in data
        assert "tools" in data
        assert "persistence" in data
        # tools 字段为 boolean
        assert isinstance(data["tools"]["gcc"], bool)
        assert isinstance(data["tools"]["z3"], bool)
        assert isinstance(data["tools"]["cbmc"], bool)
        # llm 字段
        assert set(data["llm"].keys()) >= {"mode", "provider", "model", "available"}
        # persistence 字段
        assert "db_rows" in data["persistence"]
        assert "last_write" in data["persistence"]

    def test_get_compliance_trend_empty(self, client):
        """空表 GET /api/dashboard/compliance-trend 返回 200 + []。"""
        response = client.get("/api/dashboard/compliance-trend")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_compliance_trend_with_data(self, client, db_session):
        """写入 3 条不同违规数记录后返回 3 个点，按时间正序。"""
        base = datetime.now(timezone.utc)
        records_data = [
            ("REQ-A", 1, 2, 0, 3, 0),    # 最新
            ("REQ-B", 0, 1, 1, 2, 10),
            ("REQ-C", 2, 0, 0, 2, 20),  # 最旧
        ]
        for rid, m, r, a, total, off in records_data:
            task_history_repo.create(
                db_session,
                **_make_task(
                    id=rid,
                    mandatory_count=m,
                    required_count=r,
                    advisory_count=a,
                    violation_count=total,
                    created_at=base - timedelta(seconds=off),
                ),
            )
        response = client.get("/api/dashboard/compliance-trend")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # 按时间正序：REQ-C, REQ-B, REQ-A
        assert data[0]["total"] == 2  # REQ-C
        assert data[1]["total"] == 2  # REQ-B
        assert data[2]["total"] == 3  # REQ-A
        # 字段完整性
        for item in data:
            assert set(item.keys()) == {
                "ts", "mandatory", "required", "advisory", "total"
            }

    def test_get_dashboard_stats_empty(self, client):
        """空表 GET /api/dashboard/stats 返回全 0 + 0.0。"""
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        assert response.json() == {
            "today_count": 0,
            "today_done": 0,
            "total_count": 0,
            "avg_compliance_rate": 0.0,
        }

    def test_get_dashboard_stats_with_data(self, client, db_session):
        """写入 2 条（1 violation_count=0，1 violation_count=5），avg_compliance_rate=50.0。"""
        now = datetime.now(timezone.utc)
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-001", violation_count=0, created_at=now),
        )
        task_history_repo.create(
            db_session,
            **_make_task(id="REQ-002", violation_count=5, created_at=now),
        )
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert data["today_count"] == 2  # 两条都是今日
        assert data["today_done"] == 2  # 默认 status=done
        # 1/2 = 50.0%
        assert data["avg_compliance_rate"] == 50.0

    def test_get_task_detail_not_found(self, client):
        """GET /api/dashboard/tasks/NOT-EXIST 返回 404。"""
        response = client.get("/api/dashboard/tasks/NOT-EXIST")
        assert response.status_code == 404

    def test_get_task_detail_found(self, client, db_session):
        """先写入 1 条后 GET /api/dashboard/tasks/REQ-001 返回详情。"""
        now = datetime.now(timezone.utc)
        task_history_repo.create(
            db_session,
            **_make_task(
                id="REQ-001",
                requirement="实现滤波器",
                code_hash="deadbeef",
                violation_count=3,
                mandatory_count=1,
                required_count=1,
                advisory_count=1,
                created_at=now,
            ),
        )
        response = client.get("/api/dashboard/tasks/REQ-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "REQ-001"
        assert data["requirement"] == "实现滤波器"
        assert data["code_hash"] == "deadbeef"
        assert data["violation_count"] == 3
        assert data["mandatory_count"] == 1
        assert data["required_count"] == 1
        assert data["advisory_count"] == 1
        assert data["language"] == "c"
        assert data["status"] == "done"
        assert "duration_ms" in data
        assert "stage_reached" in data
        assert "created_at" in data


# --------------------------------------------------------------------------- #
# /api/health 容错测试
# --------------------------------------------------------------------------- #


class TestHealthEndpoint:
    """/api/health 容错测试。"""

    def test_health_normal(self, client):
        """正常情况下 /api/health 返回 200，status 为 ok 或 error。"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        # 实际状态取决于 GCC/LLM/Redis 是否可用，但端点必须返回 200
        assert data["status"] in ("ok", "error")
        assert data["service"] == "SkyForge"
        assert "uptime_seconds" in data
        assert "llm" in data
        assert "gcc" in data
        assert "redis" in data

    def test_health_redis_import_failure(self, client):
        """redis_manager 导入失败时 /api/health 仍返回 200，status=error，redis=error。

        通过 sys.modules['app.services.redis_manager'] = None 触发 ImportError，
        模拟模块初始化失败的场景。
        """
        # 将 app.services.redis_manager 设为 None 触发 ImportError
        # （Python 对 sys.modules 中值为 None 的模块视为不可导入）
        with patch.dict(sys.modules, {"app.services.redis_manager": None}):
            response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        # redis 导入失败 → redis_available 为 "error" → 整体 status 为 "error"
        assert data["status"] == "error"
        assert data["redis"] == "error"
