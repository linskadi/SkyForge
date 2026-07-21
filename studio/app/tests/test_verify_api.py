"""测试 /api/verify 形式化验证路由的严格模式行为。

覆盖 Task 4.4：
- Z3/CBMC 可用时正常验证
- 工具缺失时返回 HTTP 503
"""

import os

os.environ["USE_LLM"] = "false"
os.environ["HITL_ENABLED"] = "false"

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


_SAMPLE_CONTRACT = """component: test_module
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-001]
interface:
  inputs:
    - name: input_value
      type: int32_t
      range: [0, 100]
  outputs:
    - name: output_value
      type: int32_t
      range: [0, 100]
contracts:
  preconditions:
    - "input_value >= 0"
    - "input_value <= 100"
  postconditions:
    - "output_value >= 0"
    - "output_value <= 100"
  invariants:
    - "no dynamic memory"
  fault_handling:
    - "if input_value < 0 then clamp to 0"
"""


def test_verify_with_tools_available():
    """Z3/CBMC 可用时正常验证并返回 passed/pailed 结果。"""
    mock_result = MagicMock()
    mock_result.component = "test_module"
    mock_result.contract_version = "1.0.0"
    mock_result.is_consistent = True
    mock_result.contradictions = []
    mock_result.z3_solver_time_ms = 12.3
    mock_result.test_cases = []
    mock_result.test_case_count = 0
    mock_result.cbmc_verified = False
    mock_result.cbmc_output = ""
    mock_result.cbmc_time_ms = 0.0
    mock_result.errors = []
    mock_result.warnings = []
    mock_result.z3_available = True
    mock_result.cbmc_available = False

    with patch("app.api.routes.pipeline.require_tool") as mock_require_tool:
        # z3 和 cbmc 都模拟为可用
        mock_require_tool.return_value = "1.0.0"
        with patch(
            "skyforge_engine.tools.contract_formal_verifier.verify_contract",
            return_value=mock_result,
        ):
            response = client.post(
                "/api/verify",
                json={"contract": _SAMPLE_CONTRACT},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("passed", "failed", "skipped")
    assert "summary" in data
    assert "checks" in data
    assert "tool" in data


def test_verify_returns_503_when_both_tools_missing():
    """Z3 和 CBMC 都缺失时返回 HTTP 503。"""
    from app.core.llm.mode_guard import ToolNotFoundError

    def _raise_tool_not_found(tool_name):
        raise ToolNotFoundError(
            tool_name=tool_name,
            message=f"未在 PATH 中找到工具: {tool_name}",
        )

    with patch("app.api.routes.pipeline.require_tool", side_effect=_raise_tool_not_found):
        response = client.post(
            "/api/verify",
            json={"contract": _SAMPLE_CONTRACT},
        )

    assert response.status_code == 503
    data = response.json()
    assert "error" in data
    assert "missing_tools" in data
    assert "z3" in data["missing_tools"]
    assert "cbmc" in data["missing_tools"]


def test_verify_skipped_when_no_contract():
    """未提供契约数据时返回 skipped（非 503）。"""
    response = client.post("/api/verify", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
