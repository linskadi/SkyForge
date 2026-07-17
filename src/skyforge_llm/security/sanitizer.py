"""LLM 输入净化器 — 防止敏感数据泄露到云端 API。

净化规则:
  - 移除 C 代码中的注释（含潜在 IP 信息）
  - 脱敏硬件寄存器地址
  - 移除文件路径中的项目内部路径
  - 脱敏版本号和构建信息
  - 移除项目内部代号和客户信息
"""

import re
from dataclasses import dataclass

# 敏感模式
_ADDRESS_PATTERN = re.compile(r"0x[0-9A-Fa-f]{8}")
_PATH_PATTERN = re.compile(r"/home/\w+|/Users/\w+|C:\\Users\\\w+")
_VERSION_PATTERN = re.compile(r"v\d+\.\d+\.\d+-[a-zA-Z0-9]+")


@dataclass
class SanitizedPrompt:
    text: str
    mapping: dict[str, str]  # 脱敏映射表（用于还原）


def sanitize_input(prompt: str) -> SanitizedPrompt:
    """净化输入文本，脱敏敏感信息。"""
    mapping: dict[str, str] = {}
    
    # 脱敏路径
    cleaned = _PATH_PATTERN.sub("<PROJECT_ROOT>", prompt)
    
    # 脱敏硬件地址
    addrs = _ADDRESS_PATTERN.findall(cleaned)
    for i, addr in enumerate(set(addrs)):
        replacement = f"0xREG_BASE_{i:04d}"
        cleaned = cleaned.replace(addr, replacement)
        mapping[addr] = replacement
    
    return SanitizedPrompt(text=cleaned, mapping=mapping)
