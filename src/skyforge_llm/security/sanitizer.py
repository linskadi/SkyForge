"""LLM 输入净化器 — 防止敏感数据泄露到云端 API。

净化规则（按执行顺序）:
  1. 移除 C 代码注释（/* */ 与 //），避免注释中的内容被后续规则误脱敏
  2. 脱敏文件路径（/home/user、/Users/user、C:\\Users\\user）
  3. 脱敏硬件寄存器地址（0xXXXXXXXX，8 位十六进制）
  4. 脱敏版本号（vX.Y.Z-suffix）
  5. 脱敏项目内部代号（SkyForge / skyforge / 天锻）

mapping 字典记录所有脱敏对应关系（原始敏感信息 → 占位符），可用于还原。
"""

import re
from dataclasses import dataclass

# 敏感模式
_ADDRESS_PATTERN = re.compile(r"0x[0-9A-Fa-f]{8}")
_PATH_PATTERN = re.compile(r"/home/\w+|/Users/\w+|C:\\Users\\\w+")
_VERSION_PATTERN = re.compile(r"v\d+\.\d+\.\d+-[a-zA-Z0-9]+")
_PROJECT_NAME_PATTERN = re.compile(r"SkyForge|skyforge|天锻")
_C_COMMENT_PATTERN = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


@dataclass
class SanitizedPrompt:
    text: str
    mapping: dict[str, str]  # 脱敏映射表（用于还原）


def sanitize_input(prompt: str) -> SanitizedPrompt:
    """净化输入文本，脱敏敏感信息。

    规则执行顺序（先后顺序很重要）：
      1. 移除 C 代码注释（/* */ 与 //），避免注释中的内容被后续规则误脱敏
      2. 脱敏文件路径（/home/user、/Users/user、C:\\Users\\user）
      3. 脱敏硬件寄存器地址（0xXXXXXXXX，8 位十六进制）
      4. 脱敏版本号（vX.Y.Z-suffix）
      5. 脱敏项目内部代号（SkyForge / skyforge / 天锻）

    Args:
        prompt: 原始输入文本

    Returns:
        SanitizedPrompt，包含净化后文本与脱敏映射表（用于还原）。
        mapping 字典记录所有 原始敏感信息 → 占位符 的对应关系。
    """
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}  # 原始值 → 占位符（用于去重，确保相同输入映射到同一占位符）
    counters = {"comment": 0, "address": 0, "version": 0}

    # 1. 移除 C 注释（含多行注释与单行注释），优先处理避免注释内敏感信息被二次脱敏
    def _replace_comment(m: re.Match[str]) -> str:
        text = m.group(0)
        if text in reverse:
            return reverse[text]
        key = f"<C_COMMENT_{counters['comment']}>"
        counters["comment"] += 1
        mapping[text] = key
        reverse[text] = key
        return key

    cleaned = _C_COMMENT_PATTERN.sub(_replace_comment, prompt)

    # 2. 脱敏文件路径（统一替换为 <PROJECT_ROOT>，无序号）
    def _replace_path(m: re.Match[str]) -> str:
        text = m.group(0)
        if text in reverse:
            return reverse[text]
        key = "<PROJECT_ROOT>"
        mapping[text] = key
        reverse[text] = key
        return key

    cleaned = _PATH_PATTERN.sub(_replace_path, cleaned)

    # 3. 脱敏硬件寄存器地址（按出现顺序分配 0xREG_BASE_NNNN）
    def _replace_address(m: re.Match[str]) -> str:
        text = m.group(0)
        if text in reverse:
            return reverse[text]
        key = f"0xREG_BASE_{counters['address']:04d}"
        counters["address"] += 1
        mapping[text] = key
        reverse[text] = key
        return key

    cleaned = _ADDRESS_PATTERN.sub(_replace_address, cleaned)

    # 4. 脱敏版本号（按出现顺序分配 <VERSION_N>）
    def _replace_version(m: re.Match[str]) -> str:
        text = m.group(0)
        if text in reverse:
            return reverse[text]
        key = f"<VERSION_{counters['version']}>"
        counters["version"] += 1
        mapping[text] = key
        reverse[text] = key
        return key

    cleaned = _VERSION_PATTERN.sub(_replace_version, cleaned)

    # 5. 脱敏项目内部代号（统一替换为 <PROJECT_NAME>，无序号）
    def _replace_project(m: re.Match[str]) -> str:
        text = m.group(0)
        if text in reverse:
            return reverse[text]
        key = "<PROJECT_NAME>"
        mapping[text] = key
        reverse[text] = key
        return key

    cleaned = _PROJECT_NAME_PATTERN.sub(_replace_project, cleaned)

    return SanitizedPrompt(text=cleaned, mapping=mapping)
