"""Python安全修复规则（基于《军工软件Python语言编程指南》）。"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skyforge_engine.tools.cppcheck_scanner import Violation

from skyforge_engine.agents.types import RepairAction


# ---------------------------------------------------------------------------
# P 系列 — 安全性
# ---------------------------------------------------------------------------

def _fix_p01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-01: 禁止使用 eval/exec"""
    new_code = re.sub(r'\beval\s*\([^)]*\)', 'None  # 安全替代', code)
    new_code = re.sub(r'\bexec\s*\([^)]*\)', 'pass  # 安全替代', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='移除 eval/exec 调用'
    )


def _fix_p02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-02: 禁止使用 global/nonlocal"""
    new_code = re.sub(r'\bglobal\s+\w+', '', code)
    new_code = re.sub(r'\bnonlocal\s+\w+', '', code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='移除 global/nonlocal 声明'
    )


def _fix_p03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-03: 禁止使用 pickle 序列化"""
    new_code = re.sub(r'\bpickle\.loads?\s*\(', 'json.loads(  # 安全替代: pickle -> json', code)
    new_code = re.sub(r'\bpickle\.dump\s*\(', 'json.dump(  # 安全替代: pickle -> json', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='将 pickle 替换为 json 安全序列化'
    )


def _fix_p04(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-04: subprocess 禁止 shell=True"""
    new_code = re.sub(
        r'subprocess\.(run|call|check_call|check_output)\s*\(([^)]*)\bshell\s*=\s*True\b([^)]*)\)',
        r'subprocess.\1(\2shell=False\3',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='subprocess 中 shell=True -> shell=False'
    )


def _fix_p05(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-05: 禁止使用 os.system"""
    new_code = re.sub(
        r'\bos\.system\s*\(([^)]+)\)',
        r'subprocess.run(\1, shell=False, check=True)  # 安全替代',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='os.system -> subprocess.run(shell=False)'
    )


def _fix_p06(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-06: 禁止硬编码密码"""
    new_code = re.sub(
        r"(\w+)\s*=\s*['\"][^'\"]*(?:password|pwd|secret|token)['\"][^'\"]*['\"]",
        r"\1 = os.environ.get('\1', '')  # 安全替代: 从环境变量读取",
        code, flags=re.IGNORECASE
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='硬编码密码 -> 环境变量读取'
    )


def _fix_p07(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-07: 禁止使用不安全随机数"""
    new_code = re.sub(r'\brandom\.random\b', 'secrets.token_hex(16)  # 安全随机数', code)
    new_code = re.sub(r'\brandom\.randint\b', 'secrets.randbelow(  # 安全随机数', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='random -> secrets 安全随机数'
    )


def _fix_p08(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-08: 禁止使用 MD5/SHA1"""
    new_code = re.sub(r'\bhashlib\.md5\b', 'hashlib.sha256', code)
    new_code = re.sub(r'\bhashlib\.sha1\b', 'hashlib.sha256', new_code)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='md5/sha1 -> sha256 安全哈希'
    )


def _fix_p09(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-09: assert 禁止用于验证逻辑"""
    new_code = re.sub(
        r'\bassert\s+(.+)',
        r'if not (\1): raise ValueError("断言失败")  # 安全替代',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='assert -> if not raise ValueError'
    )


def _fix_p10(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-10: input() 无输入验证"""
    new_code = re.sub(
        r'\binput\s*\(([^)]*)\)',
        r'input(\1).strip()  # 建议: 添加输入验证',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='input() 添加 strip 建议添加输入验证'
    )


def _fix_p11(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-11: yaml.load 不安全"""
    new_code = re.sub(
        r'\byaml\.load\s*\(([^,)]+)',
        r'yaml.safe_load(\1',
        code
    )
    new_code = re.sub(
        r'\byaml\.load\s*\(([^)]+)\)',
        r'yaml.safe_load(\1)',
        new_code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='yaml.load -> yaml.safe_load'
    )


def _fix_p12(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-12: requests 无超时设置"""
    new_code = re.sub(
        r'\brequests\.(get|post|put|delete|patch|head|options)\s*\(([^)]*)\)',
        r'requests.\1(\2, timeout=30)  # 建议: 设置合理超时',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='requests 调用添加 timeout 参数'
    )


def _fix_p13(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-13: 禁用 SSL 验证"""
    new_code = re.sub(
        r'verify\s*=\s*False',
        'verify=True  # 安全要求: 启用 SSL 验证',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='verify=False -> verify=True'
    )


def _fix_p14(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """P-14: 临时文件未清理"""
    # 匹配 tempfile.gettempdir() 或 tempfile.mktemp 等不安全用法
    new_code = re.sub(
        r'\btempfile\.mktemp\b',
        'tempfile.NamedTemporaryFile(delete=False)  # 请使用 with 语句确保清理',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='mktemp -> NamedTemporaryFile(delete=False) 建议 with 清理'
    )


# ---------------------------------------------------------------------------
# T 系列 — 类型标注
# ---------------------------------------------------------------------------

def _fix_t01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-01: 函数必须有类型标注"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = re.match(r'(\s*def\s+\w+\s*\()([^)]*)\)(\s*:)', line)
        if match and '->' not in line:
            lines[i] = line.replace('):', ') -> None:')
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加函数返回类型标注'
    )


def _fix_t02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-02: 函数参数必须有类型标注"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配 def func(param) 或 def func(self, param)
        m = re.match(r'(\s*def\s+\w+\s*\()([^)]+)\)(\s*:)', line)
        if m:
            params = m.group(2)
            # 跳过已有类型标注的参数（含 : 或 =）
            if ':' not in params and '=' not in params and 'self' not in params:
                new_params = ', '.join(p.strip() + ': Any' for p in params.split(',') if p.strip())
                lines[i] = f'{m.group(1)}{new_params}{m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='为无标注参数添加类型标注'
    )


def _fix_t03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-03: 必须使用 typing 模块"""
    # 检查是否已有 typing 导入
    if 'from typing import' not in code and 'import typing' not in code:
        # 在文件头部添加 typing 导入
        new_code = 'from typing import Any\n\n' + code
    else:
        new_code = code
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加 typing 模块导入'
    )


def _fix_t04(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-04: 类属性必须有类型标注"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配类属性赋值: self.xxx = ... 或 xxx = ... (在类体内)
        m = re.match(r'(\s+)(\w+)\s*=\s*(.*)', line)
        if m and ':' not in line and 'def ' not in line:
            indent, name, value = m.group(1), m.group(2), m.group(3)
            lines[i] = f'{indent}{name}: Any = {value}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='为类属性添加类型标注'
    )


def _fix_t05(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-05: 变量声明建议使用类型注解"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配简单变量赋值（非类属性、非函数内）
        m = re.match(r'^(\w+)\s*=\s*(.*)', line)
        if m and ':' not in line and 'def ' not in line and 'class ' not in line:
            name, value = m.group(1), m.group(2)
            # 跳过常量（UPPER_CASE）
            if not name.isupper():
                lines[i] = f'{name}: Any = {value}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='为变量添加类型注解'
    )


def _fix_t06(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """T-06: 返回值类型标注建议"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'(\s*def\s+\w+\s*\([^)]*\))\s*:', line)
        if m and '->' not in line:
            lines[i] = line.replace('):', ') -> None:')
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加返回值类型标注'
    )


# ---------------------------------------------------------------------------
# N 系列 — 命名规范
# ---------------------------------------------------------------------------

def _fix_n01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-01: 模块命名规范"""
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='检查模块命名规范'
    )


def _fix_n02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-02: 类名必须使用 CamelCase"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'(\s*class\s+)(\w+)(.*)', line)
        if m:
            cls_name = m.group(2)
            # 转换 snake_case 到 CamelCase
            if '_' in cls_name:
                camel = ''.join(w.capitalize() for w in cls_name.split('_'))
                lines[i] = f'{m.group(1)}{camel}{m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='类名转换为 CamelCase'
    )


def _fix_n03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-03: 函数名必须使用 snake_case"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'(\s*def\s+)(\w+)(.*)', line)
        if m:
            func_name = m.group(2)
            if func_name.startswith('_'):
                continue  # 跳过私有方法
            # 转换 camelCase 到 snake_case
            if re.search(r'[A-Z]', func_name):
                snake = re.sub(r'([A-Z])', r'_\1', func_name).lower().lstrip('_')
                lines[i] = f'{m.group(1)}{snake}{m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='函数名转换为 snake_case'
    )


def _fix_n04(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-04: 变量名必须使用 snake_case"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配变量赋值
        m = re.match(r'^(\s*)(\w+)\s*=', line)
        if m:
            var_name = m.group(2)
            if var_name.isupper():  # 跳过常量
                continue
            if re.search(r'[A-Z]', var_name) and not var_name[0].isupper():
                snake = re.sub(r'([A-Z])', r'_\1', var_name).lower()
                lines[i] = line.replace(var_name, snake, 1)
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='变量名转换为 snake_case'
    )


def _fix_n05(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-05: 常量必须使用 UPPER_SNAKE_CASE"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配模块级常量（非 def/class 内）
        m = re.match(r'^([A-Z][a-z]\w*)\s*=\s*(.*)', line)
        if m:
            const_name = m.group(1)
            upper_name = const_name.upper()
            lines[i] = line.replace(const_name, upper_name, 1)
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='常量转换为 UPPER_SNAKE_CASE'
    )


def _fix_n06(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-06: 私有成员以 _ 开头"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        # 匹配属性赋值但无下划线前缀
        m = re.match(r'(\s+)(\w+)\s*=\s*(.*)', line)
        if m and not m.group(2).startswith('_') and 'def ' not in line:
            lines[i] = f'{m.group(1)}_{m.group(2)} = {m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='私有成员添加 _ 前缀'
    )


def _fix_n07(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-07: 保护成员以 _ 开头"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'(\s+def\s+)(\w+)(.*)', line)
        if m and not m.group(2).startswith('_'):
            # 简单启发：如果方法名不含下划线且不是 dunder，加 _
            name = m.group(2)
            if not name.startswith('__') and not name.endswith('__'):
                lines[i] = f'{m.group(1)}_{name}{m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='保护方法添加 _ 前缀'
    )


def _fix_n08(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """N-08: 特殊方法必须为 __xxx__ 格式"""
    lines = code.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'(\s*def\s+)(\w+)(\s*\(.*)', line)
        if m:
            name = m.group(2)
            # 常见 dunder 方法列表
            dunders = {
                'init': '__init__', 'str': '__str__', 'repr': '__repr__',
                'eq': '__eq__', 'lt': '__lt__', 'le': '__le__',
                'gt': '__gt__', 'ge': '__ge__', 'hash': '__hash__',
                'call': '__call__', 'enter': '__enter__', 'exit': '__exit__',
                'del': '__del__', 'new': '__new__',
            }
            if name in dunders:
                lines[i] = f'{m.group(1)}{dunders[name]}{m.group(3)}\n'
    return ''.join(lines), RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='特殊方法修正为 __dunder__ 格式'
    )


# ---------------------------------------------------------------------------
# M 系列 — 模块结构
# ---------------------------------------------------------------------------

def _fix_m01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-01: 模块必须定义 __all__"""
    # 在模块顶部（导入之后）添加 __all__
    if '__all__' not in code:
        lines = code.splitlines(keepends=True)
        # 找到所有导入语句后的位置
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                insert_pos = i + 1
        new_line = '\n__all__: list[str] = []\n\n'
        lines.insert(insert_pos, new_line)
        code = ''.join(lines)
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加 __all__ 模块导出列表'
    )


def _fix_m02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-02: 导入语句必须在模块顶部"""
    # 提取散落在代码中间的 import 语句并移到顶部
    lines = code.splitlines(keepends=True)
    imports = []
    body_lines = []
    for line in lines:
        if re.match(r'^\s*(import |from .+ import)', line) and not line.strip().startswith('#'):
            imports.append(line.lstrip())
        else:
            body_lines.append(line)
    new_code = ''.join(imports) + '\n' + ''.join(body_lines)
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='将散落的 import 移到模块顶部'
    )


def _fix_m03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-03: 禁止使用 import *"""
    new_code = re.sub(
        r'from\s+(\w+)\s+import\s+\*',
        r'# from \1 import *  # 禁止: 请使用显式导入',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='注释掉 import * 并建议显式导入'
    )


def _fix_m04(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-04: __init__.py 必须存在"""
    # 此规则为结构性检查，无法自动修复
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='请手动创建 __init__.py 文件'
    )


def _fix_m05(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-05: 模块行数不超过 500"""
    # 此规则为结构性检查，无法自动修复
    line_count = len(code.splitlines())
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description=f'模块行数 {line_count} 超过 500，请拆分'
    )


def _fix_m06(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-06: 类行数不超过 200"""
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='类行数超过 200，请拆分'
    )


def _fix_m07(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """M-07: 函数行数不超过 50"""
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='函数行数超过 50，请拆分'
    )


# ---------------------------------------------------------------------------
# E 系列 — 异常处理
# ---------------------------------------------------------------------------

def _fix_e01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """E-01: 禁止裸 except"""
    new_code = re.sub(
        r'\bexcept\s*:',
        'except Exception:',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='except: -> except Exception:'
    )


def _fix_e02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """E-02: 禁止 except ... pass"""
    new_code = re.sub(
        r'(\bexcept\s+\w+(?:\s+as\s+\w+)?\s*:\s*)\n(\s+)pass\b',
        r'\1\n\2raise  # 重新抛出异常',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='except pass -> raise 重新抛出'
    )


def _fix_e03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """E-03: except 必须指定具体异常类型"""
    new_code = re.sub(
        r'\bexcept\s*:',
        'except Exception:',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='指定具体异常类型'
    )


def _fix_e04(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """E-04: 使用 finally 释放资源"""
    # 此规则为建议性检查，无法自动修复
    return code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='建议在 finally 块中释放资源'
    )


def _fix_e05(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """E-05: 使用 with 语句管理资源"""
    # 替换 open() 为 with open() 的简单模式
    new_code = re.sub(
        r'(\w+)\s*=\s*open\(([^)]+)\)',
        r'with open(\2) as \1:',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='open() -> with open() 管理资源'
    )


# ---------------------------------------------------------------------------
# L 系列 — 日志
# ---------------------------------------------------------------------------

def _fix_l01(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """L-01: 禁止使用 print"""
    new_code = re.sub(
        r'\bprint\s*\(',
        'logging.info(',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='print -> logging.info'
    )


def _fix_l02(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """L-02: 使用 logging.warning"""
    new_code = re.sub(
        r'\bprint\s*\(.*[Ww]arning',
        'logging.warning(',
        code
    )
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='print warning -> logging.warning'
    )


def _fix_l03(code: str, v: 'Violation') -> tuple[str, RepairAction]:
    """L-03: 日志格式必须包含模块名和行号"""
    # 检查是否已有 logging.basicConfig 配置
    if 'logging.basicConfig' not in code:
        new_code = (
            "logging.basicConfig(\n"
            "    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',\n"
            "    level=logging.INFO\n"
            ")\n\n" + code
        )
    else:
        new_code = code
    return new_code, RepairAction(
        rule_id=v.rule_id, line=v.line,
        description='添加日志格式配置（含模块名和行号）'
    )


# ---------------------------------------------------------------------------
# Python修复规则映射
# ---------------------------------------------------------------------------
PYTHON_FIXERS: dict[str, 'callable'] = {
    # P 系列 — 安全性
    'P-01': _fix_p01,
    'P-02': _fix_p02,
    'P-03': _fix_p03,
    'P-04': _fix_p04,
    'P-05': _fix_p05,
    'P-06': _fix_p06,
    'P-07': _fix_p07,
    'P-08': _fix_p08,
    'P-09': _fix_p09,
    'P-10': _fix_p10,
    'P-11': _fix_p11,
    'P-12': _fix_p12,
    'P-13': _fix_p13,
    'P-14': _fix_p14,
    # T 系列 — 类型标注
    'T-01': _fix_t01,
    'T-02': _fix_t02,
    'T-03': _fix_t03,
    'T-04': _fix_t04,
    'T-05': _fix_t05,
    'T-06': _fix_t06,
    # N 系列 — 命名规范
    'N-01': _fix_n01,
    'N-02': _fix_n02,
    'N-03': _fix_n03,
    'N-04': _fix_n04,
    'N-05': _fix_n05,
    'N-06': _fix_n06,
    'N-07': _fix_n07,
    'N-08': _fix_n08,
    # M 系列 — 模块结构
    'M-01': _fix_m01,
    'M-02': _fix_m02,
    'M-03': _fix_m03,
    'M-04': _fix_m04,
    'M-05': _fix_m05,
    'M-06': _fix_m06,
    'M-07': _fix_m07,
    # E 系列 — 异常处理
    'E-01': _fix_e01,
    'E-02': _fix_e02,
    'E-03': _fix_e03,
    'E-04': _fix_e04,
    'E-05': _fix_e05,
    # L 系列 — 日志
    'L-01': _fix_l01,
    'L-02': _fix_l02,
    'L-03': _fix_l03,
}
