"""SkyForge 核心协议层 (L0 Protocols)。

定义全系统分层架构的基础协议接口，所有上层模块均依赖此层。
设计原则：
- 纯抽象，无具体实现
- 最小接口，只包含必要方法
- 类型安全，完整类型注解
- 向后兼容，不破坏现有调用方
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal, Protocol, runtime_checkable


# ============================================================================
# 通用数据类
# ============================================================================

@dataclass(frozen=True)
class StageResult:
    """Pipeline 阶段执行结果。"""

    artifact: Any
    status: Literal["success", "failure", "skipped", "timeout"] = "success"
    duration_ms: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    """验证工具统一结果。"""

    passed: bool = False
    tool_name: str = ""
    tool_available: bool = False
    violations: list[dict[str, Any]] = field(default_factory=list)
    output: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Agent 执行统一结果。"""

    output: Any
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    """编码标准违规记录。"""

    file: str = ""
    line: int = 0
    column: int = 0
    severity: str = "style"
    rule_id: str = ""
    message: str = ""


# ============================================================================
# Pipeline 阶段协议
# ============================================================================

@runtime_checkable
class PipelineStageProtocol(Protocol):
    """Pipeline 阶段协议。

    每个阶段实现此协议，由 PipelineOrchestrator 统一编排。
    """

    @property
    def name(self) -> str:
        """阶段名称（唯一标识）。"""
        ...

    @property
    def description(self) -> str:
        """阶段描述。"""
        ...

    async def execute(self, artifact: Any, context: dict[str, Any] | None = None) -> StageResult:
        """执行阶段逻辑。

        Args:
            artifact: 输入产物（前一阶段的输出）。
            context: 可选的执行上下文（如 task_id, log_hook 等）。

        Returns:
            StageResult: 阶段执行结果。
        """
        ...


# ============================================================================
# Agent 策略协议
# ============================================================================

class AgentMode(Enum):
    """Agent 执行模式。"""

    MOCK = auto()
    LLM = auto()


@runtime_checkable
class AgentStrategyProtocol(Protocol):
    """Agent 执行策略协议。

    将 Agent 的执行逻辑（Mock / LLM）从 Agent 本身剥离，
    实现策略模式，便于测试和扩展。
    """

    @property
    def mode(self) -> AgentMode:
        """返回策略模式类型。"""
        ...

    def supports(self, input_type: str) -> bool:
        """检查是否支持给定输入类型。

        Args:
            input_type: 输入数据类型标识（如 "requirement", "contract", "code"）。

        Returns:
            True 如果支持处理该类型。
        """
        ...

    async def run(self, input_data: Any, **kwargs: Any) -> AgentResult:
        """执行策略逻辑。

        Args:
            input_data: 输入数据。
            **kwargs: 额外参数（如 req_id, language 等）。

        Returns:
            AgentResult: 执行结果。
        """
        ...


# ============================================================================
# 验证工具协议
# ============================================================================

@runtime_checkable
class VerifierProtocol(Protocol):
    """验证工具协议。

    所有验证工具（Z3, CBMC, Cppcheck, Contract）实现此协议。
    工具缺失时 is_available() 返回 False，verify() 抛出 ToolNotFoundError。
    """

    @property
    def tool_name(self) -> str:
        """工具名称（唯一标识）。"""
        ...

    def is_available(self) -> bool:
        """检查工具是否可用（已安装且可执行）。"""
        ...

    def verify(self, code: str, contract: str | None = None, **kwargs: Any) -> VerificationResult:
        """执行验证。

        Args:
            code: 待验证的代码。
            contract: 可选的契约文本。
            **kwargs: 工具特定参数（如 unwind, function 等）。

        Returns:
            VerificationResult: 验证结果。

        Raises:
            ToolNotFoundError: 工具不可用时抛出。
        """
        ...


# ============================================================================
# HIL 适配器协议
# ============================================================================

class HILConnectionState(Enum):
    """HIL 连接状态。"""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


@runtime_checkable
class HILAdapterProtocol(Protocol):
    """HIL 适配器协议。

    为 Hardware-In-The-Loop 测试提供统一接口。
    """

    @property
    def adapter_type(self) -> str:
        """适配器类型标识（如 "serial", "qemu", "virtual_mcu"）。"""
        ...

    def is_available(self) -> bool:
        """检查适配器后端是否可用。"""
        ...

    def connect(self) -> None:
        """建立连接。

        Raises:
            RuntimeError: 连接失败时抛出。
        """
        ...

    def disconnect(self) -> None:
        """断开连接并释放资源。"""
        ...

    def send(self, data: bytes) -> None:
        """发送数据。

        Args:
            data: 待发送的字节数据。
        """
        ...

    def receive(self, timeout_ms: int = 5000) -> bytes:
        """接收数据。

        Args:
            timeout_ms: 超时时间（毫秒）。

        Returns:
            接收到的字节数据。
        """
        ...


# ============================================================================
# 报告渲染协议
# ============================================================================

@runtime_checkable
class ReportRendererProtocol(Protocol):
    """报告渲染协议。

    支持 HTML / Markdown / PDF 等多种输出格式。
    """

    @property
    def mime_type(self) -> str:
        """输出 MIME 类型（如 "text/html", "text/markdown"）。"""
        ...

    @property
    def format_name(self) -> str:
        """格式名称（如 "html", "markdown", "pdf"）。"""
        ...

    def render(self, data: dict[str, Any]) -> str | bytes:
        """渲染报告。

        Args:
            data: 报告数据（通常来自 EvidenceCollector）。

        Returns:
            渲染后的报告内容（str 或 bytes）。
        """
        ...


# ============================================================================
# 编码标准协议
# ============================================================================

@runtime_checkable
class CodingStandardProtocol(Protocol):
    """编码标准协议。

    支持 MISRA-C / MISRA-C++ / Python Safety 等标准。
    """

    @property
    def standard_name(self) -> str:
        """标准名称（如 "MISRA-C:2012"）。"""
        ...

    @property
    def language(self) -> str:
        """目标语言（如 "c", "cpp", "python"）。"""
        ...

    def scan(self, code: str) -> list[Violation]:
        """扫描代码并返回违规列表。

        Args:
            code: 源代码字符串。

        Returns:
            违规列表。
        """
        ...

    def get_mock_scan_patterns(self) -> list[dict[str, Any]]:
        """获取 Mock 扫描模式（用于无真实工具时的降级扫描）。

        Returns:
            模式列表，每个模式包含 pattern, rule_id, message, severity 等字段。
        """
        ...


# ============================================================================
# 异常定义
# ============================================================================

class ToolNotFoundError(RuntimeError):
    """所需外部工具缺失异常。"""

    def __init__(self, tool_name: str, message: str | None = None) -> None:
        self.tool_name = tool_name
        super().__init__(message or f"工具未找到: {tool_name}")


class StageExecutionError(RuntimeError):
    """Pipeline 阶段执行异常。"""

    def __init__(self, stage_name: str, message: str, cause: Exception | None = None) -> None:
        self.stage_name = stage_name
        self.cause = cause
        super().__init__(f"阶段 '{stage_name}' 执行失败: {message}")


class VerificationError(RuntimeError):
    """验证执行异常。"""

    def __init__(self, tool_name: str, message: str, cause: Exception | None = None) -> None:
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"验证工具 '{tool_name}' 执行失败: {message}")
