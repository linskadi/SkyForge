"""简单的 API Token 鉴权依赖。

生产环境应替换为 JWT / OAuth2 / SSO 方案。
当前实现：从 X-API-Token 头读取 token，与环境变量 SKYFORGE_API_TOKEN 比对。

未配置 SKYFORGE_API_TOKEN 时，鉴权关闭（仅限开发环境）。
"""
import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


def require_write_access(
    token: str = Security(_api_key_header),
) -> str:
    """写操作鉴权依赖。

    若环境变量 SKYFORGE_API_TOKEN 未设置，则鉴权关闭（开发模式）。
    若已设置，请求必须携带匹配的 X-API-Token 头。
    """
    expected = os.environ.get("SKYFORGE_API_TOKEN", "")
    if not expected:
        return "anonymous"
    if token != expected:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token",
            headers={"WWW-Authenticate": "X-API-Token"},
        )
    return "authenticated"