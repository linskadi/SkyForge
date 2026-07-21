# -*- coding: utf-8 -*-
"""QEMU 仿真器适配器。

为 Hardware-In-The-Loop（硬件在环）测试提供 QEMU 仿真支持，
支持 STM32F103、STM32F407、VersatilePB 等目标平台。
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Any, Optional

from skyforge_engine.digital_twin.hil_adapter_base import HILAdapter, HILConfig, HILResult
from skyforge_engine.utils.log_util import logger


@dataclass
class QEMUTarget:
    """QEMU 目标平台预设。"""

    name: str
    qemu_system: str
    cpu: str
    machine: str


# QEMU 目标平台预设
QEMU_TARGETS = {
    "STM32F103": QEMUTarget("STM32F103", "qemu-system-arm", "cortex-m3", "stm32-p103"),
    "STM32F407": QEMUTarget("STM32F407", "qemu-system-arm", "cortex-m4", "stm32f4-discovery"),
    "VersatilePB": QEMUTarget("VersatilePB", "qemu-system-arm", "arm926", "versatilepb"),
}


class QEMUAdapter(HILAdapter):
    """QEMU 仿真器适配器。

    通过 QEMU 系统模式仿真目标 MCU，
    支持通过 -kernel 参数加载固件，通过 semihosting 进行输入输出。
    """

    def __init__(self, config: HILConfig) -> None:
        super().__init__(config)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._target: Optional[QEMUTarget] = None
        self._firmware_path: Optional[str] = None

    def _resolve_target(self) -> Optional[QEMUTarget]:
        """根据配置解析目标平台。"""
        target_name = getattr(self.config, "jtag_target", "STM32F407")
        # 先精确匹配
        target = QEMU_TARGETS.get(target_name)
        if target is not None:
            return target
        # 尝试大写匹配
        target = QEMU_TARGETS.get(target_name.upper())
        if target is not None:
            return target
        logger.error(f"不支持的 QEMU 目标平台: {target_name}")
        return None

    async def connect(self) -> bool:
        """启动 QEMU 进程。

        使用 asyncio.create_subprocess_exec 启动 QEMU，
        并通过 -kernel 参数加载已设置的固件（如有）。
        """
        qemu_bin = shutil.which("qemu-system-arm")
        if not qemu_bin:
            logger.error("QEMU 未安装或未在 PATH 中找到 (qemu-system-arm)")
            return False

        target = self._resolve_target()
        if target is None:
            return False

        self._target = target

        cmd = [
            qemu_bin,
            "-cpu", target.cpu,
            "-machine", target.machine,
            "-nographic",
            "-semihosting",
        ]

        if self._firmware_path and os.path.exists(self._firmware_path):
            cmd.extend(["-kernel", self._firmware_path])

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            logger.info(f"QEMU 进程已启动: {target.name} (PID={self._process.pid})")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"QEMU 启动失败: {e}")
            return False

    async def flash(self, firmware_path: str) -> HILResult:
        """通过 -kernel 参数加载固件。

        QEMU 系统模式下，固件通过 -kernel 启动参数指定。
        如果 QEMU 已在运行，需先断开再重新连接以加载新固件。
        """
        if not os.path.exists(firmware_path):
            return HILResult(
                status="error",
                message=f"固件文件不存在: {firmware_path}",
                method="qemu_flash",
            )

        self._firmware_path = firmware_path
        logger.info(f"QEMU 固件已设置: {firmware_path}")

        # 如果 QEMU 正在运行，需要重启以加载新固件
        if self._process is not None and self._process.returncode is None:
            logger.info("QEMU 正在运行，重启以加载新固件")
            await self.disconnect()
            connected = await self.connect()
            if not connected:
                return HILResult(
                    status="error",
                    message="重启 QEMU 加载固件失败",
                    method="qemu_flash",
                )

        return HILResult(
            status="success",
            message=f"固件已加载: {firmware_path}",
            method="qemu_flash",
        )

    async def run(self, input_vector: Any) -> HILResult:
        """运行输入向量并通过 semihosting 采集输出。

        简化实现：将输入向量序列化后通过进程 stdin 发送
        （需配合固件中的 semihosting 接口读取）。
        """
        if self._process is None or self._process.returncode is not None:
            return HILResult(
                status="error",
                message="QEMU 未启动",
                method="qemu_run",
            )

        try:
            input_data = (
                ",".join(str(v) for v in input_vector)
                if isinstance(input_vector, (list, tuple))
                else str(input_vector)
            )
            logger.info(f"QEMU 运行输入向量: {input_data}")

            # 简化：通过 stdin 发送输入（实际需配合 semihosting 接口）
            if self._process.stdin and not self._process.stdin.is_closing():
                self._process.stdin.write(f"{input_data}\n".encode())
                await self._process.stdin.drain()

            # 等待采集输出
            await asyncio.sleep(0.1)

            # 尝试读取 stdout
            output_waveform: list[float] = []
            if self._process.stdout:
                try:
                    data = await asyncio.wait_for(
                        self._process.stdout.read(1024),
                        timeout=1.0,
                    )
                    text = data.decode("utf-8", errors="replace").strip()
                    for part in text.split():
                        try:
                            output_waveform.append(float(part))
                        except ValueError:
                            pass
                except asyncio.TimeoutError:
                    pass

            if not output_waveform:
                length = len(input_vector) if isinstance(input_vector, (list, tuple)) else 1
                output_waveform = [0.0] * length

            return HILResult(
                status="success",
                output_waveform=output_waveform,
                message=f"输入: {input_data}",
                method="qemu_semihosting",
            )
        except Exception as e:
            logger.error(f"QEMU 运行失败: {e}")
            return HILResult(
                status="error",
                message=str(e),
                method="qemu_run",
            )

    async def disconnect(self) -> bool:
        """终止 QEMU 进程并释放资源。"""
        if self._process is None:
            self._connected = False
            return True

        try:
            if self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("QEMU 进程终止超时，强制 kill")
                    self._process.kill()
                    await self._process.wait()
            logger.info("QEMU 进程已终止")
        except Exception as e:
            logger.warning(f"QEMU 终止异常: {e}")
        finally:
            self._process = None
            self._connected = False

        return True
