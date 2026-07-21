"""鉴权测试：写接口必须校验 token。"""
import os
import unittest

os.environ["USE_LLM"] = "false"
os.environ["HITL_ENABLED"] = "false"
os.environ["SKYFORGE_API_TOKEN"] = "test-secret-token"

from fastapi.testclient import TestClient
from app.main import app


class TestWriteEndpointAuth(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_hil_toggle_requires_token(self):
        """无 token 时切换 HIL 应返回 401。"""
        response = self.client.post("/api/hil/toggle", json={"enabled": True})
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_passes(self):
        """正确 token 时应通过鉴权（可能因业务逻辑返回其他状态码）。"""
        response = self.client.post(
            "/api/hil/toggle",
            json={"enabled": True},
            headers={"X-API-Token": "test-secret-token"},
        )
        self.assertNotEqual(response.status_code, 401)

    def test_cleanup_requires_token(self):
        """无 token 时清理接口应返回 401。"""
        response = self.client.post("/api/cleanup/workdir/test-task")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()