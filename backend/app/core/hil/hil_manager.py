# -*- coding: utf-8 -*-
"""HIL（Human-In-The-Loop）人机协作管理器。

在 Agent 流水线关键检查点（需求评审 / 契约评审 / 代码评审 / 最终评审）
创建审批请求，等待人工通过 REST API 确认或拒绝，超时自动批准。

实现：
- 审批请求持久化到 Redis（支持多 worker 和进程重启恢复）
- request_approval 通过 asyncio.Event 协程等待，超时自动放行
- approve / reject 通过 API 触发，set 对应 Event 唤醒等待协程
- Redis 不可用时自动降级为纯内存模式
- HIL_ENABLED=false 时 request_approval 直接返回 approved=True（跳过）

使用方式：
    manager = get_hil_manager()
    result = await manager.request_approval(
        checkpoint="requirement_review",
        content="需求 JSON 内容...",
        timeout=300,
    )
    if result["approved"]:
        ...  # 继续后续流程
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.utils.log_util import logger


# 支持的检查点类型
VALID_CHECKPOINTS: set[str] = {
    "requirement_review",
    "contract_review",
    "code_review",
    "final_review",
}

# Redis key 前缀
REDIS_PENDING_PREFIX = "hil:pending:"
REDIS_HISTORY_KEY = "hil:history"
REDIS_RESOLVE_CHANNEL = "hil:resolve"


@dataclass
class ApprovalRequest:
    """审批请求数据结构。"""

    request_id: str
    checkpoint: str
    content: str
    timeout: int
    created_at: str
    status: str = "pending"  # pending / approved / rejected / timeout
    # 内部字段（不序列化）
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _result: Optional[dict[str, Any]] = None

    def to_dict(self, include_internal: bool = False) -> dict[str, Any]:
        """转换为可序列化字典。

        Args:
            include_internal: 是否包含内部字段（_event / _result），默认不包含。
        """
        d: dict[str, Any] = {
            "request_id": self.request_id,
            "checkpoint": self.checkpoint,
            "content": self.content,
            "timeout": self.timeout,
            "created_at": self.created_at,
            "status": self.status,
        }
        if include_internal and self._result is not None:
            d["result"] = self._result
        return d

    def to_redis_dict(self) -> dict[str, str]:
        """转换为 Redis hash 可存储的字典（所有值为字符串）。"""
        return {
            "request_id": self.request_id,
            "checkpoint": self.checkpoint,
            "content": self.content,
            "timeout": str(self.timeout),
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> "ApprovalRequest":
        """从 Redis hash 字典重建 ApprovalRequest（不含 Event）。"""
        return cls(
            request_id=data["request_id"],
            checkpoint=data["checkpoint"],
            content=data["content"],
            timeout=int(data["timeout"]),
            created_at=data["created_at"],
            status=data.get("status", "pending"),
        )


@dataclass
class ApprovalResult:
    """审批结果数据结构。"""

    request_id: str
    checkpoint: str
    approved: bool
    comments: str = ""
    reviewer: str = ""
    timestamp: str = ""
    status: str = "approved"  # approved / rejected / timeout / skipped

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "request_id": self.request_id,
            "checkpoint": self.checkpoint,
            "approved": self.approved,
            "comments": self.comments,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "status": self.status,
        }


class HILManager:
    """HIL 人机协作管理器。

    支持 Redis 持久化（多 worker / 进程重启恢复），Redis 不可用时降级为纯内存。
    线程/协程安全：通过 asyncio.Event 协调等待方与触发方。
    """

    # 类级别：Redis 连接状态（所有实例共享，避免重复连接尝试）
    _redis_checked: bool = False
    _redis_client = None
    _redis_ok: bool = False
    _redis_listener_task: Optional[asyncio.Task] = None

    def __init__(
        self,
        enabled: Optional[bool] = None,
        default_timeout: Optional[int] = None,
    ) -> None:
        """初始化 HIL 管理器。

        Args:
            enabled: 是否启用 HIL，默认从环境变量 HIL_ENABLED 读取。
            default_timeout: 默认超时时间（秒），默认从环境变量 HIL_TIMEOUT 读取。
        """
        self.enabled = (
            enabled
            if enabled is not None
            else (os.getenv("HIL_ENABLED", "true").lower() == "true")
        )
        self.default_timeout = default_timeout or int(os.getenv("HIL_TIMEOUT", "300"))
        # request_id → ApprovalRequest
        self._requests: dict[str, ApprovalRequest] = {}
        # 已完成审批的历史记录
        self._history: list[ApprovalResult] = []
        # 锁保护内部字典操作
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # Redis 初始化
    # ------------------------------------------------------------------ #

    async def _ensure_redis(self) -> bool:
        """确保 Redis 连接可用，首次调用时初始化并加载持久化数据。"""
        if HILManager._redis_checked:
            return HILManager._redis_ok
        HILManager._redis_checked = True

        try:
            from app.services.redis_manager import redis_manager

            HILManager._redis_client = await asyncio.wait_for(
                redis_manager.get_client(), timeout=0.5
            )
            HILManager._redis_ok = True
            logger.info("HILManager:Redis 连接建立成功，启用持久化模式")

            # 加载历史记录
            await self._load_history_from_redis()

            # 启动 Redis pub/sub 监听（跨 worker 审批通知）
            if HILManager._redis_listener_task is None:
                HILManager._redis_listener_task = asyncio.create_task(
                    self._listen_resolve_events()
                )

            return True
        except Exception as e:
            logger.debug(f"HILManager:Redis 不可用，降级为纯内存模式: {e}")
            HILManager._redis_ok = False
            return False

    async def _load_history_from_redis(self) -> None:
        """从 Redis 加载历史记录。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            data = await HILManager._redis_client.get(REDIS_HISTORY_KEY)
            if data:
                items = json.loads(data)
                self._history = [
                    ApprovalResult(
                        request_id=item["request_id"],
                        checkpoint=item["checkpoint"],
                        approved=item["approved"],
                        comments=item.get("comments", ""),
                        reviewer=item.get("reviewer", ""),
                        timestamp=item.get("timestamp", ""),
                        status=item.get("status", "approved"),
                    )
                    for item in items
                ]
                logger.info(f"HILManager:从 Redis 加载 {len(self._history)} 条历史记录")
        except Exception as e:
            logger.warning(f"HILManager:加载 Redis 历史记录失败: {e}")

    async def _save_history_to_redis(self) -> None:
        """将历史记录保存到 Redis。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            data = [r.to_dict() for r in self._history]
            await HILManager._redis_client.set(REDIS_HISTORY_KEY, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"HILManager:保存历史记录到 Redis 失败: {e}")

    async def _save_pending_to_redis(self, request: ApprovalRequest) -> None:
        """将待审批请求保存到 Redis。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            key = f"{REDIS_PENDING_PREFIX}{request.request_id}"
            await HILManager._redis_client.hset(key, mapping=request.to_redis_dict())
            await HILManager._redis_client.expire(key, request.timeout + 60)  # 比审批超时多 60s
        except Exception as e:
            logger.warning(f"HILManager:保存待审批请求到 Redis 失败: {e}")

    async def _remove_pending_from_redis(self, request_id: str) -> None:
        """从 Redis 移除待审批请求。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            key = f"{REDIS_PENDING_PREFIX}{request_id}"
            await HILManager._redis_client.delete(key)
        except Exception as e:
            logger.warning(f"HILManager:从 Redis 移除待审批请求失败: {e}")

    async def _publish_resolve(self, result: dict[str, Any]) -> None:
        """发布审批结果到 Redis pub/sub（通知其他 worker 的等待协程）。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            await HILManager._redis_client.publish(
                REDIS_RESOLVE_CHANNEL, json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"HILManager:发布审批结果失败: {e}")

    async def _listen_resolve_events(self) -> None:
        """后台监听 Redis pub/sub，接收其他 worker 的审批通知。"""
        if not HILManager._redis_ok or HILManager._redis_client is None:
            return
        try:
            pubsub = HILManager._redis_client.pubsub()
            await pubsub.subscribe(REDIS_RESOLVE_CHANNEL)
            logger.info("HILManager:已订阅 Redis 审批通知频道")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    result = json.loads(message["data"])
                    request_id = result.get("request_id")
                    if not request_id:
                        continue

                    async with self._lock:
                        request = self._requests.get(request_id)
                        if request and request.status == "pending":
                            request._result = result
                            request.status = result.get("status", "approved")
                            request._event.set()
                            logger.info(
                                f"HILManager:通过 Redis 收到审批通知 {request_id} "
                                f"status={request.status}"
                            )
                except Exception as e:
                    logger.warning(f"HILManager:处理 Redis 审批通知失败: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"HILManager:Redis 监听异常: {e}")

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #

    async def request_approval(
        self,
        checkpoint: str,
        content: str,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """创建审批请求，等待人工确认（或超时自动批准）。

        检查点：requirement_review / contract_review / code_review / final_review。

        行为：
        - HIL_ENABLED=false：直接返回 approved=True，不阻塞（status=skipped）
        - HIL_ENABLED=true：创建请求，asyncio.Event 等待 approve/reject 或超时
        - 超时：自动批准（status=timeout，approved=True）

        Args:
            checkpoint: 检查点名称（必须在 VALID_CHECKPOINTS 中）。
            content: 待审批的内容（如需求 JSON / 契约 YAML / 代码字符串）。
            timeout: 超时时间（秒），None 用 default_timeout。

        Returns:
            审批结果字典：{approved, comments, reviewer, timestamp, status, request_id, checkpoint}
        """
        # 1. 未启用 → 直接跳过
        if not self.enabled:
            logger.info(f"HILManager:HIL 未启用，跳过审批 checkpoint={checkpoint}")
            return {
                "approved": True,
                "comments": "HIL 已禁用，自动通过",
                "reviewer": "system",
                "timestamp": _now_iso(),
                "status": "skipped",
                "request_id": "",
                "checkpoint": checkpoint,
            }

        # 2. 检查 checkpoint 合法性
        if checkpoint not in VALID_CHECKPOINTS:
            logger.warning(f"HILManager:未知检查点 {checkpoint}，自动通过")
            return {
                "approved": True,
                "comments": f"未知检查点 {checkpoint}，自动通过",
                "reviewer": "system",
                "timestamp": _now_iso(),
                "status": "skipped",
                "request_id": "",
                "checkpoint": checkpoint,
            }

        # 3. 确保 Redis 可用
        await self._ensure_redis()

        # 4. 创建审批请求
        timeout_value = timeout if timeout is not None else self.default_timeout
        request_id = f"HIL-{uuid.uuid4().hex[:8]}"
        request = ApprovalRequest(
            request_id=request_id,
            checkpoint=checkpoint,
            content=content,
            timeout=timeout_value,
            created_at=_now_iso(),
        )

        async with self._lock:
            self._requests[request_id] = request

        # 持久化到 Redis
        await self._save_pending_to_redis(request)

        logger.info(
            f"HILManager:创建审批请求 {request_id} checkpoint={checkpoint} "
            f"timeout={timeout_value}s"
        )

        # 5. 等待人工审批或超时
        try:
            await asyncio.wait_for(request._event.wait(), timeout=timeout_value)
            # 被 approve / reject 唤醒
            result = request._result or {
                "approved": True,
                "comments": "",
                "reviewer": "",
                "timestamp": _now_iso(),
                "status": "approved",
            }
        except asyncio.TimeoutError:
            # 超时自动批准
            logger.warning(
                f"HILManager:审批 {request_id} 超时({timeout_value}s)，自动批准"
            )
            result = {
                "approved": True,
                "comments": f"超时({timeout_value}s)自动批准",
                "reviewer": "system",
                "timestamp": _now_iso(),
                "status": "timeout",
            }

        # 6. 补全请求元信息 + 移到历史
        result["request_id"] = request_id
        result["checkpoint"] = checkpoint
        request.status = (
            "approved"
            if result["approved"] and result["status"] != "timeout"
            else result["status"]
        )
        if result["status"] == "timeout":
            request.status = "timeout"
        elif result["approved"]:
            request.status = "approved"
        else:
            request.status = "rejected"

        approval_result = ApprovalResult(
            request_id=request_id,
            checkpoint=checkpoint,
            approved=result["approved"],
            comments=result.get("comments", ""),
            reviewer=result.get("reviewer", ""),
            timestamp=result.get("timestamp", _now_iso()),
            status=result["status"],
        )

        async with self._lock:
            # 从 pending 列表移除，加入历史
            self._requests.pop(request_id, None)
            self._history.append(approval_result)

        # 持久化：移除 Redis 中的 pending，保存历史
        await self._remove_pending_from_redis(request_id)
        await self._save_history_to_redis()

        return approval_result.to_dict()

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """获取所有待审批请求（status=pending）。

        Returns:
            审批请求字典列表（不含内部 _event / _result 字段）。
        """
        return [
            req.to_dict(include_internal=False)
            for req in self._requests.values()
            if req.status == "pending"
        ]

    async def approve(
        self, request_id: str, comments: str = "", reviewer: str = "reviewer"
    ) -> dict[str, Any]:
        """批准指定审批请求。

        Args:
            request_id: 审批请求 ID。
            comments: 审批意见（可选）。
            reviewer: 审批人标识（可选）。

        Returns:
            审批结果字典。若 request_id 不存在或已处理，返回 error 字段。
        """
        return await self._resolve(
            request_id=request_id,
            approved=True,
            comments=comments,
            reviewer=reviewer,
            status="approved",
        )

    async def reject(
        self, request_id: str, comments: str = "", reviewer: str = "reviewer"
    ) -> dict[str, Any]:
        """拒绝指定审批请求。

        Args:
            request_id: 审批请求 ID。
            comments: 拒绝原因（可选）。
            reviewer: 审批人标识（可选）。

        Returns:
            审批结果字典。若 request_id 不存在或已处理，返回 error 字段。
        """
        return await self._resolve(
            request_id=request_id,
            approved=False,
            comments=comments,
            reviewer=reviewer,
            status="rejected",
        )

    def get_history(self) -> list[dict[str, Any]]:
        """获取所有已完成的审批历史。

        Returns:
            审批结果字典列表（按时间顺序）。
        """
        return [r.to_dict() for r in self._history]

    def set_enabled(self, enabled: bool) -> None:
        """运行时切换 HIL 启用状态（不影响已在等待的请求）。

        Args:
            enabled: True 启用，False 禁用。
        """
        self.enabled = enabled
        logger.info(f"HILManager:HIL 已{'启用' if enabled else '禁用'}")

    def clear(self) -> None:
        """清空所有审批请求和历史（仅供测试使用）。"""
        self._requests.clear()
        self._history.clear()

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    async def _resolve(
        self,
        request_id: str,
        approved: bool,
        comments: str,
        reviewer: str,
        status: str,
    ) -> dict[str, Any]:
        """内部：完成审批请求（approve / reject 共用）。"""
        async with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                logger.warning(f"HILManager:审批请求 {request_id} 不存在或已处理")
                return {
                    "error": f"审批请求 {request_id} 不存在或已处理",
                    "request_id": request_id,
                }
            if request.status != "pending":
                logger.warning(
                    f"HILManager:审批请求 {request_id} 已处理 status={request.status}"
                )
                return {
                    "error": f"审批请求 {request_id} 已处理",
                    "request_id": request_id,
                    "status": request.status,
                }

            result = {
                "approved": approved,
                "comments": comments,
                "reviewer": reviewer,
                "timestamp": _now_iso(),
                "status": status,
                "request_id": request_id,
                "checkpoint": request.checkpoint,
            }
            request._result = result
            request.status = status
            # 唤醒等待协程
            request._event.set()

        # 发布到 Redis pub/sub（通知其他 worker）
        await self._publish_resolve(result)

        logger.info(
            f"HILManager:审批 {request_id} 已{status} "
            f"by={reviewer} comments={comments[:50]}"
        )
        return result


def _now_iso() -> str:
    """获取当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


# 全局单例
_hil_manager: Optional[HILManager] = None


def get_hil_manager() -> HILManager:
    """获取 HILManager 单例。"""
    global _hil_manager
    if _hil_manager is None:
        _hil_manager = HILManager()
    return _hil_manager


def reset_hil_manager() -> None:
    """重置 HILManager 单例（仅供测试使用，强制下次重新创建）。"""
    global _hil_manager
    _hil_manager = None
