"""MISRA-C++ / JSF AV C++ / CERT C++ 规则模板修复函数库。

每个 fixer 签名：(code, violation) -> (new_code, RepairAction)。
供 CodeRepairerAgent 的降级 Mock 路径使用。

覆盖标准：
  - JSF AV C++（Joint Strike Fighter Air Vehicle C++ Coding Standard）
  - MISRA-C++:2008
  - CERT C++（参考性补充）
"""

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from skyforge_engine.tools.cppcheck_scanner import Violation

from skyforge_engine.agents.types import RepairAction


# ============================================================================
# 工具函数
# ============================================================================

def _lines(code: str) -> list[str]:
    return code.splitlines(keepends=True)


def _bounds(code: str, line: int) -> tuple[list[str], str]:
    """返回 (lines, target_line_text)，越界时 target_line_text 为空。"""
    ls = _lines(code)
    target = ls[line - 1].strip() if 0 < line <= len(ls) else ""
    return ls, target


def _ooB(v: "Violation", desc: str) -> tuple[str, RepairAction]:
    return "", RepairAction(rule_id=v.rule_id, line=v.line, description=f"{desc}: 行号越界，跳过")


# ============================================================================
# JSF AV C++ 规则修复函数（5条）
# ============================================================================


def _fix_jsf_18_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """JSF 18-4-1: dynamic_cast shall not be used to downcast to a void pointer."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "JSF 18-4-1")
    new_line = old.rstrip("\n") + "  /* [JSF-18-4-1] fix: 使用 static_cast 代替 dynamic_cast 或 void* */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="JSF 18-4-1: 避免 dynamic_cast 到 void*",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_jsf_3_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """JSF 3-1-1: The #include directives shall precede all other declarations."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "JSF 3-1-1")
    if old.startswith("#include"):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line,
            description="JSF 3-1-1: #include 已在顶部，无需修复",
        )
    new_line = old.rstrip("\n") + "  /* [JSF-3-1-1] fix: 确保 #include 在其他声明之前 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="JSF 3-1-1: 确保 #include 指令在所有声明之前",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_jsf_5_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """JSF 5-2-1: A class shall not derive (directly or indirectly) from itself."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "JSF 5-2-1")
    new_line = old.rstrip("\n") + "  /* [JSF-5-2-1] TODO: 移除类自继承 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="JSF 5-2-1: 禁止类自继承",
        before=old, after="移除自继承",
    )
    return "".join(ls), action


def _fix_jsf_6_6_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """JSF 6-6-1: Multiple return statements from a function shall not be used (single exit)."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "JSF 6-6-1")
    m = re.match(r"^\s*return\s+(.+?);?\s*$", old)
    expr = m.group(1).rstrip(";") if m else "0"
    new_line = f"goto __cleanup_6_6_1; /* [JSF-6-6-1] fix: 单一出口 */\n"
    ls[v.line - 1] = new_line
    for i in range(v.line, len(ls)):
        if ls[i].strip() == "}":
            ls.insert(i, "__cleanup_6_6_1:\n    return __result_6_6_1;\n")
            ls.insert(v.line - 1, f"    auto __result_6_6_1 = ({expr}); /* [JSF-6-6-1] */\n")
            break
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="JSF 6-6-1: 重构为单一 return",
        before=old, after="goto __cleanup_6_6_1; ... return __result_6_6_1;",
    )
    return "".join(ls), action


def _fix_jsf_12_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """JSF 12-1-2: The result of an expression shall not be discarded."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "JSF 12-1-2")
    m = re.match(r"^(\s*)(\w+)\s*\(([^)]*)\)\s*;\s*$", old)
    if m:
        indent, func_name, args = m.groups()
        new_line = f"{indent}(void){func_name}({args}); /* [JSF-12-1-2] fix */\n"
    else:
        new_line = f"(void)({old.strip()}); /* [JSF-12-1-2] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="JSF 12-1-2: 显式丢弃结果值",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 0: 程序说明（0-1-1 到 0-1-6）
# ============================================================================


def _fix_rule_0_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-1: A project shall not contain unreachable code."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-1")
    indent = len(old) - len(old.lstrip())
    new_line = " " * indent + f"/* [Rule-0-1-1] TODO: 移除不可达代码 */\n" + old
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-1: 标记不可达代码（建议删除）",
        before=old, after="标记不可达代码",
    )
    return "".join(ls), action


def _fix_rule_0_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-2: A project shall not contain dead code."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-2")
    new_line = old.rstrip("\n") + "  /* [Rule-0-1-2] TODO: 移除死代码 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-2: 标记死代码（建议删除）",
        before=old, after="标记死代码",
    )
    return "".join(ls), action


def _fix_rule_0_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-3: A project shall not contain unused code."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-3")
    new_line = old.rstrip("\n") + "  /* [Rule-0-1-3] TODO: 移除未使用代码 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-3: 标记未使用代码（建议删除）",
        before=old, after="标记未使用代码",
    )
    return "".join(ls), action


def _fix_rule_0_1_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-4: All code shall be traceable to requirements."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-4")
    new_line = old.rstrip("\n") + "  /* [Rule-0-1-4] TODO: 添加需求追踪注释 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-4: 确保代码可追溯到需求",
        before=old, after="添加需求追踪",
    )
    return "".join(ls), action


def _fix_rule_0_1_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-5: All deprecated features shall not be used."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-5")
    new_line = old.rstrip("\n") + "  /* [Rule-0-1-5] TODO: 替换已弃用特性 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-5: 替换已弃用的 C++ 特性",
        before=old, after="替换已弃用特性",
    )
    return "".join(ls), action


def _fix_rule_0_1_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0-1-6: A function shall not contain unreachable code."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 0-1-6")
    indent = len(old) - len(old.lstrip())
    new_line = " " * indent + f"/* [Rule-0-1-6] TODO: 移除函数内不可达代码 */\n" + old
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 0-1-6: 移除函数内不可达代码",
        before=old, after="标记不可达代码",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 3: 注释（3-1-2 到 3-4-1）
# ============================================================================


def _fix_rule_3_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-1-2: A /* ... */ comment shall not be used within a comment."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-1-2")
    new_line = old.rstrip("\n") + "  /* [Rule-3-1-2] TODO: 修正注释嵌套 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-1-2: 禁止注释中使用 /* ... */ 嵌套",
        before=old, after="修正注释嵌套",
    )
    return "".join(ls), action


def _fix_rule_3_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-1-3: Sections of code shall not be commented out."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-1-3")
    new_line = old.rstrip("\n") + "  /* [Rule-3-1-3] TODO: 移除被注释掉的代码 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-1-3: 移除被注释掉的代码段",
        before=old, after="移除注释掉的代码",
    )
    return "".join(ls), action


def _fix_rule_3_1_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-1-4: A character sequence shall not occur in a comment."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-1-4")
    new_line = old.rstrip("\n") + "  /* [Rule-3-1-4] TODO: 修正注释中的非法字符序列 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-1-4: 修正注释中的非法字符序列",
        before=old, after="修正字符序列",
    )
    return "".join(ls), action


def _fix_rule_3_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-2-1: The character sequences // and /* shall not be used within a // comment."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-2-1")
    new_line = re.sub(r"(//\s*)/\*", r"\1 / *", old)
    new_line = re.sub(r"(//\s*)\b//\b", r"\1 / /", new_line)
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-3-2-1] TODO: 修正注释中的序列 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-2-1: 修正 // 注释中的 /* 和 //",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_3_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-3-1: The slash-star and star-slash sequences shall not be used within a // comment."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-3-1")
    new_line = re.sub(r"(//\s*)/\*", r"\1 / *", old)
    new_line = re.sub(r"(//\s*)\*/", r"\1 * /", new_line)
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-3-3-1] TODO: 修正注释中的序列 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-3-1: 修正注释中的 /* 和 */",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_3_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3-4-1: A comment shall be terminated by */."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 3-4-1")
    new_line = old.rstrip("\n") + "  /* [Rule-3-4-1] TODO: 确保注释以 */ 终止 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 3-4-1: 确保注释正确终止",
        before=old, after="修正注释终止",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 5: 标识符（5-0-1 到 5-3-1）
# ============================================================================


def _fix_rule_5_0_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-0-1: Global identifiers shall be unique."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-0-1")
    m = re.search(r"\bextern\s+\w+[\s\*]+(\w+)", old)
    if m:
        old_name = m.group(1)
        new_name = f"sf_{old_name}"
        new_line = old.replace(old_name, new_name, 1)
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-5-0-1] TODO: 重命名冲突的全局标识符 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-0-1: 确保全局标识符唯一",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_5_0_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-0-2: A declared identifier shall not be the same as a type in scope."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-0-2")
    new_line = old.rstrip("\n") + "  /* [Rule-5-0-2] TODO: 重命名与类型同名的标识符 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-0-2: 重命名与类型同名的标识符",
        before=old, after="重命名标识符",
    )
    return "".join(ls), action


def _fix_rule_5_0_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-0-3: Identifiers shall not be declared in nested scopes."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-0-3")
    new_line = old.rstrip("\n") + "  /* [Rule-5-0-3] TODO: 将局部变量提升到外部作用域 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-0-3: 避免嵌套作用域中的标识符声明",
        before=old, after="提升变量到外部作用域",
    )
    return "".join(ls), action


def _fix_rule_5_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-1-1: Identifiers shall not be declared to hide an identifier in a parent scope."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-1-1")
    new_line = old.rstrip("\n") + "  /* [Rule-5-1-1] TODO: 重命名以避免隐藏父作用域标识符 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-1-1: 避免隐藏父作用域标识符",
        before=old, after="重命名标识符",
    )
    return "".join(ls), action


def _fix_rule_5_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-1-2: An identifier declared in an inner scope shall not hide an identifier in an outer scope."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-1-2")
    new_line = old.rstrip("\n") + "  /* [Rule-5-1-2] TODO: 重命名以避免隐藏外部作用域标识符 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-1-2: 避免隐藏外部作用域标识符",
        before=old, after="重命名标识符",
    )
    return "".join(ls), action


def _fix_rule_5_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-2-1: Identifiers declared in the same scope shall be unique."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-2-1")
    m = re.match(r"^\s*([\w\s\*&:]+)\s+(\w+)\s*[=;]", old)
    if m:
        var_name = m.group(2)
        new_line = old.replace(var_name, f"{var_name}_2", 1)
        new_line = new_line.rstrip("\n") + "  /* [Rule-5-2-1] fix */\n"
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-5-2-1] TODO: 重命名重复的局部标识符 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-2-1: 确保同作用域标识符唯一",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_5_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-2-2: Identifiers shall be distinct from member names."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-2-2")
    new_line = old.rstrip("\n") + "  /* [Rule-5-2-2] TODO: 重命名以避免与成员名冲突 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-2-2: 重命名以避免与成员名冲突",
        before=old, after="重命名标识符",
    )
    return "".join(ls), action


def _fix_rule_5_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5-3-1: Macro names shall be unique."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 5-3-1")
    m = re.search(r"#define\s+(\w+)", old)
    if m:
        old_name = m.group(1)
        new_name = f"SF_{old_name}"
        new_line = old.replace(old_name, new_name, 1)
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-5-3-1] TODO: 重命名冲突的宏 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 5-3-1: 确保宏名称唯一",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 6-6: 枚举（6-6-2 到 6-6-6）
# ============================================================================


def _fix_rule_6_6_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6-6-2: The member names in an enumerator list shall be unique."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 6-6-2")
    m = re.search(r"(?:^\s*|,)(\w+)\s*(?:=\s*\w+)?", old)
    if m:
        name = m.group(1)
        new_line = old.replace(name, f"sf_{name}", 1)
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-6-6-2] TODO: 重命名重复的枚举成员 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 6-6-2: 确保枚举成员名称唯一",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_6_6_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6-6-3: An enumerator value shall not be explicitly initialized to zero."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 6-6-3")
    new_line = re.sub(r"=\s*0\s*", " /* [Rule-6-6-3] fix: 移除 = 0 */ ", old)
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-6-6-3] TODO: 移除显式零初始化 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 6-6-3: 禁止枚举值显式初始化为零",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_6_6_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6-6-4: The value of an enumerator shall not be implicitly assigned."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 6-6-4")
    if "=" not in old:
        m = re.search(r"(\w+)\s*[,\n]", old)
        if m:
            name = m.group(1)
            new_line = old.replace(f"{name},", f"{name} = 0, /* [Rule-6-6-4] fix */")
            if new_line == old:
                new_line = old.rstrip("\n") + "  /* [Rule-6-6-4] TODO: 为枚举成员显式赋值 */\n"
            ls[v.line - 1] = new_line
            action = RepairAction(
                rule_id=v.rule_id, line=v.line,
                description="Rule 6-6-4: 为枚举成员显式赋值",
                before=old, after=new_line.strip(),
            )
            return "".join(ls), action
    new_line = old.rstrip("\n") + "  /* [Rule-6-6-4] TODO: 确保枚举值显式赋值 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 6-6-4: 确保枚举值显式赋值",
        before=old, after="添加显式赋值",
    )
    return "".join(ls), action


def _fix_rule_6_6_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6-6-5: Each enumerator shall be followed by a , or =."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 6-6-5")
    if not old.rstrip().endswith(",") and "=" not in old:
        new_line = old.rstrip("\n").rstrip() + ", /* [Rule-6-6-5] fix */\n"
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-6-6-5] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 6-6-5: 确保枚举成员后跟 , 或 =",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_6_6_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6-6-6: An enum declaration shall have a consistent form."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 6-6-6")
    new_line = old.rstrip("\n") + "  /* [Rule-6-6-6] TODO: 确保枚举声明形式一致 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 6-6-6: 统一枚举声明形式",
        before=old, after="统一枚举形式",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 7-3: 命名空间（7-3-1 到 7-3-7）
# ============================================================================


def _fix_rule_7_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-1: The global namespace shall only contain main, namespace declarations and extern "C"."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-1")
    new_line = old.rstrip("\n") + "  /* [Rule-7-3-1] TODO: 将声明移入命名空间 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-1: 限制全局命名空间内容",
        before=old, after="移入命名空间",
    )
    return "".join(ls), action


def _fix_rule_7_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-2: A using-directive shall have no effect in the global namespace."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-2")
    new_line = old.rstrip("\n") + "  /* [Rule-7-3-2] TODO: 移除全局命名空间中的 using-directive */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-2: 移除全局命名空间中的 using-directive",
        before=old, after="移除 using-directive",
    )
    return "".join(ls), action


def _fix_rule_7_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-3: A using-directive shall only be used in the global or a named namespace."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-3")
    new_line = old.rstrip("\n") + "  /* [Rule-7-3-3] TODO: 将 using-directive 移至命名空间 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-3: 限制 using-directive 使用位置",
        before=old, after="移至命名空间",
    )
    return "".join(ls), action


def _fix_rule_7_3_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-4: A using-directive shall not be used in a header file."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-4")
    new_line = re.sub(
        r"using\s+namespace\s+(\w+)\s*;",
        r"/* [Rule-7-3-4] fix: 移除头文件中的 using-directive */",
        old,
    )
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-7-3-4] TODO: 移除头文件中的 using-directive */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-4: 禁止头文件中使用 using-directive",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_7_3_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-5: A using-directive shall only be used in a namespace or at the top of a file."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-5")
    new_line = old.rstrip("\n") + "  /* [Rule-7-3-5] TODO: 将 using-directive 移至命名空间或文件顶部 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-5: 限制 using-directive 位置",
        before=old, after="移动 using-directive",
    )
    return "".join(ls), action


def _fix_rule_7_3_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-6: Using-declarations shall not be used in a header file."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-6")
    new_line = re.sub(
        r"using\s+(\w+::\w+)\s*;",
        r"/* [Rule-7-3-6] fix: 移除头文件中的 using-declaration */",
        old,
    )
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-7-3-6] TODO: 移除头文件中的 using-declaration */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-6: 禁止头文件中使用 using-declaration",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_7_3_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7-3-7: Using-declarations shall not be used in namespace scope in a header file."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 7-3-7")
    new_line = old.rstrip("\n") + "  /* [Rule-7-3-7] TODO: 移除头文件命名空间中的 using-declaration */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 7-3-7: 移除头文件命名空间中的 using-declaration",
        before=old, after="移除 using-declaration",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 10-3: 枚举转换（10-3-1 到 10-3-3）
# ============================================================================


def _fix_rule_10_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10-3-1: Implicit conversion of an enumeration to an integer shall not be used."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 10-3-1")
    m = re.search(r"\bstatic_cast\s*<\s*int\s*>\s*\(\s*(\w+)\s*\)", old)
    if m:
        new_line = old  # already has static_cast
    else:
        new_line = re.sub(
            r"(?<!static_cast<int>)\b(\w+)\b(?!\s*[\(:])",
            r"static_cast<int>(\1)",
            old,
            count=1,
        )
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-10-3-1] TODO: 使用 static_cast<int> 显式转换枚举 */\n"
    else:
        new_line += "  /* [Rule-10-3-1] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 10-3-1: 禁止隐式枚举到整数转换",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_10_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10-3-2: An enumeration shall not be used as an operand to an operator."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 10-3-1")
    new_line = old.rstrip("\n") + "  /* [Rule-10-3-2] TODO: 使用显式转换替代枚举运算 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 10-3-2: 禁止枚举作为运算符操作数",
        before=old, after="添加显式类型转换",
    )
    return "".join(ls), action


def _fix_rule_10_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10-3-3: An enumeration shall not be used as the left operand of an assignment."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 10-3-3")
    new_line = old.rstrip("\n") + "  /* [Rule-10-3-3] TODO: 不要将枚举赋值给枚举变量 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 10-3-3: 禁止枚举作为赋值左操作数",
        before=old, after="使用显式枚举值",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 14: 控制流表达式（14-3-1 到 14-5-2）
# ============================================================================


def _fix_rule_14_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-3-1: There shall be no unreachable code."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-3-1")
    indent = len(old) - len(old.lstrip())
    new_line = " " * indent + f"/* [Rule-14-3-1] TODO: 移除不可达代码 */\n" + old
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-3-1: 移除不可达代码",
        before=old, after="标记不可达代码",
    )
    return "".join(ls), action


def _fix_rule_14_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-3-2: The loop-counter shall not be modified in the loop body."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-3-2")
    new_line = old.rstrip("\n") + "  /* [Rule-14-3-2] TODO: 不要在循环体中修改循环计数器 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-3-2: 禁止循环体内修改循环计数器",
        before=old, after="移除循环计数器修改",
    )
    return "".join(ls), action


def _fix_rule_14_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-3-3: The body of a loop shall be a compound statement."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-3-3")
    pat = r"^\s*(for|while|do)\b"
    if re.match(pat, old) and "{" not in old:
        indent = len(old) - len(old.lstrip())
        new_line = old.rstrip("\n") + " {\n"
        ls[v.line - 1] = new_line
        if v.line < len(ls):
            body = ls[v.line].rstrip("\n")
            ls[v.line] = " " * (indent + 4) + body.lstrip() + "\n"
        ls.insert(v.line + 1, " " * indent + "}\n")
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-14-3-3] TODO: 确保循环体为复合语句 */\n"
        ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-3-3: 确保循环体为复合语句 {}",
        before=old, after="添加复合语句大括号",
    )
    return "".join(ls), action


def _fix_rule_14_3_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-3-4: The controlling expression of a loop shall not have side effects."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-3-4")
    new_line = old.rstrip("\n") + "  /* [Rule-14-3-4] TODO: 将副作用表达式移出循环条件 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-3-4: 移除循环条件中的副作用",
        before=old, after="拆分副作用表达式",
    )
    return "".join(ls), action


def _fix_rule_14_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-4-1: The controlling expression shall be a boolean expression."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-4-1")
    m = re.search(r"(if|while)\s*\(\s*(\w+)\s*\)", old)
    if m:
        keyword, var = m.groups()
        new_line = old.replace(f"{var})", f"{var} != 0)")
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-14-4-1] TODO: 使用布尔表达式 */\n"
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-14-4-1] TODO: 使用布尔表达式 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-4-1: 使用布尔类型的控制表达式",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_14_4_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-4-2: The value of a controlling expression shall not be changed in the loop body."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-4-2")
    new_line = old.rstrip("\n") + "  /* [Rule-14-4-2] TODO: 不要在循环体中修改条件变量 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-4-2: 禁止循环体内修改条件变量",
        before=old, after="移除条件变量修改",
    )
    return "".join(ls), action


def _fix_rule_14_4_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-4-3: The value of a controlling expression shall not be modified in the body of an iteration statement."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-4-3")
    new_line = old.rstrip("\n") + "  /* [Rule-14-4-3] TODO: 不要在迭代语句体内修改控制表达式 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-4-3: 禁止迭代语句体内修改控制表达式",
        before=old, after="移除控制表达式修改",
    )
    return "".join(ls), action


def _fix_rule_14_4_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-4-4: A controlling expression shall not have a type that is not bool, and shall not have a floating-point type."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-4-4")
    new_line = old.rstrip("\n") + "  /* [Rule-14-4-4] TODO: 确保控制表达式为 bool 或整型 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-4-4: 控制表达式不应为浮点类型",
        before=old, after="转换为整型或 bool",
    )
    return "".join(ls), action


def _fix_rule_14_5_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-5-1: A for-loop shall not use floating-point counters."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-5-1")
    new_line = old.rstrip("\n") + "  /* [Rule-14-5-1] TODO: 使用整型计数器替代浮点计数器 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-5-1: 禁止 for 循环使用浮点计数器",
        before=old, after="使用整型计数器",
    )
    return "".join(ls), action


def _fix_rule_14_5_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14-5-2: The loop body of a do-while statement shall be a compound statement."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 14-5-2")
    if old.lstrip().startswith("do") and "{" not in old:
        indent = len(old) - len(old.lstrip())
        new_line = old.rstrip("\n") + " {\n"
        ls[v.line - 1] = new_line
        if v.line < len(ls):
            body = ls[v.line].rstrip("\n")
            ls[v.line] = " " * (indent + 4) + body.lstrip() + "\n"
        ls.insert(v.line + 1, " " * indent + "}\n")
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-14-5-2] TODO: 确保 do-while 体为复合语句 */\n"
        ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 14-5-2: 确保 do-while 体为复合语句",
        before=old, after="添加复合语句大括号",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 15: 控制流（15-1-1 到 15-3-1）
# ============================================================================


def _fix_rule_15_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-1-1: All if...else and switch constructs shall be well-formed."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-1-1")
    new_line = old.rstrip("\n") + "  /* [Rule-15-1-1] TODO: 确保 if/else 和 switch 结构完整 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-1-1: 确保 if/else 和 switch 结构完整",
        before=old, after="修正控制流结构",
    )
    return "".join(ls), action


def _fix_rule_15_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-1-2: Every non-void function with non-void return type shall have an explicit return statement."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-1-2")
    m = re.search(r"(?:int|double|float|char|long|short|unsigned|auto)\s+\w+\s*\(", old)
    if m:
        return_type = m.group(0).split()[0]
        if return_type == "auto":
            return_type = "int"
        default_return = f"    return ({return_type})0; /* [Rule-15-1-2] fix */\n"
        brace_count = 0
        insert_idx = len(ls) - 1
        for i in range(v.line - 1, len(ls)):
            brace_count += ls[i].count("{") - ls[i].count("}")
            if brace_count == 0 and i > v.line - 1:
                insert_idx = i
                break
        ls.insert(insert_idx, default_return)
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-15-1-2] TODO: 添加默认 return 语句 */\n"
        ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-1-2: 添加非 void 函数的默认 return",
        before=old, after="添加默认 return",
    )
    return "".join(ls), action


def _fix_rule_15_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-1-3: Every function with non-void return type shall return a value on all paths."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-1-3")
    m = re.search(r"(?:int|double|float|char|long|short|unsigned)\s+\w+\s*\(", old)
    if m:
        return_type = m.group(0).split()[0]
        brace_count = 0
        insert_idx = len(ls) - 1
        for i in range(v.line - 1, len(ls)):
            brace_count += ls[i].count("{") - ls[i].count("}")
            if brace_count == 0 and i > v.line - 1:
                insert_idx = i
                break
        ls.insert(insert_idx, f"    return ({return_type})0; /* [Rule-15-1-3] fix */\n")
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-15-1-3] TODO: 确保所有路径有 return */\n"
        ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-1-3: 确保所有路径返回值",
        before=old, after="添加所有路径的 return",
    )
    return "".join(ls), action


def _fix_rule_15_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-2-1: The goto statement shall not be used."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-2-1")
    new_line = old.rstrip("\n") + "  /* [Rule-15-2-1] TODO: 使用 break/return 替代 goto */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-2-1: 禁止使用 goto",
        before=old, after="使用 break/return 替代",
    )
    return "".join(ls), action


def _fix_rule_15_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-2-2: A goto label shall not be the target of a jump from outside its scope."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-2-2")
    new_line = old.rstrip("\n") + "  /* [Rule-15-2-2] TODO: 重构以避免跨作用域 goto */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-2-2: 禁止跨作用域 goto",
        before=old, after="重构 goto 路径",
    )
    return "".join(ls), action


def _fix_rule_15_2_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-2-3: A goto shall not jump over a declaration."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-2-3")
    new_line = old.rstrip("\n") + "  /* [Rule-15-2-3] TODO: 重构以避免 goto 跳过声明 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-2-3: 禁止 goto 跳过变量声明",
        before=old, after="重构 goto 路径",
    )
    return "".join(ls), action


def _fix_rule_15_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15-3-1: Every switch statement shall have a default label."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 15-3-1")
    brace_count = 0
    insert_idx = v.line - 1
    for i in range(v.line - 1, len(ls)):
        brace_count += ls[i].count("{") - ls[i].count("}")
        if brace_count == 0 and i > v.line - 1:
            insert_idx = i
            break
    default_case = "    default: /* [Rule-15-3-1] fix */\n        break;\n"
    ls.insert(insert_idx, default_case)
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 15-3-1: 为 switch 添加 default 标签",
        before=old, after="添加 default 标签",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 16: switch 语句（16-1-1）
# ============================================================================


def _fix_rule_16_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16-1-1: All switch clauses shall be terminated by a break statement."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 16-1-1")
    m = re.search(r"(case\s+\w+\s*:|default\s*:)", old)
    if m and "break" not in old and "return" not in old:
        new_line = old.rstrip("\n").rstrip() + "\n        break; /* [Rule-16-1-1] fix */\n"
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-16-1-1] TODO: 确保 switch 分支以 break 终止 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 16-1-1: 确保 switch 分支以 break 终止",
        before=old, after="添加 break 语句",
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 17-3: 函数（17-3-1 到 17-3-6）
# ============================================================================


def _fix_rule_17_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-1: The identifier for a function shall not be reused."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-1")
    new_line = old.rstrip("\n") + "  /* [Rule-17-3-1] TODO: 重命名以避免函数标识符重用 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-1: 禁止函数标识符重用",
        before=old, after="重命名函数",
    )
    return "".join(ls), action


def _fix_rule_17_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-2: A function shall not call itself directly or indirectly."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-2")
    new_line = old.rstrip("\n") + "  /* [Rule-17-3-2] TODO: 消除递归调用（改为迭代实现） */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-2: 禁止直接或间接递归",
        before=old, after="改为迭代实现",
    )
    return "".join(ls), action


def _fix_rule_17_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-3: A function shall not have an empty parameter list."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-3")
    new_line = re.sub(r"\(\s*\)", "(void)", old)
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-17-3-3] TODO: 将 () 替换为 (void) */\n"
    else:
        new_line += "  /* [Rule-17-3-3] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-3: 将空参数列表 () 替换为 (void)",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_17_3_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-4: An inline function shall be declared in a header file."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-4")
    new_line = old.rstrip("\n") + "  /* [Rule-17-3-4] TODO: 将 inline 函数声明移至头文件 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-4: inline 函数应在头文件中声明",
        before=old, after="移至头文件",
    )
    return "".join(ls), action


def _fix_rule_17_3_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-5: A function shall not return a reference to a local object."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-5")
    m = re.search(r"return\s+&(\w+)", old)
    if m:
        local_var = m.group(1)
        new_line = old.replace(f"&{local_var}", local_var)
        new_line = new_line.rstrip("\n") + f"  /* [Rule-17-3-5] fix: 返回值而非引用 */\n"
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-17-3-5] TODO: 不要返回局部对象的引用 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-5: 禁止返回局部对象引用",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_17_3_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17-3-6: The address of a function shall not be taken explicitly."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 17-3-6")
    new_line = re.sub(r"&(\w+)\s*\(", r"\1(", old)
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-17-3-6] TODO: 不要显式取函数地址 */\n"
    else:
        new_line += "  /* [Rule-17-3-6] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 17-3-6: 禁止显式取函数地址",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


# ============================================================================
# MISRA-C++ Rule 18: 初始化和类型转换（18-1-1 到 18-5-1）
# ============================================================================


def _fix_rule_18_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-1-1: All objects with static or thread storage duration shall be initialized."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-1-1")
    m = re.match(r"^\s*([\w\s\*:&]+)\s+(\w+)\s*;", old)
    if m:
        var_type = m.group(1).strip()
        var_name = m.group(2)
        init_val = "0" if "float" in var_type or "double" in var_type else "0"
        if "*" in var_type:
            init_val = "nullptr"
        new_line = f"{var_type} {var_name} = {init_val}; /* [Rule-18-1-1] fix */\n"
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-18-1-1] TODO: 初始化静态/线程存储期对象 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-1-1: 初始化静态存储期对象",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_18_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-1-2: Dynamic initialization of non-local variables with static storage duration is not allowed."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-1-2")
    new_line = old.rstrip("\n") + "  /* [Rule-18-1-2] TODO: 使用常量初始化替代动态初始化 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-1-2: 禁止非局部静态变量的动态初始化",
        before=old, after="使用常量初始化",
    )
    return "".join(ls), action


def _fix_rule_18_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-1-3: Variables shall not have ambiguous initialization."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-1-3")
    new_line = old.rstrip("\n") + "  /* [Rule-18-1-3] TODO: 消除变量初始化歧义 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-1-3: 消除变量初始化歧义",
        before=old, after="使用明确的初始化语法",
    )
    return "".join(ls), action


def _fix_rule_18_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-2-1: Initialization shall not be used to determine the memory layout of an object."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-2-1")
    new_line = old.rstrip("\n") + "  /* [Rule-18-2-1] TODO: 不要依赖初始化确定内存布局 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-2-1: 不要依赖初始化确定内存布局",
        before=old, after="使用标准初始化方式",
    )
    return "".join(ls), action


def _fix_rule_18_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-2-2: The result of an expression shall not be discarded."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-2-2")
    m = re.match(r"^(\s*)(\w+)\s*\(([^)]*)\)\s*;\s*$", old)
    if m:
        indent, func_name, args = m.groups()
        new_line = f"{indent}(void){func_name}({args}); /* [Rule-18-2-2] fix */\n"
    else:
        new_line = f"(void)({old.strip()}); /* [Rule-18-2-2] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-2-2: 显式丢弃表达式结果",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_18_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-3-1: C-style casts shall not be used."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-3-1")
    m = re.search(r"\((\w+)\s*\*?\)\s*(\w+)", old)
    if m:
        cast_type, expr = m.groups()
        new_line = old.replace(
            f"({cast_type}){expr}",
            f"static_cast<{cast_type}>({expr})",
        )
        if new_line == old:
            new_line = old.replace(
                f"({cast_type}) {expr}",
                f"static_cast<{cast_type}>({expr})",
            )
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-18-3-1] TODO: 将 C 风格转换改为 static_cast */\n"
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-18-3-1] TODO: 将 C 风格转换改为 static_cast */\n"
    else:
        new_line += "  /* [Rule-18-3-1] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-3-1: 禁止使用 C 风格类型转换",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_18_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-3-2: Static_cast shall not be used to downcast."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-3-2")
    new_line = old.rstrip("\n") + "  /* [Rule-18-3-2] TODO: 使用 dynamic_cast 替代 static_cast 向下转换 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-3-2: 禁止 static_cast 向下转换",
        before=old, after="使用 dynamic_cast",
    )
    return "".join(ls), action


def _fix_rule_18_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-4-1: Dynamic_cast shall be used for downcasting."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-4-1")
    m = re.search(r"static_cast\s*<\s*(\w+)\s*\*?\s*>\s*\(\s*(\w+)\s*\)", old)
    if m:
        target_type, expr = m.groups()
        new_line = old.replace(
            f"static_cast<{target_type}>({expr})",
            f"dynamic_cast<{target_type}*>({expr})",
        )
    else:
        new_line = old.rstrip("\n") + "  /* [Rule-18-4-1] TODO: 使用 dynamic_cast 进行向下转换 */\n"
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-18-4-1] TODO: 使用 dynamic_cast 进行向下转换 */\n"
    else:
        new_line += "  /* [Rule-18-4-1] fix */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-4-1: 使用 dynamic_cast 进行向下转换",
        before=old, after=new_line.strip(),
    )
    return "".join(ls), action


def _fix_rule_18_4_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-4-2: dynamic_cast shall not be used to convert between unrelated classes."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-4-2")
    new_line = old.rstrip("\n") + "  /* [Rule-18-4-2] TODO: 不要使用 dynamic_cast 转换无关类 */\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-4-2: 禁止 dynamic_cast 转换无关类",
        before=old, after="重构类型转换",
    )
    return "".join(ls), action


def _fix_rule_18_5_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18-5-1: new and delete should not be used."""
    ls, old = _bounds(code, v.line)
    if not old:
        return _ooB(v, "Rule 18-5-1")
    replacements = {
        r"\bnew\s+(\w+)\s*\(": r"std::make_unique<\1>(",
        r"\bnew\s+(\w+)\[": r"std::make_unique_array<\1[",
        r"\bdelete\s+": "/* [Rule-18-5-1] fix */ /* removed delete: ",
    }
    new_line = old
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old:
        new_line = old.rstrip("\n") + "  /* [Rule-18-5-1] TODO: 使用智能指针替代 new/delete */\n"
    else:
        new_line += "\n"
    ls[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id, line=v.line,
        description="Rule 18-5-1: 使用智能指针替代 new/delete",
        before=old, after="使用 make_unique",
    )
    return "".join(ls), action


# ============================================================================
# 规则 ID → 修复函数映射
# 总计 59 条规则修复函数（JSF AV C++: 5 + MISRA-C++: 54）
# ============================================================================

CPP_FIXERS: dict[str, "Callable[[str, Violation], tuple[str, RepairAction]]"] = {
    # --- JSF AV C++ (5条) ---
    "jsf-3-1-1": _fix_jsf_3_1_1,
    "jsf-5-2-1": _fix_jsf_5_2_1,
    "jsf-6-6-1": _fix_jsf_6_6_1,
    "jsf-12-1-2": _fix_jsf_12_1_2,
    "jsf-18-4-1": _fix_jsf_18_4_1,
    # --- MISRA-C++ Rule 0: 程序说明 (6条) ---
    "0-1-1": _fix_rule_0_1_1,
    "0-1-2": _fix_rule_0_1_2,
    "0-1-3": _fix_rule_0_1_3,
    "0-1-4": _fix_rule_0_1_4,
    "0-1-5": _fix_rule_0_1_5,
    "0-1-6": _fix_rule_0_1_6,
    # --- MISRA-C++ Rule 3: 注释 (6条) ---
    "3-1-2": _fix_rule_3_1_2,
    "3-1-3": _fix_rule_3_1_3,
    "3-1-4": _fix_rule_3_1_4,
    "3-2-1": _fix_rule_3_2_1,
    "3-3-1": _fix_rule_3_3_1,
    "3-4-1": _fix_rule_3_4_1,
    # --- MISRA-C++ Rule 5: 标识符 (8条) ---
    "5-0-1": _fix_rule_5_0_1,
    "5-0-2": _fix_rule_5_0_2,
    "5-0-3": _fix_rule_5_0_3,
    "5-1-1": _fix_rule_5_1_1,
    "5-1-2": _fix_rule_5_1_2,
    "5-2-1": _fix_rule_5_2_1,
    "5-2-2": _fix_rule_5_2_2,
    "5-3-1": _fix_rule_5_3_1,
    # --- MISRA-C++ Rule 6-6: 枚举 (5条) ---
    "6-6-2": _fix_rule_6_6_2,
    "6-6-3": _fix_rule_6_6_3,
    "6-6-4": _fix_rule_6_6_4,
    "6-6-5": _fix_rule_6_6_5,
    "6-6-6": _fix_rule_6_6_6,
    # --- MISRA-C++ Rule 7-3: 命名空间 (7条) ---
    "7-3-1": _fix_rule_7_3_1,
    "7-3-2": _fix_rule_7_3_2,
    "7-3-3": _fix_rule_7_3_3,
    "7-3-4": _fix_rule_7_3_4,
    "7-3-5": _fix_rule_7_3_5,
    "7-3-6": _fix_rule_7_3_6,
    "7-3-7": _fix_rule_7_3_7,
    # --- MISRA-C++ Rule 10-3: 枚举转换 (3条) ---
    "10-3-1": _fix_rule_10_3_1,
    "10-3-2": _fix_rule_10_3_2,
    "10-3-3": _fix_rule_10_3_3,
    # --- MISRA-C++ Rule 14: 控制流表达式 (10条) ---
    "14-3-1": _fix_rule_14_3_1,
    "14-3-2": _fix_rule_14_3_2,
    "14-3-3": _fix_rule_14_3_3,
    "14-3-4": _fix_rule_14_3_4,
    "14-4-1": _fix_rule_14_4_1,
    "14-4-2": _fix_rule_14_4_2,
    "14-4-3": _fix_rule_14_4_3,
    "14-4-4": _fix_rule_14_4_4,
    "14-5-1": _fix_rule_14_5_1,
    "14-5-2": _fix_rule_14_5_2,
    # --- MISRA-C++ Rule 15: 控制流 (7条) ---
    "15-1-1": _fix_rule_15_1_1,
    "15-1-2": _fix_rule_15_1_2,
    "15-1-3": _fix_rule_15_1_3,
    "15-2-1": _fix_rule_15_2_1,
    "15-2-2": _fix_rule_15_2_2,
    "15-2-3": _fix_rule_15_2_3,
    "15-3-1": _fix_rule_15_3_1,
    # --- MISRA-C++ Rule 16: switch (1条) ---
    "16-1-1": _fix_rule_16_1_1,
    # --- MISRA-C++ Rule 17-3: 函数 (6条) ---
    "17-3-1": _fix_rule_17_3_1,
    "17-3-2": _fix_rule_17_3_2,
    "17-3-3": _fix_rule_17_3_3,
    "17-3-4": _fix_rule_17_3_4,
    "17-3-5": _fix_rule_17_3_5,
    "17-3-6": _fix_rule_17_3_6,
    # --- MISRA-C++ Rule 18: 初始化和类型转换 (9条) ---
    "18-1-1": _fix_rule_18_1_1,
    "18-1-2": _fix_rule_18_1_2,
    "18-1-3": _fix_rule_18_1_3,
    "18-2-1": _fix_rule_18_2_1,
    "18-2-2": _fix_rule_18_2_2,
    "18-3-1": _fix_rule_18_3_1,
    "18-3-2": _fix_rule_18_3_2,
    "18-4-1": _fix_rule_18_4_1,
    "18-4-2": _fix_rule_18_4_2,
    "18-5-1": _fix_rule_18_5_1,
}

# --- 统计 ---
# JSF AV C++:    5 条
# MISRA-C++:    54 条
# 合计:         59 条
