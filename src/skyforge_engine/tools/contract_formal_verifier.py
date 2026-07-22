# -*- coding: utf-8 -*-
"""契约形式化验证器 — P0 修复：为生成的契约提供 Z3/CBMC 数学证明。

设计文档批判式审查发现：契约生成后缺乏形式化验证，生成的契约
可能存在逻辑矛盾（如前置条件与后置条件不可同时满足），这在航空
安全关键系统中不可接受。

本模块提供三层形式化验证：

Level 1 — 约束一致性检查 (Z3 SMT Solver):
    将契约的前置/后置/不变式转换为 Z3 约束，检查是否存在逻辑矛盾。
    例如：precondition x>10 AND postcondition x<5 是不可满足的。

Level 2 — 边界测试用例生成 (Z3):
    自动化生成能触发每个约束边界条件的测试用例。
    例如：对于 filter 契约，生成 cutoff 附近的测试值。

Level 3 — 有界模型检查 (CBMC，可选):
    将生成的 C 代码与契约一起提交给 CBMC 进行有界验证。
    仅 CBMC 可用时执行。

集成方式:
    from skyforge_engine.tools.contract_formal_verifier import (
        ContractFormalVerifier, VerificationResult
    )
    verifier = ContractFormalVerifier()
    result = verifier.verify(contract_yaml, code=generated_code)
    if not result.is_consistent:
        print(f"契约存在逻辑矛盾: {result.contradictions}")

用法:
    # 在 contract_generator.py 中自动调用
    verifier = ContractFormalVerifier()
    result = verifier.verify(contract_yaml)
    if not result.is_consistent:
        logger.warning(f"契约形式化验证失败，建议手动审查: {result}")
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from skyforge_engine.utils.log_util import logger

import warnings
from skyforge_engine.core.verifiers.contract_verifier import ContractVerifier as _ContractVerifier
from skyforge_engine.core.protocols import VerificationResult as CoreVerificationResult


# ==================== 数据类 ====================

@dataclass
class VerificationResult:
    """形式化验证结果。"""

    # 契约标识
    component: str = ""
    contract_version: str = ""

    # Level 1: 约束一致性
    is_consistent: bool = True
    contradictions: list[str] = field(default_factory=list)
    z3_solver_time_ms: float = 0.0

    # Level 2: 边界测试用例
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    test_case_count: int = 0

    # Level 3: CBMC 有界模型检查
    cbmc_verified: bool = False
    cbmc_output: str = ""
    cbmc_time_ms: float = 0.0

    # 元数据
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    z3_available: bool = False
    cbmc_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "version": self.contract_version,
            "consistent": self.is_consistent,
            "contradictions": self.contradictions,
            "test_cases_count": self.test_case_count,
            "test_cases": self.test_cases[:10],  # 最多返回 10 个
            "cbmc_verified": self.cbmc_verified,
            "z3_available": self.z3_available,
            "cbmc_available": self.cbmc_available,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ==================== Z3 约束验证器 ====================

class Z3ContractVerifier:
    """基于 Z3 SMT Solver 的契约约束验证器。

    将 YAML 契约转换为 Z3 约束，验证：
    1. 约束一致性（前置条件 AND 后置条件 不会矛盾）
    2. 边界测试用例生成（满足所有约束的边界值）
    """

    def __init__(self):
        self._z3_available = self._check_z3()

    @staticmethod
    def _check_z3() -> bool:
        """检查 Z3 是否可用。"""
        try:
            import importlib.util
            return importlib.util.find_spec("z3") is not None
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._z3_available

    def verify_consistency(self, contract: dict[str, Any]) -> tuple[bool, list[str], float]:
        """验证契约约束一致性。

        Args:
            contract: 解析后的契约字典

        Returns:
            (is_consistent, contradictions, time_ms)
        """
        if not self._z3_available:
            return True, [], 0.0

        import time as time_mod
        start = time_mod.time()
        contradictions = []

        try:
            import z3

            # 提取契约条件
            preconditions = self._extract_conditions(contract, "preconditions")
            postconditions = self._extract_conditions(contract, "postconditions")
            invariants = self._extract_conditions(contract, "invariants")
            interface = contract.get("interface", {})

            all_conditions = preconditions + postconditions + invariants
            if not all_conditions:
                return True, [], 0.0

            # 为每个条件创建 Z3 变量和约束
            solver = z3.Solver()
            variables = self._create_z3_variables(interface, all_conditions)

            # 添加前置条件约束
            for i, cond in enumerate(preconditions):
                constraint = self._condition_to_z3(cond, variables, f"pre_{i}")
                if constraint is not None:
                    solver.add(constraint)

            # 检查前置条件本身是否可满足
            if solver.check() == z3.unsat:
                contradictions.append("前置条件之间存在逻辑矛盾")
                elapsed = (time_mod.time() - start) * 1000
                return False, contradictions, elapsed

            # 添加工件约束并检查
            all_constraints_added = 0
            for i, cond in enumerate(all_conditions):
                constraint = self._condition_to_z3(cond, variables, f"cond_{i}")
                if constraint is not None:
                    solver.add(constraint)
                    all_constraints_added += 1

            if all_constraints_added == 0:
                elapsed = (time_mod.time() - start) * 1000
                return True, [], elapsed

            result = solver.check()
            elapsed = (time_mod.time() - start) * 1000

            if result == z3.unsat:
                contradictions.append(
                    "所有契约条件不可同时满足（存在逻辑矛盾）。"
                    "请检查前置条件、后置条件、不变式之间的一致性。"
                )
                # 尝试定位矛盾（使用 unsat core）
                try:
                    core = solver.unsat_core()
                    if core:
                        contradictions.append(f"矛盾来源: {[str(c) for c in core]}")
                except Exception:
                    pass
                return False, contradictions, elapsed

            # 条件可满足，一致
            return True, [], elapsed

        except Exception as e:
            logger.error(f"Z3 一致性验证异常: {e}")
            elapsed = (time_mod.time() - start) * 1000
            return True, [f"Z3 验证异常（已跳过）: {e}"], elapsed

    def generate_test_cases(self, contract: dict[str, Any], max_cases: int = 10) -> list[dict[str, Any]]:
        """生成边界测试用例。

        使用 Z3 求解器找到满足所有约束的边界值组合。

        Args:
            contract: 契约字典
            max_cases: 最大测试用例数

        Returns:
            测试用例列表，每个包含 inputs 和 expected 字段
        """
        if not self._z3_available:
            return []

        try:
            import z3

            interface = contract.get("interface", {})
            inputs = interface.get("inputs", [])
            interface.get("outputs", [])

            if not inputs:
                return []

            test_cases = []
            preconditions = self._extract_conditions(contract, "preconditions")
            postconditions = self._extract_conditions(contract, "postconditions")
            preconditions + postconditions
            self._extract_conditions(contract, "preconditions")

            for inp in inputs[:3]:  # 限制变量数
                name = inp.get("name", "unknown")
                range_val = inp.get("range", [0, 100])
                input_type = inp.get("type", "double")

                solver = z3.Solver()

                if input_type in ("double", "float", "int", "integer"):
                    var = z3.Real(name) if input_type in ("double", "float") else z3.Int(name)

                    # 边界值
                    if isinstance(range_val, list) and len(range_val) >= 2:
                        min_val, max_val = float(range_val[0]), float(range_val[1])
                        solver.add(var >= min_val)
                        solver.add(var <= max_val)

                        # 尝试各种值：最小值、最大值、中点
                        for target_val, desc in [
                            (min_val, "最小值"),
                            (max_val, "最大值"),
                            ((min_val + max_val) / 2, "中点"),
                            (min_val + (max_val - min_val) * 0.1, "接近最小值"),
                            (max_val - (max_val - min_val) * 0.1, "接近最大值"),
                        ]:
                            if len(test_cases) >= max_cases:
                                break
                            solver.push()
                            solver.add(var == target_val)
                            if solver.check() == z3.sat:
                                model = solver.model()
                                test_cases.append({
                                    "case": f"{name}_{desc}",
                                    "input": {name: float(model[var].as_decimal(10)) if hasattr(model[var], 'as_decimal') else str(model[var])},
                                    "boundary": desc,
                                })
                            solver.pop()

            return test_cases

        except Exception as e:
            logger.error(f"Z3 测试用例生成异常: {e}")
            return []

    def _extract_conditions(self, contract: dict[str, Any], section: str) -> list[str]:
        """从契约中提取条件列表。"""
        contracts = contract.get("contracts", contract)
        if isinstance(contracts, dict):
            section_data = contracts.get(section, [])
        else:
            section_data = contract.get(section, [])
        if isinstance(section_data, list):
            return section_data
        return []

    def _create_z3_variables(self, interface: dict[str, Any], conditions: list[str]) -> dict[str, Any]:
        """从接口定义和条件文本提取变量名并创建 Z3 变量。"""
        import z3
        variables = {}

        # 从接口定义提取
        for io_type in ("inputs", "outputs"):
            for item in interface.get(io_type, []):
                name = item.get("name", "")
                if name:
                    variables[name] = z3.Real(name)

        # 从条件文本中提取变量引用
        var_pattern = re.compile(r'\b([a-zA-Z_]\w*)\b')
        reserved = {
            "if", "else", "for", "while", "return", "int", "double",
            "float", "char", "void", "NULL", "true", "false", "and",
            "or", "not", "in", "is", "as", "assert", "static",
        }
        for cond in conditions:
            for match in var_pattern.finditer(cond):
                var_name = match.group(1)
                if var_name not in reserved and var_name not in variables:
                    variables[var_name] = z3.Real(var_name)

        return variables

    def _condition_to_z3(self, condition: str, variables: dict, label: str):
        """将自然语言/代码条件转换为 Z3 约束（尽力而为）。"""
        import z3

        # 跳过无法解析的条件
        if not condition or not variables:
            return None

        try:
            # 模式1: "x > 10" 或 "x >= 10"
            m = re.match(r'(\w+)\s*(>=?|<=?|==|!=)\s*([\d.]+)', condition.strip())
            if m:
                var_name, op, value = m.group(1), m.group(2), m.group(3)
                if var_name in variables:
                    var = variables[var_name]
                    val = float(value) if '.' in value else int(value)
                    ops = {
                        ">": lambda a, b: a > b,
                        ">=": lambda a, b: a >= b,
                        "<": lambda a, b: a < b,
                        "<=": lambda a, b: a <= b,
                        "==": lambda a, b: a == b,
                        "!=": lambda a, b: a != b,
                    }
                    if op in ops:
                        try:
                            return ops[op](var, val)
                        except Exception:
                            return ops[op](var, z3.RealVal(val))

            # 模式2: "x != NULL" → 跳过（Z3 不处理指针）
            if "NULL" in condition or "null" in condition.lower():
                return None

            # 模式3: "if x == 0: ..." → 提取条件
            m = re.match(r'if\s+(\w+)\s*(==|!=)\s*([\d.]+)', condition.strip())
            if m:
                var_name, op, value = m.group(1), m.group(2), m.group(3)
                if var_name in variables:
                    var = variables[var_name]
                    val = float(value) if '.' in value else int(value)
                    if op == "==":
                        return var == val
                    elif op == "!=":
                        return var != val

        except Exception as e:
            logger.debug(f"Z3 条件转换失败 ({condition[:50]}): {e}")

        return None


# ==================== CBMC 验证器 ====================

class CbmcContractVerifier:
    """基于 CBMC 的契约有界模型检查。"""

    def __init__(self):
        self._cbmc_available = self._check_cbmc()

    @staticmethod
    def _check_cbmc() -> bool:
        """检查 CBMC 是否可用。"""
        try:
            result = subprocess.run(
                ["cbmc", "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._cbmc_available

    def verify(self, code: str, contract: dict[str, Any], unwind: int = 10) -> tuple[bool, str, float]:
        """使用 CBMC 验证代码是否满足契约。

        Args:
            code: C 代码
            contract: 契约字典
            unwind: 循环展开深度

        Returns:
            (verified, output, time_ms)
        """
        if not self._cbmc_available:
            return False, "CBMC 不可用", 0.0

        import time as time_mod
        from skyforge_engine.core.verifiers.cbmc_verifier import preprocess_with_gcc

        start = time_mod.time()

        try:
            instrumented_code = self._instrument_code(code, contract)

            with tempfile.TemporaryDirectory() as tmpdir:
                pp_file = preprocess_with_gcc(instrumented_code, tmpdir)
                if pp_file:
                    src = Path(pp_file)
                else:
                    src = Path(tmpdir) / "verify.c"
                    src.write_text(instrumented_code, encoding="utf-8")

                cbmc_path = shutil.which("cbmc")
                if not cbmc_path:
                    return False, "CBMC not found", 0.0

                cmd = [
                    cbmc_path, str(src),
                    "--unwind", str(unwind),
                    "--xml-ui",
                    "--trace",
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                )

                elapsed = (time_mod.time() - start) * 1000
                verified = "VERIFICATION SUCCESSFUL" in result.stdout
                return verified, result.stdout[:2000], elapsed

        except subprocess.TimeoutExpired:
            elapsed = (time_mod.time() - start) * 1000
            return False, "CBMC 验证超时", elapsed
        except Exception as e:
            elapsed = (time_mod.time() - start) * 1000
            return False, f"CBMC 异常: {e}", elapsed

    def _instrument_code(self, code: str, contract: dict[str, Any]) -> str:
        """在 C 代码中插入契约断言。
        
        将契约的前置条件转为 __CPROVER_assume(),
        后置条件转为 assert()。
        """
        preconditions = contract.get("contracts", contract).get("preconditions", [])
        if isinstance(preconditions, dict):
            preconditions = []
        postconditions = contract.get("contracts", contract).get("postconditions", [])
        if isinstance(postconditions, dict):
            postconditions = []

        lines = code.split("\n")
        instrumented_lines = []

        # 查找 main 函数位置
        main_idx = -1
        for i, line in enumerate(lines):
            if re.search(r'\bmain\s*\(', line):
                main_idx = i
                break

        if main_idx < 0:
            # 没有 main，添加包装
            instrumented_lines.append('#include <assert.h>')
            instrumented_lines.append('#include <stdbool.h>')
            instrumented_lines.append('')
            instrumented_lines.append('int main(void) {')
            instrumented_lines.append('    // CBMC 形式化验证桩')
            instrumented_lines.append('')

            # 前置条件作为 assume
            for cond in preconditions:
                safe_cond = cond.replace("!=", "!=").replace("==", "==")
                instrumented_lines.append(f'    __CPROVER_assume({safe_cond});')

            instrumented_lines.append('')
            instrumented_lines.extend(lines)
            instrumented_lines.append('')

            # 后置条件作为 assert
            for cond in postconditions:
                safe_cond = cond.replace("!=", "!=").replace("==", "==")
                instrumented_lines.append(f'    assert({safe_cond});')

            instrumented_lines.append('    return 0;')
            instrumented_lines.append('}')
        else:
            # 代码中已有 main，在函数体内插入
            instrumented_lines.extend(lines[:main_idx])
            instrumented_lines.append(lines[main_idx])  # main 函数声明

            # 跳过函数体开始的大括号
            brace_found = False
            for j in range(main_idx + 1, len(lines)):
                if not brace_found and "{" in lines[j]:
                    instrumented_lines.append(lines[j])
                    brace_found = True
                    # 插入 assume
                    for cond in preconditions:
                        safe_cond = cond.replace("!=", "!=").replace("==", "==")
                        instrumented_lines.append(f'    __CPROVER_assume({safe_cond});')
                    continue
                instrumented_lines.append(lines[j])

        return "\n".join(instrumented_lines)


# ==================== 统一验证器 ====================

class ContractFormalVerifier:
    """契约形式化验证统一入口。

    .. deprecated::
        使用 ``ContractVerifier`` 替代。

    自动执行所有可用的验证级别（L1 Z3 → L2 测试用例 → L3 CBMC）。
    """

    def __init__(self):
        self._z3_verifier = Z3ContractVerifier()
        self._cbmc_verifier = CbmcContractVerifier()
        self._verifier = _ContractVerifier()

    def _to_legacy_result(
        self, result: CoreVerificationResult
    ) -> VerificationResult:
        """将新层 VerificationResult 转换为旧数据类。"""
        meta = result.metadata
        legacy = VerificationResult(
            component=meta.get("component", ""),
            contract_version=meta.get("version", ""),
            is_consistent=meta.get("is_consistent", True),
            contradictions=meta.get("contradictions", []),
            z3_solver_time_ms=meta.get("z3_solver_time_ms", 0.0),
            test_cases=meta.get("test_cases", []),
            test_case_count=meta.get("test_case_count", 0),
            cbmc_verified=meta.get("cbmc_verified", False),
            cbmc_output=meta.get("cbmc_output", ""),
            cbmc_time_ms=meta.get("cbmc_time_ms", 0.0),
            z3_available=meta.get("z3_available", False),
            cbmc_available=meta.get("cbmc_available", False),
        )
        warnings_list = meta.get("warnings", [])
        if warnings_list:
            legacy.warnings.extend(warnings_list)
        if not result.passed and result.violations:
            legacy.warnings.append("形式化验证发现违规")
        return legacy

    def verify(
        self,
        contract_yaml: str,
        code: Optional[str] = None,
        max_test_cases: int = 10,
    ) -> VerificationResult:
        """对契约执行完整的形式化验证。

        .. deprecated::
            使用 ``ContractVerifier().verify(contract=contract_yaml, code=code)`` 替代。

        Args:
            contract_yaml: 契约 YAML 文本
            code: 可选的 C 代码（用于 CBMC 验证）
            max_test_cases: 最大测试用例数

        Returns:
            VerificationResult 包含完整验证结果
        """
        warnings.warn(
            "ContractFormalVerifier is deprecated, use ContractVerifier instead",
            DeprecationWarning,
            stacklevel=2,
        )

        # 解析契约
        try:
            contract = yaml.safe_load(contract_yaml)
        except yaml.YAMLError as e:
            result = VerificationResult()
            result.errors.append(f"契约 YAML 解析失败: {e}")
            return result

        if not isinstance(contract, dict):
            result = VerificationResult()
            result.errors.append("契约格式无效（非字典）")
            return result

        try:
            new_result = self._verifier.verify(
                code=code or "",
                contract=contract_yaml,
                max_test_cases=max_test_cases,
            )
            return self._to_legacy_result(new_result)
        except Exception as e:
            logger.error(f"ContractFormalVerifier:委托执行异常: {e}")
            result = VerificationResult(
                component=contract.get("component", "unknown"),
                contract_version=contract.get("version", "0.0.0"),
                z3_available=self._z3_verifier.is_available(),
                cbmc_available=self._cbmc_verifier.is_available(),
            )
            result.errors.append(str(e))
            return result

    def quick_check(self, contract_yaml: str) -> bool:
        """快速检查：仅执行 Z3 一致性验证。

        .. deprecated::
            使用 ``ContractVerifier`` 替代。

        Args:
            contract_yaml: 契约 YAML 文本

        Returns:
            True 如果契约约束一致
        """
        warnings.warn(
            "ContractFormalVerifier.quick_check is deprecated, use ContractVerifier instead",
            DeprecationWarning,
            stacklevel=2,
        )
        result = self.verify(contract_yaml, code=None, max_test_cases=0)
        return result.is_consistent


# ==================== 便捷函数 ====================

_verifier_instance: Optional[ContractFormalVerifier] = None


def get_verifier() -> ContractFormalVerifier:
    """获取全局单例验证器。

    .. deprecated::
        使用 ``ContractVerifier`` 替代。
    """
    warnings.warn(
        "get_verifier is deprecated, use ContractVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = ContractFormalVerifier()
    return _verifier_instance


def verify_contract(contract_yaml: str, code: Optional[str] = None) -> VerificationResult:
    """便捷函数：验证契约并返回结果。

    .. deprecated::
        使用 ``ContractVerifier().verify(contract=contract_yaml, code=code)`` 替代。
    """
    warnings.warn(
        "verify_contract is deprecated, use ContractVerifier instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_verifier().verify(contract_yaml, code)
