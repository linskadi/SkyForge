"""SkyForge Engine — 核心引擎（机载轻量部署，零LLM，零Web）。

SLOC: ~10,000
依赖: pyyaml + numpy + loguru (仅 3 包, ~30MB)
用途: 规则引擎驱动的机载代码生成全流程（需求→架构→代码→校验→仿真→报告）

**这是整个 SkyForge v4.0 架构的基础层，上层 (llm/cli/studio) 依赖此层。**
**剥离方式: 单独安装 skyforge-engine，无需任何 LLM 或 Web 依赖。**
"""

from skyforge_engine.pipeline import run_pipeline, run_full_pipeline, repair_loop

__version__ = "0.4.0"
__all__ = ["run_pipeline", "run_full_pipeline", "repair_loop"]
