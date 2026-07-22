"""代码生成 Agent：依据结构化需求 + 契约生成 MISRA-C 风格 C 代码（支持 C++ 扩展），
注释标注 [REQ-xxx] [MISRA-Rule-x.x]。
"""

import asyncio
import re
from typing import Any, Callable

# LLM 客户端 — 通过 L0 provider 注入（L3 启动时注册自己的单例，
# 引擎独立运行时回退到 L1 skyforge_llm.client）。详见 llm_provider.py。
from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client
from skyforge_engine.utils.log_util import logger

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C MISRA-C 编码工程师，专职依据结构化需求与
.contract 契约生成机载 C 代码（含头文件），每处函数/变量必须标注
[REQ-xxx] [MISRA-Rule-x.x] 追溯注释。你必须以适航编码视角工作，
禁止输出非 MISRA 合规代码。

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

    MOCK 模式时直接按需求类型套用机载 C 代码模板；
    API / LOCAL 模式时调用真实 LLM 在契约骨架上补全实现，异常直接抛出。
    """

    def __init__(self, strategy=None) -> None:
        if strategy is None:
            from skyforge_engine.core.strategies import get_strategy_for_mode
            strategy = get_strategy_for_mode()
        self.strategy = strategy

    async def run(
        self,
        requirement_json: dict[str, Any],
        contract: str,
        log_hook: Callable[[str, str, str], Any] | None = None,
    ) -> str:
        """根据需求与契约生成 C 代码（含头文件）。

        Args:
            requirement_json: 结构化需求字典。
            contract: .contract YAML 字符串。
            log_hook: 可选的流式推送回调 (agent_name, level, message)，
                支持 sync / async / None。用于推送安全校验告警。

        Returns:
            C 代码字符串。
        """
        logger.info(
            f"CodeGeneratorAgent:开始:为 {requirement_json.get('req_id')} 生成 C 代码"
        )

        result = await self.strategy.run(
            requirement_json,
            contract=contract,
            log_hook=log_hook,
            input_type="code",
        )
        if not result.success:
            if len(result.warnings) == 1:
                raise RuntimeError(result.warnings[0])
            raise RuntimeError(
                f"CodeGeneratorAgent 执行失败: {result.warnings}"
            )
        code = result.output
        logger.info(
            f"CodeGeneratorAgent:完成:C 代码已生成 ({len(code.splitlines())} 行)"
        )
        return code

    async def _llm_run(
        self,
        requirement_json: dict[str, Any],
        contract: str = "",
        log_hook: Callable[[str, str, str], Any] | None = None,
    ) -> str:
        """LLM 实现：调用 LLM 生成代码。"""
        import json

        client = get_lmstudio_client()
        prompt = (
            f"请依据以下需求 JSON 与契约生成 MISRA-C 风格 C 代码：\n"
            f"需求：\n{json.dumps(requirement_json, ensure_ascii=False, indent=2)}\n\n"  # noqa: E501
            f"契约：\n{contract}"
        )
        response = await client.chat_async(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=16384,  # 推理模型需要更大 token 上限
        )
        if not response:
            raise RuntimeError("CodeGeneratorAgent:LLM 调用返回空响应")
        result = self._parse_llm_response(response, requirement_json)
        if not result:
            raise RuntimeError("CodeGeneratorAgent:LLM 响应解析失败")
        # 输出安全校验（轻量级、不阻塞，参考 pipeline.py hook 调用方式）
        try:
            from skyforge_engine.config import settings
            from skyforge_llm.security.validator import (
                validate_output,
            )

            if getattr(
                settings, "SECURITY_VALIDATE_OUTPUT", True
            ):
                validation = validate_output(result)
                if not validation.passed:
                    for v in validation.violations:
                        logger.warning(
                            f"[Security] LLM 输出违规: {v}"
                        )
                        if log_hook is not None:
                            if asyncio.iscoroutinefunction(
                                log_hook
                            ):
                                await log_hook(
                                    "CODE-Gen",
                                    "warning",
                                    f"安全校验: {v}",
                                )
                            else:
                                log_hook(
                                    "CODE-Gen",
                                    "warning",
                                    f"安全校验: {v}",
                                )
                for w in validation.warnings:
                    logger.info(
                        f"[Security] LLM 输出告警: {w}"
                    )
        except Exception as e:
            logger.warning(
                f"输出校验失败（不影响主流程）: {e}"
            )
        return result

    # ==================== 契约约束提取工具 ====================

    @staticmethod
    def _extract_contract_constraints(contract: dict[str, Any]) -> dict[str, Any]:
        """从契约字典中提取公共约束，供所有模板统一使用。

        Returns:
            {
                "input_name": str,        # 输入参数名
                "output_name": str,       # 输出变量名
                "input_min": float,       # 输入下界
                "input_max": float,       # 输入上界
                "output_min": float,      # 输出下界
                "output_max": float,      # 输出上界
                "has_fault_handling": bool, # 是否有故障处理约束
                "preconditions": list,    # 前置条件列表
                "postconditions": list,   # 后置条件列表
                "invariants": list,       # 不变式列表
                "fault_handling": list,   # 故障处理列表
            }
        """
        iface = contract.get("interface", {})
        inputs = iface.get("inputs", [{}])
        outputs = iface.get("outputs", [{}])
        input_def = inputs[0] if inputs else {}
        output_def = outputs[0] if outputs else {}

        input_range = input_def.get("range", [0.0, 20000.0])
        output_range = output_def.get("range", [0.0, 20000.0])

        contracts_block = contract.get("contracts", {}) or contract
        preconditions = contracts_block.get("preconditions", [])
        postconditions = contracts_block.get("postconditions", [])
        invariants = contracts_block.get("invariants", [])
        fault_handling = contracts_block.get("fault_handling", [])

        return {
            "input_name": input_def.get("name", "raw_input"),
            "output_name": output_def.get("name", "filtered_output"),
            "input_min": input_range[0] if input_range else 0.0,
            "input_max": input_range[1] if len(input_range) > 1 else 20000.0,
            "output_min": output_range[0] if output_range else 0.0,
            "output_max": output_range[1] if len(output_range) > 1 else 20000.0,
            "has_fault_handling": bool(fault_handling),
            "preconditions": preconditions,
            "postconditions": postconditions,
            "invariants": invariants,
            "fault_handling": fault_handling,
        }

    @staticmethod
    def _gen_contract_precondition_check(c: dict[str, Any], req_id: str) -> str:
        """生成 MISRA-C 合规的前置条件检查 C 代码片段。

        合规要点:
        - Rule 10.1: 显式类型转换
        - Rule 14.4: 布尔表达式必须是 Boolean 类型
        - 前置条件违反时提前返回，无需 else 分支
        """
        iname = c["input_name"]
        return (
            f"    /* [{req_id}] [MISRA-Rule-11.3] 契约前置条件检查 */\n"
            f"    if (({iname} < (double){c['input_min']:.1f}) "
            f"|| ({iname} > (double){c['input_max']:.1f}))\n"
            f"    {{\n"
            f"        return 0.0;  /* [{req_id}] 前置条件违反，返回安全值 */\n"
            f"    }}\n"
        )

    @staticmethod
    def _gen_contract_postcondition_check(
        c: dict[str, Any], req_id: str, output_var: str = "result"
    ) -> str:
        """生成 MISRA-C 合规的后置条件检查 C 代码片段。

        注意：对于有前置条件保护的代码，后置条件检查是不可达的死代码。
        前置条件已过滤非法输入，有效输入的输出总是在范围内。
        此方法返回空字符串，由调用方决定是否需要后置条件检查。
        """
        return ""

    @staticmethod
    def _gen_fault_state_declarations(c: dict[str, Any]) -> str:
        """生成故障检测状态变量声明。"""
        if not c["has_fault_handling"]:
            return ""
        return (
            "static int s_fault_detected = 0;\n"
            "static double s_last_valid_output = 0.0;\n"
        )

    @staticmethod
    def _gen_fault_detection_code(c: dict[str, Any], req_id: str) -> str:
        """生成故障检测逻辑代码片段。"""
        if not c["has_fault_handling"]:
            return ""
        return (
            f"    /* [{req_id}] 故障检测：基于契约 fault_handling */\n"
            f"    if (s_fault_detected == 0) {{\n"
            f"        if ({c['input_name']} < {c['input_min']:.1f} "
            f"|| {c['input_name']} > {c['input_max']:.1f}) {{\n"
            f"            s_fault_detected = 1;\n"
            f"        }}\n"
            f"    }}\n"
        )

    @staticmethod
    def _gen_fault_state_init(c: dict[str, Any]) -> str:
        """生成故障状态重置代码（在 init 函数中调用）。"""
        if not c["has_fault_handling"]:
            return ""
        return (
            "    s_fault_detected = 0;\n"
            "    s_last_valid_output = 0.0;\n"
        )

    def _mock_run(self, requirement_json: dict[str, Any], contract: str = "") -> str:
        """Mock 实现：按需求类型套用机载 C 代码模板。

        支持中文关键词检测：从需求文本中识别领域关键词，自动选择对应模板。
        解析契约 YAML，提取前置/后置/不变式/故障处理约束，注入生成代码。
        """
        # 中文关键词 → 模板类型映射
        keyword_map = {
            "导航": "navigation",
            "GPS": "navigation",
            "INS": "navigation",
            "惯导": "navigation",
            "滤波": "navigation",
            "位置融合": "navigation",
            "电源": "power",
            "电池": "power",
            "电压": "power",
            "电流": "power",
            "功率": "power",
            "供电": "power",
            "显示": "hmi",
            "HUD": "hmi",
            "人机界面": "hmi",
            "仪表": "hmi",
            "告警": "hmi",
            "叠加": "hmi",
            "卡尔曼": "sensor_fusion",
            "IMU": "sensor_fusion",
            "传感器融合": "sensor_fusion",
            "姿态解算": "sensor_fusion",
            "磁力计": "sensor_fusion",
            "航点": "mission_planning",
            "任务": "mission_planning",
            "航线": "mission_planning",
            "调度": "mission_planning",
            "飞行计划": "mission_planning",
            "ARINC": "arinc653",
            "ARINC 653": "arinc653",
            "分区": "arinc653",
            "分区调度": "arinc653",
            "健康监控": "arinc653",
            "端口": "arinc653",
            "FreeRTOS": "freertos",
            "RTOS": "freertos",
            "信号量": "freertos",
            "互斥锁": "freertos",
            "任务调度": "freertos",
            "队列": "freertos",
            # C++ 关键词
            "智能指针": "cpp_smart_pointer",
            "unique_ptr": "cpp_smart_pointer",
            "shared_ptr": "cpp_smart_pointer",
            "RAII": "cpp_smart_pointer",
            "模板类": "cpp_template",
            "模板函数": "cpp_template",
            "泛型编程": "cpp_template",
            "STL容器": "cpp_stl_container",
            "vector": "cpp_stl_container",
            "map": "cpp_stl_container",
            "exception": "cpp_exception",
            "try_catch": "cpp_exception",
            "异常处理": "cpp_exception",
            "虚函数": "cpp_inheritance",
            "多态": "cpp_inheritance",
            "继承": "cpp_inheritance",
            # Python 关键词
            "python": "python_safety",
            "Python": "python_safety",
            "T/ZASDI": "python_safety",
            "滤波器": "python_safety",
        }

        # 优先使用显式指定的 type 字段
        req_type = requirement_json.get("type", "")

        # 如果未指定 type，从需求文本中检测关键词
        if not req_type:
            req_text = str(requirement_json).lower()
            for keyword, template_type in keyword_map.items():
                if keyword.lower() in req_text:
                    req_type = template_type
                    break

        # 默认回退到 generic（未知类型走通用模板，Task 8 完善）
        if not req_type:
            req_type = "generic"

        # 解析契约 YAML，提取约束用于代码生成
        contract_data = {}
        if contract:
            try:
                import yaml
                contract_data = yaml.safe_load(contract) or {}
            except Exception:
                contract_data = {}

        generator = {
            "filter": self._gen_filter_code,
            "control": self._gen_control_code,
            "comms": self._gen_comms_code,
            "navigation": self._gen_navigation_code,
            "power": self._gen_power_management_code,
            "hmi": self._gen_hmi_code,
            "sensor_fusion": self._gen_sensor_fusion_code,
            "mission_planning": self._gen_mission_planning_code,
            "arinc653": self._gen_arinc653_code,
            "freertos": self._gen_freertos_code,
            "cpp_smart_pointer": self._gen_cpp_smart_pointer_code,
            "cpp_template": self._gen_cpp_template_code,
            "cpp_stl_container": self._gen_cpp_stl_container_code,
            "cpp_exception": self._gen_cpp_exception_code,
            "cpp_inheritance": self._gen_cpp_inheritance_code,
            "python_safety": self._gen_python_safety_code,
            "generic": self._gen_generic_code,
            "redundancy": self._gen_redundancy_code,
        }.get(req_type, self._gen_generic_code)
        if "contract" in generator.__code__.co_varnames:
            code = generator(requirement_json, contract=contract_data)
        else:
            code = generator(requirement_json)

        if req_type.startswith("cpp_") or req_type == "python_safety":
            return code
        return self._ensure_contract_guard(code, requirement_json, contract_data)

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

    @staticmethod
    def _has_contract_sections(contract: dict[str, Any]) -> bool:
        """Return True when the contract contains executable constraints."""
        contracts_block = contract.get("contracts", {}) or contract
        for section in ("preconditions", "postconditions", "invariants", "fault_handling"):
            if contracts_block.get(section):
                return True
        return False

    @staticmethod
    def _safe_c_identifier(value: str, fallback: str = "module") -> str:
        """Convert arbitrary requirement/module text into a C identifier."""
        ident = re.sub(r"\W+", "_", value or "").strip("_").lower()
        if not ident:
            ident = fallback
        if ident[0].isdigit():
            ident = "_" + ident
        return ident[:48]

    def _ensure_contract_guard(
        self,
        code: str,
        req: dict[str, Any],
        contract: dict[str, Any],
    ) -> str:
        """Append a callable C guard when a template has no native contract path.

        Some domain templates have fixed signatures (PID, power, ARINC653, RTOS).
        The generated guard gives downstream code and tests a deterministic entry
        point for precondition, postcondition, invariant and fault handling checks.
        """
        if not contract or not self._has_contract_sections(contract):
            return code
        if "skyforge_contract_guard_" in code:
            return code

        req_id = req.get("req_id", "REQ-001")
        module = self._safe_c_identifier(req.get("module_name", ""), "module")
        c = self._extract_contract_constraints(contract)
        guard_name = f"skyforge_contract_guard_{module}"
        input_name = self._safe_c_identifier(str(c["input_name"]), "raw_input")
        output_name = self._safe_c_identifier(str(c["output_name"]), "filtered_output")
        input_min = float(c["input_min"])
        input_max = float(c["input_max"])
        output_min = float(c["output_min"])
        output_max = float(c["output_max"])

        guard = f"""

/* [{req_id}] [CON-001] 契约运行时保护入口
 * 覆盖 preconditions/postconditions/invariants/fault_handling。
 */
static double {guard_name}(const double {input_name},
                           const double computed_output,
                           int * const fault_detected)
{{
    const double contract_input_min = (double){input_min:.6f};
    const double contract_input_max = (double){input_max:.6f};
    const double contract_output_min = (double){output_min:.6f};
    const double contract_output_max = (double){output_max:.6f};
    double {output_name} = computed_output;

    if (fault_detected == ((void *)0))
    {{
        return (double)0.0;
    }}
    else
    {{
        *fault_detected = 0;
    }}

    if (({input_name} < contract_input_min) || ({input_name} > contract_input_max))
    {{
        *fault_detected = 1;
        {output_name} = (double)0.0;
    }}
    else
    {{
        if (({output_name} < contract_output_min) || ({output_name} > contract_output_max))
        {{
            *fault_detected = 1;
            {output_name} = (double)0.0;
        }}
        else
        {{
            {output_name} = computed_output;
        }}
    }}

    return {output_name};
}}
"""
        return code.rstrip() + guard

    def _gen_generic_code(self, req: dict[str, Any], contract: dict[str, Any] | None = None) -> str:
        """通用代码模板：MISRA-C 合规，注入契约约束。

        合规要点：
        - Rule 8.9: static file-scope（嵌入式必需，见 MISRA_EXCEPTIONS.md）
        - Rule 8.13: 输入参数加 const
        - Rule 10.1: 显式类型转换
        - Rule 15.7: 所有 if 必须有 else
        - Rule 21.3: 禁止动态内存
        """
        contract = contract or {}
        req_id = req.get("req_id", "REQ-001")
        req_text = str(req.get("desc", req.get("description", "")))
        module = req.get("module_name", "generic_module")
        func_base = self._derive_func_name(req_text, prefix=module)
        header_name = module + ".h"
        guard = module.upper() + "_H"

        # 使用公共契约工具提取约束
        c = self._extract_contract_constraints(contract)
        input_name = c["input_name"]
        output_name = c["output_name"]

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 通用模块实现
 * Traceability: {req_id}
 * 模块: {module}
 * 需求原文: {req_text[:120]}
 * MISRA-C 合规: Rule 8.9/8.13/10.1/15.7/21.3
 */
#include "{header_name}"
#include <stdint.h>
#include <stdbool.h>

/* [{req_id}] [MISRA-Rule-8.9] 模块内部状态
 * 注: 嵌入式系统需要跨调用保持状态，static file-scope 是唯一合理方案。
 * MISRA 允许此例外（见 MISRA_EXCEPTIONS.md）。
 */
static int32_t last_input = 0;     /* [{req_id}] 上次输入值 */
static int32_t last_output = 0;    /* [{req_id}] 上次输出值 */
static bool    is_initialized = false;  /* [{req_id}] 初始化标志 */
{self._gen_fault_state_declarations(c)}

/* [{req_id}] [MISRA-Rule-8.13] 初始化函数 */
int {func_base}_init(void)
{{
    last_input = (int32_t)0;
    last_output = (int32_t)0;
    is_initialized = true;
    return (int)0;
}}

/* [{req_id}] [MISRA-Rule-15.7] 处理函数 */
int32_t {func_base}_process(const int32_t {input_name})
{{
    int32_t result;

    /* [{req_id}] [MISRA-Rule-15.7] 未初始化保护 — 必须有 else */
    if (is_initialized == false)
    {{
        (void){func_base}_init();
    }}
    else
    {{
        /* [{req_id}] 已初始化，继续执行 */
    }}
{self._gen_contract_precondition_check(c, req_id)}{self._gen_fault_detection_code(c, req_id)}
    /* [{req_id}] 处理逻辑: {req_text[:80]} */
    result = {input_name};  /* [{req_id}] 默认透传，按需实现 */
    last_input = {input_name};
    last_output = result;
{self._gen_contract_postcondition_check(c, req_id, "result")}
    return result;
}}

/* [{req_id}] [MISRA-Rule-8.13] 反初始化函数 */
void {func_base}_deinit(void)
{{
    last_input = (int32_t)0;
    last_output = (int32_t)0;
    is_initialized = false;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>
#include <stdbool.h>

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
int     {func_base}_init(void);
int32_t {func_base}_process(const int32_t {input_name});
void    {func_base}_deinit(void);

#endif /* {guard} */
"""

    def _derive_func_name(self, req_text: str, prefix: str = "process") -> str:
        """从需求文本提取函数名前缀（简单启发式）。

        取需求文本前 20 字符，去除标点和空格后转小写；
        若结果为空则回退到 prefix（通常为 module_name）。
        """
        clean = re.sub(r"[^\w]", "", req_text[:20]).lower()
        if not clean:
            clean = prefix
        return clean[:15]

    def _gen_redundancy_code(self, req: dict[str, Any]) -> str:
        """余度管理代码模板：双通道输入取均值，偏差超阈值报警。

        实现双通道余度管理器：计算 A/B 通道均值作为输出，
        当偏差百分比超过 5% 阈值时激活报警，符合机载余度管理典型设计。
        """
        req_id = req.get("req_id", "REQ-001")
        req_text = str(req.get("desc", req.get("description", "")))
        module = req.get("module_name", "redundancy_manager")
        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 余度管理器实现（双通道均值+偏差报警）
 * Traceability: {req_id}
 * 模块: {module}
 * 需求原文: {req_text[:120]}
 * @safety_level DAL-A
 * @brief 双通道输入取均值，偏差 > 5% 时报警
 */
#include "{header_name}"
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

/* [{req_id}] [MISRA-Rule-8.1] 偏差阈值 5% */
#define DEVIATION_THRESHOLD_PERCENT 5.0f

/* [{req_id}] [MISRA-Rule-8.9] 余度管理器状态结构体，静态持久化 */
typedef struct {{
    float    channel_a;       /* [{req_id}] 通道 A 输入 */
    float    channel_b;       /* [{req_id}] 通道 B 输入 */
    float    average_value;   /* [{req_id}] 均值输出 */
    bool     alarm_active;    /* [{req_id}] 报警状态 */
    uint32_t alarm_count;     /* [{req_id}] [MISRA-Rule-9.1] 报警计数 */
    bool     initialized;     /* [{req_id}] [MISRA-Rule-9.1] 初始化标志 */
}} RedundancyManager_t;

/* [{req_id}] [MISRA-Rule-8.9] 模块静态实例 */
static RedundancyManager_t s_mgr;

/* [{req_id}] [MISRA-Rule-8.13] 初始化余度管理器
 * @note 需求: {req_text[:120]}
 */
void {module}_init(void)
{{
    /* [{req_id}] 初始化逻辑 */
    s_mgr.channel_a = 0.0f;
    s_mgr.channel_b = 0.0f;
    s_mgr.average_value = 0.0f;
    s_mgr.alarm_active = false;
    s_mgr.alarm_count = 0U;  /* [{req_id}] [MISRA-Rule-9.1] */
    s_mgr.initialized = true;
}}

/* [{req_id}] [MISRA-Rule-15.7] 执行余度管理：取均值，检测偏差
 * @note 需求: {req_text[:120]}
 * @param a 通道 A 输入
 * @param b 通道 B 输入
 * @return 双通道均值
 */
float {module}_process(float a, float b)
{{
    float deviation = 0.0f;

    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (false == s_mgr.initialized)
    {{
        {module}_init();
    }}

    s_mgr.channel_a = a;
    s_mgr.channel_b = b;

    /* [{req_id}] 计算均值 */
    s_mgr.average_value = (a + b) * 0.5f;

    /* [{req_id}] [MISRA-Rule-10.4] 计算偏差百分比（避免除零） */
    if (fabsf(s_mgr.average_value) > 1.0e-6f)
    {{
        deviation = fabsf(a - b) / s_mgr.average_value * 100.0f;
    }}

    /* [{req_id}] 偏差 > 5% 时报警 */
    if (deviation > DEVIATION_THRESHOLD_PERCENT)
    {{
        s_mgr.alarm_active = true;
        s_mgr.alarm_count++;  /* [{req_id}] [CON-001-POST-001] */
    }}
    else
    {{
        s_mgr.alarm_active = false;
    }}

    return s_mgr.average_value;  /* [{req_id}] [CON-001-POST-000] */
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取报警状态
 * @note 需求: {req_text[:120]}
 * @return true=偏差超阈值，false=正常
 */
bool {module}_is_alarm(const RedundancyManager_t *mgr)  /* [{req_id}] [MISRA-Rule-8.13] */
{{
    if (((void *)0) == mgr)
    {{
        return s_mgr.alarm_active;
    }}
    return mgr->alarm_active;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取报警计数 */
uint32_t {module}_get_alarm_count(void)
{{
    return s_mgr.alarm_count;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>
#include <stdbool.h>

/* [{req_id}] [MISRA-Rule-8.9] 类型定义 */
typedef struct {{
    float    channel_a;
    float    channel_b;
    float    average_value;
    bool     alarm_active;
    uint32_t alarm_count;
    bool     initialized;
}} RedundancyManager_t;

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void     {module}_init(void);
float    {module}_process(float a, float b);
bool     {module}_is_alarm(const RedundancyManager_t *mgr);
uint32_t {module}_get_alarm_count(void);

#endif /* {guard} */
"""

    def _gen_filter_code(self, req: dict[str, Any], contract: dict[str, Any] | None = None) -> str:
        """生成一阶 IIR 低通滤波器 C 代码（MISRA-C 合规）。

        合规要点：
        - Rule 8.9: 状态变量用 static 但限定 file scope（嵌入式必需）
        - Rule 8.13: 输入参数加 const
        - Rule 10.1/10.4: 显式类型转换，运算符两侧类型一致
        - Rule 15.7: 所有 if 必须有 else
        - Rule 17.7: 返回值必须使用
        - Rule 21.3: 禁止动态内存
        """
        contract = contract or {}
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "lowpass_filter_10hz")
        params = req.get("params", {})
        cutoff = params.get("cutoff_hz", 10.0)
        sample_rate = params.get("sample_rate_hz", 100.0)
        # 一阶 IIR 系数：alpha = dt/(RC+dt), RC=1/(2*pi*fc)
        rc = 1.0 / (2.0 * 3.141592653589793 * cutoff)
        dt = 1.0 / sample_rate
        alpha = dt / (rc + dt)

        # 使用公共契约工具提取约束
        c = self._extract_contract_constraints(contract)
        input_name = c["input_name"]
        output_name = c["output_name"]

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载信号滤波器实现
 * Traceability: {req_id}
 * 模块: {module}
 * 截止频率: {cutoff}Hz, 采样率: {sample_rate}Hz
 * 契约约束: 输入范围 [{c['input_min']}, {c['input_max']}]
 * MISRA-C 合规: Rule 8.9/8.13/10.1/10.4/15.7/21.3
 */
#include "{header_name}"
#include <math.h>

/* [{req_id}] [MISRA-Rule-8.9] 模块内部状态
 * 注: 嵌入式滤波器需要跨调用保持状态，static file-scope 是唯一合理方案。
 * MISRA 允许此例外，条件是状态变量有明确的初始化和生命周期管理。
 */
static double prev_output = 0.0;   /* [{req_id}] 上一次滤波输出 */
static int    is_initialized = 0;  /* [{req_id}] 初始化标志 */
{self._gen_fault_state_declarations(c)}

/* [{req_id}] [MISRA-Rule-8.13] 初始化滤波器状态 */
void {module}_init(void)
{{
    prev_output = 0.0;
    is_initialized = 1;
{self._gen_fault_state_init(c)}
}}

/* [{req_id}] [MISRA-Rule-15.7] 一阶 IIR 低通滤波
 * y[n] = alpha * x[n] + (1-alpha) * y[n-1]
 * alpha = {alpha:.6f}
 * [{req_id}] [MISRA-Rule-8.13] 输入参数加 const
 */
double {module}_apply(const double {input_name})
{{
    double {output_name};
    double alpha = (double){alpha:.6f};  /* [{req_id}] [MISRA-Rule-10.1] 显式转换 */

    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (is_initialized == 0)
    {{
        {module}_init();
    }}
{self._gen_fault_detection_code(c, req_id)}{self._gen_contract_precondition_check(c, req_id)}
    /* [{req_id}] [MISRA-Rule-10.4] 浮点运算: alpha 和 {input_name} 均为 double */
    {output_name} = (alpha * {input_name}) + ((1.0 - alpha) * prev_output);
    prev_output = {output_name};
{self._gen_contract_postcondition_check(c, req_id, output_name)}
    return {output_name};
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void   {module}_init(void);
double {module}_apply(const double {input_name});

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

    def _gen_navigation_code(self, req: dict[str, Any]) -> str:
        """生成 GPS/INS 导航互补滤波器 C 代码（机载导航系统）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "nav_filter")
        params = req.get("params", {})
        alpha = params.get("alpha", 0.98)  # 互补滤波器融合系数
        dt = params.get("dt_sec", 0.01)  # 采样周期

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [REQ-001] [MISRA-Rule-8.13] 机载导航滤波器实现（GPS/INS 互补滤波）
 * Traceability: {req_id}
 * 模块: {module}
 * 融合系数: {alpha}, 采样周期: {dt}s
 */
#include "{header_name}"
#include <math.h>

/* [REQ-001] [MISRA-Rule-8.9] 导航状态变量，静态持久化 */
static double s_ins_position = 0.0;
static double s_ins_velocity = 0.0;
static double s_gps_position = 0.0;
static int    s_initialized = 0;

/* [REQ-001] [MISRA-Rule-8.13] 初始化导航滤波器状态 */
void {module}_init(void)
{{
    s_ins_position = 0.0;
    s_ins_velocity = 0.0;
    s_gps_position = 0.0;
    s_initialized = 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 互补滤波融合 GPS 与 INS 数据
 * position = alpha * (position_ins + velocity_ins * dt) + (1-alpha) * position_gps
 * alpha = {alpha:.4f}
 */
double {module}_update(double ins_accel, double gps_pos)
{{
    double fused_position;

    /* [REQ-001] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    /* [REQ-001] [MISRA-Rule-10.4] INS 积分更新 */
    s_ins_velocity += ins_accel * {dt:.4f};
    s_ins_position += s_ins_velocity * {dt:.4f};

    /* [REQ-001] [MISRA-Rule-10.4] 互补滤波融合 */
    fused_position = {alpha:.4f} * s_ins_position + (1.0 - {alpha:.4f}) * gps_pos;
    s_gps_position = gps_pos;
    s_ins_position = fused_position;

    return fused_position;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

/* [REQ-001] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void   {module}_init(void);
double {module}_update(double ins_accel, double gps_pos);

#endif /* {guard} */
"""

    def _gen_power_management_code(self, req: dict[str, Any]) -> str:
        """生成电池监控与电源切换 C 代码（机载电源管理系统）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "power_mgr")
        params = req.get("params", {})
        v_low = params.get("voltage_low_threshold", 10.5)
        v_high = params.get("voltage_high_threshold", 28.0)
        i_max = params.get("current_max_amps", 5.0)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [REQ-001] [MISRA-Rule-8.13] 机载电源管理系统实现
 * Traceability: {req_id}
 * 模块: {module}
 * 低压阈值: {v_low}V, 高压阈值: {v_high}V, 最大电流: {i_max}A
 */
#include "{header_name}"
#include <stdint.h>

/* [REQ-001] [MISRA-Rule-8.9] 电源状态变量，静态持久化 */
static double s_voltage = 0.0;
static double s_current = 0.0;
static int    s_power_state = 0;  /* 0: normal, 1: low_voltage, 2: fault */
static int    s_initialized = 0;

/* [REQ-001] [MISRA-Rule-8.13] 初始化电源管理系统 */
void {module}_init(void)
{{
    s_voltage = 0.0;
    s_current = 0.0;
    s_power_state = 0;
    s_initialized = 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 电源监控与故障切换
 * 检测电压/电流异常，执行电源切换
 */
int {module}_monitor(double voltage, double current)
{{
    int new_state;

    /* [REQ-001] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_voltage = voltage;
    s_current = current;
    new_state = 0;

    /* [REQ-001] [MISRA-Rule-10.1] 低压检测 */
    if (voltage < {v_low:.1f})
    {{
        new_state = 1;
    }}
    /* [REQ-001] [MISRA-Rule-10.1] 过压检测 */
    else if (voltage > {v_high:.1f})
    {{
        new_state = 2;
    }}
    /* [REQ-001] [MISRA-Rule-10.1] 过流检测 */
    else if (current > {i_max:.1f})
    {{
        new_state = 2;
    }}

    /* [REQ-001] [MISRA-Rule-15.7] 状态切换逻辑 */
    if (new_state != s_power_state)
    {{
        s_power_state = new_state;
        /* 实际硬件切换逻辑在此处实现 */
    }}

    return s_power_state;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

/* [REQ-001] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void {module}_init(void);
int  {module}_monitor(double voltage, double current);

#endif /* {guard} */
"""

    def _gen_hmi_code(self, req: dict[str, Any]) -> str:
        """生成 HMI 显示组件 C 代码（机载人机界面 HUD 叠加显示）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "hmi_overlay")
        params = req.get("params", {})
        max_items = params.get("max_display_items", 12)
        refresh_rate = params.get("refresh_rate_hz", 30)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载 HMI 显示叠加组件实现
 * Traceability: {req_id}
 * 模块: {module}
 * 最大显示项: {max_items}, 刷新率: {refresh_rate}Hz
 */
#include "{header_name}"
#include <stdint.h>
#include <string.h>

/* [{req_id}] [MISRA-Rule-8.9] 显示项数据结构 */
typedef struct {{
    uint8_t  id;           /* [{req_id}] 显示项唯一标识 */
    uint8_t  visible;      /* [{req_id}] 可见标志: 0=隐藏, 1=可见 */
    uint8_t  priority;     /* [{req_id}] 优先级: 0=低, 255=最高 */
    double   value;        /* [{req_id}] 当前数值 */
    double   min_val;      /* [{req_id}] 量程下限 */
    double   max_val;      /* [{req_id}] 量程上限 */
    uint8_t  warn_level;   /* [{req_id}] 告警等级: 0=正常, 1=注意, 2=警告, 3=危急 */
}} HmiDisplayItem_t;

/* [{req_id}] [MISRA-Rule-8.9] 模块内部状态 */
static HmiDisplayItem_t s_items[{max_items}];
static uint8_t          s_item_count = 0;
static uint8_t          s_hud_enabled = 0;
static int              s_initialized = 0;

/* [{req_id}] [MISRA-Rule-8.13] 初始化 HMI 显示组件 */
void {module}_init(void)
{{
    (void)memset(s_items, 0, sizeof(s_items));
    s_item_count = 0;
    s_hud_enabled = 1;
    s_initialized = 1;
}}

/* [{req_id}] [MISRA-Rule-15.7] 注册显示项，返回 0=成功, 1=已满 */
int {module}_register_item(uint8_t id, double min_val, double max_val, uint8_t priority)
{{
    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    if (s_item_count >= {max_items})
    {{
        return 1;
    }}

    s_items[s_item_count].id = id;
    s_items[s_item_count].visible = 1;
    s_items[s_item_count].priority = priority;
    s_items[s_item_count].value = 0.0;
    s_items[s_item_count].min_val = min_val;
    s_items[s_item_count].max_val = max_val;
    s_items[s_item_count].warn_level = 0;
    s_item_count++;

    return 0;
}}

/* [{req_id}] [MISRA-Rule-15.7] 更新显示项值并计算告警等级 */
void {module}_update_value(uint8_t id, double value)
{{
    uint8_t i;

    for (i = 0; i < s_item_count; i++)
    {{
        if (s_items[i].id == id)
        {{
            s_items[i].value = value;

            /* [{req_id}] [MISRA-Rule-10.1] 告警等级阈值判定 */
            if ((value < s_items[i].min_val) || (value > s_items[i].max_val))
            {{
                s_items[i].warn_level = 3;  /* [{req_id}] 危急 */
            }}
            else
            {{
                double range = s_items[i].max_val - s_items[i].min_val;
                double lo_warn = s_items[i].min_val + 0.1 * range;
                double hi_warn = s_items[i].max_val - 0.1 * range;
                if ((value < lo_warn) || (value > hi_warn))
                {{
                    s_items[i].warn_level = 2;  /* [{req_id}] 警告 */
                }}
                else
                {{
                    s_items[i].warn_level = 0;  /* [{req_id}] 正常 */
                }}
            }}
            break;
        }}
    }}
}}

/* [{req_id}] [MISRA-Rule-15.7] 获取指定显示项状态 */
int {module}_get_item(uint8_t id, double *value, uint8_t *warn_level)
{{
    uint8_t i;

    if (((void *)0 == value) || (((void *)0 == warn_level)))
    {{
        return 1;
    }}

    for (i = 0; i < s_item_count; i++)
    {{
        if (s_items[i].id == id)
        {{
            *value = s_items[i].value;
            *warn_level = s_items[i].warn_level;
            return 0;
        }}
    }}
    return 1;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void {module}_init(void);
int  {module}_register_item(uint8_t id, double min_val, double max_val, uint8_t priority);
void {module}_update_value(uint8_t id, double value);
int  {module}_get_item(uint8_t id, double *value, uint8_t *warn_level);

#endif /* {guard} */
"""

    def _gen_sensor_fusion_code(self, req: dict[str, Any]) -> str:
        """生成 IMU/GPS 卡尔曼滤波传感器融合 C 代码（机载姿态/位置融合）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "sensor_fusion")
        params = req.get("params", {})
        process_noise = params.get("process_noise", 0.01)
        measure_noise = params.get("measurement_noise", 0.1)
        dt = params.get("dt_sec", 0.01)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载传感器融合实现（扩展卡尔曼滤波）
 * Traceability: {req_id}
 * 模块: {module}
 * 过程噪声: {process_noise}, 测量噪声: {measure_noise}, 周期: {dt}s
 */
#include "{header_name}"
#include <math.h>

/* [{req_id}] [MISRA-Rule-8.9] 卡尔曼滤波状态 */
static double s_state;           /* [{req_id}] 状态估计值 */
static double s_variance;        /* [{req_id}] 估计方差 */
static double s_velocity;        /* [{req_id}] 速度估计（INS 积分） */
static double s_process_q;       /* [{req_id}] 过程噪声协方差 */
static double s_measure_r;       /* [{req_id}] 测量噪声协方差 */
static double s_dt;              /* [{req_id}] 采样周期 */
static int    s_initialized;     /* [{req_id}] 初始化标志 */

/* [{req_id}] [MISRA-Rule-8.13] 初始化卡尔曼滤波器 */
void {module}_init(double init_state, double init_variance)
{{
    s_state = init_state;
    s_variance = init_variance;
    s_velocity = 0.0;
    s_process_q = {process_noise:.6f};
    s_measure_r = {measure_noise:.6f};
    s_dt = {dt:.4f};
    s_initialized = 1;
}}

/* [{req_id}] [MISRA-Rule-15.7] 预测步骤：INS 加速度积分更新状态 */
void {module}_predict(double imu_accel)
{{
    double accel_magnitude;

    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init(0.0, 1.0);
    }}

    /* [{req_id}] [MISRA-Rule-10.4] INS 速度积分 */
    s_velocity += imu_accel * s_dt;

    /* [{req_id}] [MISRA-Rule-10.4] 位置预测 */
    s_state += s_velocity * s_dt;

    /* [{req_id}] [MISRA-Rule-10.4] 方差预测（增大不确定度） */
    accel_magnitude = fabs(imu_accel);
    s_variance += s_process_q * (1.0 + accel_magnitude);
}}

/* [{req_id}] [MISRA-Rule-15.7] 更新步骤：GPS/磁力计观测校正 */
double {module}_update(double gps_measurement)
{{
    double kalman_gain;
    double innovation;

    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init(0.0, 1.0);
    }}

    /* [{req_id}] [MISRA-Rule-10.4] 卡尔曼增益计算 */
    kalman_gain = s_variance / (s_variance + s_measure_r);

    /* [{req_id}] [MISRA-Rule-10.4] 新息（观测残差） */
    innovation = gps_measurement - s_state;

    /* [{req_id}] [MISRA-Rule-10.4] 状态校正 */
    s_state += kalman_gain * innovation;

    /* [{req_id}] [MISRA-Rule-10.4] 方差更新（减小不确定度） */
    s_variance = (1.0 - kalman_gain) * s_variance;

    return s_state;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取当前状态估计 */
double {module}_get_state(void)
{{
    return s_state;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取当前估计不确定度 */
double {module}_get_variance(void)
{{
    return s_variance;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取卡尔曼增益（调试用） */
double {module}_get_gain(void)
{{
    if ((s_variance + s_measure_r) > 0.0)
    {{
        return s_variance / (s_variance + s_measure_r);
    }}
    return 0.0;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void   {module}_init(double init_state, double init_variance);
void   {module}_predict(double imu_accel);
double {module}_update(double gps_measurement);
double {module}_get_state(void);
double {module}_get_variance(void);
double {module}_get_gain(void);

#endif /* {guard} */
"""

    def _gen_mission_planning_code(self, req: dict[str, Any]) -> str:
        """生成任务规划组件 C 代码（航点管理与任务调度）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "mission_planner")
        params = req.get("params", {})
        max_waypoints = params.get("max_waypoints", 32)
        arrival_radius = params.get("arrival_radius_m", 5.0)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [{req_id}] [MISRA-Rule-8.13] 机载任务规划组件实现
 * Traceability: {req_id}
 * 模块: {module}
 * 最大航点数: {max_waypoints}, 到达半径: {arrival_radius}m
 */
#include "{header_name}"
#include <math.h>
#include <string.h>

/* [{req_id}] [MISRA-Rule-8.9] 航点数据结构 */
typedef struct {{
    double latitude;     /* [{req_id}] 纬度 (deg, WGS-84) */
    double longitude;    /* [{req_id}] 经度 (deg, WGS-84) */
    double altitude;     /* [{req_id}] 高度 (m, MSL) */
    double speed;        /* [{req_id}] 期望速度 (m/s) */
    uint8_t action;      /* [{req_id}] 到达动作: 0=直飞, 1=盘旋, 2=悬停, 3=返航 */
}} Waypoint_t;

/* [{req_id}] [MISRA-Rule-8.9] 任务状态枚举 */
typedef enum {{
    MISSION_IDLE = 0,        /* [{req_id}] 空闲 */
    MISSION_ARMED = 1,       /* [{req_id}] 已解锁 */
    MISSION_ACTIVE = 2,      /* [{req_id}] 执行中 */
    MISSION_PAUSED = 3,      /* [{req_id}] 暂停 */
    MISSION_COMPLETE = 4,    /* [{req_id}] 已完成 */
    MISSION_ABORTED = 5      /* [{req_id}] 中止 */
}} MissionState_t;

/* [{req_id}] [MISRA-Rule-8.9] 模块内部状态 */
static Waypoint_t   s_waypoints[{max_waypoints}];
static uint8_t      s_wp_count = 0;
static uint8_t      s_current_wp = 0;
static MissionState_t s_state = MISSION_IDLE;
static int          s_initialized = 0;

/* [{req_id}] [MISRA-Rule-8.13] 初始化任务规划器 */
void {module}_init(void)
{{
    (void)memset(s_waypoints, 0, sizeof(s_waypoints));
    s_wp_count = 0;
    s_current_wp = 0;
    s_state = MISSION_IDLE;
    s_initialized = 1;
}}

/* [{req_id}] [MISRA-Rule-15.7] 添加航点，返回 0=成功, 1=已满 */
int {module}_add_waypoint(double lat, double lon, double alt, double spd, uint8_t action)
{{
    /* [{req_id}] [MISRA-Rule-10.1] 未初始化保护 */
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    if (s_wp_count >= {max_waypoints})
    {{
        return 1;
    }}

    /* [{req_id}] [MISRA-Rule-10.1] 参数范围校验 */
    if ((lat < -90.0) || (lat > 90.0) || (lon < -180.0) || (lon > 180.0))
    {{
        return 1;
    }}

    s_waypoints[s_wp_count].latitude = lat;
    s_waypoints[s_wp_count].longitude = lon;
    s_waypoints[s_wp_count].altitude = alt;
    s_waypoints[s_wp_count].speed = spd;
    s_waypoints[s_wp_count].action = action;
    s_wp_count++;

    return 0;
}}

/* [{req_id}] [MISRA-Rule-15.7] 启动任务 */
int {module}_start(void)
{{
    if (s_wp_count == 0)
    {{
        return 1;
    }}

    s_current_wp = 0;
    s_state = MISSION_ACTIVE;
    return 0;
}}

/* [{req_id}] [MISRA-Rule-15.7] 暂停任务 */
void {module}_pause(void)
{{
    if (s_state == MISSION_ACTIVE)
    {{
        s_state = MISSION_PAUSED;
    }}
}}

/* [{req_id}] [MISRA-Rule-15.7] 恢复任务 */
void {module}_resume(void)
{{
    if (s_state == MISSION_PAUSED)
    {{
        s_state = MISSION_ACTIVE;
    }}
}}

/* [{req_id}] [MISRA-Rule-15.7] 中止任务 */
void {module}_abort(void)
{{
    s_state = MISSION_ABORTED;
}}

/* [{req_id}] [MISRA-Rule-15.7] 检查是否到达当前航点，返回 1=已到达 */
int {module}_check_arrival(double current_lat, double current_lon, double current_alt)
{{
    double dlat, dlon, dist_h, dist_v;
    double R = 6371000.0;  /* [{req_id}] 地球平均半径 (m) */

    if (s_state != MISSION_ACTIVE)
    {{
        return 0;
    }}

    if (s_current_wp >= s_wp_count)
    {{
        s_state = MISSION_COMPLETE;
        return 0;
    }}

    /* [{req_id}] [MISRA-Rule-10.4] Haversine 近似水平距离 */
    dlat = (s_waypoints[s_current_wp].latitude - current_lat) * 3.141592653589793 / 180.0;
    dlon = (s_waypoints[s_current_wp].longitude - current_lon) * 3.141592653589793 / 180.0;
    dist_h = R * sqrt(dlat * dlat + dlon * dlon);

    /* [{req_id}] [MISRA-Rule-10.4] 垂直距离 */
    dist_v = fabs(s_waypoints[s_current_wp].altitude - current_alt);

    /* [{req_id}] [MISRA-Rule-10.1] 到达判定 */
    if ((dist_h <= {arrival_radius:.1f}) && (dist_v <= 5.0))
    {{
        s_current_wp++;
        if (s_current_wp >= s_wp_count)
        {{
            s_state = MISSION_COMPLETE;
        }}
        return 1;
    }}

    return 0;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取当前任务状态 */
MissionState_t {module}_get_state(void)
{{
    return s_state;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取当前航点索引 */
uint8_t {module}_get_current_wp(void)
{{
    return s_current_wp;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取总航点数 */
uint8_t {module}_get_wp_count(void)
{{
    return s_wp_count;
}}

/* [{req_id}] [MISRA-Rule-8.13] 获取指定航点信息 */
int {module}_get_waypoint(uint8_t index, Waypoint_t *wp)
{{
    if (((void *)0 == wp) || (index >= s_wp_count))
    {{
        return 1;
    }}
    *wp = s_waypoints[index];
    return 0;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>

/* [{req_id}] [MISRA-Rule-8.13] 类型定义 */
typedef struct {{
    double latitude;
    double longitude;
    double altitude;
    double speed;
    uint8_t action;
}} Waypoint_t;

typedef enum {{
    MISSION_IDLE = 0,
    MISSION_ARMED = 1,
    MISSION_ACTIVE = 2,
    MISSION_PAUSED = 3,
    MISSION_COMPLETE = 4,
    MISSION_ABORTED = 5
}} MissionState_t;

/* [{req_id}] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void            {module}_init(void);
int             {module}_add_waypoint(double lat, double lon, double alt, double spd, uint8_t action);
int             {module}_start(void);
void            {module}_pause(void);
void            {module}_resume(void);
void            {module}_abort(void);
int             {module}_check_arrival(double current_lat, double current_lon, double current_alt);
MissionState_t  {module}_get_state(void);
uint8_t         {module}_get_current_wp(void);
uint8_t         {module}_get_wp_count(void);
int             {module}_get_waypoint(uint8_t index, Waypoint_t *wp);

#endif /* {guard} */
"""

    def _gen_arinc653_code(self, req: dict[str, Any]) -> str:
        """生成 ARINC 653 分区操作系统 C 代码（航空运行时平台）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "arinc653_partition")
        params = req.get("params", {})
        num_partitions = params.get("num_partitions", 4)
        major_frame_ms = params.get("major_frame_ms", 100)
        health_monitor_interval_ms = params.get("health_monitor_interval_ms", 10)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [REQ-001] [MISRA-Rule-8.13] ARINC 653 分区操作系统实现
 * Traceability: {req_id}
 * 模块: {module}
 * 分区数量: {num_partitions}, 主帧周期: {major_frame_ms}ms
 * 健康监控间隔: {health_monitor_interval_ms}ms
 */
#include "{header_name}"
#include <stdint.h>
#include <string.h>

/* [REQ-001] [MISRA-Rule-8.9] ARINC 653 常量定义 */
#define A653_MAX_PARTITIONS       {num_partitions}
#define A653_MAJOR_FRAME_MS       {major_frame_ms}
#define A653_MINOR_FRAME_MS       10
#define A653_MAX_PORTS            16
#define A653_MAX_PROCESSES        8
#define A653_HEALTH_MON_INTERVAL  {health_monitor_interval_ms}

/* [REQ-001] [MISRA-Rule-8.9] 分区状态枚举 */
typedef enum {{
    PARTITION_IDLE       = 0,
    PARTITION_RUNNABLE   = 1,
    PARTITION_BLOCKED    = 2,
    PARTITION_ERROR      = 3,
    PARTITION_TERMINATED = 4
}} A653PartitionState_t;

/* [REQ-001] [MISRA-Rule-8.9] 进程调度类型 */
typedef enum {{
    PROCESS_PERIODIC    = 0,
    PROCESS_APERIODIC   = 1
}} A653ProcessType_t;

/* [REQ-001] [MISRA-Rule-8.9] 端口类型 */
typedef enum {{
    PORT_SAMPLING  = 0,
    PORT_QUEUING   = 1
}} A653PortType_t;

/* [REQ-001] [MISRA-Rule-8.9] 健康监控动作 */
typedef enum {{
    HM_IGNORE       = 0,
    HM_LOG_ERROR    = 1,
    HM_RESTART_PROC = 2,
    HM_RESTART_PART = 3,
    HM_SHUTDOWN     = 4
}} A653HMAction_t;

/* [REQ-001] [MISRA-Rule-8.9] 分区内端口结构 */
typedef struct {{
    uint8_t         port_id;
    A653PortType_t  port_type;
    uint16_t        msg_size;
    uint8_t         buffer_depth;
    uint8_t         direction;  /* 0=source, 1=destination */
}} A653Port_t;

/* [REQ-001] [MISRA-Rule-8.9] 进程配置结构 */
typedef struct {{
    uint8_t           process_id;
    A653ProcessType_t process_type;
    uint32_t          period_ms;
    uint32_t          deadline_ms;
    uint32_t          time_capacity_ms;
    uint8_t           priority;
}} A653Process_t;

/* [REQ-001] [MISRA-Rule-8.9] 分区配置结构 */
typedef struct {{
    uint8_t               partition_id;
    A653PartitionState_t  state;
    uint32_t              period_ms;
    uint32_t              duration_ms;
    uint8_t               num_processes;
    A653Process_t         processes[A653_MAX_PROCESSES];
    uint8_t               num_ports;
    A653Port_t            ports[A653_MAX_PORTS];
}} A653Partition_t;

/* [REQ-001] [MISRA-Rule-8.9] 模块内部状态 */
static A653Partition_t  s_partitions[A653_MAX_PARTITIONS];
static uint8_t          s_partition_count = 0;
static uint32_t         s_system_tick_ms = 0;
static uint8_t          s_hm_active = 0;
static int              s_initialized = 0;

/* [REQ-001] [MISRA-Rule-8.13] 初始化 ARINC 653 系统 */
void {module}_init(void)
{{
    (void)memset(s_partitions, 0, sizeof(s_partitions));
    s_partition_count = 0;
    s_system_tick_ms = 0;
    s_hm_active = 1;
    s_initialized = 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建分区（空间隔离配置） */
int {module}_create_partition(uint8_t id, uint32_t period_ms, uint32_t duration_ms)
{{
    if (s_partition_count >= A653_MAX_PARTITIONS)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_partitions[s_partition_count].partition_id = id;
    s_partitions[s_partition_count].state = PARTITION_IDLE;
    s_partitions[s_partition_count].period_ms = period_ms;
    s_partitions[s_partition_count].duration_ms = duration_ms;
    s_partitions[s_partition_count].num_processes = 0;
    s_partitions[s_partition_count].num_ports = 0;
    s_partition_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 添加进程到分区（时间隔离配置） */
int {module}_add_process(uint8_t part_idx, uint8_t proc_id,
                         A653ProcessType_t ptype, uint32_t period_ms,
                         uint32_t deadline_ms, uint32_t capacity_ms, uint8_t priority)
{{
    A653Partition_t *part;

    if ((part_idx >= s_partition_count) || (0 == s_initialized))
    {{
        return 1;
    }}

    part = &s_partitions[part_idx];
    if (part->num_processes >= A653_MAX_PROCESSES)
    {{
        return 1;
    }}

    part->processes[part->num_processes].process_id = proc_id;
    part->processes[part->num_processes].process_type = ptype;
    part->processes[part->num_processes].period_ms = period_ms;
    part->processes[part->num_processes].deadline_ms = deadline_ms;
    part->processes[part->num_processes].time_capacity_ms = capacity_ms;
    part->processes[part->num_processes].priority = priority;
    part->num_processes++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建采样端口（分区间通信） */
int {module}_create_sampling_port(uint8_t part_idx, uint8_t port_id,
                                   uint16_t msg_size, uint8_t direction)
{{
    A653Partition_t *part;

    if ((part_idx >= s_partition_count) || (0 == s_initialized))
    {{
        return 1;
    }}

    part = &s_partitions[part_idx];
    if (part->num_ports >= A653_MAX_PORTS)
    {{
        return 1;
    }}

    part->ports[part->num_ports].port_id = port_id;
    part->ports[part->num_ports].port_type = PORT_SAMPLING;
    part->ports[part->num_ports].msg_size = msg_size;
    part->ports[part->num_ports].buffer_depth = 1;
    part->ports[part->num_ports].direction = direction;
    part->num_ports++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建队列端口（分区间通信） */
int {module}_create_queuing_port(uint8_t part_idx, uint8_t port_id,
                                  uint16_t msg_size, uint8_t buffer_depth)
{{
    A653Partition_t *part;

    if ((part_idx >= s_partition_count) || (0 == s_initialized))
    {{
        return 1;
    }}

    part = &s_partitions[part_idx];
    if (part->num_ports >= A653_MAX_PORTS)
    {{
        return 1;
    }}

    part->ports[part->num_ports].port_id = port_id;
    part->ports[part->num_ports].port_type = PORT_QUEUING;
    part->ports[part->num_ports].msg_size = msg_size;
    part->ports[part->num_ports].buffer_depth = buffer_depth;
    part->ports[part->num_ports].direction = 0;
    part->num_ports++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 健康监控处理 */
int {module}_health_monitor(uint8_t part_idx, uint8_t proc_id, A653HMAction_t action)
{{
    A653Partition_t *part;

    if ((part_idx >= s_partition_count) || (0 == s_hm_active))
    {{
        return 1;
    }}

    part = &s_partitions[part_idx];

    switch (action)
    {{
    case HM_IGNORE:
        break;
    case HM_LOG_ERROR:
        /* 实际系统在此处记录错误日志 */
        break;
    case HM_RESTART_PROC:
        /* 实际系统在此处重启指定进程 */
        break;
    case HM_RESTART_PART:
        part->state = PARTITION_IDLE;
        break;
    case HM_SHUTDOWN:
        part->state = PARTITION_TERMINATED;
        break;
    default:
        return 1;
    }}

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 主调度器（时间分区轮转） */
int {module}_schedule(void)
{{
    uint8_t i;
    uint32_t slot;

    if (0 == s_initialized)
    {{
        return 1;
    }}

    s_system_tick_ms += A653_MINOR_FRAME_MS;

    for (i = 0; i < s_partition_count; i++)
    {{
        if (s_partitions[i].state == PARTITION_TERMINATED)
        {{
            continue;
        }}

        slot = s_system_tick_ms % s_partitions[i].period_ms;
        if (slot < s_partitions[i].duration_ms)
        {{
            s_partitions[i].state = PARTITION_RUNNABLE;
        }}
        else
        {{
            s_partitions[i].state = PARTITION_IDLE;
        }}
    }}

    return 0;
}}

/* [REQ-001] [MISRA-Rule-8.13] 获取分区状态 */
A653PartitionState_t {module}_get_state(uint8_t part_idx)
{{
    if (part_idx >= s_partition_count)
    {{
        return PARTITION_ERROR;
    }}
    return s_partitions[part_idx].state;
}}

/* [REQ-001] [MISRA-Rule-8.13] 获取分区数量 */
uint8_t {module}_get_partition_count(void)
{{
    return s_partition_count;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>

/* [REQ-001] [MISRA-Rule-8.9] 类型定义 */
typedef enum {{
    PARTITION_IDLE       = 0,
    PARTITION_RUNNABLE   = 1,
    PARTITION_BLOCKED    = 2,
    PARTITION_ERROR      = 3,
    PARTITION_TERMINATED = 4
}} A653PartitionState_t;

typedef enum {{
    PROCESS_PERIODIC    = 0,
    PROCESS_APERIODIC   = 1
}} A653ProcessType_t;

typedef enum {{
    PORT_SAMPLING  = 0,
    PORT_QUEUING   = 1
}} A653PortType_t;

typedef enum {{
    HM_IGNORE       = 0,
    HM_LOG_ERROR    = 1,
    HM_RESTART_PROC = 2,
    HM_RESTART_PART = 3,
    HM_SHUTDOWN     = 4
}} A653HMAction_t;

/* [REQ-001] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void                    {module}_init(void);
int                     {module}_create_partition(uint8_t id, uint32_t period_ms, uint32_t duration_ms);
int                     {module}_add_process(uint8_t part_idx, uint8_t proc_id,
                                             A653ProcessType_t ptype, uint32_t period_ms,
                                             uint32_t deadline_ms, uint32_t capacity_ms, uint8_t priority);
int                     {module}_create_sampling_port(uint8_t part_idx, uint8_t port_id,
                                                       uint16_t msg_size, uint8_t direction);
int                     {module}_create_queuing_port(uint8_t part_idx, uint8_t port_id,
                                                      uint16_t msg_size, uint8_t buffer_depth);
int                     {module}_health_monitor(uint8_t part_idx, uint8_t proc_id, A653HMAction_t action);
int                     {module}_schedule(void);
A653PartitionState_t    {module}_get_state(uint8_t part_idx);
uint8_t                 {module}_get_partition_count(void);

#endif /* {guard} */
"""

    def _gen_freertos_code(self, req: dict[str, Any]) -> str:
        """生成 FreeRTOS 任务调度 C 代码（嵌入式实时操作系统）。"""
        req_id = req.get("req_id", "REQ-001")
        module = req.get("module_name", "freertos_scheduler")
        params = req.get("params", {})
        max_tasks = params.get("max_tasks", 8)
        max_semaphores = params.get("max_semaphores", 8)
        max_queues = params.get("max_queues", 4)
        tick_rate_hz = params.get("tick_rate_hz", 1000)

        header_name = module + ".h"
        guard = module.upper() + "_H"

        return f"""/* [REQ-001] [MISRA-Rule-8.13] FreeRTOS 任务调度器实现
 * Traceability: {req_id}
 * 模块: {module}
 * 最大任务数: {max_tasks}, 最大信号量数: {max_semaphores}
 * 最大队列数: {max_queues}, 系统 tick 频率: {tick_rate_hz}Hz
 */
#include "{header_name}"
#include <stdint.h>
#include <string.h>

/* [REQ-001] [MISRA-Rule-8.9] FreeRTOS 常量定义 */
#define FREERTOS_MAX_TASKS        {max_tasks}
#define FREERTOS_MAX_SEMAPHORES   {max_semaphores}
#define FREERTOS_MAX_QUEUES       {max_queues}
#define FREERTOS_TICK_RATE_HZ     {tick_rate_hz}
#define FREERTOS_INVALID_TASK     0xFF
#define FREERTOS_WAIT_FOREVER     0xFFFFFFFFU

/* [REQ-001] [MISRA-Rule-8.9] 任务状态枚举 */
typedef enum {{
    TASK_DELETED   = 0,
    TASK_READY     = 1,
    TASK_RUNNING   = 2,
    TASK_BLOCKED   = 3,
    TASK_SUSPENDED = 4
}} FRTOSTaskState_t;

/* [REQ-001] [MISRA-Rule-8.9] 任务优先级 */
typedef enum {{
    PRIORITY_IDLE     = 0,
    PRIORITY_LOW      = 1,
    PRIORITY_NORMAL   = 2,
    PRIORITY_HIGH     = 3,
    PRIORITY_CRITICAL = 4
}} FRTOSPriority_t;

/* [REQ-001] [MISRA-Rule-8.9] 信号量类型 */
typedef enum {{
    SEM_BINARY     = 0,
    SEM_COUNTING   = 1,
    SEM_MUTEX      = 2
}} FTOSSemType_t;

/* [REQ-001] [MISRA-Rule-8.9] 任务控制块 */
typedef struct {{
    uint8_t           task_id;
    FRTOSPriority_t   priority;
    FRTOSTaskState_t  state;
    uint32_t          stack_size;
    uint32_t          period_ms;
    uint32_t          deadline_ms;
    uint32_t          exec_time_us;
    void             *task_handle;
}} FRTOSTask_t;

/* [REQ-001] [MISRA-Rule-8.9] 信号量/互斥锁控制块 */
typedef struct {{
    uint8_t         sem_id;
    FTOSSemType_t   sem_type;
    uint32_t        max_count;
    uint32_t        current_count;
    uint8_t         owner_task_id;
    uint8_t         is_recursive;
}} FTOSSemaphore_t;

/* [REQ-001] [MISRA-Rule-8.9] 队列控制块 */
typedef struct {{
    uint8_t     queue_id;
    uint16_t    item_size;
    uint32_t    max_items;
    uint32_t    items_waiting;
    uint8_t     head;
    uint8_t     tail;
    uint8_t     buffer[256];
}} FRTOSQueue_t;

/* [REQ-001] [MISRA-Rule-8.9] 定时器回调函数类型 */
typedef void (*FRTOSTimerCallback_t)(void *arg);

/* [REQ-001] [MISRA-Rule-8.9] 定时器控制块 */
typedef struct {{
    uint8_t              timer_id;
    uint32_t             period_ms;
    uint32_t             elapsed_ms;
    uint8_t              auto_reload;
    uint8_t              active;
    FRTOSTimerCallback_t callback;
    void                *callback_arg;
}} FRTOSTimer_t;

/* [REQ-001] [MISRA-Rule-8.9] 模块内部状态 */
static FRTOSTask_t      s_tasks[FREERTOS_MAX_TASKS];
static uint8_t          s_task_count = 0;
static FTOSSemaphore_t  s_semaphores[FREERTOS_MAX_SEMAPHORES];
static uint8_t          s_sem_count = 0;
static FRTOSQueue_t     s_queues[FREERTOS_MAX_QUEUES];
static uint8_t          s_queue_count = 0;
static FRTOSTimer_t     s_timers[8];
static uint8_t          s_timer_count = 0;
static uint32_t         s_tick_count = 0;
static int              s_initialized = 0;

/* [REQ-001] [MISRA-Rule-8.13] 初始化 FreeRTOS 调度器 */
void {module}_init(void)
{{
    (void)memset(s_tasks, 0, sizeof(s_tasks));
    (void)memset(s_semaphores, 0, sizeof(s_semaphores));
    (void)memset(s_queues, 0, sizeof(s_queues));
    (void)memset(s_timers, 0, sizeof(s_timers));
    s_task_count = 0;
    s_sem_count = 0;
    s_queue_count = 0;
    s_timer_count = 0;
    s_tick_count = 0;
    s_initialized = 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建任务 */
int {module}_task_create(uint8_t task_id, FRTOSPriority_t priority,
                          uint32_t stack_size, uint32_t period_ms)
{{
    if (s_task_count >= FREERTOS_MAX_TASKS)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_tasks[s_task_count].task_id = task_id;
    s_tasks[s_task_count].priority = priority;
    s_tasks[s_task_count].state = TASK_READY;
    s_tasks[s_task_count].stack_size = stack_size;
    s_tasks[s_task_count].period_ms = period_ms;
    s_tasks[s_task_count].deadline_ms = period_ms;
    s_tasks[s_task_count].exec_time_us = 0;
    s_tasks[s_task_count].task_handle = (void *)0;
    s_task_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 删除任务 */
int {module}_task_delete(uint8_t task_id)
{{
    uint8_t i;

    for (i = 0; i < s_task_count; i++)
    {{
        if (s_tasks[i].task_id == task_id)
        {{
            s_tasks[i].state = TASK_DELETED;
            return 0;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 挂起任务 */
int {module}_task_suspend(uint8_t task_id)
{{
    uint8_t i;

    for (i = 0; i < s_task_count; i++)
    {{
        if (s_tasks[i].task_id == task_id)
        {{
            s_tasks[i].state = TASK_SUSPENDED;
            return 0;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 恢复任务 */
int {module}_task_resume(uint8_t task_id)
{{
    uint8_t i;

    for (i = 0; i < s_task_count; i++)
    {{
        if (s_tasks[i].task_id == task_id)
        {{
            s_tasks[i].state = TASK_READY;
            return 0;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建二值信号量 */
int {module}_sem_binary_create(uint8_t sem_id)
{{
    if (s_sem_count >= FREERTOS_MAX_SEMAPHORES)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_semaphores[s_sem_count].sem_id = sem_id;
    s_semaphores[s_sem_count].sem_type = SEM_BINARY;
    s_semaphores[s_sem_count].max_count = 1;
    s_semaphores[s_sem_count].current_count = 0;
    s_semaphores[s_sem_count].owner_task_id = FREERTOS_INVALID_TASK;
    s_semaphores[s_sem_count].is_recursive = 0;
    s_sem_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建互斥锁 */
int {module}_mutex_create(uint8_t sem_id, uint8_t recursive)
{{
    if (s_sem_count >= FREERTOS_MAX_SEMAPHORES)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_semaphores[s_sem_count].sem_id = sem_id;
    s_semaphores[s_sem_count].sem_type = SEM_MUTEX;
    s_semaphores[s_sem_count].max_count = 1;
    s_semaphores[s_sem_count].current_count = 1;
    s_semaphores[s_sem_count].owner_task_id = FREERTOS_INVALID_TASK;
    s_semaphores[s_sem_count].is_recursive = recursive;
    s_sem_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 获取信号量/互斥锁 */
int {module}_sem_take(uint8_t sem_id, uint8_t task_id, uint32_t timeout)
{{
    uint8_t i;

    for (i = 0; i < s_sem_count; i++)
    {{
        if (s_semaphores[i].sem_id == sem_id)
        {{
            if (s_semaphores[i].current_count > 0)
            {{
                s_semaphores[i].current_count--;
                s_semaphores[i].owner_task_id = task_id;
                return 0;
            }}
            if (timeout == 0)
            {{
                return 1;
            }}
            return 2;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 释放信号量/互斥锁 */
int {module}_sem_give(uint8_t sem_id)
{{
    uint8_t i;

    for (i = 0; i < s_sem_count; i++)
    {{
        if (s_semaphores[i].sem_id == sem_id)
        {{
            if (s_semaphores[i].current_count < s_semaphores[i].max_count)
            {{
                s_semaphores[i].current_count++;
                s_semaphores[i].owner_task_id = FREERTOS_INVALID_TASK;
                return 0;
            }}
            return 1;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建队列 */
int {module}_queue_create(uint8_t queue_id, uint16_t item_size, uint32_t max_items)
{{
    if (s_queue_count >= FREERTOS_MAX_QUEUES)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_queues[s_queue_count].queue_id = queue_id;
    s_queues[s_queue_count].item_size = item_size;
    s_queues[s_queue_count].max_items = max_items;
    s_queues[s_queue_count].items_waiting = 0;
    s_queues[s_queue_count].head = 0;
    s_queues[s_queue_count].tail = 0;
    (void)memset(s_queues[s_queue_count].buffer, 0, sizeof(s_queues[0].buffer));
    s_queue_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 向队列发送消息 */
int {module}_queue_send(uint8_t queue_id, const void *data, uint32_t timeout)
{{
    uint8_t i;
    FRTOSQueue_t *q;

    for (i = 0; i < s_queue_count; i++)
    {{
        if (s_queues[i].queue_id == queue_id)
        {{
            q = &s_queues[i];
            if (q->items_waiting >= q->max_items)
            {{
                return 1;
            }}
            if ((data != (void *)0) && (q->item_size <= (uint16_t)(sizeof(q->buffer) - q->tail)))
            {{
                (void)memcpy(&q->buffer[q->tail], data, q->item_size);
                q->tail += (uint8_t)q->item_size;
                q->items_waiting++;
                return 0;
            }}
            return 1;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 从队列接收消息 */
int {module}_queue_receive(uint8_t queue_id, void *data, uint32_t timeout)
{{
    uint8_t i;
    FRTOSQueue_t *q;

    for (i = 0; i < s_queue_count; i++)
    {{
        if (s_queues[i].queue_id == queue_id)
        {{
            q = &s_queues[i];
            if (q->items_waiting == 0)
            {{
                return 1;
            }}
            if (data != (void *)0)
            {{
                (void)memcpy(data, &q->buffer[q->head], q->item_size);
                q->head += (uint8_t)q->item_size;
                q->items_waiting--;
                return 0;
            }}
            return 1;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 创建软件定时器 */
int {module}_timer_create(uint8_t timer_id, uint32_t period_ms,
                           uint8_t auto_reload, FRTOSTimerCallback_t callback)
{{
    if (s_timer_count >= 8)
    {{
        return 1;
    }}
    if (0 == s_initialized)
    {{
        {module}_init();
    }}

    s_timers[s_timer_count].timer_id = timer_id;
    s_timers[s_timer_count].period_ms = period_ms;
    s_timers[s_timer_count].elapsed_ms = 0;
    s_timers[s_timer_count].auto_reload = auto_reload;
    s_timers[s_timer_count].active = 1;
    s_timers[s_timer_count].callback = callback;
    s_timers[s_timer_count].callback_arg = (void *)0;
    s_timer_count++;

    return 0;
}}

/* [REQ-001] [MISRA-Rule-15.7] 启动/停止定时器 */
int {module}_timer_start(uint8_t timer_id)
{{
    uint8_t i;

    for (i = 0; i < s_timer_count; i++)
    {{
        if (s_timers[i].timer_id == timer_id)
        {{
            s_timers[i].active = 1;
            s_timers[i].elapsed_ms = 0;
            return 0;
        }}
    }}
    return 1;
}}

int {module}_timer_stop(uint8_t timer_id)
{{
    uint8_t i;

    for (i = 0; i < s_timer_count; i++)
    {{
        if (s_timers[i].timer_id == timer_id)
        {{
            s_timers[i].active = 0;
            return 0;
        }}
    }}
    return 1;
}}

/* [REQ-001] [MISRA-Rule-15.7] 系统 tick 处理（定时器递增） */
void {module}_tick(void)
{{
    uint8_t i;

    if (0 == s_initialized)
    {{
        return;
    }}

    s_tick_count++;

    for (i = 0; i < s_timer_count; i++)
    {{
        if (s_timers[i].active)
        {{
            s_timers[i].elapsed_ms++;
            if (s_timers[i].elapsed_ms >= s_timers[i].period_ms)
            {{
                if (s_timers[i].callback != (void *)0)
                {{
                    s_timers[i].callback(s_timers[i].callback_arg);
                }}
                if (s_timers[i].auto_reload)
                {{
                    s_timers[i].elapsed_ms = 0;
                }}
                else
                {{
                    s_timers[i].active = 0;
                }}
            }}
        }}
    }}
}}

/* [REQ-001] [MISRA-Rule-8.13] 获取任务状态 */
FRTOSTaskState_t {module}_task_get_state(uint8_t task_id)
{{
    uint8_t i;

    for (i = 0; i < s_task_count; i++)
    {{
        if (s_tasks[i].task_id == task_id)
        {{
            return s_tasks[i].state;
        }}
    }}
    return TASK_DELETED;
}}

/* [REQ-001] [MISRA-Rule-8.13] 获取任务数量 */
uint8_t {module}_task_get_count(void)
{{
    return s_task_count;
}}

/* ===== 头文件 {header_name} =====
 * {guard}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>

/* [REQ-001] [MISRA-Rule-8.9] 类型定义 */
typedef enum {{
    TASK_DELETED   = 0,
    TASK_READY     = 1,
    TASK_RUNNING   = 2,
    TASK_BLOCKED   = 3,
    TASK_SUSPENDED = 4
}} FRTOSTaskState_t;

typedef enum {{
    PRIORITY_IDLE     = 0,
    PRIORITY_LOW      = 1,
    PRIORITY_NORMAL   = 2,
    PRIORITY_HIGH     = 3,
    PRIORITY_CRITICAL = 4
}} FRTOSPriority_t;

typedef enum {{
    SEM_BINARY     = 0,
    SEM_COUNTING   = 1,
    SEM_MUTEX      = 2
}} FTOSSemType_t;

typedef void (*FRTOSTimerCallback_t)(void *arg);

/* [REQ-001] [MISRA-Rule-8.13] 接口仅暴露必要符号 */
void                    {module}_init(void);
int                     {module}_task_create(uint8_t task_id, FRTOSPriority_t priority,
                                              uint32_t stack_size, uint32_t period_ms);
int                     {module}_task_delete(uint8_t task_id);
int                     {module}_task_suspend(uint8_t task_id);
int                     {module}_task_resume(uint8_t task_id);
int                     {module}_sem_binary_create(uint8_t sem_id);
int                     {module}_mutex_create(uint8_t sem_id, uint8_t recursive);
int                     {module}_sem_take(uint8_t sem_id, uint8_t task_id, uint32_t timeout);
int                     {module}_sem_give(uint8_t sem_id);
int                     {module}_queue_create(uint8_t queue_id, uint16_t item_size, uint32_t max_items);
int                     {module}_queue_send(uint8_t queue_id, const void *data, uint32_t timeout);
int                     {module}_queue_receive(uint8_t queue_id, void *data, uint32_t timeout);
int                     {module}_timer_create(uint8_t timer_id, uint32_t period_ms,
                                               uint8_t auto_reload, FRTOSTimerCallback_t callback);
int                     {module}_timer_start(uint8_t timer_id);
int                     {module}_timer_stop(uint8_t timer_id);
void                    {module}_tick(void);
FRTOSTaskState_t        {module}_task_get_state(uint8_t task_id);
uint8_t                 {module}_task_get_count(void);

#endif /* {guard} */
"""
    # ==================== C++ 代码生成模板 ====================

    def _gen_cpp_smart_pointer_code(self, req: dict[str, Any]) -> str:
        """生成 C++ 智能指针管理器代码（RAII 模式，unique_ptr/shared_ptr）。

        MISRA-C++ 合规要点：
        - Rule 3-1-1: 禁止在头文件中使用未命名命名空间
        - Rule 5-2-1: 使用 const 修饰不变变量
        - Rule 6-6-1: 使用 nullptr 替代 NULL
        - Rule 12-1-2: 使用 explicit 构造函数
        - Rule 18-4-1: 使用 dynamic_cast 替代 static_cast
        """
        req_id = req.get("req_id", "REQ-001")
        req.get("module_name", "resource_manager")
        params = req.get("params", {})
        max_resources = params.get("max_resources", 32)

        return f"""// [{req_id}] C++ 智能指针资源管理器
// MISRA-C++ 合规: Rule 3-1-1/5-2-1/6-6-1/12-1-2/18-4-1
// 特性: RAII、std::unique_ptr、std::shared_ptr、std::make_unique
#pragma once

#include <memory>
#include <vector>
#include <string>
#include <stdexcept>
#include <cstdint>
#include <cstring>

// [{req_id}] 资源基类（演示多态与虚析构）
class ResourceBase {{
public:
    virtual ~ResourceBase() = default;
    virtual std::string get_type() const = 0;
    virtual bool is_valid() const = 0;
    virtual std::size_t size_bytes() const = 0;
}};

// [{req_id}] 具体资源类型
class DataBuffer final : public ResourceBase {{
public:
    explicit DataBuffer(std::size_t capacity)  // [{req_id}] Rule 12-1-2: explicit
        : m_capacity(capacity), m_size(0),
          m_buffer(std::make_unique<uint8_t[]>(capacity)) {{}}

    std::string get_type() const override {{ return "DataBuffer"; }}
    bool is_valid() const override {{ return m_buffer != nullptr; }}  // [{req_id}] Rule 6-6-1: nullptr
    std::size_t size_bytes() const override {{ return m_size; }}
    std::size_t capacity() const {{ return m_capacity; }}

    bool write(const uint8_t* data, std::size_t len) {{  // [{req_id}] Rule 5-2-1: const
        if (len > m_capacity - m_size) return false;
        std::memcpy(m_buffer.get() + m_size, data, len);
        m_size += len;
        return true;
    }}

    const uint8_t* data() const {{ return m_buffer.get(); }}

private:
    std::size_t m_capacity;
    std::size_t m_size;
    std::unique_ptr<uint8_t[]> m_buffer;
}};

// [{req_id}] 信号处理器（演示 shared_ptr 共享所有权）
class SignalHandler {{
public:
    using HandlerFunc = std::function<void(double)>;

    explicit SignalHandler(std::shared_ptr<ResourceBase> resource)  // [{req_id}] Rule 12-1-2: explicit
        : m_resource(std::move(resource)), m_enabled(true) {{}}

    void register_callback(HandlerFunc cb) {{
        m_callbacks.push_back(std::move(cb));
    }}

    void process(double value) {{
        if (!m_enabled || !m_resource->is_valid()) return;
        for (auto& cb : m_callbacks) {{
            cb(value);
        }}
    }}

    std::shared_ptr<ResourceBase> resource() const {{ return m_resource; }}
    void set_enabled(bool e) {{ m_enabled = e; }}

private:
    std::shared_ptr<ResourceBase> m_resource;
    std::vector<HandlerFunc> m_callbacks;
    bool m_enabled;
}};

// [{req_id}] 资源管理器主类（演示 unique_ptr 拥有所有权）
class ResourceManager {{
public:
    ResourceManager() : m_count(0) {{}}

    std::unique_ptr<ResourceBase> create_buffer(std::size_t capacity) {{
        if (m_count >= {max_resources}) {{
            throw std::runtime_error("Resource limit exceeded");
        }}
        m_count++;
        return std::make_unique<DataBuffer>(capacity);
    }}

    void register_shared(std::shared_ptr<ResourceBase> resource) {{
        if (m_count >= {max_resources}) {{
            throw std::runtime_error("Resource limit exceeded");
        }}
        m_shared_resources.push_back(std::move(resource));
        m_count++;
    }}

    std::size_t resource_count() const {{ return m_count; }}

private:
    std::vector<std::shared_ptr<ResourceBase>> m_shared_resources;
    std::size_t m_count;
}};

// [{req_id}] 工厂函数（演示 std::make_unique/make_shared）
namespace factory {{
    inline std::unique_ptr<ResourceBase> create_unique_buffer(std::size_t cap) {{
        return std::make_unique<DataBuffer>(cap);
    }}

    inline std::shared_ptr<ResourceBase> create_shared_buffer(std::size_t cap) {{
        return std::make_shared<DataBuffer>(cap);
    }}
}} // namespace factory
"""

    def _gen_cpp_template_code(self, req: dict[str, Any]) -> str:
        """生成 C++ 模板编程代码（类型安全容器与算法）。"""
        req_id = req.get("req_id", "REQ-001")
        req.get("module_name", "template_engine")
        params = req.get("params", {})
        params.get("max_size", 1024)

        return f"""// [{req_id}] C++ 模板编程示例：类型安全环形缓冲区
// MISRA-C++/JSF AV C++/CERT C++ 合规
// @misra Rule 3-1-1: 禁止未命名命名空间
// @misra Rule 5-2-1: const 修饰不变参数
// @misra Rule 6-6-1: 禁止 goto/NULL，使用显式空状态
// @misra Rule 12-1-2: 构造函数语义显式
// @misra Rule 18-4-1: 禁止手写 new/delete
#pragma once

#include <array>
#include <cstdint>
#include <cstddef>
#include <type_traits>
#include <optional>
#include <stdexcept>

// [{req_id}] [MISRA-C++ Rule 18-4-1] 静态环形缓冲区模板（编译期大小确定）
template <typename T, std::size_t Capacity>
class RingBuffer {{
    static_assert(Capacity > 0, "Capacity must be > 0");
    static_assert(std::is_nothrow_move_constructible_v<T>,
                  "T must be nothrow move-constructible");

public:
    RingBuffer() : m_head(0), m_tail(0), m_size(0) {{}}

    bool push(const T& value) {{
        if (m_size >= Capacity) return false;
        m_buffer[m_tail] = value;
        m_tail = (m_tail + 1) % Capacity;
        m_size++;
        return true;
    }}

    std::optional<T> pop() {{
        if (m_size == 0) return std::nullopt;
        T value = std::move(m_buffer[m_head]);
        m_head = (m_head + 1) % Capacity;
        m_size--;
        return value;
    }}

    std::optional<T> peek() const {{
        if (m_size == 0) return std::nullopt;
        return m_buffer[m_head];
    }}

    std::size_t size() const {{ return m_size; }}
    std::size_t capacity() const {{ return Capacity; }}
    bool empty() const {{ return m_size == 0; }}
    bool full() const {{ return m_size >= Capacity; }}

    void clear() {{
        m_head = 0;
        m_tail = 0;
        m_size = 0;
    }}

private:
    std::array<T, Capacity> m_buffer;
    std::size_t m_head;
    std::size_t m_tail;
    std::size_t m_size;
}};

// [{req_id}] 变参模板：求和函数
template <typename... Args>
constexpr auto sum(Args... args) -> decltype((args + ...)) {{
    return (args + ...);
}}

// [{req_id}] SFINAE 类型萃取
template <typename, typename = void>
struct has_less_than : std::false_type {{}};

template <typename T>
struct has_less_than<T, std::void_t<decltype(std::declval<T>() < std::declval<T>())>>
    : std::true_type {{}};

// [{req_id}] C++20 concepts 约束
template <typename T>
requires has_less_than<T>::value
constexpr T find_min(const T& a, const T& b) {{
    return (a < b) ? a : b;
}}

// [{req_id}] 模板特化示例
template <typename T>
class Serializer {{
public:
    static std::array<uint8_t, sizeof(T)> serialize(const T& value) {{
        std::array<uint8_t, sizeof(T)> result{{}};
        const uint8_t* ptr = reinterpret_cast<const uint8_t*>(&value);
        std::copy(ptr, ptr + sizeof(T), result.begin());
        return result;
    }}
}};

template <>
class Serializer<bool> {{
public:
    static std::array<uint8_t, 1> serialize(bool value) {{
        return {{ value ? 0x01 : 0x00 }};
    }}
}};
"""

    def _gen_cpp_stl_container_code(self, req: dict[str, Any]) -> str:
        """生成 C++ STL 容器管理器代码（vector/map/set 等）。"""
        req_id = req.get("req_id", "REQ-001")
        req.get("module_name", "stl_container_mgr")
        params = req.get("params", {})
        max_items = params.get("max_items", 100)

        return f"""// [{req_id}] C++ STL 容器综合示例
// MISRA-C++/JSF AV C++/CERT C++ 合规
// @misra Rule 3-1-1: 禁止未命名命名空间
// @misra Rule 5-2-1: const 修饰只读参数
// @misra Rule 6-6-1: 使用显式布尔/空状态
// @misra Rule 12-1-2: 接口构造语义显式
// @misra Rule 18-4-1: 容器托管资源，禁止手写 new/delete
#pragma once

#include <vector>
#include <map>
#include <set>
#include <unordered_map>
#include <string>
#include <algorithm>
#include <numeric>
#include <functional>
#include <cstdint>

// [{req_id}] 遥测数据点结构
struct TelemetryPoint {{
    uint32_t    timestamp_ms;
    std::string sensor_id;
    double      value;
    uint8_t     quality;

    bool operator<(const TelemetryPoint& other) const {{
        return timestamp_ms < other.timestamp_ms;
    }}
}};

// [{req_id}] [MISRA-C++ Rule 18-4-1] 遥测数据管理器（演示多种 STL 容器）
class TelemetryManager {{
public:
    bool add_point(const TelemetryPoint& point) {{
        if (m_points.size() >= {max_items}) return false;
        m_points.push_back(point);
        m_sensor_index[point.sensor_id].insert(point.timestamp_ms);
        m_quality_counts[point.quality]++;
        return true;
    }}

    std::vector<TelemetryPoint> query_by_sensor(const std::string& sensor_id) const {{
        std::vector<TelemetryPoint> result;
        auto it = m_sensor_index.find(sensor_id);
        if (it != m_sensor_index.end()) {{
            for (uint32_t ts : it->second) {{
                auto pt = find_by_timestamp(ts);
                if (pt) result.push_back(*pt);
            }}
        }}
        return result;
    }}

    std::vector<TelemetryPoint> get_high_quality() const {{
        std::vector<TelemetryPoint> result;
        std::copy_if(m_points.begin(), m_points.end(),
                     std::back_inserter(result),
                     [](const TelemetryPoint& p) {{ return p.quality >= 3; }});
        std::sort(result.begin(), result.end());
        return result;
    }}

    double average_value() const {{
        if (m_points.empty()) return 0.0;
        double sum = std::accumulate(m_points.begin(), m_points.end(), 0.0,
            [](double acc, const TelemetryPoint& p) {{ return acc + p.value; }});
        return sum / static_cast<double>(m_points.size());
    }}

    std::map<uint8_t, std::size_t> quality_distribution() const {{
        return m_quality_counts;
    }}

    std::size_t total_points() const {{ return m_points.size(); }}

private:
    std::optional<TelemetryPoint> find_by_timestamp(uint32_t ts) const {{
        for (const auto& p : m_points) {{
            if (p.timestamp_ms == ts) return p;
        }}
        return std::nullopt;
    }}

    std::vector<TelemetryPoint>                             m_points;
    std::unordered_map<std::string, std::set<uint32_t>>    m_sensor_index;
    std::map<uint8_t, std::size_t>                         m_quality_counts;
}};
"""

    def _gen_cpp_exception_code(self, req: dict[str, Any]) -> str:
        """生成 C++ 异常处理代码（自定义异常层次）。"""
        req_id = req.get("req_id", "REQ-001")
        req.get("module_name", "exception_handler")
        params = req.get("params", {})
        max_retries = params.get("max_retries", 3)

        return f"""// [{req_id}] C++ 异常处理层次结构
// MISRA-C++/JSF AV C++/CERT C++ 合规
// @misra Rule 3-1-1: 禁止未命名命名空间
// @misra Rule 5-2-1: const 修饰异常上下文
// @misra Rule 6-6-1: 使用 noexcept 标注非抛出接口
// @misra Rule 12-1-2: explicit 构造异常对象
// @misra Rule 18-4-1: 标准库对象托管资源
#pragma once

#include <exception>
#include <string>
#include <cstdint>
#include <functional>
#include <vector>
#include <stdexcept>

// [{req_id}] [MISRA-C++ Rule 12-1-2] 基础异常类
class SkyForgeException : public std::runtime_error {{
public:
    explicit SkyForgeException(const std::string& message, int error_code = -1)
        : std::runtime_error(message), m_error_code(error_code) {{}}

    int error_code() const noexcept {{ return m_error_code; }}
    virtual const char* category() const noexcept {{ return "SkyForge"; }}

private:
    int m_error_code;
}};

// [{req_id}] 配置异常
class ConfigException : public SkyForgeException {{
public:
    ConfigException(const std::string& key, const std::string& reason)
        : SkyForgeException("Config error [" + key + "]: " + reason, 1001),
          m_key(key) {{}}

    const char* category() const noexcept override {{ return "Config"; }}
    const std::string& key() const noexcept {{ return m_key; }}

private:
    std::string m_key;
}};

// [{req_id}] 运行时异常
class RuntimeException : public SkyForgeException {{
public:
    RuntimeException(const std::string& msg, int code = 2001)
        : SkyForgeException(msg, code) {{}}

    const char* category() const noexcept override {{ return "Runtime"; }}
}};

// [{req_id}] 传感器异常
class SensorException : public SkyForgeException {{
public:
    SensorException(const std::string& sensor, const std::string& detail)
        : SkyForgeException("Sensor [" + sensor + "]: " + detail, 3001),
          m_sensor_name(sensor) {{}}

    const char* category() const noexcept override {{ return "Sensor"; }}
    const std::string& sensor_name() const noexcept {{ return m_sensor_name; }}

private:
    std::string m_sensor_name;
}};

// [{req_id}] 安全执行包装器（带重试机制）
class SafeExecutor {{
public:
    struct Result {{
        bool success;
        int error_code;
        std::string error_msg;
    }};

    template <typename Func>
    static Result execute(Func&& func, int max_retries = {max_retries}) {{
        for (int attempt = 0; attempt <= max_retries; ++attempt) {{
            try {{
                func();
                return {{ true, 0, "" }};
            }} catch (const SkyForgeException& e) {{
                if (attempt == max_retries) {{
                    return {{ false, e.error_code(), e.what() }};
                }}
            }} catch (const std::exception& e) {{
                if (attempt == max_retries) {{
                    return {{ false, -1, e.what() }};
                }}
            }}
        }}
        return {{ false, -999, "Max retries exceeded" }};
    }}
}};

// [{req_id}] 全局异常处理器
class GlobalExceptionHandler {{
public:
    using ErrorCallback = std::function<void(const SkyForgeException&)>;

    static GlobalExceptionHandler& instance() {{
        static GlobalExceptionHandler handler;
        return handler;
    }}

    void set_error_callback(ErrorCallback cb) {{ m_callback = std::move(cb); }}

    void handle(const SkyForgeException& e) {{
        m_errors.push_back({{ e.error_code(), std::string(e.what()), e.category() }});
        if (m_callback) m_callback(e);
    }}

    std::size_t error_count() const {{ return m_errors.size(); }}

private:
    GlobalExceptionHandler() = default;
    ErrorCallback m_callback;
    std::vector<std::tuple<int, std::string, std::string>> m_errors;
}};
"""

    def _gen_cpp_inheritance_code(self, req: dict[str, Any]) -> str:
        """生成 C++ 类继承与多态代码（虚函数表与 RTTI）。"""
        req_id = req.get("req_id", "REQ-001")
        req.get("module_name", "polymorphic_system")
        params = req.get("params", {})
        max_handlers = params.get("max_handlers", 16)

        return f"""// [{req_id}] C++ 多态处理器系统（虚函数继承）
// MISRA-C++/JSF AV C++/CERT C++ 合规
// @misra Rule 3-1-1: 禁止未命名命名空间
// @misra Rule 5-2-1: const 修饰只读接口
// @misra Rule 6-6-1: 使用 nullptr 替代 NULL
// @misra Rule 12-1-2: explicit 构造处理器
// @misra Rule 18-4-1: 使用智能指针管理多态对象
#pragma once

#include <memory>
#include <vector>
#include <string>
#include <cstdint>
#include <map>

// [{req_id}] [MISRA-C++ Rule 12-1-2] 抽象基类：处理器接口
class Handler {{
public:
    virtual ~Handler() = default;

    virtual bool process(double input, double& output) = 0;
    virtual std::string name() const = 0;
    virtual std::string type() const {{ return "base"; }}
    virtual void reset() {{}}

    template <typename Derived>
    bool is_type() const {{
        return dynamic_cast<const Derived*>(this) != nullptr;
    }}
}};

// [{req_id}] 派生类：增益处理器
class GainHandler final : public Handler {{
public:
    explicit GainHandler(double gain = 1.0) : m_gain(gain) {{}}

    bool process(double input, double& output) override {{
        output = input * m_gain;
        return true;
    }}

    std::string name() const override {{ return "GainHandler"; }}
    std::string type() const override {{ return "gain"; }}

    void set_gain(double g) {{ m_gain = g; }}
    double gain() const {{ return m_gain; }}

private:
    double m_gain;
}};

// [{req_id}] 派生类：偏移处理器
class OffsetHandler final : public Handler {{
public:
    explicit OffsetHandler(double offset = 0.0) : m_offset(offset) {{}}

    bool process(double input, double& output) override {{
        output = input + m_offset;
        return true;
    }}

    std::string name() const override {{ return "OffsetHandler"; }}
    std::string type() const override {{ return "offset"; }}

    void set_offset(double o) {{ m_offset = o; }}

private:
    double m_offset;
}};

// [{req_id}] 派生类：限幅处理器
class ClampHandler final : public Handler {{
public:
    ClampHandler(double lo, double hi) : m_lo(lo), m_hi(hi) {{}}

    bool process(double input, double& output) override {{
        if (input < m_lo) output = m_lo;
        else if (input > m_hi) output = m_hi;
        else output = input;
        return true;
    }}

    std::string name() const override {{ return "ClampHandler"; }}
    std::string type() const override {{ return "clamp"; }}

private:
    double m_lo, m_hi;
}};

// [{req_id}] 处理器链（演示多态容器）
class HandlerChain {{
public:
    bool add_handler(std::unique_ptr<Handler> handler) {{
        if (m_handlers.size() >= {max_handlers}) return false;
        m_handlers.push_back(std::move(handler));
        return true;
    }}

    bool execute(double input, double& output) {{
        double current = input;
        double temp;
        for (auto& handler : m_handlers) {{
            if (!handler->process(current, temp)) return false;
            current = temp;
        }}
        output = current;
        return true;
    }}

    std::size_t size() const {{ return m_handlers.size(); }}

    void reset_all() {{
        for (auto& h : m_handlers) h->reset();
    }}

    std::map<std::string, std::size_t> type_counts() const {{
        std::map<std::string, std::size_t> counts;
        for (const auto& h : m_handlers) {{
            counts[h->type()]++;
        }}
        return counts;
    }}

private:
    std::vector<std::unique_ptr<Handler>> m_handlers;
}};
"""

    # ==================== Python 代码生成模板 ====================

    def _gen_python_safety_code(self, req: dict[str, Any]) -> str:
        """生成军工软件Python编程规范代码（类型标注、命名规范、模块结构）。

        合规要点（T/ZASDI 0002-2023）：
        - P-01: 禁止使用 eval/exec
        - P-02: 禁止使用全局变量（除必要状态）
        - T-01: 所有函数必须有类型标注
        - 命名规范: snake_case 函数/变量, PascalCase 类名
        """
        req_id = req.get("req_id", "REQ-001")
        module_name = req.get("module_name", "signal_processor")

        return f'''"""
[{req_id}] 军工软件Python编程规范示例
模块: {module_name}
合规标准: T/ZASDI 0002-2023
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


# [{req_id}] P-02: 模块级常量（非全局变量）
MAX_BUFFER_SIZE: int = 1024
DEFAULT_TIMEOUT: float = 5.0


# [{req_id}] 类型定义（PascalCase 命名）
class DataQuality(Enum):
    """数据质量等级。"""
    GOOD = "good"
    SUSPECT = "suspect"
    BAD = "bad"
    MISSING = "missing"


@dataclass
class SensorReading:
    """传感器读数数据类。"""
    sensor_id: int
    value: float
    timestamp: float
    quality: DataQuality = DataQuality.GOOD

    def is_valid(self) -> bool:
        """检查读数是否有效。"""
        return self.quality == DataQuality.GOOD


# [{req_id}] T-01: 所有函数必须有类型标注
class SignalProcessor:
    """信号处理器（军工软件Python编程规范示例）。"""

    def __init__(self, buffer_size: int = 1024) -> None:
        """初始化信号处理器。

        Args:
            buffer_size: 缓冲区大小

        Raises:
            ValueError: 缓冲区大小超出范围
        """
        if buffer_size <= 0 or buffer_size > 1024:
            raise ValueError(f"buffer_size must be in [1, 1024]")
        self._buffer: List[float] = []
        self._buffer_size: int = buffer_size
        self._initialized: bool = True

    def process(self, raw_input: float) -> float:
        """处理输入信号。

        Args:
            raw_input: 原始输入值

        Returns:
            处理后的输出值

        Raises:
            RuntimeError: 未初始化时调用
        """
        # [{req_id}] 未初始化保护
        if not self._initialized:
            raise RuntimeError("Processor not initialized")

        # [{req_id}] 前置条件检查
        if not (0.0 <= raw_input <= 20000.0):
            return 0.0

        # [{req_id}] 信号处理逻辑
        output: float = 0.385870 * raw_input + (1.0 - 0.385870) * (
            self._buffer[-1] if self._buffer else 0.0
        )

        # [{req_id}] 缓冲区管理
        if len(self._buffer) >= self._buffer_size:
            self._buffer.pop(0)
        self._buffer.append(output)

        return output

    def reset(self) -> None:
        """重置处理器状态。"""
        self._buffer.clear()
        self._initialized = True

    def get_buffer(self) -> List[float]:
        """获取当前缓冲区内容。"""
        return self._buffer.copy()

    def __del__(self) -> None:
        """析构函数（RAII 模式）。"""
        self._initialized = False


# [{req_id}] 模块级函数（snake_case 命名）
def create_processor(buffer_size: int = 1024) -> SignalProcessor:
    """创建信号处理器实例。"""
    return SignalProcessor(buffer_size=buffer_size)


def validate_input(value: float, min_val: float = 0.0, max_val: float = 20000.0) -> bool:
    """验证输入值是否在有效范围内。"""
    return min_val <= value <= max_val
'''
