"""LLR 生成 Agent：从高层需求（HLR）推导低层需求（LLR），
补全 DO-178C 要求的 HLR→LLR→Code 需求层级。

LLR 是 HLR 的细化和分解，包含：
  - 数据结构设计（类型、范围、精度）
  - 算法细节（滤波器类型、截止频率等）
  - 接口契约（输入/输出约束）
  - 时序要求（WCET、采样周期）
  - 故障处理策略（检测、隔离、恢复）

与 contract_generator_agent 的分工：
  - LLR Agent：需求细化（What to build — 详细设计需求）
  - Contract Agent：接口契约（How to verify — 前置/后置/不变式）
"""

from __future__ import annotations

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

_SYSTEM_PROMPT = """你是 DO-178C 机载系统低层需求工程师，专职从高层需求（HLR）
推导低层需求（LLR）。每个 HLR 应产生 1-5 条 LLR，LLR 必须是可验证、可追溯的。

## 可用工具
- derive_llr(hlr_json) 从 HLR 推导 LLR 列表
- refine_requirement(hlr) 细化单条 HLR 为多条 LLR
- define_data_structure(llr) 定义数据结构（类型/范围/精度）

## 输出格式（严格 JSON，禁止前后缀文字）
{
  "module_name": "altimeter_filter",
  "safety_level": "DAL-B",
  "hlr_id": "REQ-001",
  "llrs": [
    {
      "llr_id": "LLR-001",
      "hlr_ref": "REQ-001",
      "category": "algorithm",
      "description": "使用一阶 IIR 低通滤波器（截止频率 10Hz）处理原始高度传感器数据",
      "rationale": "IIR 比 FIR 计算量小，适合嵌入式 MCU 资源约束",
      "verification": "对比仿真输出与 MATLAB filter() 结果，误差 < 0.1%"
    },
    {
      "llr_id": "LLR-002",
      "hlr_ref": "REQ-001",
      "category": "data_structure",
      "description": "滤波系数 alpha=0.3 以 float64 存储，输入/输出类型为 double",
      "rationale": "DAL-B 要求浮点运算必须使用 double 精度避免溢出",
      "verification": "静态类型检查 + MISRA Rule-10.1"
    },
    {
      "llr_id": "LLR-003",
      "hlr_ref": "REQ-001",
      "category": "timing",
      "description": "滤波器 WCET < 1ms，采样周期 10ms（100Hz）",
      "rationale": "满足实时性要求，留 80% 处理器余量",
      "verification": "WCET 分析（GCC -O2 编译后指令计数）"
    }
  ]
}

字段说明：
  - llr_id: 格式 LLR-NNN（项目级唯一）
  - hlr_ref: 引用的 HLR ID（REQ-NNN）
  - category: algorithm / data_structure / interface / timing / fault_handling / constraint
  - description: 可验证的低层需求描述
  - rationale: 设计理由（可选，支撑追溯）
  - verification: 验证方法（可选）

## 禁忌
1. 禁止跳过 HLR 直接输出模糊的 LLR（每条 LLR 必须对应一条 HLR）
2. 禁止遗漏 safety_level 约束（DAL-A 要求更严格的数据结构和时序）
3. 禁止输出 JSON 以外的任何文字（含解释、Markdown 代码块）
4. 禁止生成不可验证的 LLR（如"尽量快" → 必须给出具体数值）
5. 每条 LLR 的 hlr_ref 必须对应存在的 HLR ID"""


class LLRGeneratorAgent:
    """LLR 生成 Agent：从 HLR 列表生成 LLR 列表。

    使用方式::

        from skyforge_engine.agents.llr_generator_agent import LLRGeneratorAgent
        agent = LLRGeneratorAgent()
        llr_result = await agent.generate(hlr_list, safety_level="DAL-C")
    """

    # 可复写的 category 约束
    CATEGORIES = (
        "algorithm",
        "data_structure",
        "interface",
        "timing",
        "fault_handling",
        "constraint",
    )

    def __init__(self) -> None:
        self.system_prompt = _SYSTEM_PROMPT

    async def generate(
        self,
        hlr_list: list[dict[str, Any]],
        safety_level: str = "DAL-C",
        module_name: str = "",
    ) -> dict[str, Any]:
        """从 HLR 列表生成 LLR 列表。

        Args:
            hlr_list: HLR 列表，每项含 req_id / desc / type 等字段。
                如 [{"req_id": "REQ-001", "desc": "低通滤波", "type": "functional"}]
            safety_level: DAL 等级（A-E）。
            module_name: 模块名称。

        Returns:
            LLR 结果字典，含 hlr_count / llr_count / llrs 字段。

        Raises:
            RuntimeError: LLM 生成失败。
        """
        if not hlr_list:
            logger.warning("LLRGenerator:HLR 列表为空，跳过生成")
            return {
                "hlr_count": 0,
                "llr_count": 0,
                "llrs": [],
                "safety_level": safety_level,
                "module_name": module_name,
                "generated": False,
                "reason": "HLR 列表为空",
            }

        client = get_lmstudio_client()
        if not client:
            logger.warning("LLRGenerator:LM Studio 不可用，使用规则引擎降级")
            return self._fallback_generate(hlr_list, safety_level, module_name)

        # 构建 user prompt
        user_prompt = self._build_prompt(hlr_list, safety_level, module_name)

        try:
            raw = await client.chat(
                system=self.system_prompt,
                user=user_prompt,
                temperature=0.3,
            )
            result = safe_parse_llm_json(raw)
        except Exception as e:
            logger.warning(f"LLRGenerator:LLM 生成失败: {e}，降级为规则引擎")
            return self._fallback_generate(hlr_list, safety_level, module_name)

        # 补全元数据
        result["hlr_count"] = len(hlr_list)
        result["llr_count"] = len(result.get("llrs", []))
        result["safety_level"] = safety_level
        result["module_name"] = module_name or result.get("module_name", "")
        result["generated"] = True
        result["method"] = "llm"

        logger.info(
            f"LLRGenerator:生成完成: HLR {result['hlr_count']} 条 "
            f"→ LLR {result['llr_count']} 条 (method=llm)"
        )
        return result

    def _build_prompt(
        self,
        hlr_list: list[dict[str, Any]],
        safety_level: str,
        module_name: str,
    ) -> str:
        """构建 user prompt。"""
        hlr_json = json.dumps(hlr_list, ensure_ascii=False, indent=2)
        return (
            f"请从以下 {len(hlr_list)} 条高层需求（HLR）推导低层需求（LLR）：\n\n"
            f"模块: {module_name or '未指定'}\n"
            f"安全等级: {safety_level}\n\n"
            f"HLR 列表:\n{hlr_json}\n\n"
            f"要求：每条 HLR 产生 1-5 条 LLR，覆盖 algorithm/data_structure/interface/"
            f"timing/fault_handling 等类别。输出严格 JSON，禁止前后缀文字。"
        )

    def _fallback_generate(
        self,
        hlr_list: list[dict[str, Any]],
        safety_level: str,
        module_name: str,
    ) -> dict[str, Any]:
        """规则引擎降级：为每条 HLR 生成至少一条默认 LLR。"""
        llrs: list[dict[str, Any]] = []
        for i, hlr in enumerate(hlr_list, start=1):
            req_id = hlr.get("req_id", f"REQ-{i:03d}")
            desc = hlr.get("desc", "")
            llrs.append({
                "llr_id": f"LLR-{i:03d}",
                "hlr_ref": req_id,
                "category": "constraint",
                "description": f"实现 {desc}（自 HLR {req_id} 推导，规则引擎降级）",
                "rationale": "LLM 不可用时的规则引擎兜底生成",
                "verification": "集成测试",
            })

        logger.info(
            f"LLRGenerator:规则引擎降级: HLR {len(hlr_list)} 条 "
            f"→ LLR {len(llrs)} 条 (method=fallback)"
        )
        return {
            "hlr_count": len(hlr_list),
            "llr_count": len(llrs),
            "llrs": llrs,
            "safety_level": safety_level,
            "module_name": module_name,
            "generated": True,
            "method": "fallback",
        }
