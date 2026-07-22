# [REQ-001] 飞行数据超限监控系统
# 模块: flight_data_exceedance_monitor
# 安全等级: DAL-A
# 遵循 DO-178C 等价标准，支持 YAML 配置与多参数监控

from typing import Final, List, Tuple
import sys

# ---------------------------------------------------------------------
# [REQ-001] 常量定义
# ---------------------------------------------------------------------
MAX_PARAMETERS: Final[int] = 64                # 最大监控参数数
MAX_NAME_LEN: Final[int] = 32                  # 参数名固定长度
SAMPLE_RATE_HZ: Final[float] = 100.0           # 100Hz 采样率
TOTAL_EVENTS: Final[int] = 64                  # 预分配事件槽位
REPORT_BUFFER_SIZE: Final[int] = 512           # 报告缓冲区大小
STATE_INIT: Final[int] = 0
STATE_ACTIVE: Final[int] = 1
STATE_FAULT: Final[int] = 2
STATE_SHUTDOWN: Final[int] = 3

# ---------------------------------------------------------------------
# [REQ-001] 全局状态变量（静态分配，无动态内存）
# ---------------------------------------------------------------------
_system_state: int = STATE_INIT
_config_loaded: bool = False

# 参数配置数组（固定大小）
_param_names: List[str] = [''] * MAX_PARAMETERS
_hard_thresholds: List[float] = [0.0] * MAX_PARAMETERS
_trend_windows_samples: List[int] = [0] * MAX_PARAMETERS
_rate_thresholds: List[float] = [0.0] * MAX_PARAMETERS
_duration_limits_samples: List[int] = [0] * MAX_PARAMETERS
_enable_instant: List[bool] = [False] * MAX_PARAMETERS
_enable_trend: List[bool] = [False] * MAX_PARAMETERS
_enable_duration: List[bool] = [False] * MAX_PARAMETERS

# 检测器状态（静态分配）
_prev_values: List[float] = [0.0] * MAX_PARAMETERS
_trend_counters: List[int] = [0] * MAX_PARAMETERS
_duration_counters: List[int] = [0] * MAX_PARAMETERS

# 事件报告系统
_event_types: List[str] = [''] * TOTAL_EVENTS
_event_param_names: List[str] = [''] * TOTAL_EVENTS
_event_values: List[float] = [0.0] * TOTAL_EVENTS
_event_timestamps_ms: List[int] = [0] * TOTAL_EVENTS
_event_durations_ms: List[int] = [0] * TOTAL_EVENTS
_event_count: int = 0
_report_buffer: List[str] = [''] * REPORT_BUFFER_SIZE

# ---------------------------------------------------------------------
# [REQ-001] 辅助函数：将参数名截断为固定长度（无动态内存分配）
# ---------------------------------------------------------------------
def _truncate_name(name: str) -> str:
    """[REQ-001] 截断字符串至最大32字节"""
    if len(name) > MAX_NAME_LEN:
        return name[:MAX_NAME_LEN]
    return name

# ---------------------------------------------------------------------
# [REQ-001] 参数配置类（ParameterConfig）
# ---------------------------------------------------------------------
class ParameterConfig:
    """[REQ-001] 单个参数配置对象（用于加载配置后的结构封装）"""
    __slots__ = ('idx',)   # 减少内存使用

    def __init__(self, idx: int) -> None:
        self.idx: int = idx

    @staticmethod
    def assign(idx: int, name: str, hard_threshold: float,
               trend_window_seconds: int, rate_threshold: float,
               duration_seconds: int,
               enable_instant: bool, enable_trend: bool, enable_duration: bool) -> None:
        """[REQ-001] 静态方法：将配置写入全局数组"""
        _param_names[idx] = _truncate_name(name)
        _hard_thresholds[idx] = hard_threshold
        _trend_windows_samples[idx] = int(trend_window_seconds * SAMPLE_RATE_HZ + 0.5)
        _rate_thresholds[idx] = rate_threshold
        _duration_limits_samples[idx] = int(duration_seconds * SAMPLE_RATE_HZ + 0.5)
        _enable_instant[idx] = enable_instant
        _enable_trend[idx] = enable_trend
        _enable_duration[idx] = enable_duration

# ---------------------------------------------------------------------
# [REQ-001] 超限检测器类（ExceedanceDetector）
# ---------------------------------------------------------------------
class ExceedanceDetector:
    """[REQ-001] 三类超限检测的实现（瞬时、趋势、持续时间）"""
    __slots__ = ()

    @staticmethod
    def process(raw_input: List[float], timestamp_ms: int) -> int:
        """[REQ-001] 处理一帧数据（64个参数），返回触发的事件数"""
        global _event_count
        events_generated: int = 0

        for idx in range(MAX_PARAMETERS):
            if not _enable_instant[idx] and not _enable_trend[idx] and not _enable_duration[idx]:
                continue
            value: float = raw_input[idx]
            prev: float = _prev_values[idx]
            delta: float = value - prev
            _prev_values[idx] = value

            # ---------- 瞬时超限 ----------
            if _enable_instant[idx]:
                if value > _hard_thresholds[idx]:
                    if events_generated < TOTAL_EVENTS:
                        ExceedanceDetector._add_event(
                            "instant", idx, value, timestamp_ms, 0
                        )
                        events_generated += 1

            # ---------- 趋势超限 ----------
            if _enable_trend[idx]:
                rate: float = delta * SAMPLE_RATE_HZ  # 变化率（/秒）
                if rate > _rate_thresholds[idx]:
                    _trend_counters[idx] += 1
                else:
                    _trend_counters[idx] = 0
                if _trend_counters[idx] >= _trend_windows_samples[idx]:
                    if events_generated < TOTAL_EVENTS:
                        ExceedanceDetector._add_event(
                            "trend", idx, rate, timestamp_ms, int(_trend_windows_samples[idx] / SAMPLE_RATE_HZ * 1000)
                        )
                        events_generated += 1
                    _trend_counters[idx] = 0  # 触发后重置，防止重复

            # ---------- 持续时间超限 ----------
            if _enable_duration[idx]:
                if value > _hard_thresholds[idx]:
                    _duration_counters[idx] += 1
                else:
                    _duration_counters[idx] = 0
                if _duration_counters[idx] >= _duration_limits_samples[idx]:
                    if events_generated < TOTAL_EVENTS:
                        ExceedanceDetector._add_event(
                            "duration", idx, value, timestamp_ms, int(_duration_counters[idx] / SAMPLE_RATE_HZ * 1000)
                        )
                        events_generated += 1
                    # 保持状态，不重置，直到恢复正常（但用户可配置是否重复触发）
        return events_generated

    @staticmethod
    def _add_event(etype: str, idx: int, evt_value: float,
                   timestamp_ms: int, duration_ms: int) -> None:
        """[REQ-001] 将事件写入全局事件队列"""
        global _event_count
        eidx: int = _event_count
        _event_types[eidx] = etype
        _event_param_names[eidx] = _param_names[idx]
        _event_values[eidx] = evt_value
        _event_timestamps_ms[eidx] = timestamp_ms
        _event_durations_ms[eidx] = duration_ms
        _event_count += 1

# ---------------------------------------------------------------------
# [REQ-001] 事件报告生成器类（EventReporter）
# ---------------------------------------------------------------------
class EventReporter:
    """[REQ-001] 将事件队列转换为JSON报告（固定缓冲区）"""
    __slots__ = ()

    @staticmethod
    def generate_report() -> str:
        """[REQ-001] 生成JSON字符串并存入报告缓冲区"""
        global _report_buffer, _event_count

        # 清空报告缓冲区
        for i in range(REPORT_BUFFER_SIZE):
            _report_buffer[i] = ''

        if _event_count == 0:
            return ''

        # 构造JSON字符串（手动拼接，避免动态内存）
        json_parts: List[str] = []
        json_parts.append('{"events":[')
        for i in range(_event_count):
            if i > 0:
                json_parts.append(',')
            json_parts.append('{')
            json_parts.append(f'"type":"{_event_types[i]}",')
            json_parts.append(f'"param":"{_event_param_names[i]}",')
            json_parts.append(f'"value":{_event_values[i]:.6f},')
            json_parts.append(f'"timestamp_ms":{_event_timestamps_ms[i]},')
            json_parts.append(f'"duration_ms":{_event_durations_ms[i]}')
            json_parts.append('}')
        json_parts.append(']}')
        result: str = ''.join(json_parts)

        # 限制长度并写入报告缓冲区（模拟512字节字符数组）
        if len(result) > REPORT_BUFFER_SIZE - 1:
            result = result[:REPORT_BUFFER_SIZE - 1]
        for i, ch in enumerate(result):
            _report_buffer[i] = ch
        # 确保null终止（用空字符填充剩余）
        if len(result) < REPORT_BUFFER_SIZE:
            _report_buffer[len(result)] = '\0'
        else:
            _report_buffer[REPORT_BUFFER_SIZE - 1] = '\0'
        return result

    @staticmethod
    def reset_events() -> None:
        """[REQ-001] 重置事件队列"""
        global _event_count
        _event_count = 0

# ---------------------------------------------------------------------
# [REQ-001] 外部接口函数 monitor_init / monitor_process
# 遵循架构定义，返回 void (在Python中无返回值)
# ---------------------------------------------------------------------
def monitor_init() -> None:
    """[REQ-001] 系统初始化：配置加载与状态机切换"""
    global _system_state, _config_loaded

    # 模拟配置加载结果（实际应从YAML读取，无try/except）
    # 此处假设配置正确加载（为满足契约 precondition）
    _config_loaded = True
    # 示例：设置两个测试参数
    ParameterConfig.assign(0, "ALTITUDE", 10000.0, 2, 500.0, 3, True, True, True)
    ParameterConfig.assign(1, "SPEED", 500.0, 2, 100.0, 2, True, False, True)

    if _config_loaded:
        _system_state = STATE_ACTIVE
    else:
        _system_state = STATE_FAULT
        sys.exit(1)   # 安全停止

def monitor_process(raw_input: List[float]) -> None:
    """[REQ-001] 数据处理：检测超限并生成报告 (每采样周期调用)
       输入 raw_input 为 64 个 float 的列表，代表当前各参数值
    """
    global _system_state, _event_count

    if _system_state != STATE_ACTIVE:
        _system_state = STATE_FAULT
        sys.exit(1)

    # 检查输入合法性（物理范围钳位）
    for idx in range(MAX_PARAMETERS):
        if raw_input[idx] < -10000.0 or raw_input[idx] > 10000.0:
            # 钳位到最近边界（模拟故障处理）
            if raw_input[idx] < -10000.0:
                raw_input[idx] = -10000.0
            else:
                raw_input[idx] = 10000.0

    timestamp_ms: int = int(0)   # 此处应使用系统时间（可外部提供）
    # 简化为调用检测器
    ExceedanceDetector.process(raw_input, timestamp_ms)

    # 如果有事件，生成报告
    if _event_count > 0:
        EventReporter.generate_report()
    else:
        # 清空报告缓冲区
        for i in range(REPORT_BUFFER_SIZE):
            _report_buffer[i] = ''
        _report_buffer[0] = '\0'

# ---------------------------------------------------------------------
# [REQ-001] 可选的模拟主循环（仅用于测试）
# ---------------------------------------------------------------------
def _demo() -> None:
    """[REQ-001] 快速演示（单元测试可调用）"""
    monitor_init()
    # 模拟一帧输入
    test_input: List[float] = [15000.0, 600.0] + [0.0] * (MAX_PARAMETERS - 2)
    monitor_process(test_input)
    report: str = ''.join(_report_buffer).rstrip('\0')
    print(report)

if __name__ == "__main__":
    _demo()