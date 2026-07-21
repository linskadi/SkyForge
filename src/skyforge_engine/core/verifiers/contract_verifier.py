"""契约形式化验证器 —— VerifierProtocol 实现."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult
from skyforge_engine.utils.log_util import logger

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


class ContractVerifier:
    """契约形式化验证器.

    组合 Z3 一致性检查与 CBMC 有界模型检查。
    """

    @property
    def tool_name(self) -> str:
        return "contract"

    def is_available(self) -> bool:
        return yaml is not None

    def _z3_available(self) -> bool:
        try:
            import z3  # noqa: F401
            return True
        except ImportError:
            return False

    def _cbmc_available(self) -> bool:
        try:
            result = subprocess.run(
                ["cbmc", "--version"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def verify(self, code: str = "", contract: str | None = None, *, language: str = "c", **kwargs: Any) -> VerificationResult:
        """对契约执行完整的形式化验证.

        Args:
            code: 可选的 C 代码（用于 CBMC 验证）。
            contract: 契约 YAML 文本。
            language: 代码语言，CBMC 仅支持 C/C++。
            **kwargs: 支持 max_test_cases。

        Returns:
            VerificationResult: 验证结果。

        Raises:
            ToolNotFoundError: PyYAML 未安装时抛出。
            ValueError: 契约格式无效时抛出。
        """
        if not self.is_available():
            raise ToolNotFoundError(self.tool_name, "PyYAML 未安装")

        if contract is None:
            raise ValueError("contract 参数为必填项（YAML 契约文本）")

        try:
            contract_dict = yaml.safe_load(contract)
        except Exception as e:
            raise ValueError(f"契约 YAML 解析失败: {e}")

        if not isinstance(contract_dict, dict):
            raise ValueError("契约格式无效（非字典）")

        max_test_cases = kwargs.get("max_test_cases", 10)
        z3_avail = self._z3_available()
        cbmc_avail = self._cbmc_available()

        duration_ms = 0.0
        passed = True
        violations: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {
            "component": contract_dict.get("component", "unknown"),
            "version": contract_dict.get("version", "0.0.0"),
            "z3_available": z3_avail,
            "cbmc_available": cbmc_avail,
        }
        output_parts: list[str] = []

        # Level 1: Z3 一致性验证
        if z3_avail:
            is_consistent, contradictions, z3_time = self._verify_z3_consistency(contract_dict)
            duration_ms += z3_time
            metadata["is_consistent"] = is_consistent
            metadata["contradictions"] = contradictions
            metadata["z3_solver_time_ms"] = z3_time
            passed = passed and is_consistent
            violations.extend([{"message": c} for c in contradictions])
            output_parts.append(f"Z3 一致性: {is_consistent}")

            if is_consistent:
                test_cases = self._generate_test_cases(contract_dict, max_test_cases)
                metadata["test_cases"] = test_cases
                metadata["test_case_count"] = len(test_cases)
        else:
            metadata.setdefault("warnings", []).append("Z3 不可用，契约约束一致性未验证")
            metadata["is_consistent"] = True

        # Level 3: CBMC 有界模型检查（仅支持 C/C++）
        if code and cbmc_avail:
            if language not in ("c", "cpp"):
                metadata.setdefault("warnings", []).append(
                    f"CBMC 跳过：非 C/C++ 代码 (language={language})"
                )
                output_parts.append(f"CBMC: skipped (language={language})")
            else:
                verified, cbmc_out, cbmc_time = self._verify_cbmc(code, contract_dict)
                duration_ms += cbmc_time
                metadata["cbmc_verified"] = verified
                metadata["cbmc_output"] = cbmc_out
                metadata["cbmc_time_ms"] = cbmc_time
                passed = passed and verified
                output_parts.append(f"CBMC: {verified}")
        elif code and not cbmc_avail:
            metadata.setdefault("warnings", []).append("CBMC 不可用，有界模型检查已跳过")

        return VerificationResult(
            passed=passed,
            tool_name=self.tool_name,
            tool_available=True,
            violations=violations,
            output="\n".join(output_parts),
            duration_ms=duration_ms,
            metadata=metadata,
        )

    def _verify_z3_consistency(self, contract: dict[str, Any]) -> tuple[bool, list[str], float]:
        import z3
        start = time.time()
        contradictions: list[str] = []

        preconditions = self._extract_conditions(contract, "preconditions")
        postconditions = self._extract_conditions(contract, "postconditions")
        invariants = self._extract_conditions(contract, "invariants")
        interface = contract.get("interface", {})

        all_conditions = preconditions + postconditions + invariants
        if not all_conditions:
            return True, [], 0.0

        solver = z3.Solver()
        variables = self._create_z3_variables(interface, all_conditions)

        for i, cond in enumerate(preconditions):
            constraint = self._condition_to_z3(cond, variables, f"pre_{i}")
            if constraint is not None:
                solver.add(constraint)

        if solver.check() == z3.unsat:
            contradictions.append("前置条件之间存在逻辑矛盾")
            elapsed = (time.time() - start) * 1000
            return False, contradictions, elapsed

        for i, cond in enumerate(all_conditions):
            constraint = self._condition_to_z3(cond, variables, f"cond_{i}")
            if constraint is not None:
                solver.add(constraint)

        result = solver.check()
        elapsed = (time.time() - start) * 1000

        if result == z3.unsat:
            contradictions.append("所有契约条件不可同时满足（存在逻辑矛盾）")
            try:
                core = solver.unsat_core()
                if core:
                    contradictions.append(f"矛盾来源: {[str(c) for c in core]}")
            except Exception:
                pass
            return False, contradictions, elapsed

        return True, [], elapsed

    def _generate_test_cases(self, contract: dict[str, Any], max_cases: int = 10) -> list[dict[str, Any]]:
        import z3
        try:
            interface = contract.get("interface", {})
            inputs = interface.get("inputs", [])
            if not inputs:
                return []

            test_cases: list[dict[str, Any]] = []

            for inp in inputs[:3]:
                name = inp.get("name", "unknown")
                range_val = inp.get("range", [0, 100])
                input_type = inp.get("type", "double")

                solver = z3.Solver()
                if input_type in ("double", "float", "int", "integer"):
                    var = z3.Real(name) if input_type in ("double", "float") else z3.Int(name)
                    if isinstance(range_val, list) and len(range_val) >= 2:
                        min_val, max_val = float(range_val[0]), float(range_val[1])
                        solver.add(var >= min_val)
                        solver.add(var <= max_val)

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
                                    "input": {
                                        name: float(model[var].as_decimal())
                                        if hasattr(model[var], "as_decimal")
                                        else str(model[var])
                                    },
                                    "boundary": desc,
                                })
                            solver.pop()
            return test_cases
        except Exception as e:
            logger.error(f"Z3 测试用例生成异常: {e}")
            return []

    def _verify_cbmc(self, code: str, contract: dict[str, Any], unwind: int = 10) -> tuple[bool, str, float]:
        start = time.time()
        try:
            instrumented_code = self._instrument_code(code, contract)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".c", prefix="cbmc_verify_", delete=False
            ) as f:
                f.write(instrumented_code)
                tmp_path = f.name

            cmd = [
                "cbmc", tmp_path,
                "--unwind", str(unwind),
                "--xml-ui",
                "--trace",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120,
            )

            elapsed = (time.time() - start) * 1000
            verified = "VERIFICATION SUCCESSFUL" in result.stdout
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return verified, result.stdout[:2000], elapsed

        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return False, "CBMC 验证超时", elapsed
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return False, f"CBMC 异常: {e}", elapsed

    def _extract_conditions(self, contract: dict[str, Any], section: str) -> list[str]:
        contracts = contract.get("contracts", contract)
        if isinstance(contracts, dict):
            section_data = contracts.get(section, [])
        else:
            section_data = contract.get(section, [])
        if isinstance(section_data, list):
            return section_data
        return []

    def _create_z3_variables(self, interface: dict[str, Any], conditions: list[str]) -> dict[str, Any]:
        import z3
        variables: dict[str, Any] = {}
        for io_type in ("inputs", "outputs"):
            for item in interface.get(io_type, []):
                name = item.get("name", "")
                if name:
                    variables[name] = z3.Real(name)
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

    def _condition_to_z3(self, condition: str, variables: dict[str, Any], label: str):
        import z3
        if not condition or not variables:
            return None
        try:
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
            if "NULL" in condition or "null" in condition.lower():
                return None
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

    def _instrument_code(self, code: str, contract: dict[str, Any]) -> str:
        preconditions = self._extract_conditions(contract, "preconditions")
        postconditions = self._extract_conditions(contract, "postconditions")

        lines = code.split("\n")
        instrumented_lines: list[str] = []
        main_idx = -1
        for i, line in enumerate(lines):
            if re.search(r'\bmain\s*\(', line):
                main_idx = i
                break

        if main_idx < 0:
            instrumented_lines.append('#include <assert.h>')
            instrumented_lines.append('#include <stdbool.h>')
            instrumented_lines.append('')
            instrumented_lines.append('int main(void) {')
            instrumented_lines.append('    // CBMC 形式化验证桩')
            instrumented_lines.append('')
            for cond in preconditions:
                instrumented_lines.append(f'    __CPROVER_assume({cond});')
            instrumented_lines.append('')
            instrumented_lines.extend(lines)
            instrumented_lines.append('')
            for cond in postconditions:
                instrumented_lines.append(f'    assert({cond});')
            instrumented_lines.append('    return 0;')
            instrumented_lines.append('}')
        else:
            instrumented_lines.extend(lines[:main_idx])
            instrumented_lines.append(lines[main_idx])
            brace_found = False
            for j in range(main_idx + 1, len(lines)):
                if not brace_found and "{" in lines[j]:
                    instrumented_lines.append(lines[j])
                    brace_found = True
                    for cond in preconditions:
                        instrumented_lines.append(f'    __CPROVER_assume({cond});')
                    continue
                instrumented_lines.append(lines[j])

        return "\n".join(instrumented_lines)
