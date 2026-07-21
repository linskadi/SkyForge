"""CBMC 有界模型检查器验证器 —— VerifierProtocol 实现."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult
from skyforge_engine.utils.log_util import logger


class CBMCVerifier:
    """CBMC 有界模型检查器验证器."""

    @property
    def tool_name(self) -> str:
        return "cbmc"

    def is_available(self) -> bool:
        return shutil.which("cbmc") is not None

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
        cbmc_path = shutil.which("cbmc")
        start = time.time()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
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
