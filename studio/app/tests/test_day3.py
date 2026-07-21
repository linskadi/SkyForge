"""数字孪生仿真测试：数字孪生仿真引擎（虚拟传感器 + GCC 编译运行
+ 故障注入 + 契约断言 core dump）。

测试覆盖：
- test_virtual_sensor：正常数据生成 + 5 类故障注入 + CSV 转换
- test_virtual_mcu_compile：编译成功/失败（含 GCC 不可用降级）
- test_virtual_mcu_run：运行仿真 + 输出解析（mock 模式）
- test_fault_injector：故障类型描述 + 参数校验
- test_simulation_engine_normal：正常仿真（无故障）→ passed=True
- test_simulation_engine_with_fault：注入故障→仿真完成
- test_contract_assert_injection：验证断言被注入到 test_harness
- test_mock_mode：无 GCC 时的优雅降级
"""

import unittest

import numpy as np

from app.config.setting import settings
from skyforge_engine.digital_twin.fault_injector import FaultInjector
from skyforge_engine.digital_twin.simulation_engine import SimulationEngine
from skyforge_engine.digital_twin.virtual_mcu import RunResult, VirtualMCU
from skyforge_engine.digital_twin.virtual_sensor import VirtualSensor
from skyforge_engine.tools.contract_to_assert import contract_to_assert


# 一个简单的 filter C 代码（含 double filter(double)）
FILTER_CODE = """\
double filter(double input) {
    static double last = 0.0;
    double out = 0.9 * last + 0.1 * input;
    last = out;
    return out;
}
"""

# 测试用契约 YAML（含后置条件：output >= 0）
SAMPLE_CONTRACT = """\
component: test_filter
version: 1.0.0
safety_level: DAL-B
traceability: [REQ-001]

interface:
  inputs:
    - name: raw_input
      type: double
      range: [0, 20000]
  outputs:
    - name: filtered_output
      type: double

contracts:
  preconditions:
    - "raw_input != NULL"
    - "raw_input >= 0"
  postconditions:
    - "filtered_output >= 0"
    - "filtered_output <= 20000"
  invariants:
    - "sample_rate == 100Hz"
  fault_handling:
    - "if raw_input == 0: set fault_detected = true"
"""


class TestVirtualSensor(unittest.TestCase):
    """虚拟传感器测试。"""

    def setUp(self) -> None:
        self.sensor = VirtualSensor()

    def test_generate_normal_default(self) -> None:
        """默认配置生成正弦波。"""
        data = self.sensor.generate_normal()
        self.assertEqual(len(data), 200)
        self.assertEqual(data.dtype, np.float64)
        # 正弦波应在 [-100, 100] 范围内
        self.assertGreaterEqual(data.max(), 50.0)
        self.assertLessEqual(abs(data.max()), 100.0 + 1e-6)

    def test_generate_normal_sine(self) -> None:
        """正弦波生成。"""
        data = self.sensor.generate_normal(
            steps=200,
            config={"wave_type": "sine", "amplitude": 50.0, "frequency": 1.0},
        )
        self.assertEqual(len(data), 200)
        # frequency=1.0 + steps=200 + dt=0.01 → t_max=1.99s，
        # 2*pi*1.0*1.99 ≈ 12.5 rad，覆盖 2 个完整周期，必有负值
        self.assertGreater(data.max(), 0)
        self.assertLess(data.min(), 0)

    def test_generate_normal_ramp(self) -> None:
        """斜坡波形。"""
        data = self.sensor.generate_normal(
            steps=50, config={"wave_type": "ramp", "amplitude": 100.0}
        )
        self.assertEqual(len(data), 50)
        self.assertAlmostEqual(data[0], 0.0, places=1)
        self.assertAlmostEqual(data[-1], 100.0, places=1)

    def test_generate_normal_step(self) -> None:
        """阶跃波形。"""
        data = self.sensor.generate_normal(
            steps=20, config={"wave_type": "step", "amplitude": 80.0}
        )
        self.assertAlmostEqual(data[0], 0.0, places=6)
        self.assertAlmostEqual(data[-1], 80.0, places=6)

    def test_generate_normal_constant(self) -> None:
        """常量波形。"""
        data = self.sensor.generate_normal(
            steps=10, config={"wave_type": "constant", "amplitude": 42.0}
        )
        for v in data:
            self.assertAlmostEqual(v, 42.0, places=6)

    def test_generate_normal_noise_wave(self) -> None:
        """高斯噪声波形。"""
        data = self.sensor.generate_normal(
            steps=100, config={"wave_type": "noise", "amplitude": 10.0}
        )
        self.assertEqual(len(data), 100)

    def test_generate_normal_with_noise(self) -> None:
        """正弦波叠加噪声。"""
        clean = self.sensor.generate_normal(steps=100, config={"noise_level": 0.0})
        noisy = self.sensor.generate_normal(steps=100, config={"noise_level": 5.0})
        self.assertGreater(np.std(noisy - clean), 0)

    def test_generate_normal_invalid_steps(self) -> None:
        """steps <= 0 应抛 ValueError。"""
        with self.assertRaises(ValueError):
            self.sensor.generate_normal(steps=0)
        with self.assertRaises(ValueError):
            self.sensor.generate_normal(steps=-1)

    def test_generate_normal_invalid_wave_type(self) -> None:
        """不支持的 wave_type 应抛 ValueError。"""
        with self.assertRaises(ValueError):
            self.sensor.generate_normal(config={"wave_type": "unknown"})

    def test_inject_fault_bias(self) -> None:
        """bias 故障：整体加偏置。"""
        data = self.sensor.generate_normal(steps=50, config={"amplitude": 100.0})
        biased = self.sensor.inject_fault(data, "bias", {"bias_value": 50.0})
        self.assertAlmostEqual(np.mean(biased - data), 50.0, places=6)
        self.assertNotEqual(np.mean(data), np.mean(biased))

    def test_inject_fault_signal_loss(self) -> None:
        """signal_loss 故障：指定区间设为 0。"""
        data = self.sensor.generate_normal(steps=50)
        lossy = self.sensor.inject_fault(data, "signal_loss", {"start": 10, "end": 20})
        for i in range(10, 20):
            self.assertAlmostEqual(lossy[i], 0.0, places=6)
        self.assertAlmostEqual(lossy[0], data[0], places=6)
        self.assertAlmostEqual(lossy[30], data[30], places=6)

    def test_inject_fault_noise(self) -> None:
        """noise 故障：叠加随机噪声。"""
        data = self.sensor.generate_normal(steps=50, config={"noise_level": 0.0})
        noisy = self.sensor.inject_fault(data, "noise", {"amplitude": 50.0})
        self.assertFalse(np.array_equal(data, noisy))

    def test_inject_fault_stuck(self) -> None:
        """stuck 故障：指定区间卡死。"""
        data = self.sensor.generate_normal(steps=50)
        stuck = self.sensor.inject_fault(
            data, "stuck", {"start": 5, "end": 15, "stuck_value": 999.0}
        )
        for i in range(5, 15):
            self.assertAlmostEqual(stuck[i], 999.0, places=6)
        self.assertAlmostEqual(stuck[0], data[0], places=6)

    def test_inject_fault_step(self) -> None:
        """step 故障：阶跃突变。"""
        data = self.sensor.generate_normal(steps=50)
        stepped = self.sensor.inject_fault(
            data, "step", {"step_at": 25, "step_value": 1000.0}
        )
        self.assertAlmostEqual(stepped[30] - data[30], 1000.0, places=6)
        self.assertAlmostEqual(stepped[0], data[0], places=6)

    def test_inject_fault_invalid_type(self) -> None:
        """不支持的故障类型应抛 ValueError。"""
        data = self.sensor.generate_normal(steps=10)
        with self.assertRaises(ValueError):
            self.sensor.inject_fault(data, "unknown_fault", {})

    def test_to_csv(self) -> None:
        """CSV 字符串转换。"""
        data = np.array([1.0, 2.5, 3.14], dtype=np.float64)
        csv = self.sensor.to_csv(data)
        lines = csv.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertAlmostEqual(float(lines[0]), 1.0, places=6)
        self.assertAlmostEqual(float(lines[1]), 2.5, places=6)
        self.assertAlmostEqual(float(lines[2]), 3.14, places=4)


class TestVirtualMCU(unittest.TestCase):
    """虚拟 MCU 测试。"""

    def setUp(self) -> None:
        self.mcu = VirtualMCU()
        # GCC 可用时强制走真实编译路径（默认 USE_REAL_GCC=false 走 Mock）
        self._original_use_real_gcc = settings.USE_REAL_GCC
        settings.USE_REAL_GCC = True

    def tearDown(self) -> None:
        settings.USE_REAL_GCC = self._original_use_real_gcc

    def test_is_gcc_available(self) -> None:
        """is_gcc_available 返回布尔值。"""
        available = self.mcu.is_gcc_available()
        self.assertIsInstance(available, bool)

    def test_compile_success_or_mock(self) -> None:
        """编译成功（有 GCC）或 mock 降级（无 GCC）。"""
        result = self.mcu.compile(FILTER_CODE)
        if self.mcu.is_gcc_available():
            self.assertTrue(result.success)
            self.assertFalse(result.used_mock)
            self.assertNotEqual(result.executable_path, "")
        else:
            self.assertTrue(result.used_mock)
            self.assertTrue(result.success)
        if not result.used_mock:
            self.mcu.cleanup(result)

    def test_compile_failure_bad_code(self) -> None:
        """非法 C 代码编译失败时降级到 Mock，编译错误被记录（GCC 可用时）。"""
        if not self.mcu.is_gcc_available():
            self.skipTest("GCC 未安装，跳过编译失败测试")
        bad_code = "int this is not valid C code;\n"
        result = self.mcu.compile(bad_code)
        # 设计：GCC 编译失败 → 降级 Mock（success=True, used_mock=True），
        # errors 保留 GCC 的编译错误信息（证明 GCC 确实识别了非法代码）
        self.assertTrue(result.used_mock, "编译失败应降级到 mock")
        self.assertNotEqual(result.errors, "", "编译错误信息应被保留")
        self.mcu.cleanup(result)

    def test_run_mock_mode(self) -> None:
        """mock 模式运行：低通滤波输出。"""
        input_data = np.linspace(0, 100, 50)
        result = self.mcu.run(
            executable_path="",
            input_data=input_data,
            timeout=10,
            used_mock=True,
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.output_data), 50)
        self.assertGreater(result.output_data[-1], result.output_data[0])
        self.assertEqual(result.return_code, 0)
        self.assertFalse(result.assertion_failed)

    def test_run_native_mode(self) -> None:
        """原生模式运行（GCC 可用时）。"""
        if not self.mcu.is_gcc_available():
            self.skipTest("GCC 未安装，跳过原生运行测试")
        compile_result = self.mcu.compile(FILTER_CODE)
        self.assertTrue(compile_result.success)
        try:
            input_data = np.linspace(0, 100, 50)
            result = self.mcu.run(
                compile_result.executable_path,
                input_data,
                timeout=10,
                used_mock=False,
            )
            self.assertTrue(result.success)
            self.assertEqual(len(result.output_data), 50)
            for v in result.output_data:
                self.assertFalse(np.isnan(v), "输出含 NaN")
                self.assertFalse(np.isinf(v), "输出含 Inf")
        finally:
            self.mcu.cleanup(compile_result)

    def test_run_assertion_detection(self) -> None:
        """测试断言失败检测逻辑。"""
        result = RunResult(
            success=False,
            stderr="Assertion failed: [CON-001-POST-000] 违反后置条件",
            assertion_failed=True,
            assertion_message="Assertion failed",
            failed_step=42,
        )
        self.assertTrue(result.assertion_failed)
        self.assertEqual(result.failed_step, 42)

    def test_detect_assertion_failure(self) -> None:
        """断言失败检测关键词覆盖。"""
        for kw in ["assertion failed", "core dump", "aborted", "SIGSEGV"]:
            self.assertTrue(VirtualMCU._detect_assertion_failure(kw))
        self.assertFalse(VirtualMCU._detect_assertion_failure("normal output"))
        self.assertFalse(VirtualMCU._detect_assertion_failure(""))


class TestFaultInjector(unittest.TestCase):
    """故障注入器测试。"""

    def setUp(self) -> None:
        self.injector = FaultInjector()
        self.sensor = VirtualSensor()
        self.data = self.sensor.generate_normal(steps=100)

    def test_get_fault_types(self) -> None:
        """get_fault_types 返回所有支持的故障类型。"""
        types = self.injector.get_fault_types()
        type_names = {t["type"] for t in types}
        expected = {"bias", "signal_loss", "noise", "stuck", "step"}
        self.assertGreaterEqual(len(types), 5)
        self.assertTrue(expected.issubset(type_names), f"缺失基础故障类型, 实际: {type_names}")
        for t in types:
            self.assertIn("name", t)
            self.assertIn("desc", t)
            self.assertIn("default_params", t)
            self.assertIn("params_schema", t)

    def test_validate_params_valid(self) -> None:
        """合法参数通过校验。"""
        self.assertTrue(self.injector.validate_params("bias", {"bias_value": 50.0}))
        self.assertTrue(
            self.injector.validate_params("signal_loss", {"start": 0, "end": 50})
        )
        self.assertTrue(
            self.injector.validate_params(
                "stuck", {"start": 0, "end": 50, "stuck_value": 0.0}
            )
        )

    def test_validate_params_invalid(self) -> None:
        """非法参数校验失败。"""
        self.assertFalse(self.injector.validate_params("unknown", {}))
        self.assertFalse(self.injector.validate_params("bias", {}))
        self.assertFalse(
            self.injector.validate_params("signal_loss", {"start": 50, "end": 10})
        )
        self.assertFalse(
            self.injector.validate_params("step", {"step_at": -1, "step_value": 100.0})
        )

    def test_inject_each_fault(self) -> None:
        """每类故障都能成功注入。"""
        for fault_type, params in [
            ("bias", {"bias_value": 50.0}),
            ("signal_loss", {"start": 10, "end": 20}),
            ("noise", {"amplitude": 50.0}),
            ("stuck", {"start": 10, "end": 20, "stuck_value": 999.0}),
            ("step", {"step_at": 50, "step_value": 1000.0}),
        ]:
            injected = self.injector.inject(self.data, fault_type, params)
            self.assertEqual(len(injected), 100)
            self.assertFalse(np.array_equal(self.data, injected))

    def test_inject_invalid_fault_raises(self) -> None:
        """非法故障类型抛 ValueError。"""
        with self.assertRaises(ValueError):
            self.injector.inject(self.data, "unknown", {})


class TestSimulationEngine(unittest.TestCase):
    """仿真引擎测试。"""

    def setUp(self) -> None:
        self.engine = SimulationEngine()

    def test_simulation_engine_normal(self) -> None:
        """正常仿真（无故障）→ passed=True。"""
        result = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            fault_type=None,
            fault_params=None,
            steps=100,
        )
        self.assertTrue(result.passed, f"仿真应通过: {result.terminal_log}")
        self.assertEqual(result.total_steps, 100)
        self.assertEqual(len(result.input_waveform), 100)
        self.assertEqual(len(result.output_waveform), 100)
        self.assertIsNone(result.contract_violation)
        self.assertIn("input_min", result.statistics)
        self.assertIn("output_min", result.statistics)
        self.assertIn("duration_ms", result.statistics)
        self.assertIn("success", result.compilation)
        self.assertIn("[1/6]", result.terminal_log)
        self.assertIn("[6/6]", result.terminal_log)

    def test_simulation_engine_with_fault(self) -> None:
        """注入故障→仿真完成（输出不同于正常）。"""
        normal = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            steps=100,
        )
        faulty = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            fault_type="bias",
            fault_params={"bias_value": 1000.0},
            steps=100,
        )
        self.assertEqual(faulty.fault_type, "bias")
        self.assertEqual(faulty.fault_params, {"bias_value": 1000.0})
        self.assertNotEqual(normal.input_waveform, faulty.input_waveform)

    def test_simulation_engine_signal_loss(self) -> None:
        """signal_loss 故障注入。"""
        result = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            fault_type="signal_loss",
            fault_params={"start": 0, "end": 50},
            steps=100,
        )
        for i in range(50):
            self.assertAlmostEqual(result.input_waveform[i], 0.0, places=6)
        self.assertGreater(abs(result.input_waveform[60]), 0)

    def test_simulation_engine_invalid_fault(self) -> None:
        """非法故障参数应返回失败结果。"""
        result = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            fault_type="unknown",
            fault_params={},
            steps=50,
        )
        self.assertFalse(result.passed)
        self.assertIsNotNone(result.compilation.get("errors"))

    def test_simulation_engine_no_contract(self) -> None:
        """无契约 YAML 也能仿真（跳过断言注入）。"""
        result = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml="",
            steps=50,
        )
        self.assertTrue(result.passed)
        self.assertIn("无契约", result.terminal_log)

    def test_simulation_result_to_dict(self) -> None:
        """to_dict 返回可序列化字典。"""
        result = self.engine.run_simulation(
            code=FILTER_CODE,
            contract_yaml=SAMPLE_CONTRACT,
            steps=20,
        )
        d = result.to_dict()
        self.assertIn("passed", d)
        self.assertIn("total_steps", d)
        self.assertIn("input_waveform", d)
        self.assertIn("output_waveform", d)
        self.assertIn("statistics", d)
        self.assertIn("compilation", d)
        self.assertIn("terminal_log", d)


class TestContractAssertInjection(unittest.TestCase):
    """契约断言注入测试。"""

    def test_contract_to_assert_generates_check_function(self) -> None:
        """contract_to_assert 生成 __check_contract_step_<cid> 函数。"""
        # cid 含连字符时，contract_to_assert 直接拼接（Patch 2 行为）
        # VirtualMCU._generate_test_harness 会净化为合法 C 标识符
        assert_code = contract_to_assert(SAMPLE_CONTRACT, cid="CON-001")
        self.assertIn("__check_contract_step_CON-001", assert_code)
        self.assertIn("assert(", assert_code)
        self.assertIn("isnan", assert_code)

    def test_assert_code_injected_to_harness(self) -> None:
        """断言代码被注入到 test_harness.c（连字符净化为下划线）。"""
        mcu = VirtualMCU()
        assert_code = contract_to_assert(SAMPLE_CONTRACT, cid="CON-001")
        harness = mcu._generate_test_harness(FILTER_CODE, assert_code)
        self.assertIn("double filter(double input)", harness)
        # 净化后：CON-001 → CON_001（合法 C 标识符）
        self.assertIn("__check_contract_step_CON_001", harness)
        self.assertIn("__check_contract_step_CON_001(out_val)", harness)
        self.assertIn("int main(void)", harness)
        self.assertIn("fgets(line", harness)

    def test_no_assert_code_injects_placeholder(self) -> None:
        """无断言代码时注入占位注释。"""
        mcu = VirtualMCU()
        harness = mcu._generate_test_harness(FILTER_CODE, "")
        self.assertIn("无契约断言", harness)
        self.assertNotIn("__check_contract_step_", harness)

    def test_auto_add_filter_when_missing(self) -> None:
        """用户代码缺少 filter 函数时自动添加示例。"""
        mcu = VirtualMCU()
        code_without_filter = "int some_var = 0;\n"
        harness = mcu._generate_test_harness(code_without_filter, "")
        self.assertIn("double filter(double input)", harness)


class TestMockMode(unittest.TestCase):
    """mock 模式优雅降级测试。"""

    def test_mock_mode_run(self) -> None:
        """mock 模式 run 返回低通滤波输出。"""
        mcu = VirtualMCU()
        input_data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result = mcu.run("", input_data, used_mock=True)
        self.assertTrue(result.success)
        self.assertEqual(len(result.output_data), 5)
        # 一阶低通滤波：y = 0.9 * y_prev + 0.1 * x
        # y[0] = 0.9*0 + 0.1*10 = 1.0
        self.assertAlmostEqual(result.output_data[0], 1.0, places=4)
        # y[1] = 0.9*1 + 0.1*20 = 2.9
        self.assertAlmostEqual(result.output_data[1], 2.9, places=4)


if __name__ == "__main__":
    unittest.main()
