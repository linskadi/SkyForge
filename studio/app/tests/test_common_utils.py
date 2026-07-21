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


class TestCreateTaskIdSecurity(unittest.TestCase):
    def test_task_id_unique_under_concurrency(self):
        """1000 次快速调用生成的 task_id 必须唯一。"""
        import concurrent.futures
        ids = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            ids = list(pool.map(lambda _: create_task_id(), range(1000)))
        self.assertEqual(len(set(ids)), 1000, "task_id 重复")

    def test_task_id_not_predictable(self):
        """task_id 不应完全基于时间戳（不可预测）。"""
        id1 = create_task_id()
        id2 = create_task_id()
        rand1 = id1.split("-")[-1]
        rand2 = id2.split("-")[-1]
        self.assertNotEqual(rand1, rand2, "随机部分可预测")


if __name__ == "__main__":
    unittest.main()
