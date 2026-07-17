# SkyForge 天锻 — 第三方组件说明

> **项目**: SkyForge（天锻）— AI 智能体驱动的机载软件轻量化开发工具
> **许可证**: MIT
> **更新日期**: 2026-07-16

---

## 一、运行时依赖

### 1.1 Python 核心依赖（6 包）

| 组件 | 版本 | 许可证 | 用途 | 来源 |
|------|------|--------|------|------|
| pyyaml | >=6.0 | MIT | 契约 YAML 解析 | pypi.org |
| numpy | >=2.2.5 | BSD-3-Clause | 仿真波形计算 | pypi.org |
| loguru | >=0.7.3 | MIT | 日志框架 | pypi.org |
| pydantic | >=2.10.6 | MIT | 数据模型校验 | pypi.org |
| pydantic-settings | >=2.8.0 | MIT | 配置管理 | pypi.org |
| jinja2 | >=3.1 | BSD-3-Clause | HTML 报告模板 | pypi.org |

### 1.2 Web 层依赖

| 组件 | 版本 | 许可证 | 用途 | 来源 |
|------|------|--------|------|------|
| fastapi | >=0.115.8 | MIT | REST API 框架 | pypi.org |
| uvicorn | >=0.34 | BSD-3-Clause | ASGI 服务器 | pypi.org |
| slowapi | >=0.1.9 | MIT | API 限流 | pypi.org |

### 1.3 LLM 层依赖

| 组件 | 版本 | 许可证 | 用途 | 来源 |
|------|------|--------|------|------|
| httpx | >=0.28.1 | BSD-3-Clause | HTTP 客户端 | pypi.org |
| openai | >=1.65.4 | Apache-2.0 | OpenAI/DeepSeek/Qwen API | pypi.org |
| anthropic | >=0.40.0 | MIT | Claude API | pypi.org |

### 1.4 前端依赖

| 组件 | 版本 | 许可证 | 用途 | 来源 |
|------|------|--------|------|------|
| Vue 3 | 3.5+ | MIT | 前端框架 | vuejs.org |
| shadcn-vue (reka-ui) | 2.0+ | MIT | UI 组件库 | shadcn-vue.com |
| Monaco Editor | 0.55+ | MIT | 代码编辑器 | microsoft.github.io |
| ECharts | 6.1+ | Apache-2.0 | 波形图 | echarts.apache.org |
| Pinia | 3.0+ | MIT | 状态管理 | pinia.vuejs.org |
| Vite | 6.1+ | MIT | 构建工具 | vitejs.dev |
| TypeScript | 5.x | Apache-2.0 | 类型系统 | typescriptlang.org |
| Tailwind CSS | 3.x | MIT | CSS 框架 | tailwindcss.com |

### 1.5 开发工具

| 组件 | 版本 | 许可证 | 用途 | 来源 |
|------|------|--------|------|------|
| ruff | >=0.9.10 | MIT | Python 代码质量 | pypi.org |
| uv | >=0.11 | MIT | Python 包管理 | astral.sh |
| pnpm | >=10 | MIT | Node 包管理 | pnpm.io |
| Biome | 1.x | MIT | TypeScript 代码质量 | biomejs.dev |

---

## 二、可选外部工具（可按需安装）

### 2.1 静态分析

| 工具 | 许可证 | 用途 | 集成文件 | 安装方式 |
|------|--------|------|---------|---------|
| Cppcheck | GPL-3.0 | MISRA-C 静态扫描 | `tools/cppcheck_scanner.py` | `apt install cppcheck` |
| GCC | GPL-3.0 | 代码编译 | `digital_twin/virtual_mcu.py` | 系统自带 |
| Semgrep | LGPL-2.1 | 模式匹配 + 自定义 MISRA 规则 | `tools/semgrep_scanner.py` | `pip install semgrep` |

### 2.2 形式化验证

| 工具 | 许可证 | 用途 | 集成文件 | 安装方式 |
|------|--------|------|---------|---------|
| CBMC | BSD-4-Clause | 有界模型检查 | `tools/cbmc_verifier.py` | `apt install cbmc` |
| Z3 | MIT | SMT 约束求解 | `tools/z3_verifier.py` | `pip install z3-solver` |
| Frama-C/WP | LGPL-2.1 | 演绎验证（远期） | — | `apt install frama-c` |

### 2.3 覆盖率

| 工具 | 许可证 | 用途 | 集成文件 | 安装方式 |
|------|--------|------|---------|---------|
| GCC 14.2+ | GPL-3.0 | MC/DC 覆盖率插桩 | `dal/mcdc_calculator.py` | 系统自带 |
| lcov | GPL-2.0 | 覆盖率报告生成 | `report/coverage_analyzer.py` | `apt install lcov` |

### 2.4 报告

| 工具 | 许可证 | 用途 | 集成文件 | 安装方式 |
|------|--------|------|---------|---------|
| WeasyPrint | BSD-3-Clause | HTML→PDF | `report/report_generator.py` | `pip install weasyprint` |
| ReqIF 库 | Apache-2.0 | DOORS 格式追溯 | `report/traceability_matrix.py` | `pip install reqif` |

### 2.5 航空运行时模板（远期）

| 工具 | 许可证 | 用途 | 来源 |
|------|--------|------|------|
| FreeRTOS | MIT | RTOS 任务调度 | freertos.org |
| a653lib (Airbus) | Apache-2.0 | ARINC 653 分区 | github.com/airbus/a653lib |
| ArduPilot | BSD-3-Clause | 飞控组件 | ardupilot.org |
| PX4 | BSD-3-Clause | 飞控固件 | px4.io |

---

## 三、知识库数据

| 数据 | 格式 | 大小 | 来源 | 说明 |
|------|------|------|------|------|
| MISRA-C:2012 规则 | TXT | 136KB | MISRA Consortium | 143/175 条规则覆盖 |
| DO-178C 目标清单 | Python | — | RTCA DO-178C/ED-12C | 19 项目标 DAL 自适应 |
| 组件模板 | C/YAML | 5 种 | 自主研发 | filter/control/comms/nav/power |

---

## 四、许可证兼容性说明

本项目采用 **MIT** 许可证。所有集成的第三方组件均使用兼容的开源许可证：
- **MIT** (pyyaml/loguru/pydantic/fastapi/z3-solver/FreeRTOS/Vue/Pinia/Vite/Tailwind): 完全兼容
- **BSD** (numpy/jinja2/uvicorn/httpx/CBMC/WeasyPrint/PX4): 完全兼容
- **Apache-2.0** (openai/ReqIF/a653lib/ECharts): 完全兼容
- **LGPL-2.1** (semgrep/Frama-C): 动态链接兼容
- **GPL** (Cppcheck/GCC/lcov): 外部工具调用（非链接）

核心算法（5 Agent、契约式设计、数字孪生、流水线编排）均为团队自主研发，未使用闭源或私有协议组件。
