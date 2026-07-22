"""Mock LLM 客户端。

纯模板实现，不依赖任何外部服务，用于开发测试和演示模式。
所有方法直接返回预定义的模板响应。
"""

import asyncio
import re
from typing import Any, Optional

from skyforge_engine.utils.log_util import logger


class MockClient:
    """Mock LLM 客户端。

    提供与真实 LLM 客户端相同的接口，但返回预定义模板响应。
    """

    def __init__(self):
        self._available = True

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        logger.info(f"MockClient.chat: prompt={prompt[:50]}...")
        return self._generate_mock_response(prompt, system_prompt)

    async def chat_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
    ) -> str:
        logger.info(f"MockClient.chat_async: prompt={prompt[:50]}...")
        return self._generate_mock_response(prompt, system_prompt)

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        logger.info(f"MockClient.chat_stream: prompt={prompt[:50]}...")
        return self._generate_stream_response(prompt, system_prompt)

    def is_available(self, force_recheck: bool = False) -> bool:
        return self._available

    def get_available_models(self) -> list[str]:
        return ["mock-gpt-4", "mock-qwen3"]

    def _detect_task_type(self, prompt: str, system_prompt: str) -> str:
        text = (prompt + " " + system_prompt).lower()
        if any(keyword in text for keyword in ["需求", "解析", "parse", "requirement"]):
            return "requirement_parse"
        if any(keyword in text for keyword in ["契约", "contract", "yaml"]):
            return "contract_generation"
        if any(keyword in text for keyword in ["代码", "code", "generate"]):
            return "code_generation"
        if any(keyword in text for keyword in ["修复", "repair", "fix"]):
            return "code_repair"
        if any(keyword in text for keyword in ["架构", "architecture"]):
            return "architecture_design"
        return "generic"

    def _generate_mock_response(self, prompt: str, system_prompt: str) -> str:
        task_type = self._detect_task_type(prompt, system_prompt)

        if task_type == "requirement_parse":
            return self._gen_requirement_response(prompt)
        elif task_type == "contract_generation":
            return self._gen_contract_response(prompt)
        elif task_type == "code_generation":
            return self._gen_code_response(prompt)
        elif task_type == "code_repair":
            return self._gen_repair_response(prompt)
        elif task_type == "architecture_design":
            return self._gen_architecture_response(prompt)
        else:
            return self._gen_generic_response(prompt)

    def _gen_requirement_response(self, prompt: str) -> str:
        import json
        req_id_match = re.search(r"REQ-(\d+)", prompt)
        req_id = f"REQ-{int(req_id_match.group(1)):03d}" if req_id_match else "REQ-001"

        if any(k in prompt for k in ["滤波", "filter", "low-pass"]):
            return json.dumps({
                "req_id": req_id,
                "type": "filter",
                "module_name": "lowpass_filter_10hz",
                "safety_level": "DAL-B",
                "params": {"cutoff_hz": 10.0, "sample_rate_hz": 100.0},
                "constraints": ["WCET <= 1ms"],
            }, ensure_ascii=False)
        elif any(k in prompt for k in ["控制", "pid", "control"]):
            return json.dumps({
                "req_id": req_id,
                "type": "control",
                "module_name": "pid_controller",
                "safety_level": "DAL-B",
                "params": {"kp": 1.0, "ki": 0.1, "kd": 0.01},
                "constraints": ["WCET <= 2ms"],
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "req_id": req_id,
                "type": "generic",
                "module_name": "generic_module",
                "safety_level": "DAL-C",
                "params": {},
                "constraints": [],
            }, ensure_ascii=False)

    def _gen_contract_response(self, prompt: str) -> str:
        import json
        try:
            data = json.loads(prompt) if prompt.startswith("{") else {}
        except json.JSONDecodeError:
            data = {}
        module_name = data.get("module_name", "generic_component")

        return f"""component: {module_name}
version: 1.0.0
safety_level: DAL-C
traceability: [REQ-001]
interface:
  inputs:
    - name: raw_input
      type: double
      range: [0.0, 20000.0]
  outputs:
    - name: filtered_output
      type: double
      range: [0.0, 20000.0]
contracts:
  preconditions:
    - "raw_input is a valid double value (not NaN or Inf)"
  postconditions:
    - "filtered_output >= 0.0"
    - "filtered_output <= raw_input_max"
  invariants:
    - "s_prev maintains filter state between calls"
  fault_handling:
    - "if raw_input is NaN or Inf: set filtered_output = 0.0"
    - "if raw_input < 0: clamp filtered_output to 0.0"
"""

    def _gen_code_response(self, prompt: str) -> str:
        import json
        try:
            data = json.loads(prompt) if prompt.startswith("{") else {}
        except json.JSONDecodeError:
            data = {}
        module_name = data.get("module_name", "module")

        # V0.5.1: MISRA-C:2012 合规代码 — 消除 12.1/15.5/8.9 违规
        return f"""/*
 * [REQ-001] {module_name} 模块
 * DO-178C DAL-C 目标代码（自动生成）
 * 编码标准: MISRA-C:2012
 */
#include <stdint.h>
#include <stddef.h>

/* [REQ-001] [MISRA-Rule-8.9] 模块静态状态 */
static double s_prev = 0.0;
static int s_fault = 0;

/*
 * [REQ-001] [MISRA-Rule-8.7]
 * 初始化函数：重置模块状态
 */
void {module_name}_init(void)
{{
    s_prev = 0.0;
    s_fault = 0;
}}

/*
 * [REQ-001] [MISRA-Rule-8.13]
 * 一阶低通滤波: output = alpha * input + (1-alpha) * prev
 *
 * @param raw_input 原始输入值 (double)
 * @return 滤波后输出值 (double)
 */
double {module_name}_apply(double raw_input)
{{
    const double alpha = 0.1;
    double output = 0.0;

    /* MISRA Rule 12.1: 括号明确运算符优先级 */
    if ((raw_input < 0.0) || (raw_input > 20000.0))
    {{
        s_fault = 1;
        output = 0.0;
    }}
    else
    {{
        output = (alpha * raw_input) + ((1.0 - alpha) * s_prev);
        s_prev = output;
    }}

    /* MISRA Rule 15.5: 单一 return 语句 */
    return output;
}}
"""

    def _gen_repair_response(self, prompt: str) -> str:
        import json
        # 尝试从 prompt 中提取原始代码和违规信息
        try:
            data = json.loads(prompt) if prompt.startswith("{") else {}
        except json.JSONDecodeError:
            data = {}
        module_name = data.get("module_name", "module")

        return json.dumps({
            "code": f"""/*
 * [REQ-001] 修复后的 {module_name} 模块
 * DO-178C DAL-C 目标代码（修复版本）
 * 编码标准: MISRA-C:2012
 */
#include <stdint.h>
#include <stddef.h>

/* [REQ-001] [MISRA-Rule-8.9] 静态状态变量 */
static double s_prev = 0.0;

void {module_name}_init(void)
{{
    s_prev = 0.0;
}}

double {module_name}_apply(double raw_input)
{{
    const double alpha = 0.1;
    double output;

    output = (alpha * raw_input) + ((1.0 - alpha) * s_prev);
    s_prev = output;

    return output;
}}
""",
            "actions": [
                {"rule_id": "MISRA-C:2012-Rule-21.3", "line": 0,
                 "description": "移除动态内存分配，使用静态变量"},
                {"rule_id": "MISRA-C:2012-Rule-8.9", "line": 0,
                 "description": "显式初始化静态变量"},
                {"rule_id": "MISRA-C:2012-Rule-10.1", "line": 0,
                 "description": "消除隐式类型转换，显式使用括号分组"}
            ]
        }, ensure_ascii=False)

    def _gen_architecture_response(self, prompt: str) -> str:
        import json
        return json.dumps({
            "modules": [
                {
                    "name": "sensor_module",
                    "description": "传感器数据采集模块",
                    "inputs": [{"name": "raw_input", "type": "double"}],
                    "outputs": [{"name": "filtered_output", "type": "double"}],
                    "data_structures": [],
                    "dependencies": []
                }
            ],
            "global_data": [],
            "state_machine": {},
            "interface_spec": {
                "api_version": "1.0",
                "input_interface": {"function": "module_init", "params": ["void"], "returns": "void"},
                "output_interface": {"function": "module_process", "params": [{"name": "raw_input", "type": "double"}], "returns": "double"},
                "memory_model": "static"
            },
            "architecture_diagram": ""
        }, ensure_ascii=False)

    def _gen_generic_response(self, prompt: str) -> str:
        return "这是 Mock 模式下的通用响应。在真实 LLM 模式下，此处将返回模型生成的内容。"

    def _generate_stream_response(self, prompt: str, system_prompt: str) -> Any:
        content = self._generate_mock_response(prompt, system_prompt)
        chunks = [content[i:i+50] for i in range(0, len(content), 50)]

        async def stream():
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.05)

        return stream()
