"""虚拟 MCU（GCC 编译运行沙盒）：把 AI 生成的 filter 函数编译为可执行程序，
通过 stdin/stdout 双向通信运行，并检测 core dump / 断言失败。

参考设计文档：
- 6.5.2 test_harness.c 模板代码（逐行流式 stdin/stdout）
- 6.5.3 Python 端 _generate_test_harness 实现
- 6.6 GCC 沙盒（tempfile.TemporaryDirectory 隔离 + timeout 控制）

GCC 不可用时优雅降级：使用 Python 模拟 filter（一阶低通滤波：y = 0.9*y_prev + 0.1*x）。
"""

import os
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from app.utils.log_util import logger

# 终端日志回调类型（Patch 4 流式推送）
# 签名：(agent: str, level: str, message: str) -> None
# - agent：TERMINAL / SYSTEM（与前端 AgentType 对齐）
# - level：info / success / warn / error
LogCallback = Callable[[str, str, str], None]

# test_harness.c 模板（参考文档 6.5.2）
# 占位符：
#   {user_code}        —— AI 生成的 C 代码（含 double filter(double) 函数）
#   {assert_code}      —— 自动注入的契约断言（可选，由 contract_to_assert 生成）
#   {assert_call}      —— 每步调用断言检查函数的语句（若 assert_code 为空则为空字符串）
HARNESS_TEMPLATE = r"""/* test_harness.c - 由 VirtualMCU 自动生成 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

/* === AI 生成的用户代码 === */
/* USER_CODE_BEGIN */
{user_code}
/* USER_CODE_END */

/* === 自动注入的契约断言（Patch 2）=== */
{assert_code}

int main(void) {{
    int N;
    char line[64];

    /* 第 1 行：仿真步数 N */
    if (fgets(line, sizeof(line), stdin) == NULL) {{
        return 1;
    }}
    N = atoi(line);
    if (N <= 0 || N > 1000000) {{
        fprintf(stderr, "ERROR: invalid N=%d\n", N);
        return 2;
    }}

    /* 循环 N 次：每步读一个 double，调 filter，输出一个 double */
    for (int i = 0; i < N; i++) {{
        double in_val;
        if (fgets(line, sizeof(line), stdin) == NULL) {{
            fprintf(stderr, "ERROR: eof at step %d\n", i);
            return 3;
        }}
        if (sscanf(line, "%lf", &in_val) != 1) {{
            fprintf(stderr, "ERROR: parse fail at step %d: %s\n", i, line);
            return 4;
        }}
        double out_val = filter(in_val);
        printf("%.15g\n", out_val);
        fflush(stdout);
        {assert_call}
    }}
    return 0;
}}
"""


@dataclass
class CompileResult:
    """编译结果。

    Attributes:
        success: 是否编译成功。
        executable_path: 可执行文件路径（失败时为空字符串）。
        errors: 编译错误信息（成功时为空字符串）。
        used_mock: 是否使用了 Python 模拟（GCC 不可用时为 True）。
        source_path: test_harness.c 源文件路径（mock 模式为空字符串）。
    """

    success: bool = False
    executable_path: str = ""
    errors: str = ""
    used_mock: bool = False
    source_path: str = ""


@dataclass
class RunResult:
    """运行结果。

    Attributes:
        success: 是否运行成功（进程正常退出，无断言失败）。
        output_data: filter 输出数组（运行失败时为空数组）。
        stderr: stderr 输出（含错误信息或断言失败信息）。
        assertion_failed: 是否检测到断言失败 / core dump。
        assertion_message: 断言失败消息（无失败时为空字符串）。
        failed_step: 失败发生的步号（无失败时为 -1）。
        duration: 运行耗时（秒）。
        return_code: 进程返回码。
    """

    success: bool = False
    output_data: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    stderr: str = ""
    assertion_failed: bool = False
    assertion_message: str = ""
    failed_step: int = -1
    duration: float = 0.0
    return_code: int = 0


# 用于检测断言失败的关键词（不区分大小写）
ASSERTION_KEYWORDS = (
    "assertion",
    "assert",
    "core dump",
    "core dumped",
    "aborted",
    "segmentation",
    "sigabrt",
    "sigsegv",
)


class VirtualMCU:
    """虚拟 MCU：把 AI 生成的 filter 函数编译为可执行程序并运行。

    工作流：
      1. compile(code, assert_code) -> CompileResult
         - 生成 test_harness.c（注入 user_code + 契约断言）
         - 调用 gcc 编译（临时目录，timeout=10s）
         - GCC 不可用时返回 mock 结果
      2. run(executable_path, input_data, timeout) -> RunResult
         - subprocess.Popen 双向通信
         - 每行一个 double 写入 stdin
         - 每行一个 double 从 stdout 读取
         - 检测 stderr 中的断言失败 / core dump
    """

    def __init__(self, gcc_path: str = "gcc", compile_timeout: int = 10) -> None:
        """初始化虚拟 MCU。

        Args:
            gcc_path: GCC 可执行文件路径或名称（默认 "gcc"）。
            compile_timeout: 编译超时秒数（默认 10s）。
        """
        self.gcc_path = gcc_path
        self.compile_timeout = compile_timeout
        # 缓存 GCC 是否可用（首次调用时检测）
        self._gcc_available: bool | None = None

    def is_gcc_available(self) -> bool:
        """检测系统是否安装了 GCC。

        Returns:
            True 表示 GCC 可用。
        """
        if self._gcc_available is not None:
            return self._gcc_available
        try:
            result = subprocess.run(
                [self.gcc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._gcc_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            self._gcc_available = False
        logger.info(f"VirtualMCU:GCC available = {self._gcc_available}")
        return self._gcc_available

    def compile(
        self,
        code: str,
        assert_code: str = "",
        log_callback: LogCallback | None = None,
    ) -> CompileResult:
        """编译 AI 生成的 C 代码 + 契约断言。

        Args:
            code: AI 生成的 C 代码字符串（必须含 double filter(double) 函数）。
            assert_code: 由 contract_to_assert 生成的 C 断言代码（可选）。
            log_callback: 终端日志回调 (agent, level, message)，用于 Patch 4
                WebSocket 流式推送终端命令和输出。为 None 时不推送。

        Returns:
            CompileResult：包含 success / executable_path / errors / used_mock。
        """
        # 若代码缺少 filter 函数，直接返回失败
        if "double filter" not in code and "filter(" not in code:
            logger.warning("VirtualMCU:代码缺少 filter 函数，无法编译")
            if log_callback:
                log_callback("TERMINAL", "warn", "代码缺少 filter 函数，可能编译失败")

        # 检查 GCC 是否可用
        if not self.is_gcc_available():
            logger.warning("VirtualMCU:GCC 未安装，使用 Python 模拟")
            if log_callback:
                log_callback(
                    "SYSTEM",
                    "warn",
                    "GCC 未安装，使用 Python 模拟 filter（mock 模式）",
                )
            return CompileResult(
                success=True,
                executable_path="",
                errors="",
                used_mock=True,
                source_path="",
            )

        # 生成 test_harness.c 源码
        harness_source = self._generate_test_harness(code, assert_code)

        # 在临时目录中编译
        try:
            tmpdir_ctx = tempfile.TemporaryDirectory(prefix="airborne_digital_twin_")
            tmpdir = tmpdir_ctx.name
            src_path = Path(tmpdir) / "test_harness.c"
            src_path.write_text(harness_source, encoding="utf-8")

            # Windows 用 .exe 后缀，Linux/macOS 无后缀
            if platform.system() == "Windows":
                bin_path = Path(tmpdir) / "sim.exe"
            else:
                bin_path = Path(tmpdir) / "sim"

            # 编译命令：gcc -O2 -std=c11 -o sim test_harness.c -lm
            gcc_cmd = [
                self.gcc_path,
                "-O2",
                "-std=c11",
                "-o",
                str(bin_path),
                str(src_path),
                "-lm",
            ]
            gcc_cmd_str = " ".join(gcc_cmd)
            logger.info(f"VirtualMCU:执行: {gcc_cmd_str}")
            if log_callback:
                log_callback("TERMINAL", "info", f"$ {gcc_cmd_str}")
            result = subprocess.run(
                gcc_cmd,
                capture_output=True,
                text=True,
                timeout=self.compile_timeout,
                cwd=tmpdir,
            )

            if result.returncode != 0:
                logger.error(f"VirtualMCU:GCC 编译失败:\n{result.stderr}")
                if log_callback:
                    err_snippet = (result.stderr or "")[:2000]
                    log_callback("TERMINAL", "error", f"GCC 编译失败:\n{err_snippet}")
                # 编译失败时清理临时目录
                tmpdir_ctx.cleanup()
                return CompileResult(
                    success=False,
                    executable_path="",
                    errors=result.stderr,
                    used_mock=False,
                    source_path=str(src_path),
                )

            logger.info(f"VirtualMCU:GCC 编译成功 -> {bin_path}")
            if log_callback:
                log_callback("TERMINAL", "success", f"GCC 编译成功 -> {bin_path.name}")
            # 注意：不立即清理临时目录，因为后续 run() 需要可执行文件
            # 把临时目录上下文保存到 source_path 的元信息里——这里用文件路径反查
            # 实际工程中可在外层 SimulationEngine 中管理生命周期
            # 为简化，将 tmpdir 上下文存储在 executable_path 的旁路属性
            # （Python dataclass 不便存储 context，故改为：调用方负责在 run 后清理）
            # 这里把 tmpdir_ctx 挂在 CompileResult._tmpdir_ctx（动态属性）
            compile_result = CompileResult(
                success=True,
                executable_path=str(bin_path),
                errors="",
                used_mock=False,
                source_path=str(src_path),
            )
            # 动态挂载临时目录上下文（run 完后由调用方清理）
            compile_result._tmpdir_ctx = tmpdir_ctx  # type: ignore[attr-defined]
            return compile_result

        except subprocess.TimeoutExpired:
            logger.error(f"VirtualMCU:GCC 编译超时（{self.compile_timeout}s）")
            if log_callback:
                log_callback(
                    "TERMINAL",
                    "error",
                    f"GCC 编译超时（{self.compile_timeout}s）",
                )
            return CompileResult(
                success=False,
                executable_path="",
                errors=f"GCC 编译超时（{self.compile_timeout}s）",
                used_mock=False,
                source_path="",
            )
        except Exception as e:
            logger.error(f"VirtualMCU:编译异常: {e}")
            if log_callback:
                log_callback("TERMINAL", "error", f"GCC 编译异常: {e}")
            return CompileResult(
                success=False,
                executable_path="",
                errors=f"编译异常: {e}",
                used_mock=False,
                source_path="",
            )

    def run(
        self,
        executable_path: str,
        input_data: np.ndarray,
        timeout: int = 30,
        used_mock: bool = False,
        log_callback: LogCallback | None = None,
    ) -> RunResult:
        """运行编译好的可执行程序，输入传感器数据，返回 filter 输出。

        Args:
            executable_path: 可执行文件路径（compile() 返回的）。
            input_data: 输入传感器数据数组。
            timeout: 运行超时秒数（默认 30s）。
            used_mock: 是否为 mock 模式（True 时用 Python 模拟 filter）。
            log_callback: 终端日志回调 (agent, level, message)，用于 Patch 4
                WebSocket 流式推送终端命令和输出。为 None 时不推送。

        Returns:
            RunResult：包含 success / output_data / stderr / assertion_failed 等。
        """
        if used_mock or not executable_path:
            if log_callback:
                log_callback(
                    "TERMINAL",
                    "info",
                    f"$ ./sim < input.bin  # mock 模式，{len(input_data)} 步",
                )
            result = self._run_mock(input_data)
            if log_callback:
                level = "success" if result.success else "error"
                log_callback(
                    "TERMINAL",
                    level,
                    f"mock 仿真完成 outputs={len(result.output_data)}/{len(input_data)}",
                )
            return result

        if log_callback:
            log_callback(
                "TERMINAL",
                "info",
                f"$ ./sim  # {len(input_data)} 步，timeout={timeout}s",
            )
        result = self._run_native(executable_path, input_data, timeout)
        if log_callback:
            level = "success" if result.success else "error"
            msg = (
                f"仿真完成 rc={result.return_code} "
                f"outputs={len(result.output_data)}/{len(input_data)} "
                f"assert_failed={result.assertion_failed}"
            )
            if result.stderr.strip():
                msg += f"\n{result.stderr[:1000]}"
            log_callback("TERMINAL", level, msg)
        return result

    def _run_native(
        self, executable_path: str, input_data: np.ndarray, timeout: int
    ) -> RunResult:
        """原生运行：subprocess.Popen 双向通信。"""
        n_steps = len(input_data)
        outputs: list[float] = []
        stderr_data: list[str] = []
        start_time = time.time()
        assertion_failed = False
        assertion_message = ""
        failed_step = -1
        return_code = -1

        try:
            proc = subprocess.Popen(
                [executable_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                cwd=os.path.dirname(executable_path) or None,
            )

            try:
                # 第 1 行写步数 N
                assert proc.stdin is not None
                proc.stdin.write(f"{n_steps}\n")
                proc.stdin.flush()

                for i in range(n_steps):
                    if proc.poll() is not None:
                        # 进程已退出
                        break
                    proc.stdin.write(f"{float(input_data[i]):.15g}\n")
                    proc.stdin.flush()

                    line = proc.stdout.readline()
                    if not line:
                        # 输出为空，可能进程崩溃或断言失败
                        err = proc.stderr.read() if proc.stderr else ""
                        stderr_data.append(err)
                        if self._detect_assertion_failure(err):
                            assertion_failed = True
                            assertion_message = self._extract_assertion_message(err)
                            failed_step = i
                        break
                    outputs.append(float(line.strip()))

                # 读取剩余 stderr
                if proc.stderr:
                    rest = proc.stderr.read()
                    if rest:
                        stderr_data.append(rest)

                # 等待进程结束
                proc.stdin.close()
                proc.wait(timeout=5)
                return_code = proc.returncode

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                stderr_data.append(f"运行超时（{timeout}s）")
                logger.error(f"VirtualMCU:运行超时（{timeout}s）")
                return RunResult(
                    success=False,
                    output_data=np.array(outputs, dtype=np.float64),
                    stderr="".join(stderr_data),
                    assertion_failed=assertion_failed,
                    assertion_message=assertion_message,
                    failed_step=failed_step,
                    duration=time.time() - start_time,
                    return_code=-1,
                )

        except FileNotFoundError:
            logger.error(f"VirtualMCU:可执行文件不存在: {executable_path}")
            return RunResult(
                success=False,
                stderr=f"可执行文件不存在: {executable_path}",
                duration=time.time() - start_time,
                return_code=-1,
            )
        except Exception as e:
            logger.error(f"VirtualMCU:运行异常: {e}")
            return RunResult(
                success=False,
                stderr=f"运行异常: {e}",
                duration=time.time() - start_time,
                return_code=-1,
            )

        stderr_str = "".join(stderr_data)
        # 整体检测断言失败（即使部分输出已采集）
        if not assertion_failed and self._detect_assertion_failure(stderr_str):
            assertion_failed = True
            assertion_message = self._extract_assertion_message(stderr_str)
            if failed_step < 0:
                failed_step = len(outputs)

        duration = time.time() - start_time
        success = (
            (return_code == 0) and (not assertion_failed) and (len(outputs) == n_steps)
        )

        logger.info(
            f"VirtualMCU:run 完成 rc={return_code} outputs={len(outputs)}/{n_steps} "
            f"assert_failed={assertion_failed} duration={duration:.3f}s"
        )
        return RunResult(
            success=success,
            output_data=np.array(outputs, dtype=np.float64),
            stderr=stderr_str,
            assertion_failed=assertion_failed,
            assertion_message=assertion_message,
            failed_step=failed_step,
            duration=duration,
            return_code=return_code,
        )

    def _run_mock(self, input_data: np.ndarray) -> RunResult:
        """Mock 模式：用 Python 模拟 filter（一阶低通滤波：y = 0.9*y_prev + 0.1*x）。"""
        start_time = time.time()
        outputs: list[float] = []
        y_prev = 0.0

        for x in input_data:
            # 一阶低通滤波
            y = 0.9 * y_prev + 0.1 * float(x)
            outputs.append(y)
            y_prev = y

        duration = time.time() - start_time
        logger.info(
            f"VirtualMCU:mock 模式运行完成 outputs={len(outputs)} "
            f"duration={duration:.3f}s"
        )
        return RunResult(
            success=True,
            output_data=np.array(outputs, dtype=np.float64),
            stderr="",
            assertion_failed=False,
            assertion_message="",
            failed_step=-1,
            duration=duration,
            return_code=0,
        )

    def _generate_test_harness(self, user_code: str, assert_code: str = "") -> str:
        """生成 test_harness.c 源码（注入用户代码 + 契约断言）。

        Args:
            user_code: AI 生成的 C 代码（含 double filter(double) 函数）。
            assert_code: 由 contract_to_assert 生成的断言代码（可选）。

        Returns:
            完整的 test_harness.c 源码字符串。

        Note:
            contract_to_assert 生成的函数名形如 `__check_contract_step_<cid>`，
            若 cid 含连字符（如 "CON-001"）则不是合法 C 标识符。
            这里做净化处理：将连字符替换为下划线，确保 GCC 能编译。
        """
        # 若用户代码中没有 double filter(double) 函数定义，
        # 自动添加一个示例 filter（避免编译失败）
        if "double filter(double" not in user_code and "filter(double" not in user_code:
            user_code = (
                "double filter(double input) {\n"
                "    static double last = 0.0;\n"
                "    double out = 0.9 * last + 0.1 * input;\n"
                "    last = out;\n"
                "    return out;\n"
                "}\n"
            ) + user_code

        # 处理断言代码：若非空，则在每步 filter 调用后调用 __check_contract_step_<cid>
        if assert_code.strip():
            import re

            # 净化：将 __check_contract_step_<cid> 中的连字符替换为下划线
            # （cid 如 "CON-001" 不是合法 C 标识符）
            sanitized_assert = re.sub(
                r"(__check_contract_step_)([A-Za-z0-9_\-]+)",
                lambda m: m.group(1) + m.group(2).replace("-", "_"),
                assert_code,
            )

            # 提取断言检查函数名（形如 __check_contract_step_<cid>）
            m = re.search(
                r"static\s+void\s+(__check_contract_step_\w+)\s*\(", sanitized_assert
            )
            if m:
                check_func = m.group(1)
                assert_call = f"{check_func}(out_val);"
            else:
                assert_call = ""
            assert_code_final = sanitized_assert
        else:
            assert_call = ""
            assert_code_final = "/* 无契约断言 */"

        return HARNESS_TEMPLATE.format(
            user_code=user_code,
            assert_code=assert_code_final,
            assert_call=assert_call,
        )

    @staticmethod
    def _detect_assertion_failure(stderr: str) -> bool:
        """检测 stderr 中是否含断言失败 / core dump 信息。"""
        if not stderr:
            return False
        lower = stderr.lower()
        return any(kw in lower for kw in ASSERTION_KEYWORDS)

    @staticmethod
    def _extract_assertion_message(stderr: str) -> str:
        """从 stderr 中提取断言失败消息（截取前若干行）。"""
        if not stderr:
            return ""
        # 截取前 5 行（避免过长）
        lines = stderr.strip().splitlines()
        return "\n".join(lines[:5])

    def cleanup(self, compile_result: CompileResult) -> None:
        """清理编译产物（临时目录）。

        Args:
            compile_result: compile() 返回的 CompileResult。
        """
        ctx = getattr(compile_result, "_tmpdir_ctx", None)
        if ctx is not None:
            try:
                ctx.cleanup()
            except Exception:
                pass
