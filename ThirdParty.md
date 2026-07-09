# 第三方组件说明

本文档列出 SkyForge 项目使用的所有第三方开源组件，用于航空工业软件开源创新大赛开源合规审查。

---

## 一、后端依赖（Python）

| 组件名称 | 版本要求 | 用途说明 | 许可证 |
|----------|----------|----------|--------|
| FastAPI | >=0.115.8 | 高性能 Web 框架，提供 REST API 服务 | MIT |
| Uvicorn | (FastAPI依赖) | ASGI 服务器 | BSD-3-Clause |
| OpenAI | >=1.65.4 | 调用 OpenAI/LM Studio LLM 接口 | Apache-2.0 |
| Anthropic | >=0.40.0 | 调用 Anthropic Claude LLM 接口 | MIT |
| Pydantic | >=2.10.6 | 数据模型定义与校验 | MIT |
| Pydantic Settings | >=2.8.0 | 环境变量配置管理 | MIT |
| HTTPX | >=0.28.1 | 异步 HTTP 客户端（支持 SOCKS 代理） | BSD-3-Clause |
| Redis | >=5.2.1 | 缓存/消息队列（可选） | MIT |
| Loguru | >=0.7.3 | 日志管理 | MIT |
| NumPy | >=2.2.5 | 数值计算（仿真引擎） | BSD-3-Clause |
| PyYAML | >=6.0 | YAML 解析（契约处理） | MIT |
| Jinja2 | >=3.1 | 模板引擎（报告生成） | BSD-3-Clause |

### 开发依赖

| 组件名称 | 版本要求 | 用途说明 | 许可证 |
|----------|----------|----------|--------|
| Ruff | >=0.9.10 | Python 代码规范检查与格式化 | MIT |

---

## 二、前端依赖（Node.js）

### 核心框架

| 组件名称 | 版本 | 用途说明 | 许可证 |
|----------|------|----------|--------|
| Vue | ^3.5.13 | 前端响应式框架 | MIT |
| Vue Router | 4 | 路由管理 | MIT |
| Pinia | ^3.0.1 | 状态管理 | MIT |
| Vite | ^6.1.0 | 构建工具与开发服务器 | MIT |

### UI 组件

| 组件名称 | 版本 | 用途说明 | 许可证 |
|----------|------|----------|--------|
| shadcn-vue (reka-ui) | ^2.0.0 | UI 组件库基础 | MIT |
| Tailwind CSS | 3 | 原子化 CSS 框架 | MIT |
| Lucide Vue Next | ^0.475.0 | 图标库 | ISC |

### 功能组件

| 组件名称 | 版本 | 用途说明 | 许可证 |
|----------|------|----------|--------|
| Monaco Editor | ^0.55.1 | 代码编辑器（VS Code 同款） | MIT |
| ECharts | ^6.1.0 | 数据可视化图表 | Apache-2.0 |
| Vue-ECharts | ^8.0.1 | ECharts Vue 封装 | MIT |
| Marked | ^15.0.11 | Markdown 渲染 | MIT |
| KaTeX | ^0.16.22 | 数学公式渲染 | MIT |
| DOMPurify | ^3.4.11 | HTML 净化（XSS 防护） | MPL-2.0 |
| TanStack Vue Table | ^8.21.3 | 表格组件 | MIT |
| TanStack Vue Virtual | ^3.13.31 | 虚拟滚动 | MIT |
| VueUse | ^12.7.0 | Vue 组合式工具库 | MIT |
| Marked KaTeX Extension | ^5.1.4 | Markdown KaTeX 扩展 | MIT |
| Pinia Plugin Persistedstate | ^4.5.0 | Pinia 状态持久化 | MIT |
| Class Variance Authority | ^0.7.1 | 样式变体工具 | MIT |
| clsx | ^2.1.1 | 类名构建工具 | MIT |
| Tailwind Merge | ^3.0.2 | Tailwind 类名合并 | MIT |
| Tailwind CSS Animate | ^1.0.7 | Tailwind 动画插件 | MIT |

### 开发依赖

| 组件名称 | 版本 | 用途说明 | 许可证 |
|----------|------|----------|--------|
| Biome | 1.9.4 | 代码规范检查与格式化 | MIT |
| TypeScript | ~5.7.2 | 类型系统 | Apache-2.0 |
| Vitest | ^3.2.7 | 单元测试框架 | MIT |
| Vue Test Utils | ^2.4.11 | Vue 组件测试工具 | MIT |
| Vite Plugin Vue | ^5.2.1 | Vite Vue 插件 | MIT |
| Vue TSC | ^2.2.0 | Vue TypeScript 类型检查 | MIT |
| jsdom | ^26.1.0 | DOM 模拟（测试用） | MIT |
| Autoprefixer | ^10.4.20 | CSS 浏览器前缀 | MIT |

---

## 三、开发工具链

| 工具名称 | 用途说明 | 许可证 |
|----------|----------|--------|
| Cppcheck | MISRA-C 静态代码分析（外部工具） | GPL-3.0 |
| Docker | 容器化部署 | Apache-2.0 |
| GitHub Actions | CI/CD 持续集成 | MIT |

---

## 四、核心自研模块

以下模块为团队自主研发，非第三方组件：

| 模块名称 | 文件位置 | 说明 |
|----------|----------|------|
| 需求解析 Agent | `backend/app/core/agents/requirement_parser_agent.py` | 自然语言需求转结构化 JSON |
| 契约生成 Agent | `backend/app/core/agents/contract_generator_agent.py` | 生成 DO-178C 合规契约 YAML |
| 代码生成 Agent | `backend/app/core/agents/code_generator_agent.py` | 生成 MISRA-C 风格 C 代码 |
| 代码修复 Agent | `backend/app/core/agents/code_repairer_agent.py` | MISRA 违规自动修复 |
| 全流程编排器 | `backend/app/core/pipeline.py` | Agent 协同编排 |
| 数字孪生仿真 | `backend/app/core/digital_twin/` | 虚拟传感器/MCU/故障注入 |
| HIL 人机协作 | `backend/app/core/hil/` | 关键检查点人工审批 |
| DO-178C 报告生成 | `backend/app/core/report/` | 合规报告与追溯矩阵 |
| SCADE 解析器 | `backend/app/core/scade/` | G-Lustre 文件解析与转换 |
| MISRA 规则库 | `backend/app/rag/data/misra_rules.txt` | MISRA-C 规则数据 |

---

## 五、许可证兼容性说明

本项目采用 **MIT 许可证** 开源。

| 组件许可证 | 与 MIT 兼容性 | 使用方式 |
|------------|---------------|----------|
| MIT | ✅ 完全兼容 | 直接使用 |
| Apache-2.0 | ✅ 兼容 | 需保留原始版权声明 |
| BSD-2/3-Clause | ✅ 兼容 | 需保留原始版权声明 |
| ISC | ✅ 兼容 | 与 MIT 基本等同 |
| MPL-2.0 | ✅ 兼容 | 文件级 copyleft，不影响本项目 |
| GPL-3.0（Cppcheck） | ⚠️ 仅工具使用 | 作为外部工具调用，不链接/不修改，不触发传染性 |

---

## 六、声明

1. 所有第三方组件的使用均遵循其原始许可证要求
2. 本项目的创新点（多Agent协同、数字孪生、HIL人机协作等）为团队自主研发
3. 如有任何许可证相关问题，请联系：kefu@jsopen.org.cn
