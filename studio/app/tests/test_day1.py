"""核心链路测试：需求解析→契约生成→代码生成→Cppcheck 扫描。

验证输入"实现一个低通滤波器，截止频率10Hz"后，返回包含 contract YAML + C 代码。
"""

import asyncio
import unittest

from skyforge_engine.pipeline import run_pipeline
from skyforge_engine.tools.contract_to_assert import contract_to_assert


class TestDay1Pipeline(unittest.TestCase):
    """核心流水线测试。"""

    def test_lowpass_filter_pipeline(self) -> None:
        """输入低通滤波器需求，验证返回包含契约 YAML + C 代码。"""
        requirement = "实现一个低通滤波器，截止频率10Hz"
        result = asyncio.run(run_pipeline(requirement))

        # 1) 结构化需求 JSON（含 [REQ-xxx] Tag）
        req = result["requirement"]
        self.assertEqual(req["req_id"], "REQ-001")
        self.assertEqual(req["type"], "filter")
        self.assertEqual(req["params"]["cutoff_hz"], 10.0)

        # 2) 契约 YAML（参考设计文档 6.3 节格式）
        contract: str = result["contract"]
        self.assertIn("component:", contract)
        self.assertIn("safety_level:", contract)
        self.assertIn("interface:", contract)
        self.assertIn("preconditions:", contract)
        self.assertIn("postconditions:", contract)
        self.assertIn("invariants:", contract)
        self.assertIn("fault_handling:", contract)
        self.assertIn("REQ-001", contract)

        # 3) C 代码（含 [REQ-xxx] [MISRA-Rule-x.x] 追溯注释）
        code: str = result["code"]
        self.assertIn("[REQ-001]", code)
        self.assertIn("[MISRA-Rule", code)
        self.assertIn("lowpass_filter_10hz", code)
        self.assertIn(".h", code)  # 头文件
        # 低通滤波器核心 IIR 逻辑
        self.assertIn("apply", code)
        self.assertIn("double", code)

        # 4) Cppcheck 结果（系统未装时优雅降级为空列表）
        self.assertIsInstance(result["cppcheck_result"], list)

    def test_contract_to_assert(self) -> None:
        """验证契约→断言转换器（Patch 2）能从生成的契约产出 C 断言。"""
        requirement = "实现一个低通滤波器，截止频率10Hz"
        result = asyncio.run(run_pipeline(requirement))

        c_assert = contract_to_assert(result["contract"], cid="CON-001")
        self.assertIn("assert(", c_assert)
        self.assertIn("CON-001-POST-000", c_assert)
        self.assertIn("isnan", c_assert)  # NaN/Inf 检查
        self.assertIn("后置条件", c_assert)


if __name__ == "__main__":
    unittest.main()
