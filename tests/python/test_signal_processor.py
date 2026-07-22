"""
@file test_signal_processor.py
@brief 军工软件Python编程规范示例 — 单元测试

测试覆盖:
- SignalProcessor 创建、初始化、重置
- 信号处理逻辑（正常/边界/异常）
- 缓冲区管理
- 异常处理
- 编码规范验证

运行: pytest test_signal_processor.py -v
"""

import pytest
import sys
import os

# 添加模板路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'python'))

from signal_processor import (
    SignalProcessor,
    SensorReading,
    DataQuality,
    create_processor,
    validate_input,
    MAX_BUFFER_SIZE,
)


# ==================== SignalProcessor 测试 ====================

class TestSignalProcessor:
    """SignalProcessor 单元测试。"""

    def test_creation(self):
        """测试处理器创建。"""
        processor = SignalProcessor()
        assert processor._initialized is True
        assert processor._buffer_size == 1024

    def test_creation_with_custom_size(self):
        """测试自定义缓冲区大小。"""
        processor = SignalProcessor(buffer_size=512)
        assert processor._buffer_size == 512

    def test_creation_invalid_size(self):
        """测试无效缓冲区大小。"""
        with pytest.raises(ValueError):
            SignalProcessor(buffer_size=0)
        with pytest.raises(ValueError):
            SignalProcessor(buffer_size=-1)

    def test_process_normal(self):
        """测试正常信号处理。"""
        processor = SignalProcessor()
        
        result1 = processor.process(100.0)
        assert 0.0 <= result1 <= 20000.0
        
        result2 = processor.process(100.0)
        assert 0.0 <= result2 <= 20000.0
        
        # 输出应该接近输入（滤波器收敛）
        assert abs(result2 - 100.0) < 50.0

    def test_process_out_of_range(self):
        """测试超出范围输入。"""
        processor = SignalProcessor()
        
        result1 = processor.process(20001.0)
        assert result1 == 0.0
        
        result2 = processor.process(-1.0)
        assert result2 == 0.0

    def test_process_boundary(self):
        """测试边界值。"""
        processor = SignalProcessor()
        
        result_min = processor.process(0.0)
        assert result_min >= 0.0
        
        result_max = processor.process(20000.0)
        assert result_max >= 0.0

    def test_buffer_management(self):
        """测试缓冲区管理。"""
        processor = SignalProcessor(buffer_size=5)
        
        for i in range(10):
            processor.process(float(i))
        
        buffer = processor.get_buffer()
        assert len(buffer) == 5
        assert buffer[-1] > 0.0

    def test_reset(self):
        """测试重置功能。"""
        processor = SignalProcessor()
        processor.process(100.0)
        processor.process(200.0)
        
        processor.reset()
        buffer = processor.get_buffer()
        assert len(buffer) == 0

    def test_not_initialized(self):
        """测试未初始化异常。"""
        processor = SignalProcessor()
        processor._initialized = False
        
        with pytest.raises(RuntimeError):
            processor.process(100.0)


# ==================== SensorReading 测试 ====================

class TestSensorReading:
    """SensorReading 单元测试。"""

    def test_creation(self):
        """测试读数创建。"""
        reading = SensorReading(
            sensor_id=1,
            value=25.5,
            timestamp=1000.0
        )
        assert reading.sensor_id == 1
        assert reading.value == 25.5
        assert reading.quality == DataQuality.GOOD

    def test_is_valid(self):
        """测试有效性检查。"""
        good = SensorReading(1, 25.5, 1000.0, DataQuality.GOOD)
        bad = SensorReading(1, 25.5, 1000.0, DataQuality.BAD)
        
        assert good.is_valid() is True
        assert bad.is_valid() is False


# ==================== 工具函数测试 ====================

class TestUtilityFunctions:
    """工具函数单元测试。"""

    def test_create_processor(self):
        """测试工厂函数。"""
        processor = create_processor()
        assert isinstance(processor, SignalProcessor)

    def test_validate_input(self):
        """测试输入验证。"""
        assert validate_input(100.0) is True
        assert validate_input(0.0) is True
        assert validate_input(20000.0) is True
        assert validate_input(-1.0) is False
        assert validate_input(20001.0) is False


# ==================== 编码规范验证 ====================

class TestCodingStandards:
    """编码规范验证测试。"""

    def test_no_eval_exec(self):
        """P-01: 验证禁止使用 eval/exec。"""
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'python', 'signal_processor.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'eval(' not in content
        assert 'exec(' not in content

    def test_type_annotations(self):
        """T-01: 验证所有函数有类型标注。"""
        import inspect
        from signal_processor import SignalProcessor, create_processor, validate_input
        
        # 检查类方法
        sig = inspect.signature(SignalProcessor.__init__)
        assert sig.return_annotation != inspect.Parameter.empty
        
        sig = inspect.signature(SignalProcessor.process)
        assert sig.return_annotation != inspect.Parameter.empty
        
        # 检查模块函数
        sig = inspect.signature(create_processor)
        assert sig.return_annotation != inspect.Parameter.empty
        
        sig = inspect.signature(validate_input)
        assert sig.return_annotation != inspect.Parameter.empty

    def test_snake_case_naming(self):
        """验证 snake_case 命名规范。"""
        import inspect
        from signal_processor import SignalProcessor, create_processor, validate_input
        
        # 检查方法名
        assert hasattr(SignalProcessor, 'process')
        assert hasattr(SignalProcessor, 'reset')
        assert hasattr(SignalProcessor, 'get_buffer')
        
        # 检查函数名
        assert callable(create_processor)
        assert callable(validate_input)
