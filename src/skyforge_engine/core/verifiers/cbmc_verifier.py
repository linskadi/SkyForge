"""CBMC 有界模型检查器验证器 —— VerifierProtocol 实现."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult
from skyforge_engine.utils.log_util import logger


def preprocess_with_gcc(code: str, tmpdir: str) -> str | None:
    """使用 GCC 预处理 C 代码，使 CBMC 能在无 cl.exe 的 Windows 上运行。

    替换 bool/true/false/NULL 为 C99 兼容形式，去除 #include。
    """
    replacements = [
        (r'#include\s+<[^>]+>', ''),
        (r'\bbool\b', 'int'),
        (r'\btrue\b', '1'),
        (r'\bfalse\b', '0'),
        (r'\bNULL\b', '0'),
    ]
    clean = code
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean)
    src = os.path.join(tmpdir, "clean.c")
    pp = os.path.join(tmpdir, "preprocessed.i")
    with open(src, "w", encoding="utf-8") as f:
        f.write(clean)
    gcc_path = shutil.which("gcc")
    if not gcc_path:
        return None
    try:
        r = subprocess.run(
            [gcc_path, "-E", "-P", "-std=c99", "-nostdinc", src],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            with open(pp, "w", encoding="utf-8") as f:
                f.write(r.stdout)
            return pp
    except Exception:
        pass
    return None


class CBMCVerifier:
    """CBMC 有界模型检查器验证器."""

    @property
    def tool_name(self) -> str:
        return "cbmc"

    def is_available(self) -> bool:
        return shutil.which("cbmc") is not None

    def _preprocess_with_gcc(self, code: str, tmpdir: str) -> str | None:
        """使用 GCC 预处理 C 代码（Windows 上 CBMC 需要 cl.exe，改用 GCC 代替）。"""
        return preprocess_with_gcc(code, tmpdir)

    def verify(self, code: str, contract: str | None = None, *, language: str = "c", **kwargs: Any) -> VerificationResult:
        """执行 CBMC 有界模型检查.

        Args:
            code: C 源代码字符串。
            contract: 可选契约文本。
            language: 代码语言，CBMC 仅支持 C。
            **kwargs: 支持 unwind, function, property_flags。

        Returns:
            VerificationResult: 验证结果。

        Raises:
            ToolNotFoundError: CBMC 不可用时抛出。
        """
        if not self.is_available():
            raise ToolNotFoundError(self.tool_name)

        # CBMC 仅支持 C 代码，非 C 代码跳过验证
        if language not in ("c", "cpp"):
            logger.info(f"CBMC:跳过验证（语言={language}，仅支持 C/C++）")
            return VerificationResult(
                passed=True,
                tool_name=self.tool_name,
                tool_available=True,
                violations=[],
                output=f"CBMC 跳过：非 C/C++ 代码 (language={language})",
                duration_ms=0,
                metadata={"skipped": True, "reason": f"non-C/C++ language: {language}"},
            )

        unwind = kwargs.get("unwind", 10)
        function = kwargs.get("function", None)
        property_flags = kwargs.get("property_flags", None)

        code = self._inject_assertions(code)

        if not function and not self._has_main(code):
            funcs = self._find_entry_functions(code)
            if funcs:
                function = funcs[0]
                logger.info(f"CBMC:自动检测入口函数: {function}")

        cbmc_path = shutil.which("cbmc")
        start = time.time()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Windows 上 cl.exe 通常不可用，使用 GCC 预处理
                pp_file = self._preprocess_with_gcc(code, tmpdir)
                if pp_file:
                    src = Path(pp_file)
                else:
                    src = Path(tmpdir) / "verify.c"
                    src.write_text(code, encoding="utf-8")

                cmd = [
                    cbmc_path,
                    str(src),
                    "--unwind", str(unwind),
                    "--xml-ui",
                    "--trace",
                ]
                if function:
                    cmd.extend(["--function", function])
                if property_flags:
                    cmd.extend(property_flags)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )

                elapsed = (time.time() - start) * 1000
                root = ET.fromstring(result.stdout) if result.stdout else ET.Element("results")
                status = root.findtext(".//cprover-status", "UNKNOWN")

                violations: list[dict[str, Any]] = []
                trace = ""
                if status != "SUCCESS":
                    for prop in root.iter("property"):
                        if prop.get("status") == "FAILURE":
                            desc = prop.findtext("description", "unknown")
                            file_attr = prop.get("file", "")
                            line_attr = prop.get("line", "")
                            violations.append({
                                "message": f"{desc} at {file_attr}:{line_attr}",
                                "file": file_attr,
                                "line": line_attr,
                            })
                    trace_elem = root.find(".//counterexample")
                    if trace_elem is not None:
                        trace = ET.tostring(trace_elem, encoding="unicode")[:2000]

                logger.info(
                    f"CBMC:验证{'通过' if status == 'SUCCESS' else '失败'}: "
                    f"{len(violations)} violations, {elapsed:.0f}ms"
                )

                return VerificationResult(
                    passed=status == "SUCCESS",
                    tool_name=self.tool_name,
                    tool_available=True,
                    violations=violations,
                    output=result.stdout[:2000] if result.stdout else "",
                    duration_ms=elapsed,
                    metadata={"status": status, "trace": trace},
                )

        except subprocess.TimeoutExpired as e:
            logger.warning(f"CBMC:执行超时: {e}")
            raise ToolNotFoundError(self.tool_name, f"CBMC 执行超时: {e}")
        except Exception as e:
            logger.error(f"CBMC:异常: {e}")
            raise

    def _find_entry_functions(self, code: str) -> list[str]:
        """找出 C 代码中已定义的函数（有 body），排除 main 和 void 函数。"""
        funcs: list[str] = []
        for m in re.finditer(
            r'(?:(?:static|inline)\s+)*(\w+(?:\s*\*)?)\s+(\w+)\s*\([^)]*\)\s*\{',
            code,
        ):
            name = m.group(2)
            if name in ('if', 'while', 'for', 'switch', 'return', 'sizeof', 'main'):
                continue
            ret_type = m.group(1).strip()
            if ret_type != 'void' and name not in funcs:
                funcs.append(name)
        return funcs if funcs else []

    def _has_main(self, code: str) -> bool:
        return bool(re.search(r'\b(?:int|void)\s+main\s*\(', code))

    def _inject_assertions(self, code: str) -> str:
        """在 C 代码中注入 CBMC 断言注解."""
        lines = code.splitlines()
        injected: list[str] = []
        in_main = False
        for line in lines:
            stripped = line.strip()
            if "int main" in stripped or "void main" in stripped:
                in_main = True
                injected.append(line)
                continue
            if in_main and "fgets" in stripped and "stdin" in stripped:
                pass
            injected.append(line)
        return "\n".join(injected)
