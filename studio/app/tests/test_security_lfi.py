"""安全测试：/api/verify 不得读取工作目录外的文件。"""
import os
import unittest

os.environ["USE_LLM"] = "false"
os.environ["HITL_ENABLED"] = "false"

from fastapi.testclient import TestClient
from app.main import app


class TestVerifyLFIProtection(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_verify_rejects_absolute_path(self):
        """绝对路径应被拒绝。"""
        response = self.client.post(
            "/api/verify",
            json={"contract_path": "/etc/passwd"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("illegal", response.json().get("detail", "").lower())

    def test_verify_rejects_traversal(self):
        """路径遍历应被拒绝。"""
        response = self.client.post(
            "/api/verify",
            json={"contract_path": "../../../etc/passwd"},
        )
        self.assertEqual(response.status_code, 400)

    def test_verify_rejects_non_workdir_path(self):
        """非工作目录路径应被拒绝。"""
        response = self.client.post(
            "/api/verify",
            json={"contract_path": "../config/.env"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()