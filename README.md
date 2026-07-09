# SkyForge (天锻)

> **航空工业软件开源创新大赛 参赛作品**
> 赛道：机上软件开发工具研发 - 赛题二：AI智能体驱动的机载软件轻量化开发工具

AI智能体驱动的机载软件轻量化开发工具 - 通过多 Agent 协同生成符合 DO-178C/MISRA-C 标准的机载 C 代码。

## 核心功能

- **需求解析** → 自然语言需求转结构化 JSON
- **契约生成** → 生成 DO-178C 合规契约 YAML
- **代码生成** → 生成 MISRA-C 风格 C 代码
- **合规检查** → Cppcheck MISRA-C 扫描 + 自动修复
- **数字孪生** → 虚拟传感器 + 虚拟 MCU 故障注入仿真
- **报告生成** → DO-178C 合规报告 (HTML)

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 18+ | 前端运行时 |
| pnpm | 10+ | 前端包管理器 |
| uv | 最新 | 后端包管理器 |
| Redis | 6+ | 可选，任务队列 |
| LM Studio | 最新 | 可选，本地 LLM |

### 启动

**Windows 用户（推荐）：**

```cmd
# 双击 start.bat 或在 CMD 中运行
start.bat

# 或使用 PowerShell
.\start.ps1
```

**Linux / Mac 用户：**

```bash
bash start.sh
```

脚本自动完成：环境检查、依赖安装、虚拟环境创建、清理残留进程、启动后端 + 前端。

### 访问

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 项目结构

```
SkyForge/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # FastAPI 路由（按功能域拆分）
│   │   ├── config/             # 配置管理
│   │   ├── core/
│   │   │   ├── agents/         # Agent 实现
│   │   │   ├── digital_twin/   # 数字孪生仿真
│   │   │   ├── hil/            # HIL 人机协作
│   │   │   ├── llm/            # LLM 调用层
│   │   │   ├── report/         # DO-178C 报告
│   │   │   ├── scade/          # SCADE G-Lustre 输入
│   │   │   ├── streaming/      # WebSocket 流式推送
│   │   │   └── pipeline.py     # 全流程编排
│   │   ├── rag/                # RAG 知识库
│   │   ├── schemas/            # 数据模型
│   │   ├── services/           # 服务层
│   │   ├── tests/              # 测试
│   │   └── utils/              # 工具函数
│   ├── .env.dev                # 环境配置
│   └── pyproject.toml          # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── components/         # Vue 组件
│   │   ├── pages/              # 页面
│   │   ├── composables/        # 组合式函数
│   │   └── utils/              # 工具函数
│   ├── .env.development        # 前端配置
│   └── package.json            # Node 依赖
├── docker-compose.yml          # Docker 部署
└── start.sh                    # 一键启动脚本（Git Bash / Linux / Mac）
```

## API 接口

### 基础接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |

### 代码生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 代码生成全流程 |
| POST | `/api/upload-scade` | 上传 SCADE 文件 |
| POST | `/api/repair` | MISRA 违规修复 |
| POST | `/api/check-contract` | 契约校验 |
| POST | `/api/simulate` | 数字孪生仿真 |
| GET | `/api/fault-types` | 获取故障类型列表 |

### 报告

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/report` | 生成 DO-178C 报告 |
| GET | `/api/report/download` | 下载报告 |

### 组合验证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/compose` | 组件组合验证 |
| POST | `/api/check-compatibility` | 检查组件兼容性 |

### HIL 人机协作

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/hil/pending` | 获取待审批项 |
| POST | `/api/hil/approve` | 审批通过 |
| POST | `/api/hil/reject` | 审批拒绝 |
| GET | `/api/hil/history` | 审批历史 |

### 模型管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 获取可用模型列表 |
| POST | `/api/models/select` | 选择模型 |
| POST | `/api/models/clear` | 清除模型选择 |
| GET | `/api/llm/status` | LLM 连接状态 |
| POST | `/api/llm/switch` | 切换 LLM 模式 |

### MISRA 规则

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/misra/search` | 搜索 MISRA 规则 |
| GET | `/api/misra/rule/{rule_id}` | 获取规则详情 |
| GET | `/api/misra/categories` | 获取规则分类 |
| GET | `/api/misra/rules` | 获取所有规则 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `/ws/agent-stream` | Agent 流式推送 |
| `/task/{task_id}` | 任务实时消息推送 |

## 配置

环境变量配置在 `backend/.env`（已 gitignore，不入库）：

> 首次运行请复制 `.env.example` 为 `.env` 并填写配置。

```env
# LLM 配置
USE_LLM=false
LMSTUDIO_BASE_URL=http://localhost:1234/v1

# 系统配置
ENV=dev
LOG_LEVEL=INFO
DEBUG=true

# Redis（可选）
REDIS_URL=redis://localhost:6379/0

# HIL 人机协作
HIL_ENABLED=false
HIL_TIMEOUT=300
```

## 测试

```bash
cd backend
python -m unittest discover -s app/tests -p "test_*.py"
```

## License

本项目采用 [MIT License](./LICENSE) 开源协议。

## 比赛相关

- **赛事**：航空工业软件开源创新大赛
- **赛道**：机上软件开发工具研发
- **赛题**：AI智能体驱动的机载软件轻量化开发工具
- **AtomGit仓库**：https://atomgit.com/ch-onboard/skyforge

### 项目创新点

1. **多Agent协同架构**：需求解析→契约生成→代码生成→修复闭环，全流程自动化
2. **DO-178C合规**：自动生成适航合规报告与需求追溯矩阵
3. **MISRA-C自动修复**：Cppcheck扫描+Agent智能修复+契约校验
4. **数字孪生仿真**：虚拟传感器/MCU + 故障注入测试
5. **HIL人机协作**：关键检查点引入人工审批，确保代码质量
6. **SCADE集成**：支持导入G-Lustre模型，自动转换为需求与契约

### 文档

- [使用教程](./docs/使用教程.md) - 功能模块详解与操作指南
- [部署说明](./docs/部署说明.md) - 环境配置与API接口文档
- [测试报告](./docs/测试报告.md) - 测试覆盖与质量评估
- [第三方组件说明](./ThirdParty.md) - 依赖清单与许可证信息
