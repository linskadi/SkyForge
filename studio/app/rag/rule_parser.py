"""MISRA-C 规则解析器：将 misra_rules.txt 解析为结构化的 MisraRule 列表。

支持两种格式：
1. 详解格式（文件前半部分）：
   - "Rule X.Y (强制/要求/建议): <标题>"
   - "Dir X.Y <标题>:" （含要求/解释/示例 段落）
2. 速查手册表格格式（文件后半部分）：
   - 5 行一组：<编号> / Rule X.Y / <标题> / <类别> / <可判定性> / <是否支持>

仅使用标准库（re / collections），不引入新依赖，保证离线可用。
"""

import re
from dataclasses import dataclass, field


@dataclass
class MisraRule:
    """单条 MISRA-C 规则结构化数据。"""

    rule_id: str  # 如 "Rule 8.1" / "Dir 4.1"
    category: (
        str  # type/memory/control/expression/declaration/preprocessor/std_library/other
    )
    severity: str  # 强制/要求/建议（可能为空）
    title: str
    description: str = ""
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典（供 API 序列化使用）。"""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "examples": self.examples,
        }


# 详解格式中的规则头：如 "Rule 8.1 (强制): xxx" 或 "Dir 4.1 xxx:"
_DETAILED_RULE_HEAD = re.compile(
    r"^(Rule|Dir)\s+(\d+\.\d+)\s*(?:\((强制|要求|建议)\))?\s*[:：]?\s*(.*)$"
)

# 速查手册格式：单独一行 "Rule X.Y" 或 "Dir X.Y"
_QUICK_RULE_ID_LINE = re.compile(r"^(Rule|Dir)\s+(\d+\.\d+)\s*$")

# 速查手册格式的 Analyze 编号行：如 "C2301"
_QUICK_CODE_LINE = re.compile(r"^C\d{4}$")

# 严重程度关键词
_SEVERITY_KEYWORDS = {"强制": "强制", "要求": "要求", "建议": "建议"}

# MISRA 章节号 → 默认分类（按规则号前缀）
_RULE_PREFIX_CATEGORY = {
    "1": "environment",  # 标准 C 环境
    "2": "unused_code",  # 未使用代码
    "3": "comments",  # 注释
    "4": "lexical",  # 字符集和词汇约定
    "5": "identifier",  # 标识符
    "6": "type",  # 类型
    "7": "constant",  # 文字和常量
    "8": "declaration",  # 声明和定义
    "9": "declaration",  # 初始化
    "10": "expression",  # 表达式
    "11": "expression",  # 指针类型转换
    "12": "expression",  # 表达式
    "13": "expression",  # 副作用
    "14": "control",  # 控制语句
    "15": "control",  # 跳转语句
    "16": "control",  # switch 语句
    "17": "declaration",  # 函数
    "18": "type",  # 指针
    "19": "expression",  # 重叠存储
    "20": "preprocessor",  # 预处理指令
    "21": "std_library",  # 标准库
    "22": "std_library",  # 流和 IO
}

# 任务允许的 7 个核心分类
_CORE_CATEGORIES = {
    "type",
    "memory",
    "control",
    "expression",
    "declaration",
    "preprocessor",
    "std_library",
}

# 关键词 → 分类映射（用于将环境/注释/标识符等映射到核心分类）
_KEYWORD_CATEGORY_MAP = [
    # (关键词列表, 分类)
    (["动态内存", "malloc", "free", "memory", "内存分配", "堆", "heap"], "memory"),
    (
        ["类型", "typedef", "struct", "union", "enum", "bit-field", "位域", "指针"],
        "type",
    ),
    (["switch", "if", "while", "for", "goto", "循环", "跳转", "分支"], "control"),
    (["表达式", "运算符", "转换", "隐式", "explicit", "cast", "副作用"], "expression"),
    (["声明", "定义", "函数", "原型", "标识符", "作用域", "参数"], "declaration"),
    (["预处理", "宏", "#define", "#include", "预编译", "macro"], "preprocessor"),
    (["标准库", "stdlib", "stdio", "string", "math", "errno", "FILE"], "std_library"),
]


def categorize_rule(title: str, description: str = "") -> str:
    """根据规则标题和描述自动分类。

    分类优先级：
    1. memory 关键词优先匹配（动态内存/malloc/free 等是跨章节主题）
    2. 规则号前缀映射（如 Rule 6.x → type）
    3. 其他关键词匹配
    4. 默认 fallback 为 "declaration"

    Args:
        title: 规则标题（如 "Types shall be explicitly specified"）。
        description: 规则描述（可选）。

    Returns:
        分类字符串（type/memory/control/expression/declaration/
        preprocessor/std_library 之一）。
    """
    text = f"{title} {description}"
    text_lower = text.lower()

    # 1) memory 关键词优先匹配（跨章节主题）
    # _KEYWORD_CATEGORY_MAP[0] = (keywords_list, "memory")
    memory_keywords = _KEYWORD_CATEGORY_MAP[0][0]
    for kw in memory_keywords:
        if kw.lower() in text_lower:
            return "memory"

    # 2) 先尝试从规则号前缀提取分类
    rule_id_match = re.search(r"(?:Rule|Dir)\s*(\d+)\.\d+", text)
    if rule_id_match:
        prefix = rule_id_match.group(1)
        category = _RULE_PREFIX_CATEGORY.get(prefix, "")
        if category in _CORE_CATEGORIES:
            return category

    # 3) 其他关键词匹配
    for keywords, category in _KEYWORD_CATEGORY_MAP[1:]:
        for kw in keywords:
            if kw.lower() in text_lower:
                return category

    # 4) 默认归到 declaration
    return "declaration"


def _normalize_rule_id(rule_type: str, number: str) -> str:
    """规范化规则 ID，如 ("Rule", "8.1") → "Rule 8.1"。"""
    return f"{rule_type} {number}"


def _extract_examples(block_lines: list[str]) -> list[str]:
    """从规则正文中提取示例代码块。

    识别 "示例:" / "非合规代码示例:" / "合规代码示例:" 标签，
    将其后的代码内容（直到下一个标签或段落结束）作为一个 example。

    Args:
        block_lines: 该规则正文的所有行。

    Returns:
        示例代码字符串列表。
    """
    examples: list[str] = []
    current_example: list[str] = []
    in_example = False

    example_labels = ("示例", "非合规代码示例", "合规代码示例", "不合规代码示例")
    section_labels = (
        "要求:",
        "要求：",
        "解释:",
        "解释：",
        "规则解释",
        "规则解释及益处",
    )

    for line in block_lines:
        stripped = line.strip()

        # 检测是否为示例标签行
        is_example_label = any(
            stripped.startswith(label) or stripped == label.rstrip(":")
            for label in example_labels
        )
        # 也匹配单独的 "示例:" / "示例："
        if re.match(
            r"^(示例|非合规代码示例|合规代码示例|不合规代码示例)\s*[:：]?\s*$", stripped
        ):
            is_example_label = True

        if is_example_label:
            # 收尾上一个示例
            if current_example:
                examples.append("\n".join(current_example).strip())
                current_example = []
            in_example = True
            continue

        # 检测是否进入其他段落（要求/解释等），终止当前示例
        if in_example:
            if any(stripped.startswith(label) for label in section_labels):
                if current_example:
                    examples.append("\n".join(current_example).strip())
                    current_example = []
                in_example = False
                continue

            # 在示例块内，跳过空行的开头空行
            if stripped or current_example:
                current_example.append(line.rstrip())

    # 收尾最后一个示例
    if current_example:
        examples.append("\n".join(current_example).strip())

    # 过滤空示例，且去除重复（同一代码块的合规/非合规变体保留）
    seen = set()
    unique_examples: list[str] = []
    for ex in examples:
        key = ex[:100]  # 取前 100 字符作为去重 key
        if ex and key not in seen:
            seen.add(key)
            unique_examples.append(ex)
    return unique_examples


def _extract_field(lines: list[str], field_name: str) -> str:
    """从规则正文中提取指定字段（如 '要求'/'解释'）的内容。

    Args:
        lines: 规则正文行列表。
        field_name: 字段名（"要求" / "解释"）。

    Returns:
        字段内容字符串（去除首尾空白）。
    """
    patterns = [
        rf"^{field_name}\s*[:：]\s*(.*)$",
        rf"^{field_name}[:：](.*)$",
    ]
    in_field = False
    content: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not in_field:
            for pat in patterns:
                m = re.match(pat, stripped)
                if m:
                    first_line = m.group(1).strip()
                    if first_line:
                        content.append(first_line)
                    in_field = True
                    break
            if in_field:
                continue
        else:
            # 终止条件：遇到下一个标签或空行+新段落
            if re.match(
                r"^(要求|解释|示例|非合规代码示例|合规代码示例|规则解释)", stripped
            ):
                break
            if stripped:
                content.append(stripped)
            elif content:
                # 空行表示段落结束
                break
    return "\n".join(content).strip()


def _parse_detailed_rules(content: str) -> list[MisraRule]:
    """解析详解格式的规则段（文件前半部分）。

    详解格式特点：
    - 规则头："Rule X.Y (强制): 标题" 或 "Dir X.Y 标题:"
    - 段落：要求: / 解释: / 示例: / 非合规代码示例: / 合规代码示例:
    - 一直延续到下一个规则头或章节标题

    Args:
        content: 完整文件内容。

    Returns:
        解析出的 MisraRule 列表（详解部分）。
    """
    lines = content.splitlines()
    rules: list[MisraRule] = []
    current_rule: MisraRule | None = None
    current_block: list[str] = []
    # 用于跟踪已添加的规则 ID，避免详解部分重复添加（速查表会补充覆盖度）
    seen_ids: set[str] = set()

    def _flush_current() -> None:
        """收尾当前规则，提取字段后加入 rules。"""
        nonlocal current_rule, current_block
        if current_rule is None:
            current_block = []
            return
        # 提取要求/解释
        if not current_rule.description:
            desc = _extract_field(current_block, "要求")
            if not desc:
                desc = _extract_field(current_block, "解释")
            current_rule.description = desc
        # 提取示例
        if not current_rule.examples:
            current_rule.examples = _extract_examples(current_block)
        # 若分类不在核心分类内，重新按关键词归类
        if current_rule.category not in _CORE_CATEGORIES:
            current_rule.category = categorize_rule(
                current_rule.title, current_rule.description
            )
        rules.append(current_rule)
        seen_ids.add(current_rule.rule_id)
        current_rule = None
        current_block = []

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # 检测是否进入速查手册附录部分
        if (
            "附录：MISRA C:2012 规则速查手册" in stripped
            or "MISRA C:2012 规则列表" in stripped
        ):
            _flush_current()
            break

        # 跳过章节标题（如 "2.2.6 类型 (types)"）
        if re.match(
            r"^\d+\.\d+(\.\d+)?\s+\S", stripped
        ) and not _DETAILED_RULE_HEAD.match(stripped):
            # 章节标题，但不是规则头，跳过
            continue

        # 跳过顶级章节标题（如 "1. MISRA C 概述"）
        if re.match(r"^\d+\.\s+\S", stripped):
            continue

        m = _DETAILED_RULE_HEAD.match(stripped)
        if m:
            # 命中新规则头，收尾上一个规则
            _flush_current()
            rule_type, number, severity, title = m.groups()
            rule_id = _normalize_rule_id(rule_type, number)
            severity = severity or ""
            title = title.strip().rstrip(":：").strip()
            # 提取标题中的严重程度（如 "Rule 1.1 (强制): xxx"）
            if not severity:
                sev_match = re.search(r"\((强制|要求|建议)\)", title)
                if sev_match:
                    severity = sev_match.group(1)
                    title = re.sub(r"\s*\((强制|要求|建议)\)\s*", " ", title).strip()
            # 去除标题尾部多余的冒号
            title = title.rstrip(":：").strip()
            if not title:
                # 标题为空时，从规则号推断（如 "Dir 4.1" 单独一行的情况）
                title = f"{rule_type} {number}"

            # 推断分类
            category = categorize_rule(f"{rule_id} {title}", "")

            current_rule = MisraRule(
                rule_id=rule_id,
                category=category,
                severity=severity,
                title=title,
            )
            current_block = []
            continue

        # 若当前在规则块内，累积正文行
        if current_rule is not None:
            current_block.append(line)

    _flush_current()
    return rules


def _parse_quick_reference(
    content: str, existing_rules: dict[str, MisraRule]
) -> list[MisraRule]:
    """解析速查手册表格格式（文件后半部分）。

    表格格式为 5-6 行一组：
        C2301            <- Analyze 编号
        Dir 1.1           <- 规则 ID
        如果程序的输出...   <- 规则名称
        要求              <- 类别（强制/要求/建议）
        不可判定          <- 可判定性
        否                <- 是否支持

    详解部分已有的规则会补充 severity；详解部分没有的规则会新建。

    Args:
        content: 速查手册部分的内容。
        existing_rules: 详解部分已解析的规则字典 {rule_id: MisraRule}。

    Returns:
        速查手册中新增/更新的规则列表。
    """
    lines = content.splitlines()
    new_rules: list[MisraRule] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        # 检测 Analyze 编号行
        if _QUICK_CODE_LINE.match(line):
            # 接下来的 1-2 行应该是 Rule/Dir 行
            j = i + 1
            # 跳过空行
            while j < n and not lines[j].strip():
                j += 1
            if j >= n:
                break
            rule_id_line = lines[j].strip()
            m = _QUICK_RULE_ID_LINE.match(rule_id_line)
            if not m:
                # 也许同一行：Rule X.Y 紧跟在编号后
                i += 1
                continue
            rule_type, number = m.groups()
            rule_id = _normalize_rule_id(rule_type, number)

            # 下一行是规则名称
            k = j + 1
            while k < n and not lines[k].strip():
                k += 1
            if k >= n:
                break
            title = lines[k].strip()

            # 下一行是类别（强制/要求/建议）
            idx = k + 1
            while idx < n and not lines[idx].strip():
                idx += 1
            severity = ""
            if idx < n:
                sev_line = lines[idx].strip()
                if sev_line in _SEVERITY_KEYWORDS:
                    severity = sev_line
                    idx += 1

            # 如果详解部分已经有该规则，补充 severity（若详解缺）
            if rule_id in existing_rules:
                existing = existing_rules[rule_id]
                if not existing.severity:
                    existing.severity = severity
                # 若详解缺标题但速查表有，补充标题
                if (not existing.title or existing.title == rule_id) and title:
                    existing.title = title
            else:
                # 新建规则（详解部分未覆盖的规则）
                category = categorize_rule(f"{rule_id} {title}", "")
                new_rule = MisraRule(
                    rule_id=rule_id,
                    category=category,
                    severity=severity,
                    title=title,
                    description="",
                    examples=[],
                )
                new_rules.append(new_rule)
                existing_rules[rule_id] = new_rule
            # 跳过本组剩余行
            i = idx
            continue
        i += 1

    return new_rules


def parse_misra_rules(content: str) -> list[MisraRule]:
    """解析 misra_rules.txt 内容为 MisraRule 列表。

    解析流程：
    1. 先解析详解格式部分（含示例代码、要求、解释）。
    2. 再解析速查手册附录部分，补充详解未覆盖的规则。

    Args:
        content: misra_rules.txt 文件完整内容。

    Returns:
        MisraRule 列表（按规则 ID 排序）。
    """
    # 1) 解析详解部分
    detailed_rules = _parse_detailed_rules(content)
    rules_dict: dict[str, MisraRule] = {r.rule_id: r for r in detailed_rules}

    # 2) 找到速查手册附录部分起点
    quick_start_idx = -1
    for marker in [
        "附录：MISRA C:2012 规则速查手册",
        "MISRA C:2012 规则速查手册",
        "MISRA C:2012 规则列表",
    ]:
        idx = content.find(marker)
        if idx != -1:
            quick_start_idx = idx
            break

    if quick_start_idx != -1:
        quick_content = content[quick_start_idx:]
        _parse_quick_reference(quick_content, rules_dict)

    # 3) 排序输出：Dir 在前（按数字顺序），Rule 在后
    def _sort_key(rule: MisraRule) -> tuple:
        parts = rule.rule_id.split()
        if len(parts) != 2:
            return (1, "", 0.0)
        rule_type, number = parts
        type_order = 0 if rule_type == "Dir" else 1
        try:
            num = float(number)
        except ValueError:
            num = 0.0
        return (type_order, rule_type, num)

    return sorted(rules_dict.values(), key=_sort_key)
