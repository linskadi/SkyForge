"""SCADE 模型输入支持（次级功能）。

G-Lustre 是 Lustre 数据流语言的一种变体，由 SCADE 工程转换工具生成。

本模块将 G-Lustre 文件作为可选输入，解析为结构化数据，
并转换为自然语言需求 + 契约 YAML，接入 AirborneAI 流水线。

子模块：
- lustre_parser：G-Lustre 文本解析器（node/inputs/outputs/locals/equations）
- lustre_to_requirement：G-Lustre → 自然语言需求 + 契约 YAML 转换器

模块导出：
- parse_glustre / ParsedLustre / Variable / Equation
- convert / convert_to_contract
"""

from app.core.scade.lustre_parser import (
    Equation,
    ParsedLustre,
    Variable,
    parse_glustre,
)
from app.core.scade.lustre_to_requirement import convert, convert_to_contract

__all__ = [
    # 解析器
    "Equation",
    "ParsedLustre",
    "Variable",
    "parse_glustre",
    # 转换器
    "convert",
    "convert_to_contract",
]
