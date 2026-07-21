"""Cppcheck 静态分析验证器 —— VerifierProtocol 实现."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from skyforge_engine.core.protocols import ToolNotFoundError, VerificationResult
from skyforge_engine.utils.cleanup_util import safe_tempdir
from skyforge_engine.utils.log_util import logger

LogCallback = Callable[[str, str, str], None] | None


@dataclass
class _Violation:
    file: str
    line: int
    column: int = 0
    severity: str = "style"
    rule_id: str = ""
    message: str = ""


class CppcheckVerifier:
    """Cppcheck 静态分析验证器."""

    @property
    def tool_name(self) -> str:
        return "cppcheck"

    def _find_cppcheck(self) -> str | None:
        """查找可用的 cppcheck 可执行文件。

        优先使用 MSYS2 ucrt64 的 cppcheck（版本更新且 cfg 路径正确）。
        """
        if sys.platform == "win32":
            msys2_paths = [
                r"C:\msys64\ucrt64\bin\cppcheck.exe",
                r"C:\msys64\mingw64\bin\cppcheck.exe",
            ]
            for p in msys2_paths:
                if os.path.isfile(p):
                    return p
        return shutil.which("cppcheck")

    def is_available(self) -> bool:
        return self._find_cppcheck() is not None

    def _cppcheck_version(self) -> str | None:
        cppcheck_path = self._find_cppcheck()
        if not cppcheck_path:
            return None
        try:
            proc = subprocess.run(
                [cppcheck_path, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            version = (proc.stdout or proc.stderr or "").strip()
            return version if version else None
        except Exception:
            return None

    def verify(self, code: str, contract: str | None = None, **kwargs: Any) -> VerificationResult:
        """执行 Cppcheck 静态分析扫描.

        Args:
            code: C 源代码字符串。
            contract: 可选契约文本（当前未使用）。
            **kwargs: 支持 log_callback。

        Returns:
            VerificationResult: 扫描结果。

        Raises:
            ToolNotFoundError: Cppcheck 不可用时抛出。
        """
        if not self.is_available():
            raise ToolNotFoundError(self.tool_name)

        log_callback = kwargs.get("log_callback", None)

        start = time.time()
        violations = self._scan_real(code, log_callback)
        elapsed = (time.time() - start) * 1000

        violation_dicts = [
            {
                "file": v.file,
                "line": v.line,
                "column": v.column,
                "severity": v.severity,
                "rule_id": v.rule_id,
                "message": v.message,
            }
            for v in violations
        ]

        return VerificationResult(
            passed=len(violations) == 0,
            tool_name=self.tool_name,
            tool_available=True,
            violations=violation_dicts,
            output=f"检出 {len(violations)} 条违规",
            duration_ms=elapsed,
            metadata={"cppcheck_version": self._cppcheck_version()},
        )

    def _scan_real(self, code: str, log_callback: LogCallback = None) -> list[_Violation]:
        """真实 Cppcheck 扫描路径."""
        with safe_tempdir(prefix="skyforge_cppcheck_") as tmp_dir:
            src_path = os.path.join(tmp_dir, "code.c")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            template = "{file}|{line}|{column}|{severity}|{id}|{message}"
            cppcheck_path = self._find_cppcheck() or "cppcheck"
            cmd = [
                cppcheck_path,
                "--dump",
                f"--template={template}",
                "--quiet",
            ]
            if sys.platform == "win32":
                python_path = sys.executable
                if not python_path or "WindowsApps" in python_path:
                    python_path = shutil.which("python3") or shutil.which("python")
                if python_path:
                    cmd.append(f"--addon-python={python_path}")
                misra_path = self._find_misra_addon()
                if misra_path:
                    cmd.append(f"--addon={misra_path}")
                else:
                    cmd.append("--addon=misra")
            else:
                cmd.append("--addon=misra")
            cmd.append(src_path)

            logger.info(f"CppcheckVerifier:执行: {' '.join(cmd)}")
            if log_callback:
                log_callback("TERMINAL", "info", f"$ {' '.join(cmd)}")

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

            if sys.platform == "win32":
                dump_path = Path(tmp_dir) / (os.path.basename(src_path).replace(".c", "") + ".c.dump")
                if dump_path.exists():
                    misra_path = self._find_misra_addon()
                    python_path = sys.executable
                    if not python_path or "WindowsApps" in python_path:
                        python_path = shutil.which("python3") or shutil.which("python")
                    if misra_path and python_path:
                        misra_proc = subprocess.run(
                            [python_path, misra_path, str(dump_path)],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=60,
                            check=False,
                        )
                        misra_output = (misra_proc.stdout or "") + (misra_proc.stderr or "")
                        if misra_output:
                            combined += "\n" + misra_output

            if log_callback and combined.strip():
                snippet = combined[:2000]
                level = "warn" if proc.returncode != 0 else "info"
                log_callback("TERMINAL", level, snippet)

            return self._parse_output(combined, src_path)

    def _find_misra_addon(self) -> str | None:
        if sys.platform != "win32":
            return None
        candidates: list[str] = []
        candidates.append(r"C:\msys64\ucrt64\share\cppcheck\addons\misra.py")
        candidates.append(r"C:\msys64\mingw64\share\cppcheck\addons\misra.py")
        candidates.append(r"C:\Program Files\cppcheck\addons\misra.py")
        candidates.append(r"C:\Program Files (x86)\cppcheck\addons\misra.py")
        cppcheck_path = shutil.which("cppcheck")
        if cppcheck_path:
            cppcheck_dir = Path(cppcheck_path).parent
            candidates.append(str(cppcheck_dir / ".." / "share" / "cppcheck" / "addons" / "misra.py"))
            candidates.append(str(cppcheck_dir / "addons" / "misra.py"))
        for path in candidates:
            if Path(path).exists():
                return path
        return None

    def _parse_output(self, output: str, src_path: str) -> list[_Violation]:
        """解析 cppcheck 模板化输出为违规列表."""
        violations: list[_Violation] = []
        basename = os.path.basename(src_path)
        for line in output.splitlines():
            if "|" in line:
                parts = line.split("|", 5)
                if len(parts) >= 6:
                    fpath, line_no, col, sev, rid, msg = parts
                    if basename not in fpath and src_path not in fpath:
                        continue
                    try:
                        line_int = int(line_no)
                    except ValueError:
                        continue
                    violations.append(
                        _Violation(
                            file=fpath,
                            line=line_int,
                            column=int(col) if col.isdigit() else 0,
                            severity=sev,
                            rule_id=rid,
                            message=msg,
                        )
                    )
                    continue

            match = re.match(
                r'\[(.+?):(\d+)\]\s*\((\w+)\).*\[(misra-c2012-[\d.]+)\]',
                line,
            )
            if match:
                fpath, line_no, sev, rid = match.groups()
                if basename not in fpath and src_path not in fpath:
                    continue
                try:
                    line_int = int(line_no)
                except ValueError:
                    continue
                violations.append(
                    _Violation(
                        file=fpath,
                        line=line_int,
                        column=0,
                        severity=sev,
                        rule_id=rid,
                        message=f"MISRA violation: {rid}",
                    )
                )
                continue
        return violations
