"""多语言静态分析扫描器基类。

支持C/C++/Python语言的静态分析，可扩展新的语言和编码标准。
"""

import json
import os
import re
import subprocess
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass

from skyforge_engine.utils.log_util import logger


@dataclass
class Violation:
    """静态分析违规记录。"""
    file: str
    line: int
    column: int
    severity: str
    rule_id: str
    message: str


class BaseScanner(ABC):
    """静态分析扫描器基类。"""
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查扫描工具是否可用。"""
        pass
    
    @abstractmethod
    def scan(self, code: str, **kwargs) -> list[Violation]:
        """扫描代码，返回违规列表。"""
        pass
    
    def _run_command(self, cmd: list[str], timeout: int = 60) -> tuple[str, str, int]:
        """运行外部命令。"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except FileNotFoundError:
            return "", f"Command not found: {cmd[0]}", 1
        except Exception as e:
            return "", str(e), 1


class CppcheckScanner(BaseScanner):
    """Cppcheck MISRA-C 扫描器。"""
    
    def __init__(self):
        self._cppcheck_path = self._find_cppcheck()
        self._addon_python = self._find_python()
        self._addon_path = self._find_misra_addon()
    
    def _find_cppcheck(self) -> str | None:
        """查找可用的 cppcheck 可执行文件。

        优先使用 MSYS2 ucrt64 的 cppcheck（版本更新且 cfg 路径正确）。
        """
        import sys
        if sys.platform == "win32":
            msys2_paths = [
                r"C:\msys64\ucrt64\bin\cppcheck.exe",
                r"C:\msys64\mingw64\bin\cppcheck.exe",
            ]
            for p in msys2_paths:
                if os.path.isfile(p):
                    return p
        return shutil.which("cppcheck")
    
    def _find_python(self) -> str:
        """查找Python解释器。"""
        for python in ["python", "python3", "py"]:
            path = shutil.which(python)
            if path:
                return path
        return ""
    
    def _find_misra_addon(self) -> str:
        """查找MISRA addon路径。"""
        import sys
        if sys.platform == "win32":
            candidates = [
                r"C:\msys64\ucrt64\share\cppcheck\addons\misra.py",
                r"C:\msys64\mingw64\share\cppcheck\addons\misra.py",
            ]
            for path in candidates:
                if os.path.exists(path):
                    return path
        return ""
    
    def is_available(self) -> bool:
        return self._cppcheck_path is not None
    
    def scan(self, code: str, **kwargs) -> list[Violation]:
        """使用Cppcheck扫描C代码。"""
        if not self.is_available():
            logger.warning("CppcheckScanner:Cppcheck 未安装")
            return []
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(code)
            src_path = f.name
        
        try:
            cmd = [self._cppcheck_path, "--dump", "--quiet"]
            if self._addon_python and self._addon_path:
                cmd.extend([
                    f"--addon-python={self._addon_python}",
                    f"--addon={self._addon_path}",
                ])
            cmd.append(src_path)
            
            stdout, stderr, returncode = self._run_command(cmd)
            violations = self._parse_output(stdout + stderr, src_path)
            logger.info(f"CppcheckScanner:完成:检出 {len(violations)} 条违规")
            return violations
        finally:
            os.unlink(src_path)
    
    def _parse_output(self, output: str, src_path: str) -> list[Violation]:
        """解析Cppcheck输出。"""
        violations = []
        basename = os.path.basename(src_path)
        
        # 解析模板格式: file|line|column|severity|id|message
        for line in output.splitlines():
            if "|" in line:
                parts = line.split("|", 5)
                if len(parts) >= 6:
                    fpath, line_no, col, sev, rid, msg = parts
                    if basename in fpath or src_path in fpath:
                        try:
                            violations.append(Violation(
                                file=fpath, line=int(line_no),
                                column=int(col) if col.isdigit() else 0,
                                severity=sev, rule_id=rid, message=msg
                            ))
                        except ValueError:
                            pass
        
        # 解析MISRA格式: [file:line] (severity) ... [rule-id]
        for line in output.splitlines():
            match = re.match(r'\[(.+?):(\d+)\]\s*\((\w+)\).*\[(misra-c2012-[\d.]+)\]', line)
            if match:
                fpath, line_no, sev, rid = match.groups()
                if basename in fpath or src_path in fpath:
                    violations.append(Violation(
                        file=fpath, line=int(line_no), column=0,
                        severity=sev, rule_id=rid, message=f"MISRA violation: {rid}"
                    ))
        
        return violations


class ClangTidyScanner(BaseScanner):
    """Clang-tidy C++ 静态分析扫描器。"""
    
    def __init__(self):
        self._clang_tidy_path = shutil.which("clang-tidy")
    
    def is_available(self) -> bool:
        return self._clang_tidy_path is not None
    
    def scan(self, code: str, **kwargs) -> list[Violation]:
        """使用Clang-tidy扫描C++代码。"""
        if not self.is_available():
            logger.warning("ClangTidyScanner:clang-tidy 未安装")
            return []
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
            f.write(code)
            src_path = f.name
        
        try:
            cmd = [
                self._clang_tidy_path,
                src_path,
                "--", "-std=c++17", "-Wall", "-Wextra",
                "--checks=modernize-*,cppcoreguidelines-*,bugprone-*",
            ]
            
            stdout, stderr, returncode = self._run_command(cmd)
            violations = self._parse_output(stdout + stderr, src_path)
            logger.info(f"ClangTidyScanner:完成:检出 {len(violations)} 条违规")
            return violations
        finally:
            os.unlink(src_path)
    
    def _parse_output(self, output: str, src_path: str) -> list[Violation]:
        """解析Clang-tidy输出。"""
        violations = []
        basename = os.path.basename(src_path)
        
        # 解析格式: file:line:col: warning: message [check-name]
        for line in output.splitlines():
            match = re.match(r'(.+?):(\d+):(\d+):\s*(warning|error):\s*(.+?)\s*\[(.+?)\]', line)
            if match:
                fpath, line_no, col, severity, msg, check = match.groups()
                if basename in fpath:
                    violations.append(Violation(
                        file=fpath, line=int(line_no), column=int(col),
                        severity=severity, rule_id=check, message=msg
                    ))
        
        return violations


class MypyScanner(BaseScanner):
    """Mypy Python 类型检查扫描器。"""
    
    def __init__(self):
        self._mypy_path = shutil.which("mypy")
    
    def is_available(self) -> bool:
        return self._mypy_path is not None
    
    def scan(self, code: str, **kwargs) -> list[Violation]:
        """使用Mypy扫描Python代码。"""
        if not self.is_available():
            logger.warning("MypyScanner:mypy 未安装")
            return []
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            src_path = f.name
        
        try:
            cmd = [
                self._mypy_path,
                src_path,
                "--ignore-missing-imports",
                "--no-error-summary",
            ]
            
            stdout, stderr, returncode = self._run_command(cmd)
            violations = self._parse_output(stdout + stderr, src_path)
            logger.info(f"MypyScanner:完成:检出 {len(violations)} 条违规")
            return violations
        finally:
            os.unlink(src_path)
    
    def _parse_output(self, output: str, src_path: str) -> list[Violation]:
        """解析Mypy输出。"""
        violations = []
        basename = os.path.basename(src_path)
        
        # 解析格式: file:line: error: message
        for line in output.splitlines():
            match = re.match(r'(.+?):(\d+):\s*(error|warning|note):\s*(.+)', line)
            if match:
                fpath, line_no, severity, msg = match.groups()
                if basename in fpath:
                    violations.append(Violation(
                        file=fpath, line=int(line_no), column=0,
                        severity=severity, rule_id="mypy", message=msg
                    ))
        
        return violations


class RuffScanner(BaseScanner):
    """Ruff Python 代码质量扫描器。"""
    
    def __init__(self):
        self._ruff_path = shutil.which("ruff")
    
    def is_available(self) -> bool:
        return self._ruff_path is not None
    
    def scan(self, code: str, **kwargs) -> list[Violation]:
        """使用Ruff扫描Python代码。"""
        if not self.is_available():
            logger.warning("RuffScanner:ruff 未安装")
            return []
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            src_path = f.name
        
        try:
            cmd = [
                self._ruff_path,
                "check",
                "--output-format=json",
                src_path,
            ]
            
            stdout, stderr, returncode = self._run_command(cmd)
            violations = self._parse_json_output(stdout)
            logger.info(f"RuffScanner:完成:检出 {len(violations)} 条违规")
            return violations
        finally:
            os.unlink(src_path)
    
    def _parse_json_output(self, output: str) -> list[Violation]:
        """解析Ruff JSON输出。"""
        violations = []
        try:
            data = json.loads(output) if output.strip() else []
            for item in data:
                code_val = item.get("code", "")
                if isinstance(code_val, dict):
                    severity = code_val.get("severity", "warning")
                    rule_id = code_val.get("code", "")
                else:
                    severity = "warning"
                    rule_id = str(code_val)
                violations.append(Violation(
                    file=item.get("filename", ""),
                    line=item.get("location", {}).get("row", 0),
                    column=item.get("location", {}).get("column", 0),
                    severity=severity,
                    rule_id=rule_id,
                    message=item.get("message", ""),
                ))
        except json.JSONDecodeError:
            pass
        return violations


class MultiLanguageScanner:
    """多语言静态分析扫描器。"""
    
    def __init__(self):
        self._scanners = {
            "c": CppcheckScanner(),
            "cpp": ClangTidyScanner(),
            "python": [MypyScanner(), RuffScanner()],
        }
    
    def scan(self, code: str, language: str = "c", **kwargs) -> list[Violation]:
        """根据语言选择合适的扫描器。"""
        scanners = self._scanners.get(language, [])
        if not isinstance(scanners, list):
            scanners = [scanners]
        
        all_violations = []
        for scanner in scanners:
            if scanner.is_available():
                violations = scanner.scan(code, **kwargs)
                all_violations.extend(violations)
                logger.info(f"MultiLanguageScanner:{type(scanner).__name__} 检出 {len(violations)} 条违规")
            else:
                logger.warning(f"MultiLanguageScanner:{type(scanner).__name__} 不可用")
        
        return all_violations
    
    def is_available(self, language: str = "c") -> bool:
        """检查指定语言的扫描器是否可用。"""
        scanners = self._scanners.get(language, [])
        if not isinstance(scanners, list):
            scanners = [scanners]
        return any(s.is_available() for s in scanners)
    
    def get_available_languages(self) -> list[str]:
        """获取可用的语言列表。"""
        available = []
        for lang, scanners in self._scanners.items():
            if not isinstance(scanners, list):
                scanners = [scanners]
            if any(s.is_available() for s in scanners):
                available.append(lang)
        return available
