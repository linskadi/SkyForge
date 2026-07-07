"""MISRA-C 规则模板修复函数库。

每个 fixer 签名：(code, violation) -> (new_code, RepairAction)。
供 CodeRepairerAgent 的降级 Mock 路径使用。
"""

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app.core.tools.cppcheck_scanner import Violation

from app.core.agents.types import RepairAction


def _fix_rule_8_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_8_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_8_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_10_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_10_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_15_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_17_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_20_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
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


def _fix_rule_11_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.3：不同类型指针间转换 → 添加显式强制类型转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 11.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 匹配常见的隐式指针转换模式
    m = re.search(r"\((\w+)\s*\*\)\s*(\w+)", old_line)
    if m:
        target_type, var_name = m.groups()
        new_line = old_line.replace(
            f"({target_type} *) {var_name}",
            f"({target_type} *)({var_name}) /* [MISRA-Rule-11.3] 显式指针转换（自动修复）*/",
        )
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-11.3] 显式指针转换（自动修复）*/\n"
        )
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.3: 添加显式指针类型转换",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_12_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 12.1：运算符优先级 → 添加括号明确运算顺序。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 12.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 匹配常见优先级混淆模式：混合算术和位运算、逻辑运算等
    patterns = [
        (r"(\w+)\s*\+\s*(\w+)\s*<<\s*(\w+)", r"((\1 + \2) << \3)"),
        (r"(\w+)\s*\|\s*(\w+)\s*\&\s*(\w+)", r"(\1 | (\2 & \3))"),
        (r"(\w+)\s*\+\s*(\w+)\s*\*\s*(\w+)", r"(\1 + (\2 * \3))"),
    ]
    new_line = old_line
    for pattern, replacement in patterns:
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-12.1] 添加括号明确优先级（自动修复）*/\n"
        )
    else:
        new_line += "  /* [MISRA-Rule-12.1] 添加括号明确优先级（自动修复）*/\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 12.1: 添加括号明确运算符优先级",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_14_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14.2：for 循环计数器未修改 → 添加递增检查。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 14.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 提取 for 循环中的计数器变量
    m = re.search(r"for\s*\([^;]*;\s*(\w+)\s*[<>=!]+[^;]*;", old_line)
    if m:
        counter_var = m.group(1)
        # 在 for 循环体开头添加计数器递增检查
        increment_line = f"    /* [MISRA-Rule-14.2] 确保循环计数器 {counter_var} 被修改（自动修复）*/\n"
        increment_line += f"    {counter_var}++; /* 确保循环终止 */\n"
        # 找到循环体的开头（第一个 {）
        for i in range(v.line - 1, min(v.line + 5, len(lines))):
            if "{" in lines[i]:
                lines.insert(i + 1, increment_line)
                break
        new_line = old_line.rstrip("\n") + "  /* [MISRA-Rule-14.2] 循环计数器检查（自动修复）*/\n"
        lines[v.line - 1] = new_line
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-14.2] 循环计数器检查（自动修复）*/\n"
        )
        lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 14.2: 添加 for 循环计数器递增检查",
        before=old_line.strip(),
        after="添加循环计数器递增",
    )
    return new_code, action


def _fix_rule_21_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.6：标准库 I/O 函数 → 替换为嵌入式替代方案。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 替换 printf/scanf 为嵌入式日志函数
    replacements = {
        r"\bprintf\s*\(": "LOG_INFO(",
        r"\bfprintf\s*\(": "LOG_INFO(",
        r"\bscanf\s*\(": "LOG_SCAN(",
        r"\bfscanf\s*\(": "LOG_SCAN(",
    }
    new_line = old_line
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n") + "  /* [MISRA-Rule-21.6] 替换标准库 I/O（自动修复）*/\n"
        )
    else:
        new_line += "  /* [MISRA-Rule-21.6] 替换标准库 I/O（自动修复）*/\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.6: 替换 printf/scanf 为嵌入式日志函数",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# 规则 ID → 修复函数映射（支持形如 "misra-c2012-8.1" / "Rule 8.1" / "8.1" 等格式）
FIXERS: dict[str, "Callable[[str, Violation], tuple[str, RepairAction]]"] = {
    "8.1": _fix_rule_8_1,
    "8.4": _fix_rule_8_4,
    "8.7": _fix_rule_8_7,
    "10.1": _fix_rule_10_1,
    "10.3": _fix_rule_10_3,
    "11.3": _fix_rule_11_3,
    "12.1": _fix_rule_12_1,
    "14.2": _fix_rule_14_2,
    "15.5": _fix_rule_15_5,
    "17.7": _fix_rule_17_7,
    "20.4": _fix_rule_20_4,
    "21.6": _fix_rule_21_6,
}
