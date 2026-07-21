"""契约校验器（语义分析版）：解析 YAML 契约，验证代码是否满足前置/后置/不变式/故障处理。

参考设计文档第 6.4 节："契约即测试，违约即崩溃"。
- AST 分析：解析 C 代码结构，验证代码模式而非简单关键词匹配
- Cppcheck 集成：利用静态分析工具验证 MISRA 规则和未定义行为
- 置信度评分：基于证据强度的多级评分体系
- 负面检查：检测前置条件的常见违反模式
"""

import re
import subprocess
import shutil
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

from skyforge_engine.tools.contract_to_assert import contract_to_assert
from skyforge_engine.utils.log_util import logger
from skyforge_engine.utils.cleanup_util import safe_tempdir


# ==================== 数据类定义 ====================

@dataclass
class CheckItem:
    """单条契约检查项结果。"""

    id: str
    desc: str
    passed: bool
    detail: str = ""
    confidence: float = 1.0  # 0.0-1.0, 置信度评分
    evidence: list[str] = field(default_factory=list)  # 支持证据列表


@dataclass
class CheckResult:
    """契约校验结果。

    Attributes:
        passed: 整体是否通过（所有检查项均通过）。
        preconditions: 前置条件检查项列表。
        postconditions: 后置条件检查项列表。
        invariants: 不变式检查项列表。
        fault_handling: 故障处理检查项列表。
        assert_code: 自动生成的 C 断言插桩代码。
        violations: 未通过项汇总（便于追溯）。
        cppcheck_violations: Cppcheck 检测到的违规列表。
    """

    passed: bool = False
    preconditions: list[CheckItem] = field(default_factory=list)
    postconditions: list[CheckItem] = field(default_factory=list)
    invariants: list[CheckItem] = field(default_factory=list)
    fault_handling: list[CheckItem] = field(default_factory=list)
    assert_code: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)
    cppcheck_violations: list[dict[str, str]] = field(default_factory=list)


# ==================== 置信度评分常量 ====================

class ConfidenceLevel:
    """置信度评分等级。"""
    NONE = 0.0          # 无证据
    WEAK = 0.2          # 弱模式匹配（仅关键词）
    MODERATE = 0.4      # 中等模式（结构匹配）
    STRONG = 0.6        # 强模式（特定代码结构）
    VERY_STRONG = 0.8   # 非常强（多重确认）
    DEFINITIVE = 1.0    # 确定性（Cppcheck 确认）


# ==================== C 代码 AST 分析器 ====================

class CCodeAnalyzer:
    """C 代码结构分析器，提取代码结构信息用于语义检查。"""

    def __init__(self, code: str):
        self.code = code
        self.lines = code.splitlines()
        self._parse_structure()

    def _parse_structure(self):
        """解析代码结构，提取函数、变量、控制流等信息。"""
        self.functions = []
        self.global_vars = []
        self.if_statements = []
        self.return_statements = []
        self.variable_declarations = []
        self.assignments = []
        self.array_accesses = []
        self.binary_operations = []

        in_comment = False
        brace_depth = 0
        current_function = None

        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()

            # 处理多行注释
            if in_comment:
                if "*/" in stripped:
                    in_comment = False
                continue
            if "/*" in stripped and "*/" not in stripped:
                in_comment = True
                continue
            if stripped.startswith("//"):
                continue

            # 提取函数定义
            func_match = re.match(
                r"^(?:static\s+)?(?:void|int|float|double|char|short|long|unsigned|bool)\s+"
                r"(\w+)\s*\([^)]*\)\s*\{?",
                stripped,
            )
            if func_match and "(" in stripped:
                self.functions.append({
                    "name": func_match.group(1),
                    "line": i,
                    "depth": brace_depth,
                })
                current_function = func_match.group(1)

            # 提取全局变量（不在函数内）
            if brace_depth == 0 and not stripped.startswith("//"):
                var_match = re.match(
                    r"^(?:static\s+)?(?:const\s+)?(?:void|int|float|double|char|short|long|unsigned|bool)\s+"
                    r"(\w+)\s*(?:=\s*[^;]+)?;",
                    stripped,
                )
                if var_match:
                    self.global_vars.append({
                        "name": var_match.group(1),
                        "line": i,
                    })

            # 提取 if 语句
            if_match = re.match(r"if\s*\((.+)\)\s*\{?", stripped)
            if if_match:
                self.if_statements.append({
                    "condition": if_match.group(1),
                    "line": i,
                    "function": current_function,
                })

            # 提取 return 语句
            return_match = re.match(r"return\s*(.+)?;", stripped)
            if return_match:
                self.return_statements.append({
                    "value": return_match.group(1) or "",
                    "line": i,
                    "function": current_function,
                })

            # 提取变量声明
            decl_match = re.match(
                r"(?:static\s+)?(?:const\s+)?(?:void|int|float|double|char|short|long|unsigned|bool)\s+"
                r"(\w+)\s*(?:=\s*([^;]+))?;",
                stripped,
            )
            if decl_match:
                self.variable_declarations.append({
                    "name": decl_match.group(1),
                    "initializer": decl_match.group(2),
                    "line": i,
                    "function": current_function,
                })

            # 提取赋值语句
            assign_match = re.match(r"(\w+)\s*=\s*(.+);", stripped)
            if assign_match and not stripped.startswith("//"):
                self.assignments.append({
                    "target": assign_match.group(1),
                    "value": assign_match.group(2),
                    "line": i,
                    "function": current_function,
                })

            # 提取数组访问
            arr_match = re.findall(r"(\w+)\s*\[(.+?)\]", stripped)
            for arr_name, index in arr_match:
                self.array_accesses.append({
                    "array": arr_name,
                    "index": index,
                    "line": i,
                    "function": current_function,
                })

            # 提取二元运算（除法、取模）
            binop_match = re.findall(r"(\w+)\s*([/%])\s*(\w+)", stripped)
            for left, op, right in binop_match:
                self.binary_operations.append({
                    "left": left,
                    "operator": op,
                    "right": right,
                    "line": i,
                    "function": current_function,
                })

            # 更新花括号深度
            brace_depth += stripped.count("{") - stripped.count("}")

    def has_null_check(self, param_name: str = None) -> list[dict]:
        """检查是否存在 NULL 检查。"""
        results = []
        patterns = [
            r"if\s*\(\s*\w+\s*==\s*NULL\s*\)",
            r"if\s*\(\s*NULL\s*==\s*\w+\s*\)",
            r"if\s*\(\s*\w+\s*!=\s*NULL\s*\)",
            r"if\s*\(\s*NULL\s*!=\s*\w+\s*\)",
            r"assert\s*\(\s*\w+\s*!=\s*NULL\s*\)",
        ]

        for stmt in self.if_statements:
            condition = stmt["condition"]
            for pattern in patterns:
                if re.search(pattern, f"if({condition})"):
                    results.append({
                        "line": stmt["line"],
                        "condition": condition,
                        "function": stmt["function"],
                    })
        return results

    def has_range_check(
        self, var_name: str, min_val: str = None, max_val: str = None
    ) -> list[dict]:
        """检查是否存在范围检查。"""
        results = []
        for stmt in self.if_statements:
            condition = stmt["condition"]
            # 检查变量名是否在条件中
            if var_name in condition:
                # 检查是否有比较操作
                if re.search(r"[><=!]+", condition):
                    results.append({
                        "line": stmt["line"],
                        "condition": condition,
                        "function": stmt["function"],
                    })
        return results

    def has_error_return(self) -> list[dict]:
        """检查是否存在错误返回路径。"""
        results = []
        error_patterns = [
            r"return\s+(?:ERROR|FAIL|FALSE|-1|NULL)\s*;",
            r"return\s+\d+\s*;.*//.*error",
            r"goto\s+\w*(?:error|fail|cleanup)\w*",
            r"return\s+0\s*;",  # 常见的错误处理返回值
            r"return\s+-\d+\s*;",  # 负数返回值通常表示错误
        ]

        for ret in self.return_statements:
            value = ret["value"]
            for pattern in error_patterns:
                if re.search(pattern, f"return {value};"):
                    results.append({
                        "line": ret["line"],
                        "value": value,
                        "function": ret["function"],
                    })
                    break
        return results

    def has_division_without_zero_check(self) -> list[dict]:
        """检查除法操作是否缺少零检查。"""
        results = []
        for op in self.binary_operations:
            if op["operator"] in ("/", "%"):
                # 检查除数是否有零检查
                divisor = op["right"]
                has_check = False

                for stmt in self.if_statements:
                    condition = stmt["condition"]
                    if divisor in condition and re.search(r"!=\s*0|==\s*0", condition):
                        has_check = True
                        break

                if not has_check:
                    results.append({
                        "line": op["line"],
                        "expression": f"{op['left']} {op['operator']} {op['right']}",
                        "function": op["function"],
                    })
        return results

    def has_uninitialized_vars(self) -> list[dict]:
        """检查未初始化的变量。"""
        results = []
        for decl in self.variable_declarations:
            if decl["initializer"] is None:
                # 检查是否在后续被赋值
                var_name = decl["name"]
                initialized = any(
                    a["target"] == var_name
                    for a in self.assignments
                    if a["line"] > decl["line"]
                )
                if not initialized:
                    results.append({
                        "name": var_name,
                        "line": decl["line"],
                        "function": decl["function"],
                    })
        return results

    def has_buffer_overflow_risk(self) -> list[dict]:
        """检查数组访问是否有越界风险。"""
        results = []
        for access in self.array_accesses:
            index = access["index"]
            # 检查索引是否有边界检查
            has_bound_check = False
            for stmt in self.if_statements:
                condition = stmt["condition"]
                if index in condition and re.search(r"[<>]=?\s*\d+", condition):
                    has_bound_check = True
                    break

            if not has_bound_check:
                results.append({
                    "array": access["array"],
                    "index": index,
                    "line": access["line"],
                    "function": access["function"],
                })
        return results


# ==================== Cppcheck 集成 ====================

class CppcheckVerifier:
    """Cppcheck 集成验证器，利用静态分析工具验证代码。"""

    def __init__(self):
        self.available = self._check_available()

    def _check_available(self) -> bool:
        """检测系统是否安装 cppcheck。"""
        return shutil.which("cppcheck") is not None

    def verify(self, code: str, contract_type: str = None) -> dict[str, Any]:
        """运行 Cppcheck 验证代码。

        Args:
            code: C 代码字符串
            contract_type: 契约类型
                (precondition/postcondition/invariant/fault_handling)

        Returns:
            验证结果字典
        """
        if not self.available:
            return {
                "available": False,
                "violations": [],
                "message": "cppcheck 未安装",
            }

        with safe_tempdir(prefix="skyforge_contract_") as tmp_dir:
            src_path = os.path.join(tmp_dir, "code.c")

            try:
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(code)

                # 运行 cppcheck
                template = "{file}|{line}|{column}|{severity}|{id}|{message}"
                cmd = [
                    "cppcheck",
                    "--dump",
                    "--addon=misra",
                    f"--template={template}",
                    "--quiet",
                    src_path,
                ]

                proc = subprocess.run(
                    cmd,
                    cwd=tmp_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )

                combined = (proc.stdout or "") + (proc.stderr or "")
                violations = self._parse_output(combined, src_path)

                # 根据契约类型筛选相关违规
                relevant_violations = self._filter_violations(violations, contract_type)

                return {
                    "available": True,
                    "violations": relevant_violations,
                    "all_violations": violations,
                    "message": f"检测到 {len(relevant_violations)} 条相关违规",
                }

            except subprocess.TimeoutExpired:
                return {
                    "available": True,
                    "violations": [],
                    "message": "cppcheck 扫描超时",
                }
            except Exception as e:
                return {
                    "available": True,
                    "violations": [],
                    "message": f"cppcheck 扫描异常: {e}",
                }

    def _parse_output(self, output: str, src_path: str) -> list[dict]:
        """解析 cppcheck 输出。"""
        violations = []
        basename = os.path.basename(src_path)

        for line in output.splitlines():
            if "|" not in line:
                continue
            parts = line.split("|", 5)
            if len(parts) < 6:
                continue
            fpath, line_no, col, sev, rid, msg = parts

            if basename not in fpath and src_path not in fpath:
                continue

            try:
                line_int = int(line_no)
            except ValueError:
                continue

            violations.append({
                "file": fpath,
                "line": line_int,
                "column": int(col) if col.isdigit() else 0,
                "severity": sev,
                "rule_id": rid,
                "message": msg,
            })

        return violations

    def _filter_violations(
        self, violations: list[dict], contract_type: str
    ) -> list[dict]:
        """根据契约类型筛选相关违规。"""
        if not contract_type:
            return violations

        # 契约类型与 MISRA 规则的映射
        type_rule_mapping = {
            "precondition": [
                "misra-c2012-17.7",  # 函数返回值未检查
                "misra-c2012-17.3",  # 隐式函数声明
                "misra-c2012-17.4",  # 非 const 表达式用作数组下标
            ],
            "postcondition": [
                "misra-c2012-17.7",  # 函数返回值未检查
                "misra-c2012-13.5",  # 副作用中的持久侧影响
            ],
            "invariant": [
                "misra-c2012-8.7",   # 非 static 全局变量
                "misra-c2012-8.13",  # 指针参数应为 const
            ],
            "fault_handling": [
                "misra-c2012-15.7",  # 所有 if-else 都应该有 else
                "misra-c2012-16.4",  # switch 语句必须有 default
            ],
        }

        relevant_rules = type_rule_mapping.get(contract_type, [])
        if not relevant_rules:
            return violations

        return [v for v in violations if v.get("rule_id") in relevant_rules]


# ==================== 语义检查引擎 ====================

class SemanticChecker:
    """语义检查引擎，执行具体的契约验证。"""

    def __init__(self, code: str, cppcheck_verifier: CppcheckVerifier = None):
        self.code = code
        self.analyzer = CCodeAnalyzer(code)
        self.cppcheck = cppcheck_verifier or CppcheckVerifier()

    def check_precondition(self, expr: str, cid: str, index: int) -> CheckItem:
        """检查前置条件。"""
        item_id = f"{cid}-PRE-{index:03d}"
        evidence = []

        # 1. 检查 NULL 检查
        if "null" in expr.lower():
            null_checks = self.analyzer.has_null_check()
            if null_checks:
                evidence.append(f"检测到 {len(null_checks)} 个 NULL 检查")
                for check in null_checks[:2]:  # 只显示前2个
                    evidence.append(f"  L{check['line']}: {check['condition']}")

        # 2. 检查范围检查
        range_match = re.search(r"(\w+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", expr)
        if range_match:
            var_name, op, value = range_match.groups()
            range_checks = self.analyzer.has_range_check(var_name, value)
            if range_checks:
                evidence.append(f"检测到 {len(range_checks)} 个范围检查")

        # 3. 负面检查：除法零检查
        div_issues = self.analyzer.has_division_without_zero_check()
        if div_issues:
            evidence.append(f"警告: {len(div_issues)} 个除法操作缺少零检查")

        # 4. 负面检查：未初始化变量
        uninit_vars = self.analyzer.has_uninitialized_vars()
        if uninit_vars:
            evidence.append(f"警告: {len(uninit_vars)} 个未初始化变量")

        # 5. 负面检查：缓冲区溢出风险
        buffer_issues = self.analyzer.has_buffer_overflow_risk()
        if buffer_issues:
            evidence.append(f"警告: {len(buffer_issues)} 个潜在缓冲区溢出风险")

        # 6. Cppcheck 验证
        cppcheck_result = self.cppcheck.verify(self.code, "precondition")
        if cppcheck_result["available"] and cppcheck_result["violations"]:
            cppcheck_violations = cppcheck_result["violations"]
            evidence.append(f"Cppcheck 检测到 {len(cppcheck_violations)} 条相关违规")

        # 计算置信度
        confidence = self._calculate_precondition_confidence(
            evidence, div_issues, uninit_vars, buffer_issues
        )

        # 判断是否通过
        passed = (
            confidence >= ConfidenceLevel.MODERATE
            and not div_issues
            and not uninit_vars
        )

        return CheckItem(
            id=item_id,
            desc=expr,
            passed=passed,
            detail=self._format_detail(evidence),
            confidence=confidence,
            evidence=evidence,
        )

    def check_postcondition(self, expr: str, cid: str, index: int) -> CheckItem:
        """检查后置条件。"""
        item_id = f"{cid}-POST-{index:03d}"
        evidence = []

        # 1. 检查是否有返回值赋值
        if "=" in expr or "return" in expr:
            # 检查函数是否有 return 语句
            if self.analyzer.return_statements:
                n = len(self.analyzer.return_statements)
                evidence.append(f"检测到 {n} 个返回语句")

        # 2. 检查输出变量是否被赋值
        output_match = re.search(r"(\w+)\s*(>=|<=|>|<)\s*(-?\d+)", expr)
        if output_match:
            var_name, op, value = output_match.groups()
            assignments = [
                a for a in self.analyzer.assignments
                if a["target"] == var_name
            ]
            if assignments:
                evidence.append(f"变量 {var_name} 被赋值 {len(assignments)} 次")

        # 3. Cppcheck 验证
        cppcheck_result = self.cppcheck.verify(self.code, "postcondition")
        if cppcheck_result["available"] and cppcheck_result["violations"]:
            cppcheck_violations = cppcheck_result["violations"]
            evidence.append(f"Cppcheck 检测到 {len(cppcheck_violations)} 条相关违规")

        # 计算置信度
        confidence = self._calculate_postcondition_confidence(evidence)

        # 判断是否通过
        passed = confidence >= ConfidenceLevel.MODERATE

        return CheckItem(
            id=item_id,
            desc=expr,
            passed=passed,
            detail=self._format_detail(evidence),
            confidence=confidence,
            evidence=evidence,
        )

    def check_invariant(self, expr: str, cid: str, index: int) -> CheckItem:
        """检查不变式。"""
        item_id = f"{cid}-INV-{index:03d}"
        evidence = []

        # 1. 检查全局变量是否被修改
        if self.analyzer.global_vars:
            for var in self.analyzer.global_vars:
                var_name = var["name"]
                # 检查是否有赋值
                assignments = [
                a for a in self.analyzer.assignments
                if a["target"] == var_name
            ]
                if assignments:
                    evidence.append(f"全局变量 {var_name} 被修改 {len(assignments)} 次")
                else:
                    evidence.append(f"全局变量 {var_name} 未被修改（符合不变式）")

        # 2. 检查 const 变量
        all_lines = self.code.splitlines()
        const_vars = [
            d for d in self.analyzer.variable_declarations
            if "const" in all_lines[d["line"] - 1]
        ]
        for var in const_vars:
            evidence.append(f"const 变量 {var['name']} 声明在 L{var['line']}")

        # 3. Cppcheck 验证
        cppcheck_result = self.cppcheck.verify(self.code, "invariant")
        if cppcheck_result["available"] and cppcheck_result["violations"]:
            cppcheck_violations = cppcheck_result["violations"]
            evidence.append(f"Cppcheck 检测到 {len(cppcheck_violations)} 条相关违规")

        # 计算置信度
        confidence = self._calculate_invariant_confidence(evidence)

        # 判断是否通过
        passed = confidence >= ConfidenceLevel.MODERATE

        return CheckItem(
            id=item_id,
            desc=expr,
            passed=passed,
            detail=self._format_detail(evidence),
            confidence=confidence,
            evidence=evidence,
        )

    def check_fault_handling(self, expr: str, cid: str, index: int) -> CheckItem:
        """检查故障处理。"""
        item_id = f"{cid}-FH-{index:03d}"
        evidence = []

        # 1. 检查错误返回路径
        error_returns = self.analyzer.has_error_return()
        if error_returns:
            evidence.append(f"检测到 {len(error_returns)} 个错误返回路径")
            for ret in error_returns[:2]:  # 只显示前2个
                evidence.append(f"  L{ret['line']}: return {ret['value']}")

        # 2. 检查 if-else 结构
        if_count = len(self.analyzer.if_statements)
        if if_count > 0:
            evidence.append(f"检测到 {if_count} 个条件分支")

        # 3. 检查 goto 语句（用于错误处理）
        goto_patterns = [r"goto\s+\w*(?:error|fail|cleanup)\w*"]
        for pattern in goto_patterns:
            if re.search(pattern, self.code):
                evidence.append("检测到 goto 错误处理模式")

        # 4. 检查 assert 断言
        if re.search(r"(?:assert|ASSERT)\s*\(", self.code):
            evidence.append("检测到 assert 断言")

        # 5. 检查 errno
        if re.search(r"errno\s*=", self.code):
            evidence.append("检测到 errno 设置")

        # 6. Cppcheck 验证
        cppcheck_result = self.cppcheck.verify(self.code, "fault_handling")
        if cppcheck_result["available"] and cppcheck_result["violations"]:
            cppcheck_violations = cppcheck_result["violations"]
            evidence.append(f"Cppcheck 检测到 {len(cppcheck_violations)} 条相关违规")

        # 计算置信度
        confidence = self._calculate_fault_handling_confidence(evidence, error_returns)

        # 判断是否通过
        passed = confidence >= ConfidenceLevel.STRONG

        return CheckItem(
            id=item_id,
            desc=expr,
            passed=passed,
            detail=self._format_detail(evidence),
            confidence=confidence,
            evidence=evidence,
        )

    def _calculate_precondition_confidence(
        self,
        evidence: list[str],
        div_issues: list,
        uninit_vars: list,
        buffer_issues: list,
    ) -> float:
        """计算前置条件的置信度。"""
        if div_issues or uninit_vars or buffer_issues:
            return ConfidenceLevel.WEAK

        if not evidence:
            return ConfidenceLevel.NONE

        # 基于证据数量和类型
        has_null_check = any("NULL 检查" in e for e in evidence)
        has_range_check = any("范围检查" in e for e in evidence)

        if has_null_check and has_range_check:
            return ConfidenceLevel.STRONG
        elif has_null_check or has_range_check:
            return ConfidenceLevel.MODERATE
        elif len(evidence) >= 2:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.WEAK

    def _calculate_postcondition_confidence(self, evidence: list[str]) -> float:
        """计算后置条件的置信度。"""
        if not evidence:
            return ConfidenceLevel.NONE

        has_return = any("返回语句" in e for e in evidence)
        has_assignment = any("被赋值" in e for e in evidence)
        has_cppcheck = any("Cppcheck" in e for e in evidence)

        if has_return and has_assignment:
            return ConfidenceLevel.STRONG
        elif has_return or has_assignment:
            return ConfidenceLevel.MODERATE
        elif has_cppcheck:
            return ConfidenceLevel.VERY_STRONG
        else:
            return ConfidenceLevel.WEAK

    def _calculate_invariant_confidence(self, evidence: list[str]) -> float:
        """计算不变式的置信度。"""
        if not evidence:
            return ConfidenceLevel.NONE

        has_unchanged = any("未被修改" in e for e in evidence)
        has_const = any("const" in e for e in evidence)
        has_cppcheck = any("Cppcheck" in e for e in evidence)

        if has_unchanged and has_const:
            return ConfidenceLevel.STRONG
        elif has_unchanged or has_const:
            return ConfidenceLevel.MODERATE
        elif has_cppcheck:
            return ConfidenceLevel.VERY_STRONG
        else:
            return ConfidenceLevel.WEAK

    def _calculate_fault_handling_confidence(
        self,
        evidence: list[str],
        error_returns: list,
    ) -> float:
        """计算故障处理的置信度。"""
        if not evidence:
            return ConfidenceLevel.NONE

        has_error_return = len(error_returns) > 0
        has_if_else = any("条件分支" in e for e in evidence)
        has_goto = any("goto" in e for e in evidence)
        has_assert = any("assert" in e for e in evidence)
        has_errno = any("errno" in e for e in evidence)
        has_cppcheck = any("Cppcheck" in e for e in evidence)

        # 多重确认
        strong_signals = sum([
            has_error_return,
            has_goto,
            has_assert,
            has_errno,
        ])

        if strong_signals >= 2:
            return ConfidenceLevel.VERY_STRONG
        elif strong_signals == 1:
            return ConfidenceLevel.STRONG
        elif has_if_else:
            return ConfidenceLevel.MODERATE
        elif has_cppcheck:
            return ConfidenceLevel.STRONG
        else:
            return ConfidenceLevel.WEAK

    def _format_detail(self, evidence: list[str]) -> str:
        """格式化证据详情。"""
        if not evidence:
            return "未检测到相关代码模式"
        return "\n".join(evidence)


# ==================== 主检查函数 ====================

def check(code: str, contract_yaml: str, cid: str = "CON-001", *, language: str = "c") -> CheckResult:
    """契约校验主入口（语义分析版）。

    1. 解析 YAML 契约
    2. 使用 AST 分析器解析代码结构
    3. 使用静态分析工具验证（C 用 Cppcheck，Python 用 Mypy+Ruff）
    4. 执行语义检查，生成置信度评分

    Args:
        code: 待校验的代码字符串。
        contract_yaml: .contract YAML 文本。
        cid: 契约 ID，用于断言追溯 Tag。
        language: 代码语言 ("c", "cpp", "python")。

    Returns:
        CheckResult：包含各检查项结果 + 断言插桩代码 + 违规汇总。
    """
    logger.info(f"ContractChecker:开始 cid={cid}")

    try:
        contract = yaml.safe_load(contract_yaml) or {}
    except yaml.YAMLError as e:
        logger.error(f"ContractChecker:YAML 解析失败: {e}")
        result = CheckResult(
            passed=False,
            violations=[{"id": "YAML", "desc": f"YAML 解析失败: {e}", "passed": False}],
        )
        return result

    # 初始化检查器
    cppcheck_verifier = CppcheckVerifier()
    checker = SemanticChecker(code, cppcheck_verifier)

    # 执行语义检查
    pre_items = _check_preconditions(code, contract, cid, checker)
    post_items = _check_postconditions(code, contract, cid, checker)
    inv_items = _check_invariants(code, contract, cid, checker)
    fh_items = _check_fault_handling(code, contract, cid, checker)

    # 生成断言插桩
    try:
        assert_code = contract_to_assert(contract_yaml, cid=cid)
    except Exception as e:
        logger.error(f"ContractChecker:断言生成失败: {e}")
        assert_code = f"/* 断言生成失败: {e} */\n"

    # 汇总结果
    all_items = pre_items + post_items + inv_items + fh_items
    passed = all(item.passed for item in all_items)
    violations = [
        {
            "id": item.id,
            "desc": item.desc,
            "detail": item.detail,
            "passed": item.passed,
            "confidence": item.confidence,
            "evidence": item.evidence,
        }
        for item in all_items
        if not item.passed
    ]

    # 收集静态分析违规（根据语言选择工具）
    cppcheck_violations = []
    if language in ("c", "cpp"):
        if cppcheck_verifier.available:
            cppcheck_result = cppcheck_verifier.verify(code)
            cppcheck_violations = cppcheck_result.get("violations", [])
    else:
        # 非 C/C++ 代码：使用 MultiLanguageScanner 做静态分析
        try:
            from skyforge_engine.tools.base_scanner import MultiLanguageScanner
            scanner = MultiLanguageScanner()
            violations = scanner.scan(code, language=language)
            if violations:
                cppcheck_violations = [
                    {"id": v.rule_id, "desc": v.message, "passed": False}
                    for v in violations
                ]
        except Exception as e:
            logger.warning(f"ContractChecker:语言 {language} 静态分析失败: {e}")

    result = CheckResult(
        passed=passed,
        preconditions=pre_items,
        postconditions=post_items,
        invariants=inv_items,
        fault_handling=fh_items,
        assert_code=assert_code,
        violations=violations,
        cppcheck_violations=cppcheck_violations,
    )

    logger.info(
        f"ContractChecker:完成 passed={passed} "
        f"pre={len(pre_items)} post={len(post_items)} "
        f"inv={len(inv_items)} fh={len(fh_items)} "
        f"violations={len(violations)} cppcheck={len(cppcheck_violations)}"
    )
    return result


def _check_preconditions(
    code: str, contract: dict[str, Any], cid: str, checker: SemanticChecker
) -> list[CheckItem]:
    """检查前置条件（语义分析版）。"""
    raw_list = _extract_section(contract, "preconditions")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        item = checker.check_precondition(desc, cid, i)
        items.append(item)
    return items


def _check_postconditions(
    code: str, contract: dict[str, Any], cid: str, checker: SemanticChecker
) -> list[CheckItem]:
    """检查后置条件（语义分析版）。"""
    raw_list = _extract_section(contract, "postconditions")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        item = checker.check_postcondition(desc, cid, i)
        items.append(item)
    return items


def _check_invariants(
    code: str, contract: dict[str, Any], cid: str, checker: SemanticChecker
) -> list[CheckItem]:
    """检查不变式（语义分析版）。"""
    raw_list = _extract_section(contract, "invariants")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        item = checker.check_invariant(desc, cid, i)
        items.append(item)
    return items


def _check_fault_handling(
    code: str, contract: dict[str, Any], cid: str, checker: SemanticChecker
) -> list[CheckItem]:
    """检查故障处理（语义分析版）。"""
    raw_list = _extract_section(contract, "fault_handling")
    items: list[CheckItem] = []
    for i, expr in enumerate(raw_list):
        desc = expr if isinstance(expr, str) else expr.get("desc", "")
        item = checker.check_fault_handling(desc, cid, i)
        items.append(item)
    return items


def _extract_section(contract: dict[str, Any], section: str) -> list[Any]:
    """从契约字典提取指定 section，兼容两种 YAML 布局。"""
    if section in contract:
        return contract.get(section, []) or []
    contracts_block = contract.get("contracts", {}) or {}
    return contracts_block.get(section, []) or []
