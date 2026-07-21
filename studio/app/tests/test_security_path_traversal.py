"""安全测试：清理接口不得删除工作目录外的内容。"""
import os
import unittest

os.environ["USE_LLM"] = "false"
os.environ["HITL_ENABLED"] = "false"

from fastapi.testclient import TestClient
from app.main import app


class TestCleanupPathTraversal(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_cleanup_rejects_traversal(self):
        """路径遍历应返回 400。"""
        response = self.client.post("/api/cleanup/workdir/..%2F..%2F..%2F")
        self.assertIn(response.status_code, (400, 404, 422))

    def test_cleanup_rejects_absolute_path(self):
        """绝对路径应被拒绝。"""
        response = self.client.post("/api/cleanup/workdir//etc")
        self.assertIn(response.status_code, (400, 404, 422))

    def test_cleanup_rejects_dots(self):
        """含 .. 的路径应被拒绝。"""
        response = self.client.post("/api/cleanup/workdir/task1%2F..%2Ftask2")
        self.assertIn(response.status_code, (400, 404, 422))


if __name__ == "__main__":
    unittest.main()