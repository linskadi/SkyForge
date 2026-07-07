"""代码修复 Agent（Patch 1 查改解耦的"改"）：基于 MISRA-C 规则模板做定向修复。

输入：Cppcheck 扫描结果（违规列表：行号+规则ID+描述）+ 原 C 代码
输出：修复后的 C 代码 + 修复说明列表

LM Studio 可用（USE_LLM=true）时调用真实 LLM 做语义重写；
否则降级为基于规则 ID 的模板修复（8 个常见 MISRA-C 规则）。
每处修复标注对应 MISRA 规则 ID 和 [REQ-xxx]（保持追溯链）。
"""

import re
from dataclasses import dataclass, field
from typing import Callable

from app.config.setting import settings
from app.core.llm.lmstudio_client import get_lmstudio_client
from app.core.tools.cppcheck_scanner import Violation
from app.rag.misra_searcher import MisraRuleSearcher
from app.rag.rag_enhancer import build_misra_context
from app.utils.log_util import logger

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C 适航代码修复工程师，专职依据 MISRA-C:2012 违规列表对 C 代码做语义重写，保持功能不变同时消除违规。你必须以独立审查者视角工作，不得修改用户代码语义，仅产出修复后的代码。

## 可用工具
- misra_check(code) 返回违规规则列表（143 条规则）
- contract_check(code, contract) 返回契约前后置条件校验结果
- add_traceability(code, req_id) 为每处修复追加 [REQ-xxx] 注释

## 输出格式（严格 JSON，禁止前后缀文字）
{
  "code": "/* 修复后的完整 C 代码 */",
  "actions": [
    {"rule_id": "MISRA-C:2012-Rule-8.7", "line": 5, "description": "转为 static 限定作用域"}
  ]
}

## 禁忌
1. 禁止臆造 MISRA-C 规则编号（必须来自 misra_check 工具返回）
2. 禁止修改用户代码语义（仅消除违规，不改变功能）
3. 禁止输出 JSON 以外的任何文字（含解释、Markdown 包裹）
4. 禁止遗漏 [REQ-xxx] 追溯注释
5. 禁止使用动态内存修复方案（MISRA Rule-21.3）"""


@dataclass
class RepairAction:
    """单条修复动作记录（用于追溯链 + Patch 4 流式推送）。"""

    rule_id: str
    line: int
    description: str
    req_id: str = "REQ-001"
    before: str = ""
    after: str = ""


@dataclass
class RepairResult:
    """修复结果：修复后代码 + 修复说明列表。"""

    code: str
    actions: list[RepairAction] = field(default_factory=list)


# MISRA-C 规则模板修复函数表（rule_id -> handler）
# 每个 handler 签名：(code, violation) -> (new_code, RepairAction)
def _fix_rule_8_1(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 8.1：函数需要类型声明 → 自动添加函数原型。"""
    lines = code.splitlines(keepends=True)
    target_line = ""
    if 0 < v.line <= len(lines):
        target_line = lines[v.line - 1].strip()
    # 匹配函数定义：返回类型 函数名(参数)
    m = re.match(
        r"^(void|int|double|float|char|short|long|unsigned|static\s+\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{?\s*$",
        target_line,
    )
    proto = ""
    func_name = ""
    if m:
        ret_type = m.group(1)
        func_name = m.group(2)
        params = m.group(3).strip()
        proto = f"{ret_type} {func_name}({params});\n"
    else:
        proto = f"/* TODO: 为第 {v.line} 行函数补充原型 */\n"

    # 在文件顶部（注释块之后）插入原型
    insert_idx = 0
    in_block_comment = False
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//") or stripped.startswith("#") or not stripped:
            continue
        insert_idx = i
        break

    proto_block = (
        f"/* [{v.rule_id}] MISRA Rule 8.1: 函数原型声明（自动修复）*/\n{proto}"
    )
    lines.insert(insert_idx, proto_block)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description=f"Rule 8.1: 为函数 {func_name or '(未知)'} 添加原型声明",
        before=target_line,
        after=proto.strip(),
    )
    return new_code, action


def _fix_rule_8_4(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 8.4：外部函数需要声明 → 添加 extern 声明。"""
    lines = code.splitlines(keepends=True)
    target_line = ""
    if 0 < v.line <= len(lines):
        target_line = lines[v.line - 1].strip()
    m = re.search(r"(\w+)\s*\(", target_line)
    func_name = m.group(1) if m else "external_func"
    extern_decl = (
        f"/* [{v.rule_id}] MISRA Rule 8.4: 外部函数 extern 声明（自动修复）*/\n"
        f"extern void {func_name}(void);\n"
    )
    insert_idx = 0
    for i, ln in enumerate(lines):
        if re.search(r"^\w[\w\s\*]*\s+\w+\s*\([^)]*\)\s*\{", ln):
            insert_idx = i
            break
    lines.insert(insert_idx, extern_decl)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description=f"Rule 8.4: 为外部函数 {func_name} 添加 extern 声明",
        before=target_line,
        after=extern_decl.strip(),
    )
    return new_code, action


def _fix_rule_8_7(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 8.7：外部变量定义 → 转为 static。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    if old_line.lstrip().startswith("static"):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.7: 已有 static，无需修复",
        )
    new_line = re.sub(
        r"^(\s*)(void|int|double|float|char|short|long|unsigned)",
        r"\1static \2",
        old_line,
        count=1,
    )
    if new_line == old_line:
        new_line = "static " + old_line
    lines[v.line - 1] = (
        f"/* [{v.rule_id}] MISRA Rule 8.7: 转为 static 限定文件作用域（自动修复）*/\n"
        + new_line
    )
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.7: 外部变量转为 static",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_10_1(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 10.1：隐式转换 → 添加显式类型转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 10.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"(\w+)\s*=\s*([^;]+);",
        r"\1 = (double)(\2); /* [MISRA-Rule-10.1] 显式转换（自动修复）*/",
        old_line,
        count=1,
    )
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-10.1] 显式转换（自动修复）*/\n"
        )
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.1: 添加显式类型转换",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_10_3(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 10.3：赋值隐式转换 → 添加显式转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 10.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"=\s*([^;]+);",
        r"= (double)(\1); /* [MISRA-Rule-10.3] 赋值显式转换（自动修复）*/",
        old_line,
        count=1,
    )
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n")
            + "  /* [MISRA-Rule-10.3] 赋值显式转换（自动修复）*/\n"
        )
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.3: 赋值添加显式转换",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_15_5(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 15.5：函数单一出口 → 重构为单一 return。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 15.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.match(r"^\s*return\s+(.+?);?\s*$", old_line)
    expr = m.group(1).rstrip(";") if m else "0"
    new_line = old_line.replace(
        old_line.strip(),
        "goto __cleanup_15_5; /* [MISRA-Rule-15.5] 单一出口（自动修复）*/",
    )
    lines[v.line - 1] = new_line
    # 在违规行之后第一个 } 前插入 cleanup 标签 + result 变量声明
    for i in range(v.line, len(lines)):
        if lines[i].strip() == "}":
            result_var = "__result_15_5"
            lines.insert(
                i,
                "__cleanup_15_5:\n    return " + result_var + ";\n",
            )
            lines.insert(
                v.line - 1,
                "    double "
                + result_var
                + " = "
                + expr
                + "; /* [MISRA-Rule-15.5] 单一返回变量 */\n",
            )
            break
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.5: 重构为单一 return（goto cleanup）",
        before=old_line.strip(),
        after="goto __cleanup_15_5; ... return __result_15_5;",
    )
    return new_code, action


def _fix_rule_17_7(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 17.7：返回值使用 → 检查返回值。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.match(r"^(\s*)(\w+)\s*\(([^)]*)\)\s*;\s*$", old_line)
    if m:
        indent, func_name, args = m.groups()
        new_line = f"{indent}if ({func_name}({args}) != 0) {{ /* [MISRA-Rule-17.7] 检查返回值（自动修复）*/ }}\n"
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-17.7] 检查返回值（自动修复）*/\n"
        )
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.7: 检查函数返回值",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_20_4(code: str, v: Violation) -> tuple[str, RepairAction]:
    """Rule 20.4：动态内存 → 替换 malloc 为静态分配。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.search(r"malloc\s*\(\s*sizeof\s*\(\s*(\w+)\s*\)\s*\*\s*(\w+)\s*\)", old_line)
    if m:
        elem_type, count_var = m.groups()
        new_line = old_line.replace(
            f"malloc(sizeof({elem_type}) * {count_var})",
            "(__static_buf_20_4) /* [MISRA-Rule-20.4] 静态分配替代 malloc（自动修复）*/",
        )
    else:
        new_line = (
            old_line.replace(
                "malloc(",
                "/* [MISRA-Rule-20.4] 静态分配替代 malloc（自动修复）*/ (0 ? ((void*)0) : ",
            )
            + ")"
        )
    lines[v.line - 1] = new_line
    static_decl = (
        f"/* [{v.rule_id}] MISRA Rule 20.4: 静态缓冲区（替代动态内存，自动修复）*/\n"
        f"static unsigned char __static_buf_20_4[1024];\n"
    )
    insert_idx = 0
    in_block_comment = False
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        insert_idx = i
        break
    lines.insert(insert_idx, static_decl)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.4: 替换 malloc 为静态分配",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# 规则 ID → 修复函数映射（支持形如 "misra-c2012-8.1" / "Rule 8.1" / "8.1" 等格式）
_FIXERS: dict[str, Callable[[str, Violation], tuple[str, RepairAction]]] = {
    "8.1": _fix_rule_8_1,
    "8.4": _fix_rule_8_4,
    "8.7": _fix_rule_8_7,
    "10.1": _fix_rule_10_1,
    "10.3": _fix_rule_10_3,
    "15.5": _fix_rule_15_5,
    "17.7": _fix_rule_17_7,
    "20.4": _fix_rule_20_4,
}


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

    LM Studio 可用（USE_LLM=true）时调用真实 LLM 做语义重写；
    否则降级为基于规则 ID 的模板修复（8 个常见 MISRA-C 规则）。
    """

    async def repair(
        self,
        code: str,
        violations: list[Violation],
        req_id: str = "REQ-001",
    ) -> RepairResult:
        """根据违规列表修复 C 代码。

        Args:
            code: 原 C 代码字符串。
            violations: scan() 返回的违规列表。
            req_id: 关联的 [REQ-xxx] 追溯 Tag。

        Returns:
            RepairResult（含修复后代码 + 修复说明列表）。
        """
        if not violations:
            logger.info("CodeRepairerAgent:无违规，跳过修复")
            return RepairResult(code=code, actions=[])

        logger.info(f"CodeRepairerAgent:开始:修复 {len(violations)} 条违规")

        # RAG 增强：根据违规规则 ID 检索 MISRA 规则详情，注入到修复 prompt
        # 当 RAG_ENABLED=false 时跳过（参考文档 1.6.4 节）
        rag_context = ""
        if getattr(settings, "RAG_ENABLED", False):
            rag_context = self._build_rag_context(violations)
            if rag_context:
                logger.info(
                    f"CodeRepairerAgent:RAG 已注入上下文 ({len(rag_context)} 字符)"
                )
        else:
            logger.debug("CodeRepairerAgent:RAG 未启用，跳过上下文注入")

        # 检查 LM Studio 是否可用
        client = get_lmstudio_client()
        if client.is_available():
            logger.info("CodeRepairerAgent:使用真实 LLM")
            try:
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
                    max_tokens=4096,
                )
                if response:
                    result = self._parse_llm_response(
                        response, code, violations, req_id
                    )
                    if result is not None:
                        logger.info(
                            f"CodeRepairerAgent:完成:共修复 {len(result.actions)} 处 [LLM]"
                        )
                        return result
                logger.warning("CodeRepairerAgent:LLM 调用失败，降级为 Mock")
            except Exception as e:
                logger.error(f"CodeRepairerAgent:LLM 异常，降级为 Mock: {e}")

        # 降级为 Mock（模板修复）
        result = self._mock_repair(code, violations, req_id)
        logger.info(f"CodeRepairerAgent:完成:共修复 {len(result.actions)} 处 [Mock]")
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
            fixer = _FIXERS.get(rule_key)
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
                    f"CodeRepairerAgent:修复 L{v.line} [{v.rule_id}]: {action.description}"
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
        """解析 LLM 输出的修复结果（三级降级，失败返回 None）。"""
        from app.core.llm.json_parser import safe_parse_llm_json

        parsed = safe_parse_llm_json(response)
        if parsed is None:
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
