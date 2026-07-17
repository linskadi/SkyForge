# SkyForge 架构文档

## 概述

SkyForge 采用四层可剥离架构设计，从轻量级核心引擎到完整的 Web 工作室，可根据需求灵活部署。

## 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: Web 工作室                        │
│              (FastAPI + Vue 3 + WebSocket)                   │
├─────────────────────────────────────────────────────────────┤
│                    Layer 2: CLI 工具                          │
│               (skyforge-core CLI)                            │
├─────────────────────────────────────────────────────────────┤
│                    Layer 1: LLM 抽象层                       │
│           (skyforge-llm 多模型支持)                          │
├─────────────────────────────────────────────────────────────┤
│                    Layer 0: 核心引擎                         │
│            (skyforge-engine 零LLM零Web)                      │
└─────────────────────────────────────────────────────────────┘
```

## Layer 0: 核心引擎 (skyforge_engine)

核心引擎是整个系统的基础，不依赖 LLM 和 Web 框架，可独立运行。

### 模块结构

```
skyforge_engine/
├── pipeline.py              # 全流程编排
├── agents/                  # Agent 系统
│   ├── requirement_agent.py  # 需求解析 Agent
│   ├── contract_agent.py     # 契约生成 Agent
│   ├── code_agent.py         # 代码生成 Agent
│   ├── compliance_agent.py   # 合规检查 Agent
│   └── repair_agent.py       # 修复 Agent
├── tools/                   # 工具集合
│   ├── cppcheck_tool.py      # Cppcheck 集成
│   ├── contract_tool.py      # 契约工具
│   └── toolchain_validator.py # 工具链验证
├── digital_twin/            # 数字孪生
│   ├── virtual_sensor.py     # 虚拟传感器
│   ├── virtual_mcu.py        # 虚拟 MCU
│   └── fault_injection.py    # 故障注入
├── report/                  # DO-178C 报告
│   ├── generator.py          # 报告生成器
│   └── templates/            # 报告模板
├── rag/                     # RAG 知识库
│   └── misra_rules.json      # MISRA-C 规则库
└── schemas/                 # 数据模型
    ├── requirement.py        # 需求模型
    ├── contract.py           # 契约模型
    └── code.py               # 代码模型
```

### 核心流程

```python
# pipeline.py 核心流程
class Pipeline:
    def run(self, requirement: str) -> PipelineResult:
        # 1. 需求解析
        parsed = self.requirement_agent.parse(requirement)
        
        # 2. 契约生成
        contract = self.contract_agent.generate(parsed)
        
        # 3. 代码生成
        code = self.code_agent.generate(contract)
        
        # 4. 合规检查
        compliance = self.compliance_agent.check(code)
        
        # 5. 自动修复（如需要）
        if not compliance.passed:
            code = self.repair_agent.repair(code, compliance.issues)
        
        return PipelineResult(code=code, compliance=compliance)
```

## Layer 1: LLM 抽象层 (skyforge_llm)

提供统一的 LLM 接口，支持多种模型提供商。

### 模块结构

```
skyforge_llm/
├── providers/               # 模型提供商
│   ├── openai.py            # OpenAI 兼容
│   ├── anthropic.py         # Anthropic
│   ├── qwen.py              # 通义千问
│   └── deepseek.py          # DeepSeek
├── security/                # 安全封装
│   ├── sanitizer.py         # 输入清理
│   ├── validator.py         # 输出验证
│   └── auditor.py           # 审计日志
├── client.py                # 统一客户端
├── router.py                # 模型路由
└── parser.py                # 输出解析
```

### 关键接口

```python
# client.py
class LLMClient:
    def chat(self, messages: List[Message]) -> str:
        """与 LLM 交互"""
        pass
    
    def stream(self, messages: List[Message]) -> Iterator[str]:
        """流式输出"""
        pass

# router.py
class ModelRouter:
    def route(self, task_type: str) -> str:
        """根据任务类型路由到合适的模型"""
        pass
```

## Layer 2: CLI 工具 (skyforge_core)

提供命令行接口，方便开发者快速使用。

### 命令结构

```bash
skyforge generate   # 代码生成
skyforge check      # 合规检查
skyforge simulate   # 数字孪生仿真
skyforge report     # 生成报告
```

### 实现

```python
# cli.py
@app.command()
def generate(
    requirement: str,
    output: Path = Path("output"),
    config: Optional[Path] = None
):
    """生成代码"""
    pipeline = Pipeline(config)
    result = pipeline.run(requirement)
    result.save(output)
```

## Layer 3: Web 工作室 (app)

完整的 Web 应用，支持团队协作和可视化操作。

### 模块结构

```
app/
├── api/                     # API 路由
│   ├── routes/
│   │   ├── generate.py      # 代码生成 API
│   │   ├── compose.py       # 组合验证 API
│   │   ├── hil.py           # HIL 人机协作 API
│   │   └── models.py        # 模型管理 API
│   └── deps.py              # 依赖注入
├── core/                    # 核心功能
│   ├── hil/                 # HIL 人机协作
│   │   ├── manager.py       # 协作管理器
│   │   └── workflow.py      # 工作流引擎
│   └── streaming/           # WebSocket 流式
│       ├── handler.py       # 消息处理器
│       └── manager.py       # 连接管理
├── services/                # 服务层
│   ├── redis_service.py     # Redis 服务
│   └── task_service.py      # 任务服务
├── config/                  # 配置管理
│   ├── settings.py          # 配置类
│   └── logging.py           # 日志配置
└── main.py                  # 应用入口
```

### API 架构

```
┌─────────────────────────────────────────────────┐
│                 FastAPI 应用                      │
├─────────────────────────────────────────────────┤
│  /api/generate  │  /api/compose  │  /api/hil    │
├─────────────────────────────────────────────────┤
│              服务层 (Services)                    │
├─────────────────────────────────────────────────┤
│           核心引擎 (Engine)                       │
├─────────────────────────────────────────────────┤
│           数据存储 (Redis/SQLite)                 │
└─────────────────────────────────────────────────┘
```

## 数据流

### 代码生成流程

```
用户输入 → 需求解析 → 契约生成 → 代码生成 → 合规检查 → 报告生成
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
  文本      JSON       YAML        C        HTML        PDF
```

### HIL 人机协作流程

```
Agent 决策 → 风险评估 → 人工审批 → 结果反馈 → 流程继续
    │          │          │          │
    ▼          ▼          ▼          ▼
  自动       高风险     需要审批    更新状态
```

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.12+ | 运行时 |
| FastAPI | Web 框架 |
| Pydantic | 数据验证 |
| Ruff | 代码检查 |
| Pytest | 测试框架 |
| Loguru | 日志记录 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3 | UI 框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Pinia | 状态管理 |
| Tailwind CSS | 样式框架 |

### 基础设施

| 技术 | 用途 |
|------|------|
| Docker | 容器化 |
| Redis | 缓存/队列 |
| GitHub Actions | CI/CD |

## 性能优化

### 关键优化点

1. **并行处理**：Agent 可并行执行独立任务
2. **增量更新**：只重新生成受影响的部分
3. **缓存机制**：缓存 LLM 响应和中间结果
4. **懒加载**：按需加载非核心模块

### 资源消耗

| 层级 | 内存占用 | 磁盘占用 |
|------|---------|---------|
| Layer 0 | ~50MB | ~80MB |
| Layer 1 | +20MB | +50MB |
| Layer 2 | +5MB | +5MB |
| Layer 3 | +100MB | +315MB |

## 扩展点

### 自定义 Agent

```python
from skyforge_engine.agents import BaseAgent

class CustomAgent(BaseAgent):
    def execute(self, input_data):
        # 自定义逻辑
        pass
```

### 自定义工具

```python
from skyforge_engine.tools import BaseTool

class CustomTool(BaseTool):
    def run(self, params):
        # 自定义工具逻辑
        pass
```

### 自定义模型

```python
from skyforge_llm.providers import BaseProvider

class CustomProvider(BaseProvider):
    def chat(self, messages):
        # 自定义模型调用
        pass
```

## 安全考虑

### 输入验证

- 所有用户输入都经过 Pydantic 验证
- LLM 输出经过安全检查和清理
- 防止注入攻击

### 权限控制

- API 密钥安全存储
- 角色基础的访问控制
- 操作审计日志

## 未来规划

- 微服务架构支持
- 多租户支持
- 分布式计算
- 更多模型提供商
