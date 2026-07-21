"""安全测试：CORS 配置不得使用通配符 + 凭证的组合。"""
import os
import unittest

os.environ["USE_LLM"] = "false"
os.environ["HITL_ENABLED"] = "false"

from app.config.setting import settings
from app.main import app
from fastapi.testclient import TestClient


class TestCORSConfiguration(unittest.TestCase):
    def test_cors_origins_not_wildcard(self):
        """CORS_ALLOW_ORIGINS 不得为 "*"。"""
        self.assertNotEqual(settings.CORS_ALLOW_ORIGINS, "*")

    def test_cors_no_wildcard_with_credentials(self):
        """allow_credentials=True 时不得使用通配符源。"""
        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = response.headers.get("access-control-allow-origin", "")
        self.assertNotEqual(allow_origin, "https://evil.example.com")


if __name__ == "__main__":
    unittest.main()