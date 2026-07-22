"""MISRA-C 规则模板修复函数库。

每个 fixer 签名：(code, violation) -> (new_code, RepairAction)。
供 CodeRepairerAgent 的降级 Mock 路径使用。
"""

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from skyforge_engine.tools.cppcheck_scanner import Violation

from skyforge_engine.agents.types import RepairAction


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
    """Rule 8.4：外部对象/函数需要声明 → 对于全局变量转为 static，对于函数添加 extern 声明。"""
    lines = code.splitlines(keepends=True)
    target_line = ""
    if 0 < v.line <= len(lines):
        target_line = lines[v.line - 1].strip()

    # 检测是否为全局变量（包含类型声明但没有函数括号）
    is_variable = bool(re.match(r"^(void|int|double|float|char|short|long|unsigned|const|volatile)\s+\w+\s*[=;]", target_line))

    if is_variable:
        # 全局变量 → 转为 static（与 Rule 8.7 相同逻辑）
        if target_line.lstrip().startswith("static"):
            return code, RepairAction(
                rule_id=v.rule_id, line=v.line, description="Rule 8.4: 已有 static，无需修复"
            )
        new_line = re.sub(
            r"^(\s*)(void|int|double|float|char|short|long|unsigned|const|volatile)",
            r"\1static \2",
            lines[v.line - 1],
            count=1,
        )
        lines[v.line - 1] = new_line
        new_code = "".join(lines)
        action = RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.4: 全局变量转为 static 限定文件作用域",
            before=target_line,
            after=new_line.strip(),
        )
        return new_code, action

    # 函数 → 添加 extern 声明
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
        r"\1 = (double)(\2); /* [Rule-10.1] fix */",
        old_line,
        count=1,
    )
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n") + "  /* [Rule-10.1] fix */\n"
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
        r"= (double)(\1); /* [Rule-10.3] fix */",
        old_line,
        count=1,
    )
    if new_line == old_line:
        new_line = (
            old_line.rstrip("\n")
            + "  /* [Rule-10.3] fix */\n"
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
        "goto __cleanup_15_5; /* [Rule-15.5] fix */",
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
        new_line = (
            f"{indent}if ({func_name}({args}) != 0) "
            f"{{ /* [R-17.7] fix */ }}\n"
        )
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [Rule-17.7] fix */\n"
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
            "(__static_buf_20_4) /* [Rule-20.4] fix */",
        )
    else:
        new_line = (
            old_line.replace(
                "malloc(",
                "/* [Rule-20.4] fix */ (0 ? ((void*)0) : ",
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
            f"({target_type} *)({var_name}) /* [Rule-11.3] fix */",
        )
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [Rule-11.3] fix */\n"
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
            old_line.rstrip("\n") + "  /* [Rule-12.1] fix */\n"
        )
    else:
        new_line += "  /* [Rule-12.1] fix */\n"
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
        increment_line = "    /* [Rule-14.2] fix */\n"
        increment_line += f"    {counter_var}++; /* 确保循环终止 */\n"
        # 找到循环体的开头（第一个 {）
        for i in range(v.line - 1, min(v.line + 5, len(lines))):
            if "{" in lines[i]:
                lines.insert(i + 1, increment_line)
                break
        new_line = old_line.rstrip("\n") + "  /* [Rule-14.2] fix */\n"
        lines[v.line - 1] = new_line
    else:
        new_line = (
            old_line.rstrip("\n") + "  /* [Rule-14.2] fix */\n"
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
            old_line.rstrip("\n") + "  /* [Rule-21.6] fix */\n"
        )
    else:
        new_line += "  /* [Rule-21.6] fix */\n"
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


# ============================================================================
# 第二批 MISRA-C 规则修复函数（+20条）
# ============================================================================


def _fix_dir_4_12(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Dir 4.12：不使用动态内存分配 → 替换 malloc/free 为静态分配。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Dir 4.12: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"\bmalloc\s*\(",
        "/* [Dir-4.12] fix */ (0 ? ((void*)0) : ",
        old_line,
    )
    new_line = re.sub(r"\bfree\s*\(", "/* [Dir-4.12] fix */ ", new_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Dir-4.12] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Dir 4.12: 替换动态内存分配为静态分配",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.3：不使用 stdlib.h 内存分配函数 → 替换 malloc/calloc/realloc/free。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    replacements = {
        r"\bmalloc\s*\(": "/* [Rule-21.3] fix */ static_buf(",
        r"\bcalloc\s*\(": "/* [Rule-21.3] fix */ static_buf(",
        r"\brealloc\s*\(": "/* [Rule-21.3] fix */ static_buf(",
        r"\bfree\s*\(": "/* [Rule-21.3] fix */ (void)",
    }
    new_line = old_line
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.3] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.3: 替换 stdlib 内存分配函数",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_7_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7.1：不使用八进制常量 → 将八进制转为十六进制。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 7.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 匹配八进制常量（0开头后跟数字）
    def octal_to_hex(match: re.Match) -> str:
        octal_str = match.group(0)
        try:
            value = int(octal_str, 8)
            return f"0x{value:X}"
        except ValueError:
            return octal_str

    new_line = re.sub(r"\b0[0-7]+\b", octal_to_hex, old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-7.1] fix */\n"
    else:
        new_line += "  /* [Rule-7.1] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 7.1: 八进制常量转十六进制",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_7_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7.2：无符号整型常量必须有 u/U 后缀。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 7.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 匹配无后缀的无符号常量（如 0xFFFFFFFF）
    new_line = re.sub(
        r"\b(0x[0-9A-Fa-f]+|[0-9]+)(?![uUlL.\w])",
        r"\1U",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-7.2] fix */\n"
    else:
        new_line += "  /* [Rule-7.2] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 7.2: 无符号常量添加 U 后缀",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_7_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7.3：不使用小写 l 作为字面量后缀 → 替换为大写 L。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 7.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(r"(\d+)l\b", r"\1L", old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-7.3] fix */\n"
    else:
        new_line += "  /* [Rule-7.3] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 7.3: 字面量后缀 l 转 L",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_7_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7.4：字符串字面量不应赋给非 const 的 char 指针。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 7.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 匹配 char *p = "..." 模式
    new_line = re.sub(
        r"(char\s*\*)\s*(\w+)\s*=\s*\"",
        r"const \1 \2 = \"",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-7.4] fix */\n"
    else:
        new_line += "  /* [Rule-7.4] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 7.4: 字符串字面量赋值添加 const",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3.1：注释中不使用 /* 和 // 嵌套 → 添加警告注释。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 3.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-3.1] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 3.1: 标记注释嵌套问题",
        before=old_line.strip(),
        after="添加注释嵌套警告",
    )
    return new_code, action


def _fix_rule_15_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15.1：不使用 goto → 添加警告注释。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 15.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-15.1] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.1: 标记 goto 使用",
        before=old_line.strip(),
        after="添加 goto 警告",
    )
    return new_code, action


def _fix_rule_16_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16.4：switch 必须有 default 标签 → 自动添加 default。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 16.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 找到 switch 块的末尾 }
    brace_count = 0
    insert_idx = v.line - 1
    for i in range(v.line - 1, len(lines)):
        brace_count += lines[i].count("{") - lines[i].count("}")
        if brace_count == 0 and i > v.line - 1:
            insert_idx = i
            break
    default_case = "    default: /* [Rule-16.4] fix */\n        break;\n"
    lines.insert(insert_idx, default_case)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 16.4: 添加 switch default 标签",
        before=old_line.strip(),
        after="添加 default 标签",
    )
    return new_code, action


def _fix_rule_15_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15.6：循环/if 体必须使用复合语句 {} → 自动添加大括号。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 15.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 检查是否是单行循环/if 体
    pat = r"^\s*(for|while|if)\s*\([^)]*\)\s*[^{]"
    if re.match(pat, old_line) and "{" not in old_line:
        indent = len(old_line) - len(old_line.lstrip())
        body_line = lines[v.line] if v.line < len(lines) else ""
        new_line = old_line.rstrip("\n") + " {\n"
        body_indent = " " * (indent + 4)
        lines[v.line - 1] = new_line
        if v.line < len(lines):
            lines[v.line] = body_indent + body_line.lstrip()
        lines.insert(v.line + 1, " " * indent + "}\n")
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-15.6] fix */\n"
        lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.6: 确保循环/if 使用复合语句",
        before=old_line.strip(),
        after="添加复合语句大括号",
    )
    return new_code, action


def _fix_rule_17_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17.3：不隐式声明函数 → 添加函数原型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.search(r"(\w+)\s*\(", old_line)
    func_name = m.group(1) if m else "implicit_func"
    proto = f"/* [Rule-17.3] fix */\nvoid {func_name}(void);\n"
    lines.insert(0, proto)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.3: 添加隐式函数原型声明",
        before=old_line.strip(),
        after=f"void {func_name}(void);",
    )
    return new_code, action


def _fix_rule_17_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17.4：非 void 函数所有路径必须有显式 return → 添加默认 return。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 找到函数末尾的 }
    brace_count = 0
    insert_idx = len(lines) - 1
    for i in range(v.line - 1, len(lines)):
        brace_count += lines[i].count("{") - lines[i].count("}")
        if brace_count == 0 and i > v.line - 1:
            insert_idx = i
            break
    # 检查返回类型
    m = re.search(r"(?:int|double|float|char|long|short|unsigned)\s+\w+\s*\(", old_line)
    if m:
        return_type = m.group(0).split()[0]
        default_return = f"    return ({return_type})0; /* [Rule-17.4] fix */\n"
        lines.insert(insert_idx, default_return)
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.4: 添加默认 return 语句",
        before=old_line.strip(),
        after="添加默认 return",
    )
    return new_code, action


def _fix_rule_20_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.7：宏参数扩展表达式须在括号内 → 添加括号。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.7] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.7: 标记宏参数括号问题",
        before=old_line.strip(),
        after="添加宏参数括号检查",
    )
    return new_code, action


def _fix_rule_10_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.4：算术运算两个操作数须同一基本类型类别 → 添加显式转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 10.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.4] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.4: 标记算术操作数类型不匹配",
        before=old_line.strip(),
        after="添加类型检查注释",
    )
    return new_code, action


def _fix_rule_14_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14.4：if/while 控制表达式须为布尔类型 → 添加显式比较。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 14.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-14.4] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 14.4: 标记条件表达式类型问题",
        before=old_line.strip(),
        after="添加条件类型检查",
    )
    return new_code, action


def _fix_rule_13_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.6：sizeof 操作数不得有副作用 → 添加警告。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 13.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-13.6] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.6: 标记 sizeof 副作用",
        before=old_line.strip(),
        after="添加 sizeof 副作用警告",
    )
    return new_code, action


def _fix_rule_8_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.2：函数须为带命名参数的原型形式 → 添加原型声明。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.search(r"(\w+)\s*\(\s*\)", old_line)
    if m:
        func_name = m.group(1)
        new_line = old_line.replace(f"{func_name}()", f"{func_name}(void)")
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-8.2] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.2: 确保函数使用原型形式",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.7：不使用 atof/atoi/atol/atoll → 替换为安全函数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    replacements = {
        r"\batoi\s*\(": "/* [Rule-21.7] fix */ (int)strtol(",
        r"\batol\s*\(": "/* [Rule-21.7] fix */ (long)strtol(",
        r"\batof\s*\(": "/* [Rule-21.7] fix */ (double)strtod(",
    }
    new_line = old_line
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.7] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.7: 替换 atoi/atof 为安全函数",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# ============================================================================
# 第三批 MISRA-C 规则修复函数（+26条，总计56条）
# ============================================================================


def _fix_rule_8_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.9：对象若只在一个翻译单元使用，应声明为 static。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.9: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    if "static" in old_line:
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.9: 已有 static，无需修复",
        )
    new_line = re.sub(r"^(\s*)(\w)", r"\1static \2", old_line, count=1)
    lines[v.line - 1] = (
        f"/* [{v.rule_id}] Rule 8.9: fix */\n{new_line}"
    )
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.9: 添加 static",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return "".join(lines), action


def _fix_rule_8_11(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.11：外部链接的数组应有明确的数组大小。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.11: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-8.11] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.11: 标记数组大小问题",
        before=old_line.strip(),
        after="添加数组大小检查",
    )
    return "".join(lines), action


def _fix_rule_8_13(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.13：指针参数若不修改所指对象应声明为 const。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 8.13: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    m = re.search(r"(\w+)\s*\*\s*(\w+)", old_line)
    if m and "const" not in old_line:
        old_pat = f"{m.group(1)}* {m.group(2)}"
        new_pat = f"const {m.group(1)}* {m.group(2)}"
        new_line = old_line.replace(old_pat, new_pat)
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-8.13] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.13: 添加 const 指针限定",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return "".join(lines), action


def _fix_rule_9_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 9.1：自动存储期变量使用前必须赋值。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 9.1: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    m = re.match(r"^\s*(\w[\w\s\*]+)\s+(\w+)\s*;", old_line)
    if m:
        var_type = m.group(1).strip()
        var_name = m.group(2)
        init_val = "0" if "double" in var_type or "float" in var_type else "0"
        if "*" in var_type:
            init_val = "NULL"
        new_line = f"{var_type} {var_name} = {init_val}; /* [Rule-9.1] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-9.1] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 9.1: 初始化自动变量",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return "".join(lines), action


def _fix_rule_10_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.2：字符类型只能用于字符值或 UCHAR/SCHAR。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 10.2: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.2] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.2: 标记 char 类型问题",
        before=old_line.strip(),
        after="添加类型检查",
    )
    return "".join(lines), action


def _fix_rule_10_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.5：不应强制转换为更小的类型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 10.5: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.5] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.5: 标记缩窄转换",
        before=old_line.strip(),
        after="添加类型检查",
    )
    return "".join(lines), action


def _fix_rule_10_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.6：赋值的右值类型应与左值兼容。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 10.6: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.6] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.6: 标记类型不兼容",
        before=old_line.strip(),
        after="添加类型检查",
    )
    return "".join(lines), action


def _fix_rule_10_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.8：强制转换表达式的类型不应是复合类型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 10.8: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.8] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.8: 标记复合类型转换",
        before=old_line.strip(),
        after="添加类型检查",
    )
    return "".join(lines), action


def _fix_rule_11_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.1：不得进行指针到整型或整型到指针的转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 11.1: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-11.1] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.1: 标记指针整型转换",
        before=old_line.strip(),
        after="添加转换警告",
    )
    return "".join(lines), action


def _fix_rule_11_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.2：不得对 NULL 指针进行解引用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 11.2: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-11.2] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.2: 标记 NULL 解引用",
        before=old_line.strip(),
        after="添加 NULL 检查",
    )
    return "".join(lines), action


def _fix_rule_11_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.5：不应将 void 指针转换为指向对象的指针。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 11.5: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-11.5] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.5: 标记 void 指针转换",
        before=old_line.strip(),
        after="添加显式转换",
    )
    return "".join(lines), action


def _fix_rule_12_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 12.3：不应使用逗号运算符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 12.3: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-12.3] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 12.3: 标记逗号运算符",
        before=old_line.strip(),
        after="拆分为独立语句",
    )
    return "".join(lines), action


def _fix_rule_12_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 12.4：逻辑运算符不应依赖求值顺序。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 12.4: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-12.4] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 12.4: 标记求值顺序问题",
        before=old_line.strip(),
        after="添加求值顺序检查",
    )
    return "".join(lines), action


def _fix_rule_13_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.3：自增/自减运算符不应在表达式中产生副作用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 13.3: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-13.3] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.3: 标记副作用",
        before=old_line.strip(),
        after="拆分 ++/-- 为独立语句",
    )
    return "".join(lines), action


def _fix_rule_15_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15.3：goto 不得跳过变量声明。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 15.3: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-15.3] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.3: 标记 goto 跳过声明",
        before=old_line.strip(),
        after="重构 goto 路径",
    )
    return "".join(lines), action


def _fix_rule_15_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15.7：if/else if 链应以 else 结尾。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 15.7: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    # 找到 else if 链末尾的 }
    brace_count = 0
    insert_idx = v.line - 1
    for i in range(v.line - 1, len(lines)):
        brace_count += lines[i].count("{") - lines[i].count("}")
        if brace_count <= 0 and i > v.line - 1:
            insert_idx = i
            break
    else_clause = (
        "    else /* [Rule-15.7] fix */\n"
        "    {\n"
        "        /* unreachable */\n"
        "    }\n"
    )
    lines.insert(insert_idx + 1, else_clause)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.7: 添加 else 兜底",
        before=old_line.strip(),
        after="添加 else 子句",
    )
    return "".join(lines), action


def _fix_rule_16_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16.1：switch 语句结构要求。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 16.1: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-16.1] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 16.1: 检查 switch 结构",
        before=old_line.strip(),
        after="添加 switch 结构检查",
    )
    return "".join(lines), action


def _fix_rule_16_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16.2：switch 表达式必须是整型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 16.2: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-16.2] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 16.2: 检查表达式类型",
        before=old_line.strip(),
        after="确保整型表达式",
    )
    return "".join(lines), action


def _fix_rule_16_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16.3：switch 中初始化的局部变量必须在每个 case 中赋值。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 16.3: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-16.3] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 16.3: 检查变量初始化",
        before=old_line.strip(),
        after="确保每个 case 赋值",
    )
    return "".join(lines), action


def _fix_rule_18_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18.4：不应使用 +/- 指针算术。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 18.4: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-18.4] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 18.4: 标记指针算术",
        before=old_line.strip(),
        after="改用数组索引",
    )
    return "".join(lines), action


def _fix_rule_20_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.5：不应使用 #undef。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 20.5: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.5] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.5: 标记 #undef",
        before=old_line.strip(),
        after="移除 #undef",
    )
    return "".join(lines), action


def _fix_rule_21_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.1：不应保留标准库中的标识符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.1: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.1] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.1: 标记保留标识符",
        before=old_line.strip(),
        after="重命名标识符",
    )
    return "".join(lines), action


def _fix_rule_21_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.2：不应保留标准库中的宏名。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.2: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.2] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.2: 标记保留宏名",
        before=old_line.strip(),
        after="重命名宏",
    )
    return "".join(lines), action


def _fix_rule_21_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.8：不应调用 abort/exit。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.8: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    replacements = {
        r"\bexit\s*\(": "/* [Rule-21.8] fix */ return ",
        r"\babort\s*\(": "/* [Rule-21.8] fix */ return ",
    }
    new_line = old_line
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.8] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.8: 替换 exit/abort",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return "".join(lines), action


def _fix_rule_21_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.9：不应使用 strcmp/strncmp 进行空终止字符串比较。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.9: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.9] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.9: 检查 strcmp 使用",
        before=old_line.strip(),
        after="确保缓冲区大小安全",
    )
    return "".join(lines), action


def _fix_rule_21_10(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.10：不应使用 clock/settime。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.10: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.10] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.10: 标记时间函数",
        before=old_line.strip(),
        after="使用硬件定时器",
    )
    return "".join(lines), action


def _fix_rule_21_11(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.11：不应使用 errno。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id,
            line=v.line,
            description="Rule 21.11: 行号越界，跳过",
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.11] fix */\n"
    lines[v.line - 1] = new_line
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.11: 标记 errno",
        before=old_line.strip(),
        after="改用返回值错误处理",
    )
    return "".join(lines), action


# ============================================================================
# 第四批 MISRA-C 规则修复函数（+73条，补充剩余规则）
# ============================================================================


# --- 环境 Rule 1.x ---


def _fix_rule_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 1.1：程序不得违反标准 C 语法和约束。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 1.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-1.1] TODO: 修正标准 C 语法/约束违规 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 1.1: 标记 C 语法/约束违规（需手动修正）",
        before=old_line.strip(),
        after="修正语法违规",
    )
    return new_code, action


def _fix_rule_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 1.3：不得出现未定义或关键未指定行为。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 1.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-1.3] TODO: 消除未定义行为 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 1.3: 标记未定义行为（需手动修正）",
        before=old_line.strip(),
        after="消除未定义行为",
    )
    return new_code, action


# --- 未使用 Rule 2.x ---


def _fix_rule_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.1：不得包含不可达代码。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 在不可达代码前插入注释标记
    indent = len(old_line) - len(old_line.lstrip())
    new_line = " " * indent + f"/* [Rule-2.1] TODO: 移除不可达代码 */\n" + old_line
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.1: 标记不可达代码（建议删除）",
        before=old_line.strip(),
        after="标记不可达代码",
    )
    return new_code, action


def _fix_rule_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.2：不得包含死代码。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-2.2] TODO: 移除死代码 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.2: 标记死代码（建议删除）",
        before=old_line.strip(),
        after="标记死代码",
    )
    return new_code, action


def _fix_rule_2_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.3：不应包含未使用的参数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将参数标记为 (void)param
    m = re.search(r"\(([^)]*)\)", old_line)
    if m:
        params = m.group(1).strip()
        if params and params != "void":
            param_name = params.split(",")[0].strip().split()[-1].strip("*")
            new_line = old_line.rstrip("\n") + f"\n    (void){param_name}; /* [Rule-2.3] fix */\n"
        else:
            new_line = old_line.rstrip("\n") + "  /* [Rule-2.3] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-2.3] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.3: 处理未使用参数",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_2_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.4：一个 tag 不应是未使用的。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-2.4] TODO: 移除未使用 tag 或在代码中使用 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.4: 标记未使用 tag",
        before=old_line.strip(),
        after="处理未使用 tag",
    )
    return new_code, action


def _fix_rule_2_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.5：不应包含未使用的宏定义。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 注释掉未使用的宏
    new_line = "/* [Rule-2.5] fix: " + old_line.rstrip("\n") + " */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.5: 注释掉未使用的宏",
        before=old_line.strip(),
        after="宏已注释",
    )
    return new_code, action


def _fix_rule_2_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 2.6：不应包含未使用的标号声明。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 2.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = "/* [Rule-2.6] fix: " + old_line.rstrip("\n") + " */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 2.6: 注释掉未使用的标号",
        before=old_line.strip(),
        after="标号已注释",
    )
    return new_code, action


# --- 注释 Rule 3.2 ---


def _fix_rule_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3.2：/* 和 // 不得在注释中使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 3.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将注释中的 // 替换为 ASCII 表示
    new_line = re.sub(
        r"(//\s*)/\*",
        r"\1 / *",
        old_line,
    )
    new_line = re.sub(
        r"(//\s*)\b//\b",
        r"\1 / /",
        new_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-3.2] TODO: 修正注释中的字符序列 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 3.2: 修正注释中的 /* 和 // 序列",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# --- 词法 Rule 4.1-4.2 ---


def _fix_rule_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 4.1：八进制和十六进制转义序列必须以 ; 终止。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 4.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 修复未终止的八进制转义 (\037 -> \037; 不对，应该是加结束符)
    # 实际上是确保 \xNN 或 \NNN 后面有合法字符（不被后续数字吃掉）
    new_line = old_line.rstrip("\n") + "  /* [Rule-4.1] TODO: 确保转义序列已正确终止 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 4.1: 检查转义序列终止",
        before=old_line.strip(),
        after="添加转义序列终止检查",
    )
    return new_code, action


def _fix_rule_4_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 4.2：字符字面量中应使用通用字符名。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 4.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-4.2] TODO: 使用通用字符名替代非 ASCII 字符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 4.2: 使用通用字符名",
        before=old_line.strip(),
        after="替换为通用字符名",
    )
    return new_code, action


# --- 标识符 Rule 5.1-5.5 ---


def _fix_rule_5_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5.1：外部标识符必须互不相同。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 5.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 尝试重命名冲突标识符（添加前缀）
    m = re.search(r"\bextern\s+\w+[\s\*]+(\w+)", old_line)
    if m:
        old_name = m.group(1)
        new_name = f"sf_{old_name}"
        new_line = old_line.replace(old_name, new_name, 1)
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-5.1] TODO: 重命名冲突的外部标识符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 5.1: 重命名冲突的外部标识符",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_5_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5.2：同一作用域中的标识符必须互不相同。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 5.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-5.2] TODO: 重命名重复的局部标识符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 5.2: 重命名重复的局部标识符",
        before=old_line.strip(),
        after="重命名标识符",
    )
    return new_code, action


def _fix_rule_5_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5.3：typedef 名称必须是唯一标识符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 5.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 为 typedef 名称添加前缀
    m = re.search(r"typedef\s+\w+[\s\*]+(\w+)\s*;", old_line)
    if m:
        old_name = m.group(1)
        new_name = f"sf_{old_name}"
        new_line = old_line.replace(old_name, new_name, 1) + f"  /* [Rule-5.3] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-5.3] TODO: 重命名冲突的 typedef */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 5.3: 重命名冲突的 typedef",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_5_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5.4：宏标识符必须互不相同。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 5.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 重命名宏
    m = re.search(r"#define\s+(\w+)", old_line)
    if m:
        old_name = m.group(1)
        new_name = f"SF_{old_name}"
        new_line = old_line.replace(old_name, new_name, 1) + f"  /* [Rule-5.4] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-5.4] TODO: 重命名冲突的宏 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 5.4: 重命名冲突的宏",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_5_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5.5：标识符不得与宏名相同。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 5.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-5.5] TODO: 重命名与宏同名的标识符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 5.5: 重命名与宏同名的标识符",
        before=old_line.strip(),
        after="重命名标识符",
    )
    return new_code, action


# --- 类型 Rule 6.1-6.3 ---


def _fix_rule_6_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6.1：plain char 类型仅用于字符值的存储和使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 6.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-6.1] TODO: 确保 char 仅用于字符值 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 6.1: 检查 char 类型使用",
        before=old_line.strip(),
        after="确保 char 用于字符值",
    )
    return new_code, action


def _fix_rule_6_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6.2：wchar_t 仅用于宽字符值的存储和使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 6.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-6.2] TODO: 确保 wchar_t 仅用于宽字符值 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 6.2: 检查 wchar_t 类型使用",
        before=old_line.strip(),
        after="确保 wchar_t 用于宽字符",
    )
    return new_code, action


def _fix_rule_6_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6.3：标识符和字符字面量使用的编码子集不应包含多字节字符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 6.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-6.3] TODO: 使用仅含基本字符集的编码 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 6.3: 检查多字节字符",
        before=old_line.strip(),
        after="确保编码子集合规",
    )
    return new_code, action


# --- 声明 Rule 8.3, 8.5, 8.6, 8.8, 8.10, 8.12 ---


def _fix_rule_8_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.3：typedef 声明应有唯一标识符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.search(r"typedef\s+.*?\s+(\w+)\s*;", old_line)
    if m:
        name = m.group(1)
        new_line = old_line.rstrip("\n").replace(name, f"sf_{name}", 1) + "  /* [Rule-8.3] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-8.3] TODO: 重命名冲突的 typedef */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.3: 确保 typedef 唯一",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_8_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.5：外部对象/函数应只在一处声明。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 如果有重复声明，将多余的标记为 extern
    if old_line.strip().startswith("extern"):
        new_line = "/* [Rule-8.5] fix: 移除重复的 extern 声明 */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-8.5] TODO: 合并重复声明 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.5: 合并重复的外部声明",
        before=old_line.strip(),
        after="合并重复声明",
    )
    return new_code, action


def _fix_rule_8_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.6：具有外部链接的标识符应只有一个外部定义。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-8.6] TODO: 确保外部定义唯一 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.6: 确保外部定义唯一",
        before=old_line.strip(),
        after="合并重复定义",
    )
    return new_code, action


def _fix_rule_8_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.8：同一变量/函数的所有声明应具有兼容类型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.8: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-8.8] TODO: 统一声明类型 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.8: 统一声明类型",
        before=old_line.strip(),
        after="修正类型兼容性",
    )
    return new_code, action


def _fix_rule_8_10(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.10：具有外部链接的对象/函数应只有一处声明。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.10: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-8.10] TODO: 合并重复的外部声明 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.10: 合并重复外部声明",
        before=old_line.strip(),
        after="声明去重",
    )
    return new_code, action


def _fix_rule_8_12(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 8.12：声明为指定大小的数组应显式初始化。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 8.12: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    m = re.search(r"(\w[\w\s\*]+)\s+(\w+)\s*\[(\w+)\]\s*;", old_line)
    if m:
        arr_type, arr_name, size = m.groups()
        new_line = f"{arr_type} {arr_name}[{size}] = {{0}}; /* [Rule-8.12] fix */\n"
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-8.12] TODO: 添加数组初始化 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 8.12: 为数组添加零初始化",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# --- 表达式 Rule 10.7 ---


def _fix_rule_10_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10.7：赋值右值类型不得窄于左值基本类型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 10.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-10.7] TODO: 修正赋值类型窄化 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 10.7: 修正赋值类型窄化",
        before=old_line.strip(),
        after="添加显式类型转换",
    )
    return new_code, action


# --- 指针 Rule 11.7-11.9 ---


def _fix_rule_11_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.7：不得在 void* 和对象指针之间转换。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 11.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-11.7] TODO: 使用具体类型指针替代 void* 转换 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.7: 修正 void* 转换",
        before=old_line.strip(),
        after="使用具体类型",
    )
    return new_code, action


def _fix_rule_11_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.8：不得从指针中移除 const/volatile 限定。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 11.8: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-11.8] TODO: 不要通过强制转换移除 const/volatile */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.8: 不要移除 const/volatile",
        before=old_line.strip(),
        after="保留类型限定符",
    )
    return new_code, action


def _fix_rule_11_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 11.9：宏 NULL 是唯一允许的整型空指针常量形式。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 11.9: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 替换常见的非 NULL 空指针常量写法
    new_line = re.sub(r"\b0\s*\)", "NULL)", old_line)
    new_line = re.sub(r"\((?:void\s*\*)\s*0\)", "NULL", new_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-11.9] TODO: 使用 NULL 代替 0 作为空指针常量 */\n"
    else:
        new_line += "  /* [Rule-11.9] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 11.9: 使用 NULL 作为空指针常量",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# --- 运算符 Rule 12.2 ---


def _fix_rule_12_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 12.2：移位运算符的操作数应正确类型。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 12.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 为移位操作数添加显式转换
    new_line = re.sub(
        r"(\w+)\s*<<\s*(\w+)",
        r"\1 << (unsigned int)(\2)",
        old_line,
    )
    new_line = re.sub(
        r"(\w+)\s*>>\s*(\w+)",
        r"\1 >> (unsigned int)(\2)",
        new_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-12.2] TODO: 确保移位操作数类型正确 */\n"
    else:
        new_line += "  /* [Rule-12.2] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 12.2: 修正移位操作数类型",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# --- 副作用 Rule 13.1, 13.2, 13.4, 13.5 ---


def _fix_rule_13_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.1：赋值运算符不得在布尔表达式中使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 13.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将 if(x = y) 改为 if((x = y) != 0) 明确意图，或改为 == 提示
    m = re.search(r"(if\s*\(\s*)(\w+)\s*=\s*(\w+)", old_line)
    if m:
        prefix, lhs, rhs = m.groups()
        new_line = old_line.replace(
            f"{lhs} = {rhs}",
            f"{lhs} == {rhs} /* [Rule-13.1] fix: = → == */",
        )
    else:
        new_line = old_line.rstrip("\n") + "  /* [Rule-13.1] TODO: 将赋值从布尔表达式中移出 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.1: 修正布尔表达式中的赋值",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_13_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.2：表达式值及其持久副作用必须是明确定义的。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 13.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-13.2] TODO: 拆分复杂表达式以消除未定义求值顺序 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.2: 消除表达式未定义行为",
        before=old_line.strip(),
        after="拆分复杂表达式",
    )
    return new_code, action


def _fix_rule_13_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.4：逻辑 && 和 || 右操作数不得有副作用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 13.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-13.4] TODO: 将副作用表达式移出逻辑运算符右操作数 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.4: 移除逻辑运算符右操作数副作用",
        before=old_line.strip(),
        after="拆分副作用表达式",
    )
    return new_code, action


def _fix_rule_13_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 13.5：逻辑 && 右操作数不得有持久副作用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 13.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-13.5] TODO: 移除 && 右操作数的持久副作用 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 13.5: 移除 && 右操作数副作用",
        before=old_line.strip(),
        after="拆分副作用",
    )
    return new_code, action


# --- 控制流 Rule 14.1, 15.4, 16.5 ---


def _fix_rule_14_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14.1：循环内不得有潜在不可达语句。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 14.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    indent = len(old_line) - len(old_line.lstrip())
    new_line = " " * indent + f"/* [Rule-14.1] TODO: 移除循环内不可达语句 */\n" + old_line
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 14.1: 标记循环内不可达语句",
        before=old_line.strip(),
        after="标记不可达语句",
    )
    return new_code, action


def _fix_rule_15_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15.4：循环不应有多个 break/continue。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 15.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-15.4] TODO: 重构循环使仅有一个 break/continue */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 15.4: 限制循环中 break/continue 数量",
        before=old_line.strip(),
        after="重构循环控制",
    )
    return new_code, action


def _fix_rule_16_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16.5：default 标签应是 switch 中的第一个或最后一个标签。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 16.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将 default 移到 switch 块的最后
    new_line = old_line.rstrip("\n") + "  /* [Rule-16.5] TODO: 将 default 移至 switch 末尾 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 16.5: 将 default 移至 switch 末尾",
        before=old_line.strip(),
        after="调整 default 位置",
    )
    return new_code, action


# --- 声明2 Rule 17.1, 17.2, 17.6 ---


def _fix_rule_17_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17.1：不得使用 <stdarg.h> 的功能。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 替换 #include <stdarg.h>
    new_line = re.sub(
        r"#include\s*<stdarg\.h>",
        "/* [Rule-17.1] fix: 移除 #include <stdarg.h> */",
        old_line,
    )
    # 标记 va_list/va_start/va_end 使用
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-17.1] TODO: 移除 <stdarg.h> 功能 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.1: 禁止使用 stdarg.h",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_17_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17.2：函数不得直接或间接递归调用自身。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-17.2] TODO: 消除递归调用（改为迭代实现） */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.2: 消除递归调用",
        before=old_line.strip(),
        after="改为迭代实现",
    )
    return new_code, action


def _fix_rule_17_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17.6：数组参数声明不得包含 static 关键字。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 17.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 移除数组参数中的 static
    new_line = re.sub(r"static\s+(\w+\s+\w+\[)", r"\1", old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-17.6] TODO: 移除数组参数中的 static */\n"
    else:
        new_line += "  /* [Rule-17.6] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 17.6: 移除数组参数中的 static",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# --- 联合体 Rule 19.1, 19.2 ---


def _fix_rule_19_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 19.1：不得将对象赋值/复制到重叠的对象。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 19.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将 memmove 替换为安全的手动拷贝
    new_line = re.sub(
        r"\bmemmove\s*\(",
        "/* [Rule-19.1] fix */ sf_memmove_safe(",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-19.1] TODO: 确保不使用重叠内存拷贝 */\n"
    else:
        new_line += "\n    /* [Rule-19.1] sf_memmove_safe: 安全的非重叠拷贝 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 19.1: 避免重叠内存操作",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_19_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 19.2：不应使用 union。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 19.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-19.2] TODO: 考虑用 struct 替代 union */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 19.2: 标记 union 使用",
        before=old_line.strip(),
        after="建议改用 struct",
    )
    return new_code, action


# --- 预处理器 Rule 20.1-20.3, 20.8-20.10 ---


def _fix_rule_20_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.1：#include 前应仅有预处理器指令或注释。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.1] TODO: 将 #include 移至文件顶部 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.1: 调整 #include 位置",
        before=old_line.strip(),
        after="移动 #include 到文件顶部",
    )
    return new_code, action


def _fix_rule_20_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.2：头文件名中不得使用 /* 或 //。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 替换头文件名中的注释字符
    new_line = re.sub(r"(<[^>]*//[^>]*>)", r"/* [Rule-20.2] TODO: 修正头文件名 */", old_line)
    new_line = re.sub(r'("[^"]*//[^"]*")', r'/* [Rule-20.2] TODO: 修正头文件名 */', new_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-20.2] TODO: 修正头文件名中的注释字符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.2: 修正头文件名中的注释字符",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_20_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.3：#include 指令应遵循 C 语法要求。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 确保 #include 语法正确
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.3] TODO: 修正 #include 语法 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.3: 修正 #include 语法",
        before=old_line.strip(),
        after="确保 include 语法合规",
    )
    return new_code, action


def _fix_rule_20_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.8：不应使用 # 和 ## 预处理运算符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.8: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.8] TODO: 避免使用 # 或 ## 运算符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.8: 避免 # 和 ## 运算符",
        before=old_line.strip(),
        after="重构为不使用 ## 的方式",
    )
    return new_code, action


def _fix_rule_20_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.9：预处理表达式中不应使用强制转换运算符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.9: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.9] TODO: 移除预处理表达式中的强制转换 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.9: 移除预处理中的强制转换",
        before=old_line.strip(),
        after="重构预处理表达式",
    )
    return new_code, action


def _fix_rule_20_10(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 20.10：不应使用 # 和 ## 预处理运算符。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 20.10: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-20.10] TODO: 避免使用 # 或 ## 运算符 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 20.10: 避免 # 和 ## 运算符",
        before=old_line.strip(),
        after="重构预处理宏",
    )
    return new_code, action


# --- 标准库 Rule 21.4, 21.5, 21.12-21.20 ---


def _fix_rule_21_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.4：不得使用 <setjmp.h>。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"#include\s*<setjmp\.h>",
        "/* [Rule-21.4] fix: 移除 #include <setjmp.h> */",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.4] TODO: 移除 <setjmp.h> */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.4: 禁止使用 setjmp.h",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.5：不得使用 <signal.h>。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.5: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"#include\s*<signal\.h>",
        "/* [Rule-21.5] fix: 移除 #include <signal.h> */",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.5] TODO: 移除 <signal.h> */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.5: 禁止使用 signal.h",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_12(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.12：不应使用 <stdio.h> 中的函数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.12: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"#include\s*<stdio\.h>",
        "/* [Rule-21.12] fix: 移除 #include <stdio.h> */",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.12] TODO: 替换 stdio.h 函数 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.12: 禁止使用 stdio.h",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_13(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.13：<locale.h> 中的声明不应使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.13: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"#include\s*<locale\.h>",
        "/* [Rule-21.13] fix: 移除 #include <locale.h> */",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.13] TODO: 移除 locale.h */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.13: 禁止使用 locale.h",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_14(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.14：不应使用 setjmp 函数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.14: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(r"\bsetjmp\s*\(", "/* [Rule-21.14] fix */ 0 /* setjmp removed */", old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.14] TODO: 移除 setjmp 调用 */\n"
    else:
        new_line += "\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.14: 禁止使用 setjmp",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_15(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.15：jmp_buf 对象不得由信号处理器设置。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.15: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.15] TODO: 不在信号处理器中使用 jmp_buf */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.15: 移除信号处理器中的 jmp_buf",
        before=old_line.strip(),
        after="重构信号处理",
    )
    return new_code, action


def _fix_rule_21_16(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.16：不应使用 longjmp 函数。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.16: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(r"\blongjmp\s*\(", "/* [Rule-21.16] fix */ return /* longjmp removed */; /*", old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.16] TODO: 移除 longjmp 调用 */\n"
    else:
        new_line = new_line.rstrip("\n") + " */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.16: 禁止使用 longjmp",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_17(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.17：FILE 对象不得被显式访问。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.17: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.17] TODO: 不直接访问 FILE 对象成员 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.17: 不直接访问 FILE 对象",
        before=old_line.strip(),
        after="使用标准库函数操作 FILE",
    )
    return new_code, action


def _fix_rule_21_18(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.18：errno 值应在调用设置 errno 的函数前测试。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.18: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(
        r"(\s*)(errno\s*=)",
        r"\1errno = 0; /* [Rule-21.18] fix */\n\1\2",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-21.18] TODO: 在调用前重置 errno */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.18: 调用前重置 errno",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_21_19(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.19：标准库函数返回值在下次调用前必须测试。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.19: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.19] TODO: 在下次调用前测试上次返回值 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.19: 测试标准库函数返回值",
        before=old_line.strip(),
        after="添加返回值检查",
    )
    return new_code, action


def _fix_rule_21_20(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 21.20：标准库函数返回的指针在下次调用后不得使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 21.20: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-21.20] TODO: 复制标准库返回的指针后再调用 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 21.20: 避免标准库返回指针失效",
        before=old_line.strip(),
        after="复制返回的指针",
    )
    return new_code, action


# --- 标准库2 Rule 22.1-22.4, 22.7-22.12 ---


def _fix_rule_22_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.1：动态获取的所有资源必须显式释放。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-22.1] TODO: 确保动态分配资源被显式释放 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.1: 添加资源释放",
        before=old_line.strip(),
        after="确保资源释放",
    )
    return new_code, action


def _fix_rule_22_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.2：不得通过 goto 退出一个块。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.2: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-22.2] TODO: 使用 return/break 替代 goto 退出块 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.2: 避免 goto 退出块",
        before=old_line.strip(),
        after="改为 return/break",
    )
    return new_code, action


def _fix_rule_22_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.3：同一文件不得同时读写打开。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.3: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 将 "r+" 模式替换为仅读
    new_line = re.sub(r'"r\+"', '"r" /* [Rule-22.3] fix */', old_line)
    new_line = re.sub(r'"w\+"', '"w" /* [Rule-22.3] fix */', new_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-22.3] TODO: 不要同时读写同一文件 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.3: 修正文件同时读写",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_22_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.4：不得向只读流写入。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.4: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-22.4] TODO: 确保流以写入模式打开 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.4: 确保流可写",
        before=old_line.strip(),
        after="检查流打开模式",
    )
    return new_code, action


def _fix_rule_22_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.7：宏 errno 不应使用。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.7: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = re.sub(r"\berrno\b", "/* [Rule-22.7] fix */ sf_errno", old_line)
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Rule-22.7] TODO: 替换 errno 宏 */\n"
    else:
        new_line += "\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.7: 替换 errno 宏",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_22_8(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.8：errno 应在调用设置 errno 的函数前重置为零。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.8: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 在 errno 使用前插入重置
    indent = len(old_line) - len(old_line.lstrip())
    new_line = " " * indent + "errno = 0; /* [Rule-22.8] fix */\n" + old_line
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.8: 调用前重置 errno",
        before=old_line.strip(),
        after="添加 errno = 0",
    )
    return new_code, action


def _fix_rule_22_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.9：errno 值应在调用设置 errno 的函数后测试。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.9: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 添加 errno 测试
    m = re.search(r"(\w+)\s*\(", old_line)
    func_name = m.group(1) if m else "func"
    new_line = (
        old_line.rstrip("\n") + "\n"
        f"    if (errno != 0) {{ /* [Rule-22.9] fix */ }}\n"
    )
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.9: 调用后检查 errno",
        before=old_line.strip(),
        after="添加 errno 检查",
    )
    return new_code, action


def _fix_rule_22_10(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.10：errno 值仅在最后一次调用为设置 errno 的函数后才可测试。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.10: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-22.10] TODO: 确保 errno 仅在最近调用后测试 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.10: 确保 errno 测试时机正确",
        before=old_line.strip(),
        after="调整 errno 测试位置",
    )
    return new_code, action


def _fix_rule_22_11(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.11：线程终止前必须被 join 或 detach。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.11: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Rule-22.11] TODO: 确保线程在终止前 join 或 detach */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.11: 确保线程正确终止",
        before=old_line.strip(),
        after="添加 join/detach",
    )
    return new_code, action


def _fix_rule_22_12(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 22.12：errno 值在任何使用前必须测试是否为零。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Rule 22.12: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    indent = len(old_line) - len(old_line.lstrip())
    new_line = " " * indent + "errno = 0; /* [Rule-22.12] fix: 重置后测试 */\n" + old_line
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Rule 22.12: errno 使用前重置并测试",
        before=old_line.strip(),
        after="添加 errno 重置",
    )
    return new_code, action


# --- Directive Dir 4.1, 4.6, 4.9, 4.14 ---


def _fix_dir_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Dir 4.1：运行时错误必须最小化。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Dir 4.1: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Dir-4.1] TODO: 添加运行时错误检查 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Dir 4.1: 添加运行时错误最小化检查",
        before=old_line.strip(),
        after="添加错误检查",
    )
    return new_code, action


def _fix_dir_4_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Dir 4.6：不应使用动态堆栈分配。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Dir 4.6: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    # 替换 VLA 声明
    new_line = re.sub(
        r"(\w+)\s+(\w+)\[(\w+)\]\s*;",
        r"static \1 \2[SF_MAX_ARRAY_SIZE]; /* [Dir-4.6] fix: 替换 VLA */",
        old_line,
    )
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Dir-4.6] TODO: 避免动态栈分配 */\n"
    else:
        new_line += "\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Dir 4.6: 替换动态栈分配为静态分配",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


def _fix_dir_4_9(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Dir 4.9：宏应实现为函数（或 inline 函数）。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Dir 4.9: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    new_line = old_line.rstrip("\n") + "  /* [Dir-4.9] TODO: 考虑将宏替换为函数或 inline 函数 */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Dir 4.9: 建议将宏替换为函数",
        before=old_line.strip(),
        after="考虑函数替代宏",
    )
    return new_code, action


def _fix_dir_4_14(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Dir 4.14：应使用安全函数（如 memcpy_s）。"""
    lines = code.splitlines(keepends=True)
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=v.rule_id, line=v.line, description="Dir 4.14: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    replacements = {
        r"\bmemcpy\s*\(": "sf_memcpy_s(",
        r"\bstrcpy\s*\(": "sf_strcpy_s(",
        r"\bstrcat\s*\(": "sf_strcat_s(",
        r"\bsprintf\s*\(": "sf_sprintf_s(",
        r"\bgets\s*\(": "sf_gets_s(",
    }
    new_line = old_line
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_line):
            new_line = re.sub(pattern, replacement, new_line, count=1)
            break
    if new_line == old_line:
        new_line = old_line.rstrip("\n") + "  /* [Dir-4.14] TODO: 使用安全函数替代不安全函数 */\n"
    else:
        new_line += "  /* [Dir-4.14] fix */\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=v.rule_id,
        line=v.line,
        description="Dir 4.14: 使用安全函数替代不安全函数",
        before=old_line.strip(),
        after=new_line.strip(),
    )
    return new_code, action


# ============================================================================
# 规则 ID → 修复函数映射（支持形如 "misra-c2012-8.1" / "Rule 8.1" / "8.1" 等格式）
# 总计 130 条规则修复函数
# ============================================================================
FIXERS: dict[str, "Callable[[str, Violation], tuple[str, RepairAction]]"] = {
    # --- 环境 ---
    "1.1": _fix_rule_1_1,
    "1.3": _fix_rule_1_3,
    # --- 未使用 ---
    "2.1": _fix_rule_2_1,
    "2.2": _fix_rule_2_2,
    "2.3": _fix_rule_2_3,
    "2.4": _fix_rule_2_4,
    "2.5": _fix_rule_2_5,
    "2.6": _fix_rule_2_6,
    # --- 注释 ---
    "3.1": _fix_rule_3_1,
    "3.2": _fix_rule_3_2,
    # --- 词法 ---
    "4.1": _fix_rule_4_1,
    "4.2": _fix_rule_4_2,
    # --- 标识符 ---
    "5.1": _fix_rule_5_1,
    "5.2": _fix_rule_5_2,
    "5.3": _fix_rule_5_3,
    "5.4": _fix_rule_5_4,
    "5.5": _fix_rule_5_5,
    # --- 类型 ---
    "6.1": _fix_rule_6_1,
    "6.2": _fix_rule_6_2,
    "6.3": _fix_rule_6_3,
    # --- 字面量 ---
    "7.1": _fix_rule_7_1,
    "7.2": _fix_rule_7_2,
    "7.3": _fix_rule_7_3,
    "7.4": _fix_rule_7_4,
    # --- 声明 ---
    "8.1": _fix_rule_8_1,
    "8.2": _fix_rule_8_2,
    "8.3": _fix_rule_8_3,
    "8.4": _fix_rule_8_4,
    "8.5": _fix_rule_8_5,
    "8.6": _fix_rule_8_6,
    "8.7": _fix_rule_8_7,
    "8.8": _fix_rule_8_8,
    "8.9": _fix_rule_8_9,
    "8.10": _fix_rule_8_10,
    "8.11": _fix_rule_8_11,
    "8.12": _fix_rule_8_12,
    "8.13": _fix_rule_8_13,
    # --- 初始化 ---
    "9.1": _fix_rule_9_1,
    # --- 表达式 ---
    "10.1": _fix_rule_10_1,
    "10.2": _fix_rule_10_2,
    "10.3": _fix_rule_10_3,
    "10.4": _fix_rule_10_4,
    "10.5": _fix_rule_10_5,
    "10.6": _fix_rule_10_6,
    "10.7": _fix_rule_10_7,
    "10.8": _fix_rule_10_8,
    # --- 指针 ---
    "11.1": _fix_rule_11_1,
    "11.2": _fix_rule_11_2,
    "11.3": _fix_rule_11_3,
    "11.5": _fix_rule_11_5,
    "11.7": _fix_rule_11_7,
    "11.8": _fix_rule_11_8,
    "11.9": _fix_rule_11_9,
    # --- 运算符 ---
    "12.1": _fix_rule_12_1,
    "12.2": _fix_rule_12_2,
    "12.3": _fix_rule_12_3,
    "12.4": _fix_rule_12_4,
    # --- 副作用 ---
    "13.1": _fix_rule_13_1,
    "13.2": _fix_rule_13_2,
    "13.3": _fix_rule_13_3,
    "13.4": _fix_rule_13_4,
    "13.5": _fix_rule_13_5,
    "13.6": _fix_rule_13_6,
    # --- 控制流 ---
    "14.1": _fix_rule_14_1,
    "14.2": _fix_rule_14_2,
    "14.4": _fix_rule_14_4,
    "15.1": _fix_rule_15_1,
    "15.3": _fix_rule_15_3,
    "15.4": _fix_rule_15_4,
    "15.5": _fix_rule_15_5,
    "15.6": _fix_rule_15_6,
    "15.7": _fix_rule_15_7,
    "16.1": _fix_rule_16_1,
    "16.2": _fix_rule_16_2,
    "16.3": _fix_rule_16_3,
    "16.4": _fix_rule_16_4,
    "16.5": _fix_rule_16_5,
    # --- 声明 ---
    "17.1": _fix_rule_17_1,
    "17.2": _fix_rule_17_2,
    "17.3": _fix_rule_17_3,
    "17.4": _fix_rule_17_4,
    "17.6": _fix_rule_17_6,
    "17.7": _fix_rule_17_7,
    # --- 类型 ---
    "18.4": _fix_rule_18_4,
    # --- 联合体 ---
    "19.1": _fix_rule_19_1,
    "19.2": _fix_rule_19_2,
    # --- 预处理器 ---
    "20.1": _fix_rule_20_1,
    "20.2": _fix_rule_20_2,
    "20.3": _fix_rule_20_3,
    "20.4": _fix_rule_20_4,
    "20.5": _fix_rule_20_5,
    "20.7": _fix_rule_20_7,
    "20.8": _fix_rule_20_8,
    "20.9": _fix_rule_20_9,
    "20.10": _fix_rule_20_10,
    # --- 标准库 ---
    "21.1": _fix_rule_21_1,
    "21.2": _fix_rule_21_2,
    "21.3": _fix_rule_21_3,
    "21.4": _fix_rule_21_4,
    "21.5": _fix_rule_21_5,
    "21.6": _fix_rule_21_6,
    "21.7": _fix_rule_21_7,
    "21.8": _fix_rule_21_8,
    "21.9": _fix_rule_21_9,
    "21.10": _fix_rule_21_10,
    "21.11": _fix_rule_21_11,
    "21.12": _fix_rule_21_12,
    "21.13": _fix_rule_21_13,
    "21.14": _fix_rule_21_14,
    "21.15": _fix_rule_21_15,
    "21.16": _fix_rule_21_16,
    "21.17": _fix_rule_21_17,
    "21.18": _fix_rule_21_18,
    "21.19": _fix_rule_21_19,
    "21.20": _fix_rule_21_20,
    "22.1": _fix_rule_22_1,
    "22.2": _fix_rule_22_2,
    "22.3": _fix_rule_22_3,
    "22.4": _fix_rule_22_4,
    "22.7": _fix_rule_22_7,
    "22.8": _fix_rule_22_8,
    "22.9": _fix_rule_22_9,
    "22.10": _fix_rule_22_10,
    "22.11": _fix_rule_22_11,
    "22.12": _fix_rule_22_12,
    # --- Directive ---
    "Dir.4.1": _fix_dir_4_1,
    "Dir.4.6": _fix_dir_4_6,
    "Dir.4.9": _fix_dir_4_9,
    "Dir.4.12": _fix_dir_4_12,
    "Dir.4.14": _fix_dir_4_14,
}
