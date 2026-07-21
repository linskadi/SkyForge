"""代码修复 Agent（Patch 1 查改解耦的"改"）：基于 MISRA-C 规则模板做定向修复。

输入：Cppcheck 扫描结果（违规列表：行号+规则ID+描述）+ 原 C 代码
输出：修复后的 C 代码 + 修复说明列表

本地 LLM 可用（USE_LLM=true）时调用真实 LLM 做语义重写；
否则降级为基于规则 ID 的模板修复（8 个常见 MISRA-C 规则）。
每处修复标注对应 MISRA 规则 ID 和 [REQ-xxx]（保持追溯链）。
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from skyforge_engine.config import settings
from skyforge_engine.agents.misra_fixes import FIXERS
from skyforge_engine.agents.types import RepairAction
# LLM 客户端 — 通过 L0 provider 注入（L3 启动时注册自己的单例，
# 引擎独立运行时回退到 L1 skyforge_llm.client）。详见 llm_provider.py。
from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client
from skyforge_engine.tools.cppcheck_scanner import Violation
from skyforge_engine.rag.misra_searcher import MisraRuleSearcher
from skyforge_engine.rag.rag_enhancer import build_misra_context
from skyforge_engine.utils.log_util import logger

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C 适航代码修复工程师，专职依据 MISRA-C:2012
违规列表对 C 代码做语义重写，保持功能不变同时消除违规。你必须以独立审查者
视角工作，不得修改用户代码语义，仅产出修复后的代码。

## 可用工具
- misra_check(code) 返回违规规则列表（143 条规则）
- contract_check(code, contract) 返回契约前后置条件校验结果
- add_traceability(code, req_id) 为每处修复追加 [REQ-xxx] 注释

## 输出格式（严格 JSON，禁止前后缀文字）
{
  "code": "/* 修复后的完整 C 代码 */",
  "actions": [
    {"rule_id": "MISRA-C:2012-Rule-8.7", "line": 5,
     "description": "转为 static 限定作用域"}
  ]
}

## 禁忌
1. 禁止臆造 MISRA-C 规则编号（必须来自 misra_check 工具返回）
2. 禁止修改用户代码语义（仅消除违规，不改变功能）
3. 禁止输出 JSON 以外的任何文字（含解释、Markdown 包裹）
4. 禁止遗漏 [REQ-xxx] 追溯注释
5. 禁止使用动态内存修复方案（MISRA Rule-21.3）"""


@dataclass
class RepairResult:
    """修复结果：修复后代码 + 修复说明列表。"""

    code: str
    actions: list[RepairAction] = field(default_factory=list)


def _normalize_rule_id(rule_id: str) -> str:
    """从各种格式中提取规则编号（如 'misra-c2012-8.1' → '8.1'）。"""
    m = re.search(r"(\d+\.\d+)\s*$", rule_id.strip())
    if m:
        return m.group(1)
    return ""


class CodeRepairerAgent:
    """代码修复 Agent。

    输入：Cppcheck 扫描违规列表 + 原 C 代码。
    输出：修复后的 C 代码 + 修复说明列表（RepairAction）。

    本地 LLM 可用（USE_LLM=true）时调用真实 LLM 做语义重写；
    否则降级为基于规则 ID 的模板修复（8 个常见 MISRA-C 规则）。
    """

    def __init__(self, strategy=None) -> None:
        if strategy is None:
            from skyforge_engine.core.strategies import get_strategy_for_mode
            strategy = get_strategy_for_mode()
        self.strategy = strategy

    async def repair(
        self,
        code: str,
        violations: list[Violation],
        req_id: str = "REQ-001",
        log_hook: Callable[[str, str, str], Any] | None = None,
    ) -> RepairResult:
        """根据违规列表修复 C 代码。

        Args:
            code: 原 C 代码字符串。
            violations: scan() 返回的违规列表。
            req_id: 关联的 [REQ-xxx] 追溯 Tag。
            log_hook: 可选的流式推送回调 (agent_name, level, message)，
                支持 sync / async / None。用于推送安全校验告警。

        Returns:
            RepairResult（含修复后代码 + 修复说明列表）。
        """
        if not violations:
            logger.info("CodeRepairerAgent:无违规，跳过修复")
            return RepairResult(code=code, actions=[])

        logger.info(f"CodeRepairerAgent:开始:修复 {len(violations)} 条违规")

        result = await self.strategy.run(
            code,
            violations=violations,
            req_id=req_id,
            log_hook=log_hook,
            input_type="repair",
        )
        if not result.success:
            if len(result.warnings) == 1:
                raise RuntimeError(result.warnings[0])
            raise RuntimeError(
                f"CodeRepairerAgent 执行失败: {result.warnings}"
            )
        repair_result = result.output
        logger.info(
            f"CodeRepairerAgent:完成:共修复 {len(repair_result.actions)} 处"
        )
        return repair_result

    async def _llm_run(
        self,
        code: str,
        violations: list[Violation],
        req_id: str = "REQ-001",
        log_hook: Callable[[str, str, str], Any] | None = None,
    ) -> RepairResult:
        """LLM 实现：调用 LLM 修复代码。"""
        client = get_lmstudio_client()
        if not client.is_available():
            raise RuntimeError("CodeRepairerAgent:LLM 不可用")

        # RAG 增强
        rag_context = ""
        if getattr(settings, "RAG_ENABLED", False):
            rag_context = self._build_rag_context(violations)

        violations_desc = "\n".join(
            f"- L{v.line} [{v.rule_id}] {v.message}" for v in violations
        )
        prompt_parts = [
            f"请修复以下 C 代码中的 MISRA-C 违规（保持功能不变，"
            f"为每处修复追加 [{req_id}] 注释）：\n\n"
            f"违规列表：\n{violations_desc}\n\n"
        ]
        if rag_context:
            prompt_parts.append(f"{rag_context}\n\n")
        prompt_parts.append(f"原代码：\n{code}")
        prompt = "".join(prompt_parts)
        response = await client.chat_async(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=8192,
        )
        if not response:
            raise RuntimeError("CodeRepairerAgent:LLM 调用返回空响应")
        result = self._parse_llm_response(response, code, violations, req_id)
        if result is None:
            raise RuntimeError("CodeRepairerAgent:LLM 输出解析失败")

        # 输出安全校验
        try:
            from skyforge_llm.security.validator import (
                validate_output,
            )

            if getattr(settings, "SECURITY_VALIDATE_OUTPUT", True):
                validation = validate_output(result.code)
                if not validation.passed:
                    for v in validation.violations:
                        logger.warning(f"[Security] LLM 输出违规: {v}")
                        if log_hook is not None:
                            if asyncio.iscoroutinefunction(log_hook):
                                await log_hook(
                                    "REPAIR", "warning", f"安全校验: {v}"
                                )
                            else:
                                log_hook(
                                    "REPAIR", "warning", f"安全校验: {v}"
                                )
                for w in validation.warnings:
                    logger.info(f"[Security] LLM 输出告警: {w}")
        except Exception as e:
            logger.warning(f"输出校验失败（不影响主流程）: {e}")
        return result

    def _build_rag_context(self, violations: list[Violation]) -> str:
        """根据违规列表构建 MISRA 规则上下文（RAG 增强）。

        遍历违规规则 ID，从 MISRA 知识库检索规则详情，注入到修复 prompt。
        静态红线规则 + 动态检索规则 + 去重（参考文档 1.6.4 节）。

        Args:
            violations: 违规列表。

        Returns:
            MISRA 规则上下文文本（无可用规则时返回空字符串）。
        """
        try:
            searcher = MisraRuleSearcher.get_instance()
            if not searcher.get_all_rules():
                return ""
            rule_ids: list[str] = []
            for violation in violations:
                rule_id = violation.rule_id or ""
                if rule_id:
                    rule_ids.append(rule_id)
            if not rule_ids:
                return ""
            return build_misra_context(rule_ids)
        except Exception as e:
            logger.error(f"CodeRepairerAgent:构建 RAG 上下文失败: {e}")
            return ""

    def _mock_repair(
        self,
        code: str,
        violations: list[Violation],
        req_id: str = "REQ-001",
    ) -> RepairResult:
        """Mock 实现：基于规则 ID 的模板修复（8 个常见 MISRA-C 规则）。"""
        # 按行号降序排序，避免插入修复影响后续行号
        sorted_violations = sorted(violations, key=lambda v: v.line, reverse=True)
        actions: list[RepairAction] = []
        current_code = code

        for v in sorted_violations:
            rule_key = _normalize_rule_id(v.rule_id)
            fixer = FIXERS.get(rule_key)
            if fixer is None:
                actions.append(
                    RepairAction(
                        rule_id=v.rule_id,
                        line=v.line,
                        description=f"未实现模板修复（规则 {v.rule_id}），待 LLM 接通",
                        req_id=req_id,
                    )
                )
                continue
            try:
                current_code, action = fixer(current_code, v)
                action.req_id = req_id
                actions.append(action)
                logger.info(
                    f"CodeRepairerAgent:修复 L{v.line}"
                    f" [{v.rule_id}]: {action.description}"
                )
            except Exception as e:
                logger.error(f"CodeRepairerAgent:修复失败 L{v.line} [{v.rule_id}]: {e}")
                actions.append(
                    RepairAction(
                        rule_id=v.rule_id,
                        line=v.line,
                        description=f"修复异常: {e}",
                        req_id=req_id,
                    )
                )

        # 在文件顶部追加修复总览注释
        overview = self._build_overview(actions, req_id)
        final_code = overview + current_code
        return RepairResult(code=final_code, actions=actions)

    def _parse_llm_response(
        self,
        response: str,
        original_code: str,
        violations: list[Violation],
        req_id: str,
    ) -> RepairResult | None:
        """解析 LLM 输出的修复结果（失败返回 None）。"""
        from skyforge_llm.parser import JSONParseError, safe_parse_llm_json

        try:
            parsed = safe_parse_llm_json(response)
        except JSONParseError:
            logger.warning("CodeRepairerAgent:LLM 输出解析失败，降级为 Mock")
            return None

        repaired_code = parsed.get("code")
        if not repaired_code or not isinstance(repaired_code, str):
            logger.warning("CodeRepairerAgent:LLM 输出缺 code 字段，降级为 Mock")
            return None

        # 基本校验：必须含 C 代码特征
        c_markers = ["#include", "void ", "double ", "int ", "static "]
        if not any(m in repaired_code for m in c_markers):
            logger.warning("CodeRepairerAgent:LLM 输出缺 C 代码特征，降级为 Mock")
            return None

        # 解析修复说明列表
        actions_data = parsed.get("actions", [])
        actions: list[RepairAction] = []
        if isinstance(actions_data, list):
            for a in actions_data:
                if not isinstance(a, dict):
                    continue
                actions.append(
                    RepairAction(
                        rule_id=a.get("rule_id", "unknown"),
                        line=a.get("line", 0),
                        description=a.get("description", "LLM 修复"),
                        req_id=req_id,
                    )
                )

        # 若 LLM 未给出 actions，按违规列表构造占位说明
        if not actions:
            for v in violations:
                actions.append(
                    RepairAction(
                        rule_id=v.rule_id,
                        line=v.line,
                        description=f"LLM 语义修复（规则 {v.rule_id}）",
                        req_id=req_id,
                    )
                )

        # 在文件顶部追加修复总览注释
        overview = self._build_overview(actions, req_id)
        final_code = overview + repaired_code
        return RepairResult(code=final_code, actions=actions)

    def _build_overview(self, actions: list[RepairAction], req_id: str) -> str:
        """生成修复总览注释块（保持追溯链）。"""
        lines = [
            f"/* ===== [{req_id}] MISRA-C 自动修复总览 =====",
            f" * 共 {len(actions)} 处修复：",
        ]
        for a in actions:
            lines.append(f" *   L{a.line} [{a.rule_id}] {a.description}")
        lines.append(" */")
        return "\n".join(lines) + "\n\n"
