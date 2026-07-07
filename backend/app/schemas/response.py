"""响应数据模型定义。"""

from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4


class Message(BaseModel):
    """消息基类。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    msg_type: str  # system | agent | user | tool | approval
    content: str | None = None


class SystemMessage(Message):
    msg_type: Literal["system", "agent", "user", "tool"] = "system"  # type: ignore[assignment]
    type: Literal["info", "warning", "success", "error"] = "info"


class AgentMessage(Message):
    msg_type: Literal["system", "agent", "user", "tool"] = "agent"  # type: ignore[assignment]
    agent_type: str  # RequirementParserAgent | ContractGeneratorAgent | etc.


class StreamMessage(BaseModel):
    """WebSocket 流式消息。"""

    level: str  # info | success | warning | error | complete
    agent: str | None = None
    content: str
    data: dict | None = None
