"""外部工具链注册表 API。

提供工具链注册表现状查询，前端可动态获取工具列表和可用性状态。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.tool_manager import TOOLS_REQUIREMENTS, check_all_tools

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/registry")
async def get_tool_registry() -> JSONResponse:
    """返回工具链注册表的实时状态。

    包括所有已注册工具的名称、最低版本、用途描述、安装提示、
    实际检测到的版本和是否可用。

    前端系统设置页面通过此接口动态渲染工具链状态列表。
    """
    tools = check_all_tools()
    return JSONResponse(
        content=[
            {
                "name": t.name,
                "min_version": t.min_version,
                "description": t.description,
                "install_hint": t.install_hint,
                "found": t.found,
                "version": t.version,
            }
            for t in tools
        ],
        headers={"Cache-Control": "no-store"},
    )


# ============================================================================
# 工具执行与安装指引端点
# ============================================================================

from app.core.tool_manager import ToolExecutor, get_install_hint  # noqa: E402
from app.core.auth import require_write_access  # noqa: E402


@router.get("/{tool_name}/install-hint")
async def get_tool_install_hint(tool_name: str) -> JSONResponse:
    """返回指定工具在不同平台上的安装指引。"""
    hints = get_install_hint(tool_name)
    return JSONResponse(
        content={
            "tool_name": tool_name,
            "hints": hints,
        },
        headers={"Cache-Control": "max-age=3600"},
    )


@router.post("/execute")
async def execute_tool(
    payload: dict,
    _user: str = Depends(require_write_access),
) -> JSONResponse:
    """执行指定工具并返回标准化结果。

    注意：此端点需要写权限。生产环境应配置额外的安全限制。

    请求体:
        tool_name: 工具名称
        args: 命令行参数列表（可选）
        timeout: 超时时间秒（可选，默认 60）
    """
    tool_name = payload.get("tool_name", "")
    if not tool_name:
        return JSONResponse(
            status_code=400,
            content={"detail": "必须指定 tool_name"},
        )

    # 安全校验：只允许执行已注册的工具
    registered = {t.name for t in TOOLS_REQUIREMENTS}
    if tool_name not in registered:
        return JSONResponse(
            status_code=403,
            content={"detail": f"工具 {tool_name} 未注册，禁止执行"},
        )

    args = payload.get("args") or []
    timeout = int(payload.get("timeout") or 60)

    result = ToolExecutor.run(tool_name=tool_name, args=args, timeout=timeout)

    return JSONResponse(
        content={
            "tool_name": result.tool_name,
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout": result.stdout[:8000],  # 限制输出大小
            "stderr": result.stderr[:8000],
            "duration_ms": result.duration_ms,
            "parsed_result": result.parsed_result,
            "error_message": result.error_message,
        },
        headers={"Cache-Control": "no-store"},
    )
