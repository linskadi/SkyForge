"""通用工具函数单元测试。"""

import unittest

from app.utils.common_utils import create_task_id, ensure_safe_task_id


class TestCommonUtils(unittest.TestCase):
    """测试 common_utils 模块的核心函数。"""

    def test_create_task_id(self):
        """测试任务 ID 生成。"""
        task_id = create_task_id()
        self.assertIsInstance(task_id, str)
        self.assertTrue(len(task_id) > 0)

    def test_ensure_safe_task_id_valid(self):
        """测试合法任务 ID 验证。"""
        safe_id = ensure_safe_task_id("test-123")
        self.assertEqual(safe_id, "test-123")

    def test_ensure_safe_task_id_invalid(self):
        """测试非法任务 ID 验证。"""
        with self.assertRaises(ValueError):
            ensure_safe_task_id("../../../etc/passwd")

    def test_ensure_safe_task_id_empty(self):
        """测试空任务 ID 验证。"""
        with self.assertRaises(ValueError):
            ensure_safe_task_id("")


if __name__ == "__main__":
    unittest.main()
