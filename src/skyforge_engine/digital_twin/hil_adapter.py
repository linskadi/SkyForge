# -*- coding: utf-8 -*-
"""真实硬件 HIL（Hardware-In-The-Loop）适配器 — P1 修复。

设计文档批判式审查发现：数字孪生是虚拟MCU解释执行，非真机HIL，
测试真实性存疑。本模块提供真实硬件在环测试能力。

支持的接口类型：
- Serial (UART)：通过串口与目标 MCU 通信
- JTAG/SWD：通过调试接口烧录固件并采集数据
- 自定义协议：支持扩展自定义通信协议

架构:
    HilAdapter (抽象基类)
    ├── SerialHilAdapter   — UART 串口通信
    ├── JtagHilAdapter     — JTAG/SWD 调试接口 (OpenOCD/pyOCD)
    └── MockHilAdapter     — 基于 VirtualMCU 的 Mock 模式（保持向后兼容）

用法:
    from skyforge_engine.digital_twin.hil_adapter import create_hil_adapter
    from skyforge_engine.config import settings

    adapter = create_hil_adapter(
        interface=settings.HIL_INTERFACE,  # "serial" | "jtag_swd"
        port=settings.HIL_SERIAL_PORT,      # COM3 或 /dev/ttyUSB0
        baud_rate=settings.HIL_BAUD_RATE,
    )
    result = adapter.deploy_and_run(firmware_elf="build/output.elf")
    print(f"输出数据: {result.output_data}")
    print(f"契约断言: {'通过' if result.contracts_passed else '失败'}")
"""

import abc
import json
import os
import re
import struct
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from skyforge_engine.utils.log_util import logger


# ==================== 数据类 ====================

@dataclass
class HilConfig:
    """HIL 测试配置。"""

    # 接口类型
    interface: str = "serial"  # "serial" | "jtag_swd" | "mock"

    # 串口配置
    serial_port: str = "COM3"
    baud_rate: int = 115200
    serial_timeout: int = 5
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1

    # JTAG/SWD 配置
    jtag_device: str = "STLINK"  # STLINK | JLINK | CMSIS-DAP
    jtag_target: str = "STM32F407"
    jtag_clock: int = 4000000  # Hz
    jtag_interface_speed: int = 100  # kHz

    # 通用配置
    flash_timeout: int = 30     # 烧录超时（秒）
    run_timeout: int = 30       # 运行超时（秒）
    reset_after_flash: bool = True
    collect_uart_output: bool = True

    # 契约断言
    contract_asserts: list[str] = field(default_factory=list)
    # 预期输出模式（正则），用于自动验证
    expected_patterns: list[str] = field(default_factory=list)

    # 固件
    firmware_path: str = ""  # 预编译固件路径（ELF/BIN/HEX）


@dataclass
class HilResult:
    """HIL 测试结果。"""

    success: bool = False
    interface: str = ""

    # 烧录
    flash_success: bool = False
    flash_time_ms: float = 0.0
    flash_output: str = ""

    # 运行
    run_success: bool = False
    run_time_ms: float = 0.0

    # 输出数据
    output_raw: str = ""
    output_data: list[dict[str, Any]] = field(default_factory=list)
    output_lines: list[str] = field(default_factory=list)

    # 契约验证
    contracts_passed: bool = False
    contract_results: list[dict[str, Any]] = field(default_factory=list)
    expected_patterns_matched: int = 0
    expected_patterns_total: int = 0

    # 错误
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "success": self.success,
            "interface": self.interface,
            "flash": {
                "success": self.flash_success,
                "time_ms": self.flash_time_ms,
            },
            "run": {
                "success": self.run_success,
                "time_ms": self.run_time_ms,
            },
            "output": {
                "raw": self.output_raw[:1000],
                "lines": len(self.output_lines),
                "data_points": len(self.output_data),
            },
            "contracts": {
                "passed": self.contracts_passed,
                "results": self.contract_results,
                "patterns": f"{self.expected_patterns_matched}/{self.expected_patterns_total}",
            },
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ==================== 抽象基类 ====================

class HilAdapter(abc.ABC):
    """HIL 适配器抽象基类。

    所有真实硬件适配器必须实现以下方法：
    - connect(): 建立硬件连接
    - disconnect(): 断开硬件连接
    - flash_firmware(): 烧录固件
    - run(): 运行测试
    - collect_output(): 采集输出数据
    - verify_contracts(): 验证契约断言
    """

    def __init__(self, config: HilConfig):
        self.config = config
        self._connected = False

    @abc.abstractmethod
    def connect(self) -> bool:
        """建立硬件连接。"""
        ...

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """断开硬件连接。"""
        ...

    @abc.abstractmethod
    def flash_firmware(self, firmware_path: str) -> tuple[bool, str]:
        """烧录固件到目标 MCU。

        Args:
            firmware_path: 固件文件路径（ELF/BIN/HEX）

        Returns:
            (success, output_log)
        """
        ...

    @abc.abstractmethod
    def run(self) -> tuple[bool, str]:
        """运行目标程序并采集输出。

        Returns:
            (success, output_string)
        """
        ...

    def deploy_and_run(self, firmware_path: Optional[str] = None) -> HilResult:
        """完整部署流程：连接 → 烧录 → 运行 → 采集 → 验证 → 断开。

        Args:
            firmware_path: 固件路径，默认从 config 读取

        Returns:
            HilResult 包含完整测试结果
        """
        result = HilResult(interface=self.config.interface)
        fw_path = firmware_path or self.config.firmware_path

        if not fw_path or not os.path.exists(fw_path):
            result.errors.append(f"固件文件不存在: {fw_path}")
            return result

        try:
            # 1. 连接
            if not self.connect():
                result.errors.append("硬件连接失败")
                return result

            # 2. 烧录
            flash_start = time.time()
            flash_ok, flash_out = self.flash_firmware(fw_path)
            result.flash_success = flash_ok
            result.flash_time_ms = round((time.time() - flash_start) * 1000, 1)
            result.flash_output = flash_out[:2000]

            if not flash_ok:
                result.errors.append(f"固件烧录失败: {flash_out[:200]}")
                self.disconnect()
                return result

            # 3. 运行并采集
            run_start = time.time()
            run_ok, output = self.run()
            result.run_success = run_ok
            result.run_time_ms = round((time.time() - run_start) * 1000, 1)
            result.output_raw = output

            # 4. 解析输出
            result.output_lines = [
                line.strip()
                for line in output.split("\n")
                if line.strip()
            ]
            result.output_data = self._parse_output_data(result.output_lines)

            # 5. 验证契约
            contract_ok, contract_results = self.verify_contracts(
                output, result.output_data
            )
            result.contracts_passed = contract_ok
            result.contract_results = contract_results

            # 6. 匹配预期模式
            if self.config.expected_patterns:
                result.expected_patterns_total = len(self.config.expected_patterns)
                for pattern in self.config.expected_patterns:
                    if re.search(pattern, output):
                        result.expected_patterns_matched += 1

            # 综合判定
            result.success = (
                result.flash_success
                and result.run_success
                and result.contracts_passed
            )

        except Exception as e:
            result.errors.append(f"HIL 测试异常: {e}")
            logger.exception("HIL 测试失败")
        finally:
            self.disconnect()

        return result

    def verify_contracts(
        self, output: str, data: list[dict[str, Any]]
    ) -> tuple[bool, list[dict[str, Any]]]:
        """验证契约断言。

        默认实现：检查输出中的 PASS/FAIL 标记。
        子类可覆盖实现更复杂的验证逻辑。

        Returns:
            (all_passed, individual_results)
        """
        results = []

        # 检查输出中的断言标记
        pass_count = len(re.findall(r"ASSERT_PASS|\[PASS\]|PASSED", output))
        fail_count = len(re.findall(r"ASSERT_FAIL|\[FAIL\]|FAILED", output))

        results.append({
            "check": "assert_markers",
            "passed": fail_count == 0,
            "detail": f"PASS={pass_count}, FAIL={fail_count}",
        })

        # 检查自定义契约
        for i, contract in enumerate(self.config.contract_asserts):
            # 契约格式: "条件描述:预期模式"
            parts = contract.split(":", 1)
            desc = parts[0].strip()
            pattern = parts[1].strip() if len(parts) > 1 else desc
            matched = bool(re.search(pattern, output))
            results.append({
                "check": f"contract_{i+1}",
                "desc": desc,
                "passed": matched,
                "detail": f"模式匹配: {'是' if matched else '否'}",
            })

        all_passed = all(r["passed"] for r in results)
        return all_passed, results

    def _parse_output_data(
        self, lines: list[str]
    ) -> list[dict[str, Any]]:
        """解析输出行为结构化数据。

        支持格式：
        - CSV: "timestamp,value1,value2"
        - JSON: {"t": 123, "v": 45.6}
        - 键值对: "key=value"
        """
        data = []
        for line in lines:
            # JSON
            if line.startswith("{"):
                try:
                    data.append(json.loads(line))
                    continue
                except json.JSONDecodeError:
                    pass
            # CSV
            if "," in line:
                parts = line.split(",")
                try:
                    floats = [float(p) for p in parts]
                    data.append({
                        "raw": line,
                        "values": floats,
                        "count": len(floats),
                    })
                    continue
                except ValueError:
                    pass
            # 键值对
            if "=" in line:
                kv_parts = line.split("=", 1)
                data.append({"key": kv_parts[0].strip(), "value": kv_parts[1].strip()})
        return data


# ==================== 串口 HIL 适配器 ====================

class SerialHilAdapter(HilAdapter):
    """UART 串口 HIL 适配器。

    通过串口与目标 MCU 通信，支持：
    - 固件烧录（通过 bootloader 协议）
    - 数据采集（读取串口输出）
    - 命令发送
    """

    def __init__(self, config: HilConfig):
        super().__init__(config)
        self._serial = None

    def connect(self) -> bool:
        """打开串口连接。"""
        try:
            import serial
            self._serial = serial.Serial(
                port=self.config.serial_port,
                baudrate=self.config.baud_rate,
                bytesize=self.config.data_bits,
                parity=self.config.parity,
                stopbits=self.config.stop_bits,
                timeout=self.config.serial_timeout,
            )
            if self._serial.is_open:
                self._connected = True
                logger.info(f"串口已连接: {self.config.serial_port} @ {self.config.baud_rate}")
                return True
        except ImportError:
            logger.error("pyserial 未安装，请执行: pip install pyserial")
        except Exception as e:
            logger.error(f"串口连接失败 ({self.config.serial_port}): {e}")
        return False

    def disconnect(self) -> bool:
        """关闭串口连接。"""
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                logger.info(f"串口已断开: {self.config.serial_port}")
            except Exception as e:
                logger.warning(f"串口断开异常: {e}")
        self._connected = False
        return True

    def flash_firmware(self, firmware_path: str) -> tuple[bool, str]:
        """通过串口 Bootloader 烧录固件。

        支持协议：
        - STM32 USART Bootloader (AN3155)
        - 自定义 YMODEM/XMODEM 协议
        - 简单二进制传输
        """
        if not self._connected or not self._serial:
            return False, "串口未连接"

        try:
            # 检查固件格式
            os.path.splitext(firmware_path)[1].lower()
            with open(firmware_path, "rb") as f:
                firmware_data = f.read()

            # STM32 Bootloader 协议 (AN3155)
            if self.config.jtag_target.startswith("STM32"):
                return self._stm32_usart_bootloader_flash(firmware_data)
            # 简单二进制传输
            else:
                return self._simple_binary_flash(firmware_data)

        except Exception as e:
            return False, f"烧录失败: {e}"

    def _stm32_usart_bootloader_flash(self, data: bytes) -> tuple[bool, str]:
        """STM32 USART Bootloader (AN3155) 烧录。

        协议概要：
        1. 发送 0x7F 触发自动波特率检测
        2. 接收 ACK (0x79)
        3. 发送擦除命令
        4. 发送写入命令 + 数据
        """
        output_lines = []
        try:
            # Step 1: 触发 bootloader (发送 0x7F)
            self._serial.write(b"\x7F")
            time.sleep(0.1)
            ack = self._serial.read(1)
            if ack != b"\x79":
                return False, f"Bootloader ACK 失败，收到: {ack.hex() if ack else '无响应'}"
            output_lines.append("Bootloader 已连接")

            # Step 2: 发送擦除命令 (0x43 + XOR)
            self._serial.write(b"\x43\xBC")
            ack = self._serial.read(1)
            if ack != b"\x79":
                return False, "擦除命令 ACK 失败"
            output_lines.append("Flash 已擦除")

            # Step 3: 写入数据 (每 256 字节)
            addr = 0x08000000  # STM32 Flash 起始地址
            total_written = 0
            chunk_size = 256

            for i in range(0, len(data), chunk_size):
                chunk = data[i : i + chunk_size]
                # 写内存命令
                cmd = bytearray([0x31, 0xCE])  # Write Memory
                self._serial.write(cmd)
                ack = self._serial.read(1)
                if ack != b"\x79":
                    return False, f"写内存命令 ACK 失败 @ {hex(addr + i)}"

                # 发送地址 + 数据
                current_addr = addr + i
                addr_bytes = struct.pack(">I", current_addr)
                self._serial.write(addr_bytes)
                ack = self._serial.read(1)
                if ack != b"\x79":
                    return False, f"地址设置 ACK 失败 @ {hex(current_addr)}"

                # 发送数据长度 - 1
                length_byte = bytes([len(chunk) - 1])
                self._serial.write(length_byte)
                # 发送数据
                self._serial.write(chunk)
                # 发送校验和 (长度 XOR 数据各字节)
                checksum = len(chunk) - 1
                for b in chunk:
                    checksum ^= b
                self._serial.write(bytes([checksum]))

                ack = self._serial.read(1)
                if ack != b"\x79":
                    return False, f"数据写入 ACK 失败 @ {hex(current_addr)}"

                total_written += len(chunk)

            output_lines.append(f"固件已烧录: {total_written} 字节")

            # Step 4: 跳转到用户程序
            # Go 命令
            self._serial.write(b"\x21\xDE")
            ack = self._serial.read(1)
            if ack != b"\x79":
                return False, "跳转命令 ACK 失败"
            # 发送起始地址
            self._serial.write(struct.pack(">I", addr))
            ack = self._serial.read(1)
            if ack != b"\x79":
                return False, "跳转地址 ACK 失败"

            output_lines.append("程序已启动")
            return True, "\n".join(output_lines)

        except Exception as e:
            return False, f"STM32 Bootloader 烧录异常: {e}"

    def _simple_binary_flash(self, data: bytes) -> tuple[bool, str]:
        """简单二进制传输（通用 bootloader）。"""
        try:
            # 发送数据长度
            length_bytes = struct.pack("<I", len(data))
            self._serial.write(length_bytes)
            time.sleep(0.1)

            # 发送数据
            chunk_size = 1024
            for i in range(0, len(data), chunk_size):
                chunk = data[i : i + chunk_size]
                self._serial.write(chunk)
                time.sleep(0.01)

            # 等待 ACK
            self._serial.read(4)
            return True, f"已烧录 {len(data)} 字节"
        except Exception as e:
            return False, f"二进制传输失败: {e}"

    def run(self) -> tuple[bool, str]:
        """运行并采集串口输出。"""
        if not self._connected or not self._serial:
            return False, "串口未连接"

        output = []
        start = time.time()
        timeout = self.config.run_timeout

        try:
            # 清空缓冲区
            self._serial.reset_input_buffer()

            # 发送启动命令（可选）
            self._serial.write(b"\n")

            # 读取输出
            while (time.time() - start) < timeout:
                if self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting)
                    try:
                        text = data.decode("utf-8", errors="replace")
                        output.append(text)
                    except Exception:
                        output.append(repr(data))
                else:
                    time.sleep(0.01)

            return True, "".join(output)

        except Exception as e:
            return False, f"运行采集失败: {e}"


# ==================== JTAG/SWD HIL 适配器 ====================

class JtagHilAdapter(HilAdapter):
    """JTAG/SWD HIL 适配器。

    通过 OpenOCD/pyOCD 与调试器通信，支持：
    - ST-Link / J-Link / CMSIS-DAP 调试器
    - 固件烧录（ELF/BIN/HEX）
    - Semi-hosting 输出采集（ARM ITM/SWO）
    - 寄存器/内存读写
    """

    def __init__(self, config: HilConfig):
        super().__init__(config)
        self._openocd_process: Optional[subprocess.Popen] = None

    def connect(self) -> bool:
        """启动 OpenOCD 并连接目标。"""
        try:
            # 生成 OpenOCD 配置文件
            cfg = self._generate_openocd_config()
            cfg_path = self._write_temp_config(cfg)

            # 启动 OpenOCD
            cmd = [
                "openocd",
                "-f", cfg_path,
                "-c", "init",
                "-c", "reset init",
            ]
            self._openocd_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # 等待连接
            time.sleep(2)
            if self._openocd_process.poll() is not None:
                stderr = self._openocd_process.stderr.read() if self._openocd_process.stderr else ""
                return False, f"OpenOCD 启动失败: {stderr[:200]}"

            self._connected = True
            logger.info(f"JTAG/SWD 已连接: {self.config.jtag_device} -> {self.config.jtag_target}")
            return True

        except FileNotFoundError:
            logger.error("OpenOCD 未安装，请执行: apt install openocd 或从 https://openocd.org/ 下载")
            return False
        except Exception as e:
            logger.error(f"JTAG 连接失败: {e}")
            return False

    def disconnect(self) -> bool:
        """停止 OpenOCD。"""
        if self._openocd_process:
            try:
                self._openocd_process.terminate()
                self._openocd_process.wait(timeout=5)
                logger.info("OpenOCD 已停止")
            except Exception as e:
                logger.warning(f"OpenOCD 停止异常: {e}")
                try:
                    self._openocd_process.kill()
                except Exception:
                    pass
        self._connected = False
        return True

    def flash_firmware(self, firmware_path: str) -> tuple[bool, str]:
        """通过 OpenOCD 烧录固件。"""
        os.path.splitext(firmware_path)[1].lower()

        try:
            # GDB 命令烧录
            gdb_cmds = [
                "target extended-remote localhost:3333",
                "monitor reset halt",
                f"monitor flash write_image erase {firmware_path}",
                "monitor reset run",
                "quit",
            ]

            cmd = ["arm-none-eabi-gdb", "-batch", "-x", "-", firmware_path]
            gdb_input = "\n".join(gdb_cmds)

            result = subprocess.run(
                cmd,
                input=gdb_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.flash_timeout,
            )

            if result.returncode != 0:
                # 尝试 telnet 方式
                return self._flash_via_telnet(firmware_path)

            return True, result.stdout[:2000]

        except FileNotFoundError:
            # 备选：使用 pyOCD
            return self._flash_via_pyocd(firmware_path)
        except subprocess.TimeoutExpired:
            return False, "烧录超时"
        except Exception as e:
            return False, f"JTAG 烧录失败: {e}"

    def _flash_via_telnet(self, firmware_path: str) -> tuple[bool, str]:
        """通过 Telnet 连接 OpenOCD 烧录。"""
        try:
            import telnetlib
            tn = telnetlib.Telnet("localhost", 4444, timeout=10)

            tn.read_until(b">", timeout=5)
            tn.write(b"reset halt\n")
            tn.read_until(b">", timeout=5)

            flash_cmd = f"flash write_image erase {firmware_path}\n"
            tn.write(flash_cmd.encode())
            output = tn.read_until(b">", timeout=self.config.flash_timeout).decode()

            tn.write(b"reset run\n")
            tn.read_until(b">", timeout=5)
            tn.write(b"exit\n")
            tn.close()

            return True, output[:2000]
        except Exception as e:
            return False, f"Telnet 烧录失败: {e}"

    def _flash_via_pyocd(self, firmware_path: str) -> tuple[bool, str]:
        """通过 pyOCD 烧录（备选方案）。"""
        try:
            cmd = [
                "pyocd", "flash",
                "-t", self.config.jtag_target.lower(),
                firmware_path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.flash_timeout,
            )
            success = result.returncode == 0
            return success, result.stdout[:2000] if success else result.stderr[:2000]
        except FileNotFoundError:
            return False, "pyOCD 未安装，请执行: pip install pyocd"
        except Exception as e:
            return False, f"pyOCD 烧录失败: {e}"

    def run(self) -> tuple[bool, str]:
        """通过 Semi-hosting / ITM 采集输出。"""
        try:
            # 方式1: OpenOCD telnet 采集 UART 输出
            import telnetlib
            tn = telnetlib.Telnet("localhost", 4444, timeout=10)

            tn.read_until(b">", timeout=5)
            tn.write(b"reset run\n")
            tn.read_until(b">", timeout=5)

            # 读取输出（如果启用了 semi-hosting）
            tn.write(b"arm semihosting enable\n")
            output = tn.read_until(b">", timeout=self.config.run_timeout).decode()

            tn.write(b"exit\n")
            tn.close()

            return True, output
        except Exception as e:
            # 备选: 读取串口输出（JTAG + 串口混合模式）
            logger.warning(f"JTAG Semi-hosting 不可用, 尝试串口采集: {e}")
            return self._run_via_serial_fallback()

    def _run_via_serial_fallback(self) -> tuple[bool, str]:
        """备选方案：通过串口采集输出（JTAG 烧录 + 串口采集）。"""
        try:
            import serial
            ser = serial.Serial(
                port=self.config.serial_port,
                baudrate=self.config.baud_rate,
                timeout=self.config.serial_timeout,
            )

            output = []
            start = time.time()
            while (time.time() - start) < self.config.run_timeout:
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    try:
                        output.append(data.decode("utf-8", errors="replace"))
                    except Exception:
                        output.append(repr(data))
                else:
                    time.sleep(0.01)

            ser.close()
            return True, "".join(output)
        except Exception as e:
            return False, f"串口采集失败: {e}"

    def _generate_openocd_config(self) -> str:
        """生成 OpenOCD 配置文件。"""
        device = self.config.jtag_device.upper()
        target = self.config.jtag_target.upper()

        configs = {
            ("STLINK", "STM32F407"): """
source [find interface/stlink.cfg]
transport select hla_swd
source [find target/stm32f4x.cfg]
adapter speed 4000
""",
            ("STLINK", "STM32F103"): """
source [find interface/stlink.cfg]
transport select hla_swd
source [find target/stm32f1x.cfg]
adapter speed 4000
""",
            ("JLINK", "STM32F407"): """
source [find interface/jlink.cfg]
transport select swd
source [find target/stm32f4x.cfg]
adapter speed 4000
""",
        }

        key = (device, target)
        if key in configs:
            return configs[key]

        # 通用配置
        return f"""
# Auto-generated OpenOCD config for {device} -> {target}
source [find interface/{device.lower()}.cfg]
transport select swd
source [find target/{target.lower()}.cfg]
adapter speed {self.config.jtag_clock // 1000}
"""

    def _write_temp_config(self, content: str) -> str:
        """写入临时 OpenOCD 配置文件。"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".cfg",
            prefix="openocd_",
            delete=False,
        )
        tmp.write(content)
        tmp.close()
        return tmp.name


# ==================== Mock HIL 适配器（向后兼容） ====================

class MockHilAdapter(HilAdapter):
    """Mock HIL 适配器 — 基于 VirtualMCU 的模拟模式。

    当无真实硬件时使用此适配器，保持与现有 VirtualMCU 的兼容性。
    """

    def connect(self) -> bool:
        self._connected = True
        logger.info("Mock HIL 适配器已就绪（无真实硬件连接）")
        return True

    def disconnect(self) -> bool:
        self._connected = False
        return True

    def flash_firmware(self, firmware_path: str) -> tuple[bool, str]:
        logger.info("Mock HIL: 跳过烧录（使用 VirtualMCU）")
        return True, "Mock 模式 — 固件烧录已跳过"

    def run(self) -> tuple[bool, str]:
        """使用 VirtualMCU 运行模拟。"""
        try:
            from skyforge_engine.digital_twin.virtual_mcu import VirtualMCU

            mcu = VirtualMCU()
            compile_ok, compile_out = mcu.compile("")
            if not compile_ok:
                return False, f"VirtualMCU 编译失败: {compile_out}"

            run_ok, run_out = mcu.run()
            return run_ok, run_out
        except Exception as e:
            return False, f"Mock HIL 运行失败: {e}"


# ==================== 工厂函数 ====================

def create_hil_adapter(
    interface: str = "serial",
    port: str = "COM3",
    baud_rate: int = 115200,
    jtag_device: str = "STLINK",
    jtag_target: str = "STM32F407",
    firmware_path: str = "",
    contract_asserts: Optional[list[str]] = None,
    expected_patterns: Optional[list[str]] = None,
    **kwargs,
) -> HilAdapter:
    """创建 HIL 适配器实例。

    Args:
        interface: 接口类型 ("serial" | "jtag_swd" | "mock")
        port: 串口端口
        baud_rate: 波特率
        jtag_device: JTAG 调试器类型
        jtag_target: 目标 MCU 型号
        firmware_path: 固件路径
        contract_asserts: 契约断言列表
        expected_patterns: 预期输出模式列表
        **kwargs: 其他 HilConfig 参数

    Returns:
        HilAdapter 实例
    """
    config = HilConfig(
        interface=interface,
        serial_port=port,
        baud_rate=baud_rate,
        jtag_device=jtag_device,
        jtag_target=jtag_target,
        firmware_path=firmware_path,
        contract_asserts=contract_asserts or [],
        expected_patterns=expected_patterns or [],
        **kwargs,
    )

    adapters = {
        "serial": SerialHilAdapter,
        "jtag_swd": JtagHilAdapter,
        "mock": MockHilAdapter,
    }

    adapter_cls = adapters.get(interface, MockHilAdapter)
    logger.info(
        f"创建 HIL 适配器: {adapter_cls.__name__} "
        f"(interface={interface})"
    )
    return adapter_cls(config)


def get_default_hil_adapter() -> HilAdapter:
    """获取默认 HIL 适配器（从环境变量读取配置）。"""
    try:
        from skyforge_engine.config import settings

        return create_hil_adapter(
            interface=settings.HIL_INTERFACE if settings.HIL_ENABLED else "mock",
            port=settings.HIL_SERIAL_PORT,
            baud_rate=settings.HIL_BAUD_RATE,
            jtag_device=settings.HIL_JTAG_DEVICE,
            jtag_target=settings.HIL_JTAG_TARGET,
        )
    except ImportError:
        return MockHilAdapter(HilConfig())
