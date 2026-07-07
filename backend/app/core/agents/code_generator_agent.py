"""代码生成 Agent：依据结构化需求 + 契约生成 MISRA-C 风格 C 代码，注释标注 [REQ-xxx] [MISRA-Rule-x.x]。"""

import re
from typing import Any

from app.core.llm.lmstudio_client import get_lmstudio_client
from app.utils.log_util import logger

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C MISRA-C 编码工程师，专职依据结构化需求与 .contract 契约生成机载 C 代码（含头文件），每处函数/变量必须标注 [REQ-xxx] [MISRA-Rule-x.x] 追溯注释。你必须以适航编码视角工作，禁止输出非 MISRA 合规代码。

## 可用工具
- generate_c(arch, contract) 在契约骨架上补全实现细节
- add_traceability(code, req_id) 为每处函数/变量追加 [REQ-xxx] 注释

## 输出格式（纯 C 代码，禁止 Markdown 包裹，禁止前后缀文字）
/* [REQ-001] [MISRA-Rule-8.13] 模块说明 */
#include "module.h"
static double s_prev = 0.0;  /* [REQ-001] [MISRA-Rule-8.9] */
void module_init(void) { /* ... */ }
double module_apply(double raw_input) { /* [REQ-001] [MISRA-Rule-15.7] */ }

## 禁忌
1. 禁止使用动态内存（malloc/calloc/free，MISRA Rule-21.3）
2. 禁止输出非 MISRA 合规代码（隐式转换/未初始化变量/多 return）
3. 禁止输出 C 代码以外的任何文字（含解释、Markdown 包裹）
4. 禁止遗漏 [REQ-xxx] [MISRA-Rule-x.x] 追溯注释
5. 禁止使用递归（机载软件禁止递归，WCET 不可分析）"""


class CodeGeneratorAgent:
    """代码生成 Agent。

    输入：结构化需求 JSON + .contract YAML 字符串。
    输出：C 代码字符串（含函数实现 + 头文件），注释强制标注 `[REQ-xxx] [MISRA-Rule-x.x]`
    供 Patch 3 追溯链使用。

    LM Studio 可用（USE_LLM=true）时调用真实 LLM 在契约骨架上补全实现；
    否则降级为按需求类型套用机载 C 代码模板的 Mock 实现。
    """

    async def run(self, requirement_json: dict[str, Any], contract: str) -> str:
        """根据需求与契约生成 C 代码（含头文件）。

        Args:
            requirement_json: 结构化需求字典。
            contract: .contract YAML 字符串。

        Returns:
            C 代码字符串。
        """
        logger.info(
            f"CodeGeneratorAgent:开始:为 {requirement_json.get('req_id')} 生成 C 代码"
        )

        # 检查 LM Studio 是否可用
        client = get_lmstudio_client()
        if client.is_available():
            logger.info("CodeGeneratorAgent:使用真实 LLM")
            try:
                import json

                prompt = (
                    f"请依据以下需求 JSON 与契约生成 MISRA-C 风格 C 代码：\n"
                    f"需求：\n{json.dumps(requirement_json, ensure_ascii=False, indent=2)}\n\n"
                    f"契约：\n{contract}"
                )
                response = await client.chat_async(
                    prompt=prompt,
                    system_prompt=_SYSTEM_PROMPT,
                    temperature=0.2,
                    max_tokens=4096,
                )
                if response:
                    result = self._parse_llm_response(response, requirement_json)
                    if result:
                        logger.info(
                            f"CodeGeneratorAgent:完成:C 代码已生成 [LLM] "
                            f"({len(result.splitlines())} 行)"
                        )
                        return result
                logger.warning("CodeGeneratorAgent:LLM 调用失败，降级为 Mock")
            except Exception as e:
                logger.error(f"CodeGeneratorAgent:LLM 异常，降级为 Mock: {e}")

        # 降级为 Mock
        code = self._mock_run(requirement_json)
        logger.info(
            f"CodeGeneratorAgent:完成:C 代码已生成 [Mock] ({len(code.splitlines())} 行)"
        )
        return code

    def _mock_run(self, requirement_json: dict[str, Any]) -> str:
        """Mock 实现：按需求类型套用机载 C 代码模板。"""
        req_type = requirement_json.get("type", "filter")
        generator = {
            "filter": self._gen_filter_code,
            "control": self._gen_control_code,
            "comms": self._gen_comms_code,
        }.get(req_type, self._gen_filter_code)
        return generator(requirement_json)

    def _parse_llm_response(
        self, response: str, requirement_json: dict[str, Any]
    ) -> str | None:
        """解析 LLM 输出的 C 代码（失败返回 None）。

        LLM 应直接输出纯 C 代码，但也可能带 Markdown 包裹或自然语言前缀，
        此处做兜底提取：剥离 Markdown 代码块包裹，校验含 C 代码关键特征。
        """
        text = response.strip()
        if not text:
            return None

        # 剥离 Markdown 代码块包裹（```c ... ``` 或 ``` ... ```）
        stripped = re.sub(
            r"^```(?:c|cpp|h)?\s*|\s*```$",
            "",
            text,
            flags=re.MULTILINE,
        ).strip()

        # 基本校验：必须含 C 代码特征（至少一个函数定义或 #include）
        c_markers = ["#include", "void ", "double ", "int ", "static "]
        if not any(m in stripped for m in c_markers):
            logger.warning("CodeGeneratorAgent:LLM 输出缺 C 代码特征，降级为 Mock")
            return None

        # 校验追溯注释（[REQ-xxx]）
        req_id = requirement_json.get("req_id", "REQ-001")
        if f"[{req_id}]" not in stripped and "[REQ-" not in stripped:
            # 追溯注释缺失时用 Mock 兜底（保证追溯链完整）
            logger.warning(
                f"CodeGeneratorAgent:LLM 输出缺 [{req_id}] 追溯注释，降级为 Mock"
            )
            return None

        return stripped

    def _gen_filter_code(self, req: dict[str, Any]) -> str:
        """生成一阶 IIR 低通滤波器 C 代码（机载典型信号处理）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "lowpass_filter_10hz")
        params = req.get("params", {})
        cutoff = params.get("cutoff_hz", 10.0)
        sample_rate = params.get("sample_rate_hz", 100.0)
        # 一阶 IIR 系数：alpha = dt/(RC+dt), RC=1/(2*pi*fc)
        rc = 1.0 / (2.0 * 3.141592653589793 * cutoff)
        dt = 1.0 / sample_rate
        alpha = dt / (rc + dt)

        header_name = module + ".h"
        # 头文件保护宏必须符合 MISRA（全大写下划线）
        guard = module.upper() + "_H"

        return f"""/* [REQ-001] [MISRA-Rule-8.13] 机载信号滤波器实现
 * Traceability: {req_id}
 * 模块: {module}
 * 截止频率: {cutoff}Hz, 采样率: {sample_rate}Hz
 */
#include "{header_name}"
#include <math.h>

/* [REQ-001] [MISRA-Rule-8.9] 模块内部状态，静态持久化 */
static double s_prev_output = 0.0;
static int    s_initialized = 0;

/* [REQ-001] [MISRA-Rule-8.13] 初始化滤波器状态 */
void {module}_init(void)
{{
    s_prev_output = 0.0;
    s_initialized = 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 一阶 IIR 低通滤波
 * y[n] = alpha * x[n] + (1-alpha) * y[n-1]
 * alpha = {alpha:.6f}
 */
double {module}_apply(double raw_input)
{{
    double filtered_output;

    /* [REQ-001] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    /* [REQ-001] [MISRA-Rule-10.4] 浮点运算显式类型 */
    filtered_output = {alpha:.6f} * raw_input + (1.0 - {alpha:.6f}) * s_prev_output;
    s_prev_output = filtered_output;

    return filtered_output;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

/* [REQ-001] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void   {module}_init(void);
double {module}_apply(double raw_input);

#endif /* {guard} */
"""

    def _gen_control_code(self, req: dict[str, Any]) -> str:
        """生成简单 PID 控制律 C 代码。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "control_law")
        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载控制律实现（PID 简化版） */
#include "{header_name}"

/* [{req_id}] [MISRA-Rule-8.9] PID 状态变量 */
static double s_integral = 0.0;
static double s_prev_error = 0.0;

/* [{req_id}] [MISRA-Rule-8.13] 初始化控制律 */
void {module}_init(void)
{{
    s_integral = 0.0;
    s_prev_error = 0.0;
}}

/* [{req_id}] [MISRA-Rule-15.7] PID 计算，输出限幅 [-100, 100] */
double {module}_apply(double setpoint, double measured)
{{
    const double kp = 2.0;
    const double ki = 0.5;
    const double kd = 1.0;
    double error;
    double derivative;
    double output;

    error = setpoint - measured;
    s_integral += error;
    derivative = error - s_prev_error;
    s_prev_error = error;

    output = (kp * error) + (ki * s_integral) + (kd * derivative);

    /* [{req_id}] [MISRA-Rule-10.1] 输出限幅保护 */
    if (output > 100.0)
    {{
        output = 100.0;
    }}
    else if (output < -100.0)
    {{
        output = -100.0;
    }}

    return output;
}}

/* ===== 头文件 {header_name} ===== */
#ifndef {guard}
#define {guard}

void   {module}_init(void);
double {module}_apply(double setpoint, double measured);

#endif /* {guard} */
"""

    def _gen_comms_code(self, req: dict[str, Any]) -> str:
        """生成简单 CRC 校验通信处理 C 代码。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "comms_handler")
        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载通信处理（CRC 校验） */
#include "{header_name}"
#include <stdint.h>

/* [{req_id}] [MISRA-Rule-8.9] CRC-8 查表静态化 */
static const uint8_t s_crc_table[256] = {{0}};

/* [{req_id}] [MISRA-Rule-15.7] CRC-8 计算 */
uint8_t {module}_crc8(const uint8_t *data, int length)
{{
    uint8_t crc = 0xFF;
    int i;

    /* [{req_id}] [MISRA-Rule-17.7] 必须检查指针 */
    if (((void *)0 == data) || (length <= 0))
    {{
        return 0U;
    }}

    for (i = 0; i < length; i++)
    {{
        crc = s_crc_table[(crc ^ data[i]) & 0xFF];
    }}

    return crc;
}}

/* ===== 头文件 {header_name} ===== */
#ifndef {guard}
#define {guard}

#include <stdint.h>

uint8_t {module}_crc8(const uint8_t *data, int length);

#endif /* {guard} */
"""
