"""应用配置模块，基于 pydantic-settings 管理环境变量和全局配置。"""

import json
from enum import Enum
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Annotated, Optional


class ApiType(str, Enum):
    """LLM API 类型枚举。"""

    OPENAI_CHAT = "openai-chat"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic"


def parse_cors(value: str | list) -> list[str]:
    """将 CORS 配置解析为 URL 列表。

    支持格式：
    - "*" → ["*"]
    - "url1,url2" → ["url1", "url2"]
    - '["url1","url2"]' → ["url1", "url2"]
    - ["url1", "url2"] → ["url1", "url2"]（已是列表）

    Args:
        value: CORS 配置值。

    Returns:
        解析后的 URL 列表。
    """
    if isinstance(value, list):
        return value
    if value == "*":
        return ["*"]
    # 尝试 JSON 数组解析
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    # 逗号分隔
    if "," in value:
        return [url.strip() for url in value.split(",")]
    return [value]


class Settings(BaseSettings):
    """全局应用配置，从环境变量和 .env 文件加载。"""

    ENV: str = "dev"

    # LLM 配置
    USE_LLM: bool = False
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LLM_MODEL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MAX_TOKENS: int = 8192

    # 系统配置
    MAX_RETRIES: int = 3
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # Agent LLM 配置
    REQ_PARSER_API_TYPE: str = "openai-chat"
    REQ_PARSER_API_KEY: str = ""
    REQ_PARSER_MODEL: str = ""
    REQ_PARSER_BASE_URL: str = ""
    REQ_PARSER_MAX_TOKENS: int = 4096

    CON_GEN_API_TYPE: str = "openai-chat"
    CON_GEN_API_KEY: str = ""
    CON_GEN_MODEL: str = ""
    CON_GEN_BASE_URL: str = ""
    CON_GEN_MAX_TOKENS: int = 4096

    CODE_GEN_API_TYPE: str = "openai-chat"
    CODE_GEN_API_KEY: str = ""
    CODE_GEN_MODEL: str = ""
    CODE_GEN_BASE_URL: str = ""
    CODE_GEN_MAX_TOKENS: int = 4096

    REPAIR_API_TYPE: str = "openai-chat"
    REPAIR_API_KEY: str = ""
    REPAIR_MODEL: str = ""
    REPAIR_BASE_URL: str = ""
    REPAIR_MAX_TOKENS: int = 4096

    # Redis 配置（可选）
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10

    # CORS 配置
    CORS_ALLOW_ORIGINS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = "*"

    # 服务地址
    SERVER_HOST: str = "http://localhost:8000"

    # HIL 人机协作配置
    HIL_ENABLED: bool = False
    HIL_TIMEOUT: int = 300

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="allow",
    )

    @classmethod
    def from_env(cls, env: str | None = None):
        """根据环境名称加载对应配置。

        Args:
            env: 环境名称（如 dev、prod），默认从 ENV 环境变量获取。
        """
        env = env or os.getenv("ENV", "dev")
        env_file = f".env.{env.lower()}"
        return cls(_env_file=(".env", env_file), _env_file_encoding="utf-8")  # type: ignore[call-arg]


# 根据 ENV 环境变量加载对应配置文件
_env = os.getenv("ENV", "dev")
settings = Settings(_env_file=(".env", f".env.{_env}"), _env_file_encoding="utf-8")
