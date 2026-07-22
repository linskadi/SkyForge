"""多语言代码生成 Agent：支持 C/C++/Python 代码生成。"""

import re
from typing import Any

# LLM 客户端 — 通过 L0 provider 注入（L3 启动时注册自己的单例，
# 引擎独立运行时回退到 L1 skyforge_llm.client）。详见 llm_provider.py。
from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client
from skyforge_engine.utils.log_util import logger

# C语言系统提示词
_C_SYSTEM_PROMPT = """你是 DO-178C MISRA-C 编码工程师，专职依据结构化需求与
.contract 契约生成机载 C 代码（含头文件），每处函数/变量必须标注
[REQ-xxx] [MISRA-Rule-x.x] 追溯注释。你必须以适航编码视角工作，
禁止输出非 MISRA 合规代码。

## 输出格式（纯 C 代码）
/* [REQ-001] [MISRA-Rule-8.13] 模块说明 */
#include "module.h"
static double s_prev = 0.0;  /* [REQ-001] [MISRA-Rule-8.9] */
void module_init(void) { /* ... */ }
double module_apply(double raw_input) { /* [REQ-001] [MISRA-Rule-15.7] */ }

## 禁忌
1. 禁止使用动态内存（malloc/calloc/free，MISRA Rule-21.3）
2. 禁止输出非 MISRA 合规代码
3. 禁止遗漏 [REQ-xxx] [MISRA-Rule-x.x] 追溯注释
4. 禁止使用递归"""

# C++系统提示词
_CPP_SYSTEM_PROMPT = """你是 DO-178C MISRA-C++/JSF AV C++ 编码工程师，专职依据结构化需求与
.contract 契约生成机载 C++ 代码，每处函数/类/变量必须标注
[REQ-xxx] [MISRA-Rule-x.x] 追溯注释。你必须以适航编码视角工作。

## 输出格式（纯 C++ 代码）
/* [REQ-001] [MISRA-Rule-2.5] 模块说明 */
#pragma once
#include <cstdint>

class LowPassFilter {
public:
    /* [REQ-001] [MISRA-Rule-15.2] */
    LowPassFilter();
    double apply(double raw_input);
    bool get_fault() const;

private:
    /* [REQ-001] [MISRA-Rule-8.9] */
    double m_prev_output = 0.0;
    bool m_fault_detected = false;
};

## 禁忌
1. 禁止使用 new/delete（JSF-008）
2. 禁止使用异常（JSF-006）
3. 禁止使用 dynamic_cast（JSF-005）
4. 禁止使用 RTTI（JSF-007）
5. 禁止使用多重继承（JSF-009）"""

# Python系统提示词
_PYTHON_SYSTEM_PROMPT = """你是军用安全关键Python编码工程师，专职依据结构化需求与
.contract 契约生成符合《军工软件Python语言编程指南》的代码。

## 输出格式（纯 Python 代码）
# [REQ-001] 模块说明
from typing import Final

# [REQ-001] 常量定义
ALPHA: Final[float] = 0.1

class LowPassFilter:
    "[REQ-001] 低通滤波器类"
    
    def __init__(self) -> None:
        "[REQ-001] 初始化"
        self._prev_output: float = 0.0
    
    def apply(self, raw_input: float) -> float:
        "[REQ-001] 滤波处理"
        return ALPHA * raw_input + (1.0 - ALPHA) * self._prev_output

## 禁忌
1. 禁止使用 eval/exec（P-01）
2. 禁止使用 global/nonlocal（P-02）
3. 禁止使用 try/except（P-04）
4. 禁止使用递归（P-05）
5. 所有函数必须有类型标注（T-01）"""


class MultiLanguageCodeGenerator:
    """多语言代码生成 Agent。"""

    def __init__(self, strategy=None):
        self._prompts = {
            "c": _C_SYSTEM_PROMPT,
            "cpp": _CPP_SYSTEM_PROMPT,
            "python": _PYTHON_SYSTEM_PROMPT,
        }
        if strategy is None:
            from skyforge_engine.core.strategies import get_strategy_for_mode
            strategy = get_strategy_for_mode()
        self.strategy = strategy

    async def run(self, requirement_json: dict[str, Any], contract: str, language: str = "c") -> str:
        """根据需求与契约生成代码。"""
        language = language.lower()
        if language not in self._prompts:
            logger.warning(f"不支持的语言: {language}，默认使用 C")
            language = "c"

        logger.info(f"CodeGeneratorAgent:开始:为 {requirement_json.get('req_id')} 生成 {language.upper()} 代码")

        result = await self.strategy.run(
            requirement_json,
            contract=contract,
            language=language,
            input_type="code_multi",
        )
        if not result.success:
            if len(result.warnings) == 1:
                raise RuntimeError(result.warnings[0])
            raise RuntimeError(
                f"CodeGeneratorAgent 执行失败: {result.warnings}"
            )
        code = result.output
        logger.info(f"CodeGeneratorAgent:完成:{language.upper()} 代码已生成 ({len(code.splitlines())} 行)")
        return code

    async def _llm_run(self, requirement_json: dict[str, Any], contract: str, language: str) -> str:
        """LLM 实现：调用 LLM 生成多语言代码。"""
        import json

        client = get_lmstudio_client()
        prompt = (
            f"请依据以下需求 JSON 与契约生成 {language.upper()} 代码：\n"
            f"需求：\n{json.dumps(requirement_json, ensure_ascii=False, indent=2)}\n\n"
            f"契约：\n{contract}"
        )
        # deepseek-v4-flash 是推理模型，reasoning + content 共享 max_tokens
        # C ~100行 + Python ~200行: 16384 足够；C++ ~800行: 32768
        max_tokens = {"c": 16384, "python": 16384, "cpp": 32768}.get(language, 16384)
        response = await client.chat_async(
            prompt=prompt,
            system_prompt=self._prompts[language],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        if not response:
            raise RuntimeError("CodeGeneratorAgent:LLM 调用返回空响应")
        result = self._parse_response(response, language)
        if not result:
            raise RuntimeError("CodeGeneratorAgent:LLM 响应解析失败")
        return result

    def _parse_response(self, response: str, language: str) -> str:
        """解析LLM响应，提取代码。"""
        code = re.sub(r'`(?:c|cpp|python)?\n?', '', response)
        code = re.sub(r'`\n?$', '', code)
        return code.strip()

    def _mock_run(self, requirement_json: dict[str, Any], language: str) -> str:
        """Mock实现：按语言类型生成示例代码。"""
        if language == "c":
            return self._mock_c(requirement_json)
        elif language == "cpp":
            return self._mock_cpp(requirement_json)
        elif language == "python":
            return self._mock_python(requirement_json)
        return self._mock_c(requirement_json)

    def _mock_c(self, req: dict) -> str:
        """生成 MISRA-C:2012 合规的 C 语言示例代码。

        V0.5.1: 消除 MISRA 12.1/15.5/8.9 违规。
        - Rule 12.1: 括号明确运算符优先级
        - Rule 15.5: 单一 return 语句
        - Rule 8.9: 单一定义点
        """
        module_name = req.get("module_name", "module")
        return (
            "/* [REQ-001] [MISRA-Rule-8.13] " + module_name + " 模块实现 */\n"
            "#include <stdint.h>\n"
            "#include <stddef.h>\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-8.9] 静态变量 — 单一定义 */\n"
            "static double s_prev = 0.0;\n"
            "static int s_fault = 0;\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-8.4] 函数声明 */\n"
            "void " + module_name + "_init(void);\n"
            "double " + module_name + "_apply(double input);\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.7] 初始化函数 */\n"
            "void " + module_name + "_init(void) {\n"
            "    s_prev = 0.0;\n"
            "    s_fault = 0;\n"
            "}\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.7] 处理函数 */\n"
            "double " + module_name + "_apply(double input) {\n"
            "    const double alpha = 0.1;\n"
            "    double output = 0.0;\n"
            "\n"
            "    /* MISRA Rule 12.1: 括号明确运算符优先级 */\n"
            "    if ((input < 0.0) || (input > 20000.0)) {\n"
            "        s_fault = 1;\n"
            "        output = 0.0;\n"
            "    } else {\n"
            "        output = (alpha * input) + ((1.0 - alpha) * s_prev);\n"
            "        s_prev = output;\n"
            "    }\n"
            "\n"
            "    /* MISRA Rule 15.5: 单一 return 语句 */\n"
            "    return output;\n"
            "}\n"
        )

    def _mock_cpp(self, req: dict) -> str:
        """生成C++示例代码。"""
        module_name = req.get("module_name", "Module")
        class_name = module_name.title().replace("_", "")
        return (
            "/* [REQ-001] [MISRA-Rule-2.5] " + module_name + " 模块实现 */\n"
            "#pragma once\n"
            "\n"
            "#include <cstdint>\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.1] 类定义 */\n"
            "class " + class_name + " {\n"
            "public:\n"
            "    /* [REQ-001] [MISRA-Rule-15.2] 构造函数 */\n"
            "    " + class_name + "() noexcept;\n"
            "    \n"
            "    /* [REQ-001] [MISRA-Rule-15.6] 处理函数 */\n"
            "    double apply(double input) noexcept;\n"
            "    \n"
            "    /* [REQ-001] [MISRA-Rule-15.6] 状态查询 */\n"
            "    bool get_fault() const noexcept;\n"
            "\n"
            "private:\n"
            "    /* [REQ-001] [MISRA-Rule-8.9] 成员变量 */\n"
            "    double m_prev_output = 0.0;\n"
            "    bool m_fault_detected = false;\n"
            "};\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.2] 构造函数实现 */\n"
            + class_name + "::" + class_name + "() noexcept\n"
            "    : m_prev_output(0.0), m_fault_detected(false) {\n"
            "}\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.6] 处理函数实现 */\n"
            "double " + class_name + "::apply(double input) noexcept {\n"
            "    if (input < 0.0 || input > 20000.0) {\n"
            "        m_fault_detected = true;\n"
            "        return 0.0;\n"
            "    }\n"
            "    constexpr double alpha = 0.1;\n"
            "    double output = alpha * input + (1.0 - alpha) * m_prev_output;\n"
            "    m_prev_output = output;\n"
            "    return output;\n"
            "}\n"
            "\n"
            "/* [REQ-001] [MISRA-Rule-15.6] 状态查询实现 */\n"
            "bool " + class_name + "::get_fault() const noexcept {\n"
            "    return m_fault_detected;\n"
            "}"
        )

    def _mock_python(self, req: dict) -> str:
        """生成Python示例代码。"""
        module_name = req.get("module_name", "module")
        class_name = module_name.title().replace("_", "")
        lines = [
            "# [REQ-001] " + module_name + " 模块实现",
            "# 符合《军工软件Python语言编程指南》(T/ZASDI 0002-2023)",
            "",
            "from typing import Final",
            "",
            "# [REQ-001] 常量定义",
            "ALPHA: Final[float] = 0.1",
            "",
            "",
            "class " + class_name + ":",
            '    """[REQ-001] ' + module_name + ' 类"""',
            "    ",
            "    def __init__(self) -> None:",
            '        """[REQ-001] 初始化"""',
            "        self._prev_output: float = 0.0",
            "        self._fault_detected: bool = False",
            "    ",
            "    def apply(self, raw_input: float) -> float:",
            '        """[REQ-001] 处理函数"""',
            "        if raw_input < 0.0 or raw_input > 20000.0:",
            "            self._fault_detected = True",
            "            return 0.0",
            "        ",
            "        output: float = ALPHA * raw_input + (1.0 - ALPHA) * self._prev_output",
            "        self._prev_output = output",
            "        return output",
            "    ",
            "    def get_fault(self) -> bool:",
            '        """[REQ-001] 状态查询"""',
            "        return self._fault_detected",
        ]
        return "\n".join(lines)
