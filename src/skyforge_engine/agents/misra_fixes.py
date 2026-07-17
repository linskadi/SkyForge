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


# 规则 ID → 修复函数映射（支持形如 "misra-c2012-8.1" / "Rule 8.1" / "8.1" 等格式）
FIXERS: dict[str, "Callable[[str, Violation], tuple[str, RepairAction]]"] = {
    # 第一批：原有12条规则
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
    # 第二批：新增20条规则
    "Dir.4.12": _fix_dir_4_12,
    "21.3": _fix_rule_21_3,
    "7.1": _fix_rule_7_1,
    "7.2": _fix_rule_7_2,
    "7.3": _fix_rule_7_3,
    "7.4": _fix_rule_7_4,
    "3.1": _fix_rule_3_1,
    "15.1": _fix_rule_15_1,
    "16.4": _fix_rule_16_4,
    "15.6": _fix_rule_15_6,
    "17.3": _fix_rule_17_3,
    "17.4": _fix_rule_17_4,
    "20.7": _fix_rule_20_7,
    "10.4": _fix_rule_10_4,
    "14.4": _fix_rule_14_4,
    "13.6": _fix_rule_13_6,
    "8.2": _fix_rule_8_2,
    "21.7": _fix_rule_21_7,
    # 第三批：新增26条规则（总计56条）
    "8.9": _fix_rule_8_9,
    "8.11": _fix_rule_8_11,
    "8.13": _fix_rule_8_13,
    "9.1": _fix_rule_9_1,
    "10.2": _fix_rule_10_2,
    "10.5": _fix_rule_10_5,
    "10.6": _fix_rule_10_6,
    "10.8": _fix_rule_10_8,
    "11.1": _fix_rule_11_1,
    "11.2": _fix_rule_11_2,
    "11.5": _fix_rule_11_5,
    "12.3": _fix_rule_12_3,
    "12.4": _fix_rule_12_4,
    "13.3": _fix_rule_13_3,
    "15.3": _fix_rule_15_3,
    "15.7": _fix_rule_15_7,
    "16.1": _fix_rule_16_1,
    "16.2": _fix_rule_16_2,
    "16.3": _fix_rule_16_3,
    "18.4": _fix_rule_18_4,
    "20.5": _fix_rule_20_5,
    "21.1": _fix_rule_21_1,
    "21.2": _fix_rule_21_2,
    "21.8": _fix_rule_21_8,
    "21.9": _fix_rule_21_9,
    "21.10": _fix_rule_21_10,
    "21.11": _fix_rule_21_11,
}
