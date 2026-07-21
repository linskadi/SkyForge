"""编码标准插件系统。

DO-178C 过程标准固定不动，编码标准通过插件化注册机制实现可插拔。
开发者可通过以下步骤添加新编码标准：

1. 在本包下创建新模块（如 my_standard.py）
2. 定义 CodingStandard 实例
3. 调用 get_registry().register(standard) 注册

示例：
    from skyforge_engine.coding_standards import CodingStandard, get_registry

    standard = CodingStandard(
        standard_id="my_std",
        name="My Coding Standard",
        languages=["c"],
        rule_data_file="path/to/rules.txt",
    )
    get_registry().register(standard)
"""

from skyforge_engine.coding_standards.base import (
    CodingStandard,
    CodingStandardRegistry,
    get_registry,
)

__all__ = [
    "CodingStandard",
    "CodingStandardRegistry",
    "get_registry",
]
