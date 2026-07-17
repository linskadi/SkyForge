"""PSAC 生成器单元测试。"""

import unittest

from skyforge_engine.report.psac_generator import PSACDocument, generate_psac


class TestPSACGenerator(unittest.TestCase):
    """测试 PSAC 文档生成器。"""

    def setUp(self) -> None:
        self.basic_result = {
            "requirement": {
                "module_name": "altimeter_filter",
                "desc": "实现一个低通滤波器",
                "safety_level": "DAL-C",
                "version": "V3.2",
            },
            "contract": "version: 1.0\npre: input >= 0",
            "final_code": "double filter(double in) { return in; }",
            "final_violations": [],
            "contract_check_result": {"passed": True},
            "simulation_result": {"passed": True},
        }

    def test_generate_basic_psac(self) -> None:
        """测试基本 PSAC 文档生成。"""
        doc = generate_psac(self.basic_result)
        self.assertIsInstance(doc, PSACDocument)
        self.assertEqual(doc.meta.software_name, "SkyForge")
        self.assertEqual(doc.meta.certification_level, "DAL-C")
        self.assertGreater(len(doc.sections), 0)

    def test_psac_to_markdown(self) -> None:
        """测试 Markdown 渲染。"""
        doc = generate_psac(self.basic_result)
        md = doc.to_markdown()
        self.assertIn("PSAC", md)
        self.assertIn("SkyForge", md)
        self.assertIn("DAL-C", md)

    def test_psac_empty_result(self) -> None:
        """测试空 result 的 PSAC 生成。"""
        doc = generate_psac({})
        self.assertEqual(doc.meta.software_name, "SkyForge")
        self.assertEqual(doc.meta.certification_level, "DAL-C")

    def test_psac_with_violations(self) -> None:
        """测试含违规的 PSAC 生成。"""
        result = {**self.basic_result, "final_violations": [
            {"rule_id": "Rule-8.13", "line": 24}
        ]}
        doc = generate_psac(result)
        md = doc.to_markdown()
        self.assertIn("1 条", md)

    def test_psac_with_failed_simulation(self) -> None:
        """测试仿真失败的 PSAC 生成。"""
        result = {
            **self.basic_result,
            "simulation_result": {"passed": False},
        }
        doc = generate_psac(result)
        md = doc.to_markdown()
        self.assertIn("未通过", md)


if __name__ == "__main__":
    unittest.main()
