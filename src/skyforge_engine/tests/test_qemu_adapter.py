# -*- coding: utf-8 -*-
"""QEMU 适配器测试。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


from skyforge_engine.digital_twin.hil_adapter_base import HILConfig, HILMode
from skyforge_engine.digital_twin.qemu_adapter import QEMUAdapter, QEMU_TARGETS


class TestQEMUAdapter:
    """QEMU 适配器测试套件。"""

    def _create_adapter(self, target: str = "STM32F407") -> QEMUAdapter:
        config = HILConfig(mode=HILMode.QEMU, jtag_target=target)
        return QEMUAdapter(config)

    @patch("shutil.which")
    def test_qemu_not_found_returns_error(self, mock_which):
        """QEMU 未安装时 connect() 应返回 False。"""
        mock_which.return_value = None
        adapter = self._create_adapter()
        result = asyncio.run(adapter.connect())
        assert result is False
        assert adapter._connected is False

    @patch("shutil.which")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_connect_starts_qemu_process(self, mock_subprocess, mock_which):
        """connect() 应使用 asyncio.create_subprocess_exec 启动 QEMU 进程。"""
        mock_which.return_value = "/usr/bin/qemu-system-arm"
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_subprocess.return_value = mock_process

        adapter = self._create_adapter()
        result = asyncio.run(adapter.connect())
        assert result is True
        assert adapter._connected is True
        assert adapter._process is mock_process
        mock_subprocess.assert_awaited_once()

        # 验证命令参数包含目标平台
        call_args = mock_subprocess.call_args[0]
        assert "-cpu" in call_args
        assert "cortex-m4" in call_args
        assert "-machine" in call_args
        assert "stm32f4-discovery" in call_args
        assert "-nographic" in call_args
        assert "-semihosting" in call_args

    @patch("shutil.which")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_disconnect_terminates_process(self, mock_subprocess, mock_which):
        """disconnect() 应终止 QEMU 进程并清理状态。"""
        mock_which.return_value = "/usr/bin/qemu-system-arm"
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        adapter = self._create_adapter()
        asyncio.run(adapter.connect())
        assert adapter._connected is True

        result = asyncio.run(adapter.disconnect())
        assert result is True
        assert adapter._connected is False
        assert adapter._process is None
        mock_process.terminate.assert_called_once()

    @patch("shutil.which")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_flash_restarts_qemu_with_kernel(self, mock_subprocess, mock_which):
        """flash() 应通过 -kernel 参数加载固件，并重启 QEMU 进程。"""
        mock_which.return_value = "/usr/bin/qemu-system-arm"
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        adapter = self._create_adapter()
        asyncio.run(adapter.connect())

        # 模拟固件文件存在
        with patch("os.path.exists", return_value=True):
            result = asyncio.run(adapter.flash("/tmp/firmware.elf"))

        assert result.status == "success"
        assert result.method == "qemu_flash"

        # connect 启动一次，flash 重启一次，共两次
        assert mock_subprocess.call_count == 2
        second_call_args = mock_subprocess.call_args_list[1][0]
        assert "-kernel" in second_call_args
        assert "/tmp/firmware.elf" in second_call_args

    def test_qemu_targets_preset(self):
        """QEMU 目标平台预设应包含 STM32F103、STM32F407、VersatilePB。"""
        assert "STM32F103" in QEMU_TARGETS
        assert "STM32F407" in QEMU_TARGETS
        assert "VersatilePB" in QEMU_TARGETS

        target = QEMU_TARGETS["STM32F103"]
        assert target.qemu_system == "qemu-system-arm"
        assert target.cpu == "cortex-m3"
        assert target.machine == "stm32-p103"

        target = QEMU_TARGETS["STM32F407"]
        assert target.qemu_system == "qemu-system-arm"
        assert target.cpu == "cortex-m4"
        assert target.machine == "stm32f4-discovery"

        target = QEMU_TARGETS["VersatilePB"]
        assert target.qemu_system == "qemu-system-arm"
        assert target.cpu == "arm926"
        assert target.machine == "versatilepb"

    @patch("shutil.which")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_without_connect_returns_error(self, mock_subprocess, mock_which):
        """未连接时 run() 应返回错误。"""
        adapter = self._create_adapter()
        result = asyncio.run(adapter.run([1.0, 2.0, 3.0]))
        assert result.status == "error"
        assert "QEMU 未启动" in result.message

    @patch("shutil.which")
    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    def test_run_with_input_returns_waveform(self, mock_subprocess, mock_which):
        """连接后 run() 应返回输出波形。"""
        mock_which.return_value = "/usr/bin/qemu-system-arm"
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdin = MagicMock()
        mock_process.stdin.is_closing.return_value = False
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stdout.read = AsyncMock(return_value=b"1.5 2.5 3.5")
        mock_subprocess.return_value = mock_process

        adapter = self._create_adapter()
        asyncio.run(adapter.connect())

        result = asyncio.run(adapter.run([1.0, 2.0, 3.0]))
        assert result.status == "success"
        assert result.method == "qemu_semihosting"
        assert result.output_waveform == [1.5, 2.5, 3.5]
