"""链上证据锚定 API 路由测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "studio"))

import pytest

from skyforge_engine.chain.evidence_anchor import (
    CHAIN_ID,
    compute_anchor_hash_from_report,
)

try:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.api.routes.evidence import AnchorInfoRequest  # noqa: F401

    client = TestClient(app)

    @pytest.fixture(autouse=True)
    def _ensure_env():
        return

    def test_anchor_info_returns_hash_and_chain():
        pipeline_result = {
            "pipeline_version": "v0.5.0",
            "language": "C",
            "metrics": {"code_lines": 128, "misra_violations": 0},
        }
        resp = client.post("/api/evidence/anchor-info", json={"pipeline_result": pipeline_result})
        assert resp.status_code == 200
        data = resp.json()
        assert data["anchor_hash"] == compute_anchor_hash_from_report(pipeline_result)
        assert data["chain"]["chain_id"] == CHAIN_ID
        assert data["contract"]["address"].startswith("0x")
        assert len(data["contract"]["address"]) == 42

    def test_anchor_info_deterministic():
        pipeline_result = {"language": "C", "metrics": {"code_lines": 128}}
        r1 = client.post("/api/evidence/anchor-info", json={"pipeline_result": pipeline_result})
        r2 = client.post("/api/evidence/anchor-info", json={"pipeline_result": pipeline_result})
        assert r1.json()["anchor_hash"] == r2.json()["anchor_hash"]

    def test_anchor_info_empty_result_ok():
        resp = client.post("/api/evidence/anchor-info", json={"pipeline_result": {}})
        assert resp.status_code == 200
        assert len(resp.json()["anchor_hash"]) == 64

except ImportError as exc:  # pragma: no cover
    pytest.skip(f"FastAPI 依赖缺失，跳过: {exc}", allow_module_level=True)
