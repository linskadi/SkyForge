# -*- coding: utf-8 -*-
"""ARINC 653 Adapter 单元测试。

覆盖:
- Partition 数据类默认值 / 自定义值
- Arinc653Adapter 初始化 / 分区创建删除 / 调度表重建
- tick 推进时间 / 上下文切换 / MTF 边界
- inject_overrun 超时故障注入 / 健康监控事件
- create_port / send_message / receive_message 跨分区通信
- get_state 状态快照
- validate_constraints ARINC 653 约束验证
- 与 examples/arinc653_partition/ 示例的集成测试
"""

import pytest

from skyforge_engine.digital_twin.arinc653_adapter import (
    Arinc653Adapter,
    Partition,
    PartitionState,
    ScheduleError,
)


class TestPartition:
    """测试 Partition 数据类。"""

    def test_default_partition(self) -> None:
        p = Partition(name="P1")
        assert p.name == "P1"
        assert p.period_ms == 200
        assert p.time_slice_ms == 50
        assert p.state == PartitionState.IDLE

    def test_custom_partition(self) -> None:
        p = Partition(
            name="Display",
            period_ms=200,
            time_slice_ms=80,
            entry_point="main_display",
        )
        assert p.name == "Display"
        assert p.time_slice_ms == 80
        assert p.entry_point == "main_display"


class TestArinc653Adapter:
    """测试 Arinc653Adapter。"""

    def test_init_default(self) -> None:
        adapter = Arinc653Adapter()
        assert adapter.mtf_ms == 200
        assert adapter.partitions == {}
        assert adapter.schedule_table == []

    def test_create_partition(self) -> None:
        adapter = Arinc653Adapter()
        p = Partition(name="P1", time_slice_ms=50)
        adapter.create_partition(p)
        assert "P1" in adapter.partitions
        assert len(adapter.schedule_table) == 1

    def test_create_duplicate_partition_raises(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        with pytest.raises(ScheduleError):
            adapter.create_partition(Partition(name="P1"))

    def test_delete_partition(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        adapter.delete_partition("P1")
        assert "P1" not in adapter.partitions

    def test_delete_nonexistent_raises(self) -> None:
        adapter = Arinc653Adapter()
        with pytest.raises(ScheduleError):
            adapter.delete_partition("nonexistent")

    def test_total_time_slice_exceeds_mtf_raises(self) -> None:
        adapter = Arinc653Adapter(mtf_ms=100)
        adapter.create_partition(Partition(name="P1", time_slice_ms=60))
        # 60 + 50 = 110 > 100，应抛出异常并回滚 P2
        with pytest.raises(ScheduleError):
            adapter.create_partition(Partition(name="P2", time_slice_ms=50))
        # P2 不应被保留
        assert "P2" not in adapter.partitions

    def test_tick_empty_schedule(self) -> None:
        adapter = Arinc653Adapter()
        result = adapter.tick(10)
        assert result["status"] == "idle"
        assert result["active_partition"] is None

    def test_tick_activates_first_partition(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1", time_slice_ms=50))
        result = adapter.tick(10)
        assert result["status"] == "running"
        assert result["active_partition"] == "P1"
        assert adapter.partitions["P1"].state == PartitionState.RUNNING

    def test_tick_triggers_context_switch(self) -> None:
        adapter = Arinc653Adapter(mtf_ms=100)
        adapter.create_partition(Partition(name="P1", time_slice_ms=30))
        adapter.create_partition(Partition(name="P2", time_slice_ms=30))

        # 第一段时间 (0-30ms): P1
        adapter.tick(20)
        assert adapter.current_partition == "P1"

        # 切换到 P2 (30-60ms)
        adapter.tick(15)
        assert adapter.current_partition == "P2"
        assert adapter.partitions["P1"].state == PartitionState.WAITING
        # 首次激活 (None→P1) 不计入上下文切换，仅 P1→P2 计 1 次
        assert adapter.context_switches == 1

    def test_inject_overrun(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        event = adapter.inject_overrun("P1", overrun_ms=5)
        assert event["type"] == "deadline_miss"
        assert event["partition"] == "P1"
        assert adapter.partitions["P1"].overrun_count == 1
        assert adapter.partitions["P1"].state == PartitionState.STOPPED
        assert len(adapter.hm_events) == 1

    def test_inject_overrun_nonexistent_raises(self) -> None:
        adapter = Arinc653Adapter()
        with pytest.raises(ScheduleError):
            adapter.inject_overrun("nonexistent", overrun_ms=5)

    def test_create_port_and_communicate(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        adapter.create_partition(Partition(name="P2"))

        adapter.create_port("port1", "P1", "P2", max_message_size=1024)
        adapter.send_message("port1", "hello")
        msg = adapter.receive_message("port1")
        assert msg == "hello"

    def test_receive_empty_port(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        adapter.create_partition(Partition(name="P2"))
        adapter.create_port("port1", "P1", "P2")
        assert adapter.receive_message("port1") is None

    def test_send_message_nonexistent_port_raises(self) -> None:
        adapter = Arinc653Adapter()
        with pytest.raises(ScheduleError):
            adapter.send_message("nonexistent", "data")

    def test_receive_message_nonexistent_port_raises(self) -> None:
        adapter = Arinc653Adapter()
        with pytest.raises(ScheduleError):
            adapter.receive_message("nonexistent")

    def test_create_port_nonexistent_src_raises(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        with pytest.raises(ScheduleError):
            adapter.create_port("p", "no_src", "P1")

    def test_create_port_nonexistent_dst_raises(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        with pytest.raises(ScheduleError):
            adapter.create_port("p", "P1", "no_dst")

    def test_send_message_exceeds_size_raises(self) -> None:
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        adapter.create_partition(Partition(name="P2"))
        adapter.create_port("port1", "P1", "P2", max_message_size=4)
        with pytest.raises(ScheduleError):
            adapter.send_message("port1", "toolongmessage")

    def test_get_state(self) -> None:
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(Partition(name="P1", time_slice_ms=50))
        adapter.create_partition(Partition(name="P2", time_slice_ms=80))

        state = adapter.get_state()
        assert state["mtf_ms"] == 200
        assert len(state["partitions"]) == 2
        assert len(state["schedule_table"]) == 2
        assert state["context_switches"] == 0

    def test_validate_constraints_pass(self) -> None:
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(Partition(name="P1", period_ms=200, time_slice_ms=50))
        adapter.create_partition(Partition(name="P2", period_ms=200, time_slice_ms=80))
        violations = adapter.validate_constraints()
        assert violations == []

    def test_validate_constraints_period_mismatch(self) -> None:
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(Partition(name="P1", period_ms=100, time_slice_ms=50))
        violations = adapter.validate_constraints()
        assert len(violations) == 1
        assert "period" in violations[0].lower()

    def test_integration_with_examples_arinc653(self) -> None:
        """与 examples/arinc653_partition/ 示例集成测试。

        模拟 README.md 中描述的三分区 IMA 调度:
        P1 Display (50ms) + P2 Navigation (80ms) + P3 HealthMonitoring (70ms) = 200ms MTF
        """
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(
            Partition(
                name="P1_Display",
                period_ms=200,
                time_slice_ms=50,
                entry_point="main_display",
            )
        )
        adapter.create_partition(
            Partition(
                name="P2_Navigation",
                period_ms=200,
                time_slice_ms=80,
                entry_point="main_navigation",
            )
        )
        adapter.create_partition(
            Partition(
                name="P3_HealthMonitoring",
                period_ms=200,
                time_slice_ms=70,
                entry_point="main_hm",
            )
        )

        # 验证约束通过 (时间片守恒: 50+80+70=200=MTF)
        violations = adapter.validate_constraints()
        assert violations == []

        # 模拟一个完整 MTF 周期
        # 0-50ms: P1
        adapter.tick(30)
        assert adapter.current_partition == "P1_Display"
        adapter.tick(20)  # 进入 P2 (offset=50)
        assert adapter.current_partition == "P2_Navigation"
        adapter.tick(80)  # 进入 P3 (offset=130)
        assert adapter.current_partition == "P3_HealthMonitoring"
        adapter.tick(70)  # MTF 结束 (offset=200%200=0)
        # 应该回到 P1 或处于边界

    def test_mtf_boundary_resets_partition(self) -> None:
        """MTF 边界应重置当前分区状态。"""
        adapter = Arinc653Adapter(mtf_ms=100)
        adapter.create_partition(Partition(name="P1", time_slice_ms=40))
        # 激活 P1
        adapter.tick(20)
        assert adapter.current_partition == "P1"
        # 推进到时间片外但仍在 MTF 内的间隙 (假设无分区覆盖)
        # 这里 40 < offset < 100 但只有 P1 在 0-40，所以 40-100 无分区
        result = adapter.tick(50)  # offset = 70
        # P1 时间片是 0-40，offset=70 落在间隙
        assert result["status"] == "mtf_boundary"
        assert adapter.current_partition is None
        assert adapter.partitions["P1"].state == PartitionState.WAITING

    def test_overrun_hm_event_content(self) -> None:
        """超时 HM 事件应包含完整的字段。"""
        adapter = Arinc653Adapter(mtf_ms=200)
        adapter.create_partition(
            Partition(name="P1", err_handler="my_hm_handler")
        )
        adapter.tick(10)  # 设置 current_offset_ms
        event = adapter.inject_overrun("P1", overrun_ms=15)
        assert event["handler"] == "my_hm_handler"
        assert event["overrun_ms"] == 15
        assert event["action"] == "invoke_hm_handler"
        assert "timestamp_ms" in event

    def test_get_state_includes_ports(self) -> None:
        """get_state 应包含端口信息。"""
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1"))
        adapter.create_partition(Partition(name="P2"))
        adapter.create_port("port1", "P1", "P2")
        adapter.send_message("port1", "msg")

        state = adapter.get_state()
        assert "port1" in state["ports"]
        assert state["ports"]["port1"]["src"] == "P1"
        assert state["ports"]["port1"]["dst"] == "P2"
        assert state["ports"]["port1"]["queue_size"] == 1

    def test_delete_current_partition_clears_state(self) -> None:
        """删除当前运行分区应清除 current_partition。"""
        adapter = Arinc653Adapter()
        adapter.create_partition(Partition(name="P1", time_slice_ms=50))
        adapter.tick(10)
        assert adapter.current_partition == "P1"
        adapter.delete_partition("P1")
        assert adapter.current_partition is None
