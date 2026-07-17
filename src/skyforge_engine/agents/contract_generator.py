"""契约生成 Agent：依据结构化需求生成 .contract YAML 内容
（前置/后置/不变式/故障处理）。
"""

import json
from typing import Any

try:
    from skyforge_llm.parser import safe_parse_llm_json
except ImportError:
    safe_parse_llm_json = lambda x: {} 
try:
    from skyforge_llm.client import get_lmstudio_client
except ImportError:
    get_lmstudio_client = None
from skyforge_engine.utils.log_util import logger

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C 机载系统契约工程师，专职依据结构化需求生成
.contract YAML（前置条件/后置条件/不变式/故障处理），确保接口契约满足适航
可验证性。你必须以设计契约视角工作，所有断言必须可在 C 代码中断言。

## 可用工具
- design_contract(req_json) 依据需求 JSON 生成契约骨架
- define_interface(module) 定义输入/输出接口与量程
- gen_fault_handling(safety_level) 按 DAL 等级生成故障处理分支

## 输出格式（严格 YAML，禁止 JSON 包裹，禁止前后缀文字）
component: lowpass_filter_10hz
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
  postconditions:
    - "filtered_output >= 0"
  invariants:
    - "sample_rate == 100Hz"
  fault_handling:
    - "if raw_input == 0: set fault_detected = true"

## 禁忌
1. 禁止生成与 safety_level 不符的耦合结构（DAL-A 禁止外部全局状态）
2. 禁止输出 YAML 以外的任何文字（含解释、JSON 包裹、Markdown 代码块）
3. 禁止遗漏 fault_handling 段（机载软件必须含故障处理）
4. 禁止使用动态内存相关字段（MISRA Rule-21.3）
5. traceability 必须包含对应 [REQ-xxx]"""


class ContractGeneratorAgent:
    """契约生成 Agent。

    输入：RequirementParserAgent 产出的结构化需求 JSON。
    输出：.contract YAML 文件内容（字符串），格式参考设计文档第 6.3 节。

    LM Studio 可用（USE_LLM=true）时调用真实 LLM 做契约补全；
    否则降级为按类型套用机载契约模板的 Mock 实现。
    """

    async def run(self, requirement_json: dict[str, Any]) -> str:
        """根据结构化需求生成 .contract YAML 字符串。

        Args:
            requirement_json: 结构化需求字典（含 req_id/desc/type/params 等）。

        Returns:
            .contract YAML 文本。
        """
        logger.info(
            f"ContractGeneratorAgent:开始:为 {requirement_json.get('req_id')} 生成契约"
        )

        # 检查 LM Studio 是否可用
        client = get_lmstudio_client()
        if client.is_available():
            logger.info("ContractGeneratorAgent:使用真实 LLM")
            try:
                prompt = (
                    f"请依据以下结构化需求生成 .contract YAML：\n"
                    f"{json.dumps(requirement_json, ensure_ascii=False, indent=2)}"
                )
                response = await client.chat_async(
                    prompt=prompt,
                    system_prompt=_SYSTEM_PROMPT,
                    temperature=0.4,
                )
                if response:
                    result = self._parse_llm_response(response)
                    if result:
                        logger.info(
                            f"ContractGeneratorAgent:完成:契约已生成 [LLM] "
                            f"(component={requirement_json.get('module_name')})"
                        )
                        return result
                logger.warning("ContractGeneratorAgent:LLM 调用失败，降级为 Mock")
            except Exception as e:
                logger.error(f"ContractGeneratorAgent:LLM 异常，降级为 Mock: {e}")

        # 降级为 Mock
        yaml_str = self._mock_run(requirement_json)
        logger.info(
            f"ContractGeneratorAgent:完成:契约已生成 [Mock] "
            f"(component={requirement_json.get('module_name')})"
        )
        return yaml_str

    def _mock_run(self, requirement_json: dict[str, Any]) -> str:
        """Mock 实现：按需求类型套用机载契约模板。"""
        req_type = requirement_json.get("type", "filter")
        generator = {
            "filter": self._gen_filter_contract,
            "control": self._gen_control_contract,
            "comms": self._gen_comms_contract,
            "navigation": self._gen_navigation_contract,
            "power": self._gen_power_contract,
        }.get(req_type, self._gen_filter_contract)
        return generator(requirement_json)

    def _parse_llm_response(self, response: str) -> str | None:
        """解析 LLM 输出的契约 YAML（失败返回 None）。

        LLM 应直接输出 YAML 文本，但也可能输出 JSON 包裹或 Markdown，
        此处做兜底提取：剥离 Markdown 包裹后返回纯文本。
        """
        text = response.strip()
        if not text:
            return None

        # 剥离 Markdown 代码块包裹（```yaml ... ``` 或 ``` ... ```）
        import re

        stripped = re.sub(
            r"^```(?:ya?ml)?\s*|\s*```$",
            "",
            text,
            flags=re.MULTILINE,
        ).strip()

        # 基本校验：必须包含机载契约的关键段
        required_keys = [
            "component:",
            "contracts:",
            "preconditions:",
            "postconditions:",
        ]
        missing = [k for k in required_keys if k not in stripped]
        if missing:
            # 尝试从 JSON 解析中提取（LLM 可能返回 JSON 而非 YAML）
            parsed = safe_parse_llm_json(text)
            if parsed and "component" in parsed:
                # 简单的 dict → YAML 文本拼接（保证可解析）
                return self._dict_to_yaml(parsed)
            logger.warning(
                f"ContractGeneratorAgent:LLM 输出缺字段 {missing}，降级为 Mock"
            )
            return None

        return stripped

    def _dict_to_yaml(self, d: dict) -> str:
        """将字典简单拼接为 YAML 文本（兜底，非完整 YAML 序列化）。"""
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{k}:")
                for kk, vv in v.items():
                    lines.append(f"  {kk}: {vv}")
            elif isinstance(v, list):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _gen_filter_contract(self, req: dict[str, Any]) -> str:
        """滤波器类契约模板（参考设计文档 6.3 节 altimeter_filter 示例）。"""
        module = req.get("module_name", "signal_filter")
        req_id = req.get("req_id", "REQ-001")
        safety = req.get("safety_level", "DAL-B")
        params = req.get("params", {})
        cutoff = params.get("cutoff_hz", 10.0)
        sample_rate = params.get("sample_rate_hz", 100.0)
        rmin = params.get("range_min", 0.0)
        rmax = params.get("range_max", 20000.0)

        return f"""component: {module}
version: 1.0.0
safety_level: {safety}
traceability: [{req_id}]

interface:
  inputs:
    - name: raw_input
      type: double
      unit: meter
      range: [{rmin}, {rmax}]
  outputs:
    - name: filtered_output
      type: double
      unit: meter
      range: [{rmin}, {rmax}]

contracts:
  preconditions:
    - "raw_input != NULL"
    - "raw_input >= {rmin} && raw_input <= {rmax}"
  postconditions:
    - "filtered_output >= {rmin}"
    - "filtered_output <= {rmax}"
    - "abs(filtered_output - raw_input) < 100 || fault_detected == true"
  invariants:
    - "filter_buffer initialized after init"
    - "sampling_rate == {sample_rate}Hz"
    - "cutoff_freq == {cutoff}Hz"
  fault_handling:
    - "if raw_input == 0 for > 0.5s: set fault_detected = true"
    - "if |delta| > 500: reject sample, use prediction"

composability:
  depends_on: []
  provides: [filtered_signal]
  consumes: [sensor_raw]
  timing:
    wcet: 1ms
    period: 10ms
"""

    def _gen_control_contract(self, req: dict[str, Any]) -> str:
        """控制律类契约模板。"""
        module = req.get("module_name", "control_law")
        req_id = req.get("req_id", "REQ-001")
        safety = req.get("safety_level", "DAL-A")
        return f"""component: {module}
version: 1.0.0
safety_level: {safety}
traceability: [{req_id}]

interface:
  inputs:
    - name: setpoint
      type: double
      range: [-1000, 1000]
    - name: measured
      type: double
      range: [-1000, 1000]
  outputs:
    - name: actuator_cmd
      type: double
      range: [-100, 100]

contracts:
  preconditions:
    - "setpoint != NULL"
    - "measured != NULL"
  postconditions:
    - "actuator_cmd >= -100"
    - "actuator_cmd <= 100"
    - "abs(actuator_cmd) <= 100 || fault_detected == true"
  invariants:
    - "control_law_period == 20ms"
  fault_handling:
    - "if |setpoint - measured| > 500: set fault_detected = true"

composability:
  depends_on: []
  provides: [actuator_command]
  consumes: [setpoint, measured]
  timing:
    wcet: 2ms
    period: 20ms
"""

    def _gen_comms_contract(self, req: dict[str, Any]) -> str:
        """通信处理类契约模板。"""
        module = req.get("module_name", "comms_handler")
        req_id = req.get("req_id", "REQ-001")
        safety = req.get("safety_level", "DAL-C")
        return f"""component: {module}
version: 1.0.0
safety_level: {safety}
traceability: [{req_id}]

interface:
  inputs:
    - name: rx_buffer
      type: uint8_t*
      range: [0, 255]
  outputs:
    - name: decoded_msg
      type: struct
      range: [valid, invalid]

contracts:
  preconditions:
    - "rx_buffer != NULL"
    - "buffer_length > 0"
  postconditions:
    - "decoded_msg == valid || decoded_msg == invalid"
    - "crc_check_pass == true || decoded_msg == invalid"
  invariants:
    - "baud_rate == 115200"
  fault_handling:
    - "if crc_check_fail_count > 3: set fault_detected = true"

composability:
  depends_on: []
  provides: [decoded_message]
  consumes: [raw_rx_buffer]
  timing:
    wcet: 5ms
    period: 50ms
"""

    def _gen_navigation_contract(self, req: dict[str, Any]) -> str:
        """导航处理类契约模板。"""
        module = req.get("module_name", "navigation_module")
        req_id = req.get("req_id", "REQ-001")
        safety = req.get("safety_level", "DAL-A")
        params = req.get("params", {})
        update_rate = params.get("update_rate_hz", 10.0)
        return f"""component: {module}
version: 1.0.0
safety_level: {safety}
traceability: [{req_id}]

interface:
  inputs:
    - name: gps_position
      type: struct
      range: [valid, invalid]
    - name: ins_data
      type: struct
      range: [valid, invalid]
  outputs:
    - name: fused_position
      type: struct
      range: [valid, invalid]
    - name: velocity
      type: double[3]
      range: [-500, 500]

contracts:
  preconditions:
    - "gps_position != NULL"
    - "ins_data != NULL"
    - "update_rate == {update_rate}Hz"
  postconditions:
    - "fused_position == valid || fallback_mode == true"
    - "abs(velocity[i]) < 500 for i in [0,1,2]"
  invariants:
    - "position_accuracy < 10m (GPS+INS fusion)"
    - "velocity_accuracy < 0.5m/s"
  fault_handling:
    - "if gps_signal_lost > 2s: switch to INS-only mode"
    - "if ins_drift > 100m: trigger fault alarm"

composability:
  depends_on: [gps_receiver, ins_sensor]
  provides: [fused_position, velocity]
  consumes: [gps_raw, ins_raw]
  timing:
    wcet: 5ms
    period: 100ms
"""

    def _gen_power_contract(self, req: dict[str, Any]) -> str:
        """电源管理类契约模板。"""
        module = req.get("module_name", "power_manager")
        req_id = req.get("req_id", "REQ-001")
        safety = req.get("safety_level", "DAL-B")
        params = req.get("params", {})
        battery_capacity = params.get("battery_capacity_mah", 10000)
        nominal_voltage = params.get("nominal_voltage_v", 28.0)
        return f"""component: {module}
version: 1.0.0
safety_level: {safety}
traceability: [{req_id}]

interface:
  inputs:
    - name: battery_voltage
      type: double
      range: [0, 50]
    - name: current_draw
      type: double
      range: [0, 100]
  outputs:
    - name: power_status
      type: enum
      range: [normal, low_battery, critical, fault]
    - name: remaining_capacity
      type: double
      range: [0, {battery_capacity}]

contracts:
  preconditions:
    - "battery_voltage >= 0"
    - "current_draw >= 0"
  postconditions:
    - "power_status in [normal, low_battery, critical, fault]"
    - "0 <= remaining_capacity <= {battery_capacity}"
  invariants:
    - "nominal_voltage == {nominal_voltage}V"
    - "capacity_update_rate == 1Hz"
  fault_handling:
    - "if battery_voltage < {nominal_voltage * 0.8}: set power_status = low_battery"
    - "if battery_voltage < {nominal_voltage * 0.7}: set power_status = critical"
    - "if current_draw > 80: trigger overcurrent protection"

composability:
  depends_on: []
  provides: [power_status, remaining_capacity]
  consumes: [voltage_sense, current_sense]
  timing:
    wcet: 1ms
    period: 1000ms
"""
