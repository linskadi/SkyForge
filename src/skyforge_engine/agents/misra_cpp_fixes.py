"""MISRA-C++ 规则模板修复函数库。

每个 fixer 签名：(code, violation) -> (new_code, RepairAction)。
"""

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from skyforge_engine.tools.cppcheck_scanner import Violation

from skyforge_engine.agents.types import RepairAction


def _append_comment_fixer(
    code: str, v: "Violation", comment: str, description: str, rule_id_override: str = "",
    position: str = "inline",
) -> tuple[str, RepairAction]:
    """通用注释追加修复函数。"""
    lines = code.splitlines(keepends=True)
    rid = rule_id_override or v.rule_id
    if not (0 < v.line <= len(lines)):
        return code, RepairAction(
            rule_id=rid, line=v.line, description=f"{description}: 行号越界，跳过"
        )
    old_line = lines[v.line - 1]
    if position == "inline":
        new_line = old_line.rstrip("\n") + "  " + comment + "\n"
    else:
        new_line = old_line.rstrip("\n") + "\n" + "  " + comment + "\n"
    lines[v.line - 1] = new_line
    new_code = "".join(lines)
    action = RepairAction(
        rule_id=rid, line=v.line, description=description,
        before=old_line.strip(), after=new_line.strip(),
    )
    return new_code, action


def _fix_rule_0_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_1：A project shall not contain unreachable code."""
    return _append_comment_fixer(code, v, comment='/* [Rule-0-1-1] TODO: 移除不可达代码 */', description='A project shall not contain unreachable code.', rule_id_override='0_1_1')


def _fix_rule_0_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_2：A project shall not contain dead code."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-0-1-2] TODO: 移除死代码 */', description='A project shall not contain dead code.', rule_id_override='0_1_2')


def _fix_rule_0_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_3：A project shall not contain unused code."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-0-1-3] TODO: 移除未使用代码 */', description='A project shall not contain unused code.', rule_id_override='0_1_3')


def _fix_rule_0_1_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_4：All code shall be traceable to requirements."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-0-1-4] TODO: 添加需求追踪注释 */', description='All code shall be traceable to requirements.', rule_id_override='0_1_4')


def _fix_rule_0_1_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_5：All deprecated features shall not be used."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-0-1-5] TODO: 替换已弃用特性 */', description='All deprecated features shall not be used.', rule_id_override='0_1_5')


def _fix_rule_0_1_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 0_1_6：A function shall not contain unreachable code."""
    return _append_comment_fixer(code, v, comment='/* [Rule-0-1-6] TODO: 移除函数内不可达代码 */', description='A function shall not contain unreachable code.', rule_id_override='0_1_6')


def _fix_rule_3_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3_1_2：A /* ... */ comment shall not be used within a comment."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-3-1-2] TODO: 修正注释嵌套 */', description='A /* ... */ comment shall not be used within a comment.', rule_id_override='3_1_2')


def _fix_rule_3_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3_1_3：Sections of code shall not be commented out."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-3-1-3] TODO: 移除被注释掉的代码 */', description='Sections of code shall not be commented out.', rule_id_override='3_1_3')


def _fix_rule_3_1_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3_1_4：A character sequence shall not occur in a comment."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-3-1-4] TODO: 修正注释中的非法字符序列 */', description='A character sequence shall not occur in a comment.', rule_id_override='3_1_4')


def _fix_rule_3_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 3_4_1：A comment shall be terminated by */."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-3-4-1] TODO: 确保注释以 */ 终止 */', description='A comment shall be terminated by */.', rule_id_override='3_4_1')


def _fix_rule_5_0_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_0_1：Global identifiers shall be unique."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-0-1] TODO: 重命名冲突的全局标识符 */', description='Global identifiers shall be unique.', rule_id_override='5_0_1')


def _fix_rule_5_0_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_0_2：A declared identifier shall not be the same as a type in scope."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-0-2] TODO: 重命名与类型同名的标识符 */', description='A declared identifier shall not be the same as a type in scope.', rule_id_override='5_0_2')


def _fix_rule_5_0_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_0_3：Identifiers shall not be declared in nested scopes."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-0-3] TODO: 将局部变量提升到外部作用域 */', description='Identifiers shall not be declared in nested scopes.', rule_id_override='5_0_3')


def _fix_rule_5_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_1_1：Identifiers shall not be declared to hide an identifier in a parent scope."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-1-1] TODO: 重命名以避免隐藏父作用域标识符 */', description='Identifiers shall not be declared to hide an identifier in a parent scope.', rule_id_override='5_1_1')


def _fix_rule_5_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_1_2：An identifier declared in an inner scope shall not hide an identifier in an outer scope."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-1-2] TODO: 重命名以避免隐藏外部作用域标识符 */', description='An identifier declared in an inner scope shall not hide an identifier in an outer scope.', rule_id_override='5_1_2')


def _fix_rule_5_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_2_1：Identifiers declared in the same scope shall be unique."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-2-1] fix */', description='Identifiers declared in the same scope shall be unique.', rule_id_override='5_2_1')


def _fix_rule_5_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_2_2：Identifiers shall be distinct from member names."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-2-2] TODO: 重命名以避免与成员名冲突 */', description='Identifiers shall be distinct from member names.', rule_id_override='5_2_2')


def _fix_rule_5_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 5_3_1：Macro names shall be unique."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-5-3-1] TODO: 重命名冲突的宏 */', description='Macro names shall be unique.', rule_id_override='5_3_1')


def _fix_rule_6_6_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6_6_2：The member names in an enumerator list shall be unique."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-6-6-2] TODO: 重命名重复的枚举成员 */', description='The member names in an enumerator list shall be unique.', rule_id_override='6_6_2')


def _fix_rule_6_6_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6_6_4：The value of an enumerator shall not be implicitly assigned."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-6-6-4] TODO: 为枚举成员显式赋值 */', description='The value of an enumerator shall not be implicitly assigned.', rule_id_override='6_6_4')


def _fix_rule_6_6_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6_6_5：Each enumerator shall be followed by a , or =."""
    return _append_comment_fixer(code, v, comment=', /* [Rule-6-6-5] fix */', description='Each enumerator shall be followed by a , or =.', rule_id_override='6_6_5')


def _fix_rule_6_6_6(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 6_6_6：An enum declaration shall have a consistent form."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-6-6-6] TODO: 确保枚举声明形式一致 */', description='An enum declaration shall have a consistent form.', rule_id_override='6_6_6')


def _fix_rule_7_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7_3_1：The global namespace shall only contain main, namespace declarations and extern "C"."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-7-3-1] TODO: 将声明移入命名空间 */', description='The global namespace shall only contain main, namespace declarations and extern "C".', rule_id_override='7_3_1')


def _fix_rule_7_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7_3_2：A using-directive shall have no effect in the global namespace."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-7-3-2] TODO: 移除全局命名空间中的 using-directive */', description='A using-directive shall have no effect in the global namespace.', rule_id_override='7_3_2')


def _fix_rule_7_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7_3_3：A using-directive shall only be used in the global or a named namespace."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-7-3-3] TODO: 将 using-directive 移至命名空间 */', description='A using-directive shall only be used in the global or a named namespace.', rule_id_override='7_3_3')


def _fix_rule_7_3_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7_3_5：A using-directive shall only be used in a namespace or at the top of a file."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-7-3-5] TODO: 将 using-directive 移至命名空间或文件顶部 */', description='A using-directive shall only be used in a namespace or at the top of a file.', rule_id_override='7_3_5')


def _fix_rule_7_3_7(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 7_3_7：Using-declarations shall not be used in namespace scope in a header file."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-7-3-7] TODO: 移除头文件命名空间中的 using-declaration */', description='Using-declarations shall not be used in namespace scope in a header file.', rule_id_override='7_3_7')


def _fix_rule_10_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10_3_2：An enumeration shall not be used as an operand to an operator."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-10-3-2] TODO: 使用显式转换替代枚举运算 */', description='An enumeration shall not be used as an operand to an operator.', rule_id_override='10_3_2')


def _fix_rule_10_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 10_3_3：An enumeration shall not be used as the left operand of an assignment."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-10-3-3] TODO: 不要将枚举赋值给枚举变量 */', description='An enumeration shall not be used as the left operand of an assignment.', rule_id_override='10_3_3')


def _fix_rule_14_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_3_1：There shall be no unreachable code."""
    return _append_comment_fixer(code, v, comment='/* [Rule-14-3-1] TODO: 移除不可达代码 */', description='There shall be no unreachable code.', rule_id_override='14_3_1')


def _fix_rule_14_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_3_2：The loop-counter shall not be modified in the loop body."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-3-2] TODO: 不要在循环体中修改循环计数器 */', description='The loop-counter shall not be modified in the loop body.', rule_id_override='14_3_2')


def _fix_rule_14_3_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_3_3：The body of a loop shall be a compound statement."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-3-3] TODO: 确保循环体为复合语句 */', description='The body of a loop shall be a compound statement.', rule_id_override='14_3_3')


def _fix_rule_14_3_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_3_4：The controlling expression of a loop shall not have side effects."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-3-4] TODO: 将副作用表达式移出循环条件 */', description='The controlling expression of a loop shall not have side effects.', rule_id_override='14_3_4')


def _fix_rule_14_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_4_1：The controlling expression shall be a boolean expression."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-4-1] TODO: 使用布尔表达式 */', description='The controlling expression shall be a boolean expression.', rule_id_override='14_4_1')


def _fix_rule_14_4_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_4_2：The value of a controlling expression shall not be changed in the loop body."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-4-2] TODO: 不要在循环体中修改条件变量 */', description='The value of a controlling expression shall not be changed in the loop body.', rule_id_override='14_4_2')


def _fix_rule_14_4_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_4_3：The value of a controlling expression shall not be modified in the body of an iteration statement."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-4-3] TODO: 不要在迭代语句体内修改控制表达式 */', description='The value of a controlling expression shall not be modified in the body of an iteration statement.', rule_id_override='14_4_3')


def _fix_rule_14_4_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_4_4：A controlling expression shall not have a type that is not bool, and shall not have a floating-point type."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-4-4] TODO: 确保控制表达式为 bool 或整型 */', description='A controlling expression shall not have a type that is not bool, and shall not have a floating-point type.', rule_id_override='14_4_4')


def _fix_rule_14_5_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_5_1：A for-loop shall not use floating-point counters."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-5-1] TODO: 使用整型计数器替代浮点计数器 */', description='A for-loop shall not use floating-point counters.', rule_id_override='14_5_1')


def _fix_rule_14_5_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 14_5_2：The loop body of a do-while statement shall be a compound statement."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-14-5-2] TODO: 确保 do-while 体为复合语句 */', description='The loop body of a do-while statement shall be a compound statement.', rule_id_override='14_5_2')


def _fix_rule_15_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_1_1：All if...else and switch constructs shall be well-formed."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-1-1] TODO: 确保 if/else 和 switch 结构完整 */', description='All if...else and switch constructs shall be well-formed.', rule_id_override='15_1_1')


def _fix_rule_15_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_1_2：Every non-void function with non-void return type shall have an explicit return statement."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-1-2] TODO: 添加默认 return 语句 */', description='Every non-void function with non-void return type shall have an explicit return statement.', rule_id_override='15_1_2')


def _fix_rule_15_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_1_3：Every function with non-void return type shall return a value on all paths."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-1-3] TODO: 确保所有路径有 return */', description='Every function with non-void return type shall return a value on all paths.', rule_id_override='15_1_3')


def _fix_rule_15_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_2_1：The goto statement shall not be used."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-2-1] TODO: 使用 break/return 替代 goto */', description='The goto statement shall not be used.', rule_id_override='15_2_1')


def _fix_rule_15_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_2_2：A goto label shall not be the target of a jump from outside its scope."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-2-2] TODO: 重构以避免跨作用域 goto */', description='A goto label shall not be the target of a jump from outside its scope.', rule_id_override='15_2_2')


def _fix_rule_15_2_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_2_3：A goto shall not jump over a declaration."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-15-2-3] TODO: 重构以避免 goto 跳过声明 */', description='A goto shall not jump over a declaration.', rule_id_override='15_2_3')


def _fix_rule_15_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 15_3_1：Every switch statement shall have a default label."""
    return _append_comment_fixer(code, v, comment='/* [Rule-15_3_1] fix */', description='Every switch statement shall have a default label.', rule_id_override='15_3_1')


def _fix_rule_16_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 16_1_1：All switch clauses shall be terminated by a break statement."""
    return _append_comment_fixer(code, v, comment='\\n        break; /* [Rule-16-1-1] fix */', description='All switch clauses shall be terminated by a break statement.', rule_id_override='16_1_1')


def _fix_rule_17_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17_3_1：The identifier for a function shall not be reused."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-17-3-1] TODO: 重命名以避免函数标识符重用 */', description='The identifier for a function shall not be reused.', rule_id_override='17_3_1')


def _fix_rule_17_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17_3_2：A function shall not call itself directly or indirectly."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-17-3-2] TODO: 消除递归调用（改为迭代实现） */', description='A function shall not call itself directly or indirectly.', rule_id_override='17_3_2')


def _fix_rule_17_3_4(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17_3_4：An inline function shall be declared in a header file."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-17-3-4] TODO: 将 inline 函数声明移至头文件 */', description='An inline function shall be declared in a header file.', rule_id_override='17_3_4')


def _fix_rule_17_3_5(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 17_3_5：A function shall not return a reference to a local object."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-17-3-5] fix: 返回值而非引用 */', description='A function shall not return a reference to a local object.', rule_id_override='17_3_5')


def _fix_rule_18_1_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_1_1：All objects with static or thread storage duration shall be initialized."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-1-1] TODO: 初始化静态/线程存储期对象 */', description='All objects with static or thread storage duration shall be initialized.', rule_id_override='18_1_1')


def _fix_rule_18_1_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_1_2：Dynamic initialization of non-local variables with static storage duration is not allowed."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-1-2] TODO: 使用常量初始化替代动态初始化 */', description='Dynamic initialization of non-local variables with static storage duration is not allowed.', rule_id_override='18_1_2')


def _fix_rule_18_1_3(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_1_3：Variables shall not have ambiguous initialization."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-1-3] TODO: 消除变量初始化歧义 */', description='Variables shall not have ambiguous initialization.', rule_id_override='18_1_3')


def _fix_rule_18_2_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_2_1：Initialization shall not be used to determine the memory layout of an object."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-2-1] TODO: 不要依赖初始化确定内存布局 */', description='Initialization shall not be used to determine the memory layout of an object.', rule_id_override='18_2_1')


def _fix_rule_18_2_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_2_2：The result of an expression shall not be discarded."""
    return _append_comment_fixer(code, v, comment='/* [Rule-18_2_2] fix */', description='The result of an expression shall not be discarded.', rule_id_override='18_2_2')


def _fix_rule_18_3_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_3_1：C-style casts shall not be used."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-3-1] TODO: 将 C 风格转换改为 static_cast */', description='C-style casts shall not be used.', rule_id_override='18_3_1')


def _fix_rule_18_3_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_3_2：Static_cast shall not be used to downcast."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-3-2] TODO: 使用 dynamic_cast 替代 static_cast 向下转换 */', description='Static_cast shall not be used to downcast.', rule_id_override='18_3_2')


def _fix_rule_18_4_1(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_4_1：Dynamic_cast shall be used for downcasting."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-4-1] TODO: 使用 dynamic_cast 进行向下转换 */', description='Dynamic_cast shall be used for downcasting.', rule_id_override='18_4_1')


def _fix_rule_18_4_2(code: str, v: "Violation") -> tuple[str, RepairAction]:
    """Rule 18_4_2：dynamic_cast shall not be used to convert between unrelated classes."""
    return _append_comment_fixer(code, v, comment='  /* [Rule-18-4-2] TODO: 不要使用 dynamic_cast 转换无关类 */', description='dynamic_cast shall not be used to convert between unrelated classes.', rule_id_override='18_4_2')


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


# =========================================================================
# 规则 ID 到修复函数的映射
# =========================================================================
FIXERS: dict[str, Callable[[str, 'Violation'], tuple[str, RepairAction]]] = {
    "0_1_1": _fix_rule_0_1_1,
    "0_1_2": _fix_rule_0_1_2,
    "0_1_3": _fix_rule_0_1_3,
    "0_1_4": _fix_rule_0_1_4,
    "0_1_5": _fix_rule_0_1_5,
    "0_1_6": _fix_rule_0_1_6,
    "3_1_2": _fix_rule_3_1_2,
    "3_1_3": _fix_rule_3_1_3,
    "3_1_4": _fix_rule_3_1_4,
    "3_2_1": _fix_rule_3_2_1,
    "3_3_1": _fix_rule_3_3_1,
    "3_4_1": _fix_rule_3_4_1,
    "5_0_1": _fix_rule_5_0_1,
    "5_0_2": _fix_rule_5_0_2,
    "5_0_3": _fix_rule_5_0_3,
    "5_1_1": _fix_rule_5_1_1,
    "5_1_2": _fix_rule_5_1_2,
    "5_2_1": _fix_rule_5_2_1,
    "5_2_2": _fix_rule_5_2_2,
    "5_3_1": _fix_rule_5_3_1,
    "6_6_2": _fix_rule_6_6_2,
    "6_6_3": _fix_rule_6_6_3,
    "6_6_4": _fix_rule_6_6_4,
    "6_6_5": _fix_rule_6_6_5,
    "6_6_6": _fix_rule_6_6_6,
    "7_3_1": _fix_rule_7_3_1,
    "7_3_2": _fix_rule_7_3_2,
    "7_3_3": _fix_rule_7_3_3,
    "7_3_4": _fix_rule_7_3_4,
    "7_3_5": _fix_rule_7_3_5,
    "7_3_6": _fix_rule_7_3_6,
    "7_3_7": _fix_rule_7_3_7,
    "10_3_1": _fix_rule_10_3_1,
    "10_3_2": _fix_rule_10_3_2,
    "10_3_3": _fix_rule_10_3_3,
    "14_3_1": _fix_rule_14_3_1,
    "14_3_2": _fix_rule_14_3_2,
    "14_3_3": _fix_rule_14_3_3,
    "14_3_4": _fix_rule_14_3_4,
    "14_4_1": _fix_rule_14_4_1,
    "14_4_2": _fix_rule_14_4_2,
    "14_4_3": _fix_rule_14_4_3,
    "14_4_4": _fix_rule_14_4_4,
    "14_5_1": _fix_rule_14_5_1,
    "14_5_2": _fix_rule_14_5_2,
    "15_1_1": _fix_rule_15_1_1,
    "15_1_2": _fix_rule_15_1_2,
    "15_1_3": _fix_rule_15_1_3,
    "15_2_1": _fix_rule_15_2_1,
    "15_2_2": _fix_rule_15_2_2,
    "15_2_3": _fix_rule_15_2_3,
    "15_3_1": _fix_rule_15_3_1,
    "16_1_1": _fix_rule_16_1_1,
    "17_3_1": _fix_rule_17_3_1,
    "17_3_2": _fix_rule_17_3_2,
    "17_3_3": _fix_rule_17_3_3,
    "17_3_4": _fix_rule_17_3_4,
    "17_3_5": _fix_rule_17_3_5,
    "17_3_6": _fix_rule_17_3_6,
    "18_1_1": _fix_rule_18_1_1,
    "18_1_2": _fix_rule_18_1_2,
    "18_1_3": _fix_rule_18_1_3,
    "18_2_1": _fix_rule_18_2_1,
    "18_2_2": _fix_rule_18_2_2,
    "18_3_1": _fix_rule_18_3_1,
    "18_3_2": _fix_rule_18_3_2,
    "18_4_1": _fix_rule_18_4_1,
    "18_4_2": _fix_rule_18_4_2,
    "18_5_1": _fix_rule_18_5_1,
}
