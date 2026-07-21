"""V1 task protocol regression tests."""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.task import Task, TaskEvent  # noqa: F401
from app.repositories import task_repo
from app.core.hil.hil_manager import HILManager
from app.api.routes import generate
from app.api.routes import tasks_v1
from app.services import task_service as service_module
from app.services.task_service import TaskService
from skyforge_engine.execution import ToolEvidence
from skyforge_engine.config import settings


@pytest.fixture()
def isolated_sessions(tmp_path, monkeypatch):
    db_path = tmp_path / "tasks-v1.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service_module, "SessionLocal", factory)
    yield factory
    engine.dispose()


def test_idempotency_and_task_requirement_ids_are_separate(
    isolated_sessions, monkeypatch
):
    async def fake_pipeline(**_kwargs):
        return {
            "requirement": {"req_id": "REQ-001"},
            "final_code": "int filter(void) { return 0; }",
            "final_violations": [],
            "simulation_result": {
                "passed": True,
                "compilation": {"success": True, "used_mock": True},
            },
            "tool_evidence": {
                "compilation": {
                    "status": "simulated",
                    "engine": "python-simulator",
                }
            },
        }

    monkeypatch.setattr(service_module, "run_full_pipeline", fake_pipeline)

    async def scenario():
        service = TaskService()
        first, duplicate = await asyncio.gather(
            service.create(
                requirement="low pass filter", language="c", profile_id="local",
                idempotency_key="idem-test-0001",
            ),
            service.create(
                requirement="low pass filter", language="c", profile_id="local",
                idempotency_key="idem-test-0001",
            ),
        )
        runner = service._running.get(first["id"])
        if runner is not None:
            await runner
        return first, duplicate

    first, duplicate = asyncio.run(scenario())
    assert first["id"] == duplicate["id"]
    assert first["id"].startswith("TASK-")
    assert first["id"] != "REQ-001"

    with isolated_sessions() as db:
        persisted = task_repo.get(db, first["id"])
        assert persisted is not None
        assert persisted.requirement_id == "REQ-001"
        assert persisted.status == "done"
        payload = task_repo.serialize_task(persisted)
        assert payload["result"]["code"].startswith("int filter")
        assert payload["provenance"]["tools"]["compilation"]["status"] == "simulated"
        events = task_repo.events_after(db, first["id"])
        assert [event.seq for event in events] == list(range(1, len(events) + 1))


def test_cancelled_task_does_not_return_to_running(
    isolated_sessions, monkeypatch
):
    started = asyncio.Event()

    async def slow_pipeline(**_kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service_module, "run_full_pipeline", slow_pipeline)

    async def scenario():
        service = TaskService()
        created = await service.create(
            requirement="cancel me", language="c", profile_id="local",
            idempotency_key="idem-cancel-0001",
        )
        await started.wait()
        runner = service._running[created["id"]]
        assert await service.cancel(created["id"])
        await runner
        return created

    created = asyncio.run(scenario())

    with isolated_sessions() as db:
        persisted = task_repo.get(db, created["id"])
        assert persisted is not None
        assert persisted.status == "cancelled"
        assert persisted.current_stage == "cancelled"


def test_restart_marks_only_active_tasks_interrupted(isolated_sessions):
    with isolated_sessions() as db:
        task_repo.create_task(
            db,
            task_id="TASK-RUNNING",
            idempotency_key="idem-running",
            requirement="r",
            language="c",
            profile_id="local",
        )
        task_repo.create_task(
            db,
            task_id="TASK-DONE",
            idempotency_key="idem-done",
            requirement="d",
            language="c",
            profile_id="cloud",
        )
        task_repo.update_task(db, "TASK-RUNNING", status="running")
        task_repo.update_task(db, "TASK-DONE", status="done")
        assert task_repo.mark_running_interrupted(db) == 1
        assert task_repo.get(db, "TASK-RUNNING").status == "interrupted"
        assert task_repo.get(db, "TASK-DONE").status == "done"


def test_unavailable_tool_is_not_encoded_as_passed():
    evidence = ToolEvidence(status="unavailable", engine="z3")
    encoded = json.loads(json.dumps(evidence.__dict__))
    assert encoded["status"] == "unavailable"
    assert "passed" not in encoded


def test_local_profile_does_not_reuse_cloud_model(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM", True)
    monkeypatch.setattr(settings, "SKYFORGE_LLM_MODE", "api")
    monkeypatch.setattr(settings, "LOCAL_LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "LMSTUDIO_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "LLM_MODEL", "deepseek-v4-flash")

    config = service_module._task_llm_config("local")

    assert config["mode"] == "local"
    assert config["base_url"] == "http://localhost:11434/v1"
    assert config["model"] is None
    assert service_module._display_model(config) == "qwen3:8b"


def test_missing_task_profile_follows_saved_llm_mode(monkeypatch):
    monkeypatch.setattr(settings, "SKYFORGE_LLM_MODE", "api")
    assert tasks_v1._resolve_profile_id(None) == "cloud"
    assert generate._resolve_legacy_profile_id({}) == "cloud"
    assert tasks_v1._resolve_profile_id("local") == "local"
    assert generate._resolve_legacy_profile_id({"profile_id": "local"}) == "local"

    monkeypatch.setattr(settings, "SKYFORGE_LLM_MODE", "local")
    assert tasks_v1._resolve_profile_id(None) == "local"
    assert generate._resolve_legacy_profile_id({}) == "local"


def test_hitl_review_keeps_task_scope_and_hil_is_separate():
    async def scenario():
        manager = HILManager(enabled=False)
        return await manager.request_approval(
            checkpoint="requirement_review",
            content="REQ-001",
            task_id="TASK-SCOPED-001",
        )

    result = asyncio.run(scenario())
    assert result["task_id"] == "TASK-SCOPED-001"
    assert hasattr(settings, "HITL_ENABLED")
    assert hasattr(settings, "HIL_ENABLED")
