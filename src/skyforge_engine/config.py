"""应用配置模块，基于 pydantic-settings 管理环境变量和全局配置。"""

import json
from enum import Enum
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_files(env: str) -> tuple[str, str, str]:
    """Return repository-absolute env paths, independent of process cwd."""
    return (
        str(_REPO_ROOT / "config" / ".env"),
        str(_REPO_ROOT / ".env"),
        str(_REPO_ROOT / f".env.{env.lower()}"),
    )


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
    """全局应用配置，从环境变量和 .env 文件加载。

    字段分组：
        - LLM：USE_LLM / LMSTUDIO_BASE_URL / LLM_MODEL 等，主 LLM 调用配置
        - LLM 缓存：LLM_CACHE_ENABLED / LLM_CACHE_TTL
        - 系统：MAX_RETRIES / LOG_LEVEL / DEBUG
        - 数字孪生 / 虚拟 MCU：USE_REAL_GCC
        - HIL：HIL_ENABLED / HIL_INTERFACE 等，真实硬件在环测试
        - Agent LLM：REQ_PARSER_* / CON_GEN_* / CODE_GEN_* / REPAIR_*
        - Redis / CORS / 服务地址
        - 工具开关：USE_REAL_CPPCHECK / RAG_ENABLED
        - 安全：SECURITY_SANITIZE_INPUT / SECURITY_AUDIT_ENABLED / SECURITY_VALIDATE_OUTPUT
            - SECURITY_SANITIZE_INPUT：是否对 LLM 输入执行净化，默认 False。
              关闭原因：净化可能破坏 LLM 对代码注释、版本号、字符串字面量的语义理解，
              导致生成代码错乱；仅在受控场景下手动开启。
            - SECURITY_AUDIT_ENABLED：是否记录 LLM 调用审计日志，默认 True。
              启用原因：DO-178C 工具鉴定要求对工具操作留痕，审计日志是合规性证据。
            - SECURITY_VALIDATE_OUTPUT：是否校验 LLM 输出禁止模式，默认 True。
              启用原因：机载软件禁用 malloc/free/goto/system/exec 等不安全构造，
              输出校验是阻断危险代码进入编译流程的最后一道防线。
    """

    ENV: str = "dev"

    # LLM 配置
    USE_LLM: bool = True
    LMSTUDIO_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MAX_TOKENS: int = 8192
    # 显式选择 mock 模式，非降级结果
    SKYFORGE_LLM_MODE: str = "mock"
    SKYFORGE_LLM_PROVIDER: Optional[str] = None
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434/v1"
    SKYFORGE_LLM_WARMUP: bool = False

    # LLM 响应缓存配置（对相同 prompt + system_prompt 的非流式调用做缓存）
    LLM_CACHE_ENABLED: bool = True
    LLM_CACHE_TTL: int = 3600

    # 系统配置
    MAX_RETRIES: int = 3
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True
    STRICT_MODE: bool = True

    # 数字孪生 / 虚拟 MCU 配置
    # USE_REAL_GCC=true 时启用真实 GCC 编译（需系统已安装 gcc）
    USE_REAL_GCC: bool = True

    # HIL（Hardware-in-the-Loop）真实硬件测试配置
    # HIL_ENABLED=true 时启用真实硬件在环测试（需连接真实 MCU）
    HIL_ENABLED: bool = False
    # HIL 接口类型：serial（UART串口）| jtag_swd（JTAG/SWD调试接口）
    HIL_INTERFACE: str = "serial"
    # 串口配置（HIL_INTERFACE=serial 时生效）
    HIL_SERIAL_PORT: str = "COM3"
    HIL_BAUD_RATE: int = 115200
    HIL_SERIAL_TIMEOUT: int = 5
    # JTAG/SWD 配置（HIL_INTERFACE=jtag_swd 时生效）
    HIL_JTAG_DEVICE: str = "STLINK"
    HIL_JTAG_TARGET: str = "STM32F407"
    HIL_JTAG_CLOCK: int = 4000000
    # HIL 通用配置
    HIL_FLASH_TIMEOUT: int = 30
    HIL_RUN_TIMEOUT: int = 30
    # 固件文件路径（HIL 模式下预编译的 ELF/BIN 文件，为空则尝试在线编译）
    HIL_FIRMWARE_PATH: str = ""

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
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 服务地址
    SERVER_HOST: str = "http://localhost:8000"

    # HITL（Human-in-the-Loop）人工审查配置。
    # HIL_ENABLED 在上方只控制真实 Hardware-in-the-Loop，二者不得混用。
    HITL_ENABLED: bool = False
    HITL_TIMEOUT: int = 300

    # Cppcheck 扫描配置
    # True（默认）：调用真实 cppcheck --addon=misra --dump
    USE_REAL_CPPCHECK: bool = True

    # RAG 知识库配置
    # True（默认）：MISRA-C 规则通过 RAG 注入代码修复 prompt，提升修复准确率
    # False：关闭 RAG 增强，仅使用 Agent 自身知识
    RAG_ENABLED: bool = True

    # 安全配置（接入 security/ 子模块：审计日志、输出校验、输入净化）
    # 是否对 LLM 输入执行净化（默认关闭：避免破坏 LLM 对代码注释/版本号/字符串字面量的语义理解）
    SECURITY_SANITIZE_INPUT: bool = False
    # 是否记录 LLM 调用审计日志（默认启用：DO-178C 工具鉴定要求对工具操作留痕）
    SECURITY_AUDIT_ENABLED: bool = True
    # 是否校验 LLM 输出禁止模式（默认启用：检测 malloc/free/goto/system/exec 等机载软件禁用构造）
    SECURITY_VALIDATE_OUTPUT: bool = True

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
        return cls(
            _env_file=_env_files(env),
            _env_file_encoding="utf-8",
        )  # type: ignore[call-arg]


# 根据 ENV 环境变量加载对应配置文件
_env = os.getenv("ENV", "dev")
settings = Settings(
    _env_file=_env_files(_env),
    _env_file_encoding="utf-8",
)
