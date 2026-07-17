"""WebSocket 流式推送路由：Agent 思考过程实时推送到前端。

WebSocket /ws/agent-stream
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from skyforge_engine.pipeline import run_full_pipeline
from app.core.streaming import get_stream_manager
from app.utils.log_util import logger

router = APIRouter()


@router.websocket("/ws/agent-stream")
async def agent_stream(websocket: WebSocket) -> None:
    """Agent 流式推送 WebSocket。

    协议：
    1. 前端连接后发送 JSON：{"requirement": "...", "scade_file": "..."}
    2. 后端运行 run_full_pipeline，通过 log_hook 逐条推送 Agent 思考消息
    3. 流水线完成后推送 {"level": "complete", "result": {...}}
    4. 连接保持，可继续接收下一个生成请求

    消息格式（与前端 AgentTerminal.vue 对齐）：
    {
        "agent": "REQ-Parser" | "CON-Gen" | "CODE-Gen" | "REPAIR" |
                 "SYSTEM" | "TERMINAL",
        "level": "info" | "success" | "warn" | "error" | "complete",
        "thought": "消息内容",
        "time": "ISO 8601 时间戳"
    }
    """
    await websocket.accept()
    stream_manager = get_stream_manager()
    ws_id = await stream_manager.register(websocket)
    logger.info(f"WebSocket /ws/agent-stream 连接建立 id={ws_id}")

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket 接收消息异常: {e}")
                break

            if not isinstance(data, dict):
                data = {"requirement": str(data)}

            requirement = data.get("requirement", "") or ""
            scade_file = data.get("scade_file", "") or ""

            if not requirement and not scade_file:
                await websocket.send_json(
                    {
                        "agent": "SYSTEM",
                        "level": "error",
                        "thought": "必须提供 requirement 或 scade_file 至少一项",
                        "time": datetime.now().isoformat(),
                    }
                )
                continue

            req_preview = (
                requirement[:50] if requirement else f"<scade_file {len(scade_file)}B>"
            )
            logger.info(f"WebSocket /ws/agent-stream 收到请求: {req_preview}...")

            async def log_hook(agent_name: str, level: str, message: str) -> None:
                try:
                    await websocket.send_json(
                        {
                            "agent": agent_name,
                            "level": level,
                            "thought": message,
                            "time": datetime.now().isoformat(),
                        }
                    )
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    pass

            try:
                result = await run_full_pipeline(
                    requirement=requirement or None,
                    scade_file=scade_file or None,
                    log_hook=log_hook,
                )
                serializable_result = dict(result)
                if "cppcheck_result" in serializable_result:
                    serializable_result["cppcheck_result"] = [
                        asdict(v) for v in serializable_result["cppcheck_result"]
                    ]
                await websocket.send_json(
                    {
                        "agent": "SYSTEM",
                        "level": "complete",
                        "thought": "全流程完成",
                        "result": serializable_result,
                        "time": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"WebSocket pipeline 异常: {e}")
                try:
                    await websocket.send_json(
                        {
                            "agent": "SYSTEM",
                            "level": "error",
                            "thought": f"流水线异常: {e}",
                            "time": datetime.now().isoformat(),
                        }
                    )
                except (WebSocketDisconnect, RuntimeError, ConnectionError):
                    pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket /ws/agent-stream 断开 id={ws_id}")
    except Exception as e:
        logger.error(f"WebSocket /ws/agent-stream 异常: {e}")
    finally:
        await stream_manager.unregister(ws_id)
        logger.info(f"WebSocket /ws/agent-stream 连接清理 id={ws_id}")
