"""Pipeline Stage 共享工具函数。"""

from __future__ import annotations

import functools
import inspect
import shutil
import subprocess
import warnings
from dataclasses import asdict
from typing import Any, Awaitable, Callable, Union

from skyforge_engine.utils.log_util import logger

LogHook = Callable[[str, str, str], Union[None, Awaitable[None]]]
AsyncLogHook = Callable[[str, str, str], Awaitable[None]]


def deprecated(reason: str = "") -> Callable:
    """标记函数/协程为已弃用。"""

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(
                    f"{func.__name__} is deprecated. {reason}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(
                    f"{func.__name__} is deprecated. {reason}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def _installed_tool_version(command: str) -> str | None:
    path = shutil.which(command)
    if path is None:
        return None
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        lines = (result.stdout or result.stderr).splitlines()
        return lines[0].strip() if lines else None
    except (OSError, subprocess.TimeoutExpired):
        return None


async def _default_hook(agent_name: str, level: str, message: str) -> None:
    """默认日志 hook：输出到 logger。"""
    logger.info(f"[Pipeline] {agent_name}[{level}]: {message}")


def _normalize_hook(log_hook: LogHook | None) -> AsyncLogHook:
    """归一化 hook 为 async 形式，兼容 sync / async / None。"""
    if log_hook is None:
        return _default_hook
    if inspect.iscoroutinefunction(log_hook):
        return log_hook

    async def _wrapper(agent_name: str, level: str, message: str) -> None:
        log_hook(agent_name, level, message)

    return _wrapper


def _make_sync_log_collector() -> tuple[
    Callable[[str, str, str], None], list[tuple[str, str, str]]
]:
    """创建同步 log_callback，收集消息供后续异步推送。"""
    messages: list[tuple[str, str, str]] = []

    def callback(agent: str, level: str, message: str) -> None:
        messages.append((agent, level, message))

    return callback, messages


async def _flush_collected_logs(
    hook: AsyncLogHook, messages: list[tuple[str, str, str]]
) -> None:
    """将收集到的同步日志通过 async hook 推送。"""
    for agent, level, msg in messages:
        await hook(agent, level, msg)


async def _push_agent_thought(
    hook: AsyncLogHook, agent_name: str, context_desc: str
) -> None:
    """推送一条 Agent 思考消息。"""
    from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client

    client = get_lmstudio_client()
    if client.is_available():
        try:
            thought = ""
            async for token in client.chat_stream(
                prompt=(
                    "你是航空软件工程 Agent。用一句话（不超过 50 字）"
                    f"简述你即将执行的任务：{context_desc}"
                ),
                max_tokens=80,
            ):
                thought += token
            thought = thought.strip() or context_desc
            await hook(agent_name, "info", thought)
            return
        except Exception as e:
            logger.warning(f"Pipeline:LLM 流式思考生成失败，降级为静态文案: {e}")
    await hook(agent_name, "info", context_desc)


async def _log_llm_status(hook: AsyncLogHook) -> None:
    """记录 LM Studio 状态（使用真实 LLM 还是 Mock）。"""
    import os

    from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client

    use_llm_env = os.getenv("USE_LLM", "true").lower() == "true"
    client = get_lmstudio_client()
    if use_llm_env and client.is_available():
        models = client.get_available_models()
        await hook(
            "SYSTEM",
            "info",
            f"[LLM模式] 真实 LLM 已启用，已加载模型: {models}",
        )
        logger.info(
            f"[Pipeline] ✅ 使用真实 LLM（USE_LLM=true），已加载模型: {models}"
        )
    elif not use_llm_env:
        await hook(
            "SYSTEM",
            "warn",
            "[降级] USE_LLM=false，Agent 将使用 Mock 模式（关键词匹配+模板拼接，非 AI 推理）",
        )
        logger.warning(
            "[Pipeline] ⚠️ 使用 Mock 模式（USE_LLM=false）"
            "——这不是真实 AI 推理，仅作为降级方案"
        )
    else:
        await hook(
            "SYSTEM",
            "warn",
            "[降级] 本地 LLM 不可用，Agent 将使用 Mock 模式（关键词匹配+模板拼接，非 AI 推理）。"
            "请启动 Ollama / LM Studio 等本地 LLM 服务并加载模型以启用真实 LLM。",
        )
        logger.warning(
            "[Pipeline] ⚠️ 使用 Mock 模式（本地 LLM 不可用）"
            "——这不是真实 AI 推理，仅作为降级方案。"
            "请启动 Ollama / LM Studio 等本地 LLM 服务并加载模型。"
        )


async def _run_hil_checkpoint(
    checkpoint: str,
    content: str,
    hook: AsyncLogHook,
    timeout: int = 300,
    task_id: str = "",
) -> dict[str, Any]:
    """在 HIL 检查点请求人工审批，返回审批结果字典。"""
    from skyforge_engine.hil_provider import get_hil_manager

    manager = get_hil_manager()
    await hook("SYSTEM", "info", f"{checkpoint}:等待人工审批")
    result = await manager.request_approval(
        checkpoint=checkpoint,
        content=content,
        timeout=timeout,
        task_id=task_id,
    )
    status_str = result.get("status", "approved")
    approved = result.get("approved", False)
    level = "success" if approved else "error"
    await hook(
        "SYSTEM",
        level,
        f"{checkpoint}:审批完成 status={status_str} approved={approved}",
    )
    return result


def _check_result_to_dict(result: Any) -> dict[str, Any]:
    """将 CheckResult 转为可序列化字典（供 API 返回）。"""
    from skyforge_engine.tools.contract_checker import CheckResult

    if not isinstance(result, CheckResult):
        return {}
    return {
        "passed": result.passed,
        "preconditions": [asdict(item) for item in result.preconditions],
        "postconditions": [asdict(item) for item in result.postconditions],
        "invariants": [asdict(item) for item in result.invariants],
        "fault_handling": [asdict(item) for item in result.fault_handling],
        "assert_code": result.assert_code,
        "violations": result.violations,
    }
