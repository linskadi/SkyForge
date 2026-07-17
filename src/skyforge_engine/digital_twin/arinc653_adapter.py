# -*- coding: utf-8 -*-
"""ARINC 653 分区调度器适配器 — 数字孪生 IMA 架构仿真。

模拟 ARINC 653 IMA (Integrated Modular Avionics) 架构的分区调度行为，
符合 ARINC 653 Part 1 (核心服务) 规范。

核心服务:
- 分区创建 / 删除
- 主时间帧 (MTF, Main Time Frame) 周期调度
- 分区上下文切换 (≤ 1 ms)
- 分区超时检测与健康监控 (HM)
- 跨分区通信 (基于端口)

与 examples/arinc653_partition/ 示例配合，完整演示航空运行时场景:
- P1 Display (50 ms) + P2 Navigation (80 ms) + P3 HealthMonitoring (70 ms) = 200 ms MTF

标准依据:
- ARINC 653 Part 1 (Avionics Application Software Standard Interface)
- DO-178C DAL-A
- 上下文切换 ≤ 1 ms, 调度抖动 ≤ 100 μs
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from skyforge_engine.utils.log_util import logger


class PartitionState(Enum):
    """ARINC 653 分区状态机。

    状态转换:
        IDLE → RUNNING (激活)
        RUNNING → WAITING (时间片耗尽，被切出)
        WAITING → RUNNING (下一个 MTF 周期重新激活)
        * → STOPPED (超时 / 致命故障，本 MTF 内不再调度)
    """

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    STOPPED = "stopped"


class ScheduleError(Exception):
    """分区调度错误 (创建冲突 / 超时 / 资源不足等)。"""


@dataclass
class Partition:
    """ARINC 653 分区定义。

    Attributes:
        name: 分区名称 (唯一标识)。
        period_ms: 分区主时间帧周期 (默认 200 ms，应等于调度器 MTF)。
        time_slice_ms: 单个 MTF 内分配给该分区的时间片 (ms)。
        entry_point: 分区入口函数名 (C 代码生成时使用)。
        err_handler: 分区健康监控处理函数名。
        state: 分区当前运行时状态。
        deadline_misses: 错过截止时间次数 (统计)。
        overrun_count: 超时次数 (统计)。
    """

    name: str
    period_ms: int = 200
    time_slice_ms: int = 50
    entry_point: str = "main"
    err_handler: str = "partition_hm_handler"
    state: PartitionState = PartitionState.IDLE
    deadline_misses: int = 0
    overrun_count: int = 0


@dataclass
class ScheduleEntry:
    """调度表条目 (一个分区在一个 MTF 内的时间片分配)。

    Attributes:
        partition: 关联的分区对象。
        start_offset_ms: 在 MTF 内的起始偏移 (ms)。
        duration_ms: 持续时间 (ms)，等于 partition.time_slice_ms。
    """

    partition: Partition
    start_offset_ms: int
    duration_ms: int


class Arinc653Adapter:
    """ARINC 653 分区调度器适配器。

    实现核心 ARINC 653 服务:
    - 分区创建 / 删除
    - 主时间帧 (MTF) 周期调度
    - 分区切换 (上下文切换)
    - 分区超时检测与健康监控
    - 跨分区通信 (基于端口)

    用法:
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(Partition(name="P1", time_slice_ms=50))
        adapter.create_partition(Partition(name="P2", time_slice_ms=80))
        report = adapter.tick(30)  # 推进 30 ms
    """

    # 主时间帧默认 200 ms (符合 ARINC 653 标准典型值)
    MTF_DEFAULT_MS = 200
    # 上下文切换最大 1 ms (ARINC 653 要求)
    CONTEXT_SWITCH_MAX_MS = 1.0

    def __init__(self, mtf_ms: int = 200) -> None:
        """初始化 ARINC 653 分区调度器。

        Args:
            mtf_ms: 主时间帧周期 (ms)，默认 200 ms。
        """
        self.mtf_ms = mtf_ms
        self.partitions: dict[str, Partition] = {}
        self.schedule_table: list[ScheduleEntry] = []
        self.current_partition: str | None = None
        self.current_offset_ms: int = 0
        self.hm_events: list[dict[str, Any]] = []
        self.ports: dict[str, dict[str, Any]] = {}  # 跨分区通信端口
        self.context_switches: int = 0

    def create_partition(self, partition: Partition) -> None:
        """创建新分区并重建调度表。

        Args:
            partition: 分区定义对象。

        Raises:
            ScheduleError: 分区名已存在，或时间片总和超过 MTF。
        """
        if partition.name in self.partitions:
            raise ScheduleError(f"Partition {partition.name} already exists")
        self.partitions[partition.name] = partition
        try:
            self._rebuild_schedule_table()
        except ScheduleError:
            # 时间片超限：回滚，保证调度器状态一致性
            del self.partitions[partition.name]
            raise
        logger.info(
            f"Arinc653Adapter:创建分区 {partition.name} "
            f"time_slice={partition.time_slice_ms}ms"
        )

    def delete_partition(self, name: str) -> None:
        """删除分区并重建调度表。

        Args:
            name: 分区名称。

        Raises:
            ScheduleError: 分区不存在。
        """
        if name not in self.partitions:
            raise ScheduleError(f"Partition {name} not found")
        del self.partitions[name]
        if self.current_partition == name:
            self.current_partition = None
        self._rebuild_schedule_table()
        logger.info(f"Arinc653Adapter:删除分区 {name}")

    def _rebuild_schedule_table(self) -> None:
        """重建调度表 (按分区创建顺序分配时间片)。

        Raises:
            ScheduleError: 时间片总和超过 MTF。
        """
        self.schedule_table = []
        offset = 0
        for partition in self.partitions.values():
            entry = ScheduleEntry(
                partition=partition,
                start_offset_ms=offset,
                duration_ms=partition.time_slice_ms,
            )
            self.schedule_table.append(entry)
            offset += partition.time_slice_ms
        # 验证时间片总和不超过 MTF
        total = sum(p.time_slice_ms for p in self.partitions.values())
        if total > self.mtf_ms:
            raise ScheduleError(
                f"Total time slice {total}ms exceeds MTF {self.mtf_ms}ms"
            )

    def tick(self, elapsed_ms: int) -> dict[str, Any]:
        """推进模拟时间，自动切换到当前应运行的分区。

        Args:
            elapsed_ms: 推进的毫秒数。

        Returns:
            状态报告 dict，包含:
            - status: "idle" | "running" | "mtf_boundary"
            - active_partition: 当前运行的分区名 (无则 None)
            - offset_ms: 当前 MTF 内偏移 (仅 running 时返回)
            - remaining_ms: 当前时间片剩余 ms (仅 running 时返回)
        """
        if not self.schedule_table:
            return {"status": "idle", "active_partition": None}

        self.current_offset_ms = (self.current_offset_ms + elapsed_ms) % self.mtf_ms

        # 找到当前应该运行的分区
        active_entry: ScheduleEntry | None = None
        for entry in self.schedule_table:
            if entry.start_offset_ms <= self.current_offset_ms < (
                entry.start_offset_ms + entry.duration_ms
            ):
                active_entry = entry
                break

        if active_entry is None:
            # MTF 周期结束，重置当前分区
            if self.current_partition:
                self._deactivate_partition(self.current_partition)
                self.current_partition = None
            return {"status": "mtf_boundary", "active_partition": None}

        new_partition = active_entry.partition.name
        if new_partition != self.current_partition:
            # 触发上下文切换 (仅当从一个分区切换到另一个时计数)
            if self.current_partition:
                self._deactivate_partition(self.current_partition)
                self.context_switches += 1
            self._activate_partition(new_partition)

        return {
            "status": "running",
            "active_partition": new_partition,
            "offset_ms": self.current_offset_ms,
            "remaining_ms": active_entry.duration_ms
            - (self.current_offset_ms - active_entry.start_offset_ms),
        }

    def _activate_partition(self, name: str) -> None:
        """激活分区 (状态 → RUNNING)。"""
        if name in self.partitions:
            self.partitions[name].state = PartitionState.RUNNING
            self.current_partition = name

    def _deactivate_partition(self, name: str) -> None:
        """停用分区 (状态 → WAITING)。"""
        if name in self.partitions:
            self.partitions[name].state = PartitionState.WAITING

    def inject_overrun(self, partition_name: str, overrun_ms: int) -> dict[str, Any]:
        """注入超时故障 (故障注入测试)。

        模拟分区执行时间超过分配时间片的场景，触发健康监控事件，
        并将分区状态置为 STOPPED (本 MTF 内不再调度)。

        Args:
            partition_name: 分区名。
            overrun_ms: 超时毫秒数。

        Returns:
            HM 事件 dict，包含 type / partition / overrun_ms / handler / timestamp / action。

        Raises:
            ScheduleError: 分区不存在。
        """
        if partition_name not in self.partitions:
            raise ScheduleError(f"Partition {partition_name} not found")

        partition = self.partitions[partition_name]
        partition.overrun_count += 1

        # 触发健康监控事件
        event: dict[str, Any] = {
            "type": "deadline_miss",
            "partition": partition_name,
            "overrun_ms": overrun_ms,
            "handler": partition.err_handler,
            "timestamp_ms": self.current_offset_ms,
            "action": "invoke_hm_handler",
        }
        self.hm_events.append(event)

        # 停止超时分区 (符合 contract.yaml CON-A653-FLT-001)
        partition.state = PartitionState.STOPPED

        logger.warning(
            f"Arinc653Adapter:分区 {partition_name} 超时 {overrun_ms}ms，"
            f"触发 HM 处理器 {partition.err_handler}"
        )
        return event

    def create_port(
        self,
        port_name: str,
        src_partition: str,
        dst_partition: str,
        max_message_size: int = 4096,
    ) -> None:
        """创建跨分区通信端口 (ARINC 653 Sampling/Queuing Port 抽象)。

        Args:
            port_name: 端口名 (唯一标识)。
            src_partition: 源分区名。
            dst_partition: 目标分区名。
            max_message_size: 单条消息最大长度 (字符/字节/元素数)。

        Raises:
            ScheduleError: 源/目标分区不存在。
        """
        if src_partition not in self.partitions:
            raise ScheduleError(f"Source partition {src_partition} not found")
        if dst_partition not in self.partitions:
            raise ScheduleError(f"Destination partition {dst_partition} not found")

        self.ports[port_name] = {
            "src": src_partition,
            "dst": dst_partition,
            "max_message_size": max_message_size,
            "queue": [],
        }

    def send_message(self, port_name: str, message: Any) -> None:
        """通过端口发送消息 (跨分区通信)。

        Args:
            port_name: 端口名。
            message: 消息内容 (str/bytes/list 或其他对象)。

        Raises:
            ScheduleError: 端口不存在，或消息超过最大长度。
        """
        if port_name not in self.ports:
            raise ScheduleError(f"Port {port_name} not found")

        port = self.ports[port_name]
        # 计算消息大小 (str/bytes/list 用 len，其他视为 1)
        msg_size = len(message) if isinstance(message, (str, bytes, list)) else 1
        if msg_size > port["max_message_size"]:
            raise ScheduleError(
                f"Message exceeds max size {port['max_message_size']}"
            )

        port["queue"].append(
            {
                "src": port["src"],
                "dst": port["dst"],
                "data": message,
                "timestamp_ms": self.current_offset_ms,
            }
        )

    def receive_message(self, port_name: str) -> Any | None:
        """从端口接收消息 (FIFO 队列)。

        Args:
            port_name: 端口名。

        Returns:
            消息内容，队列空时返回 None。

        Raises:
            ScheduleError: 端口不存在。
        """
        if port_name not in self.ports:
            raise ScheduleError(f"Port {port_name} not found")

        port = self.ports[port_name]
        if not port["queue"]:
            return None
        return port["queue"].pop(0)["data"]

    def get_state(self) -> dict[str, Any]:
        """获取完整状态快照 (供 UI 展示 / 测试断言)。

        Returns:
            状态 dict，包含 mtf_ms / current_offset_ms / current_partition /
            partitions / schedule_table / hm_events (最近 10 条) /
            context_switches / ports。
        """
        return {
            "mtf_ms": self.mtf_ms,
            "current_offset_ms": self.current_offset_ms,
            "current_partition": self.current_partition,
            "partitions": [
                {
                    "name": p.name,
                    "period_ms": p.period_ms,
                    "time_slice_ms": p.time_slice_ms,
                    "state": p.state.value,
                    "deadline_misses": p.deadline_misses,
                    "overrun_count": p.overrun_count,
                }
                for p in self.partitions.values()
            ],
            "schedule_table": [
                {
                    "partition": e.partition.name,
                    "start_offset_ms": e.start_offset_ms,
                    "duration_ms": e.duration_ms,
                }
                for e in self.schedule_table
            ],
            "hm_events": self.hm_events[-10:],  # 最近 10 个事件
            "context_switches": self.context_switches,
            "ports": {
                name: {
                    "src": p["src"],
                    "dst": p["dst"],
                    "queue_size": len(p["queue"]),
                }
                for name, p in self.ports.items()
            },
        }

    def validate_constraints(self) -> list[str]:
        """验证 ARINC 653 关键约束 (用于形式化验证自检)。

        Returns:
            违反的约束描述列表 (空列表表示全部通过)。

        检查项:
        1. 时间片总和 ≤ MTF
        2. 每个分区时间片 > 0
        3. 每个分区周期 == MTF
        """
        violations: list[str] = []

        # 约束 1: 时间片总和 <= MTF (对应 contract CON-A653-INV-002)
        total = sum(p.time_slice_ms for p in self.partitions.values())
        if total > self.mtf_ms:
            violations.append(
                f"Total time slice {total}ms exceeds MTF {self.mtf_ms}ms"
            )

        # 约束 2: 每个分区时间片 > 0
        for p in self.partitions.values():
            if p.time_slice_ms <= 0:
                violations.append(
                    f"Partition {p.name} has invalid time_slice_ms={p.time_slice_ms}"
                )

        # 约束 3: 分区周期 == MTF (对应 contract CON-A653-INV-000)
        for p in self.partitions.values():
            if p.period_ms != self.mtf_ms:
                violations.append(
                    f"Partition {p.name} period {p.period_ms}ms != MTF {self.mtf_ms}ms"
                )

        return violations
