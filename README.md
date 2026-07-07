# SkyForge (天锻)

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

**统一使用 `start.sh`（推荐）：**

```bash
bash start.sh
```

脚本自动完成：依赖检查、虚拟环境创建、依赖安装、清理残留进程、启动后端 + 前端。

> **Windows 用户**：请使用 [Git Bash](https://git-scm.com/download/win) 运行 `bash start.sh`，或在 WSL 中执行。不支持 CMD / PowerShell。

### 访问

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 项目结构

```
airborne-toolkit/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # FastAPI 路由
│   │   ├── config/            # 配置管理
│   │   ├── core/
│   │   │   ├── agents/        # Agent 实现
│   │   │   ├── digital_twin/  # 数字孪生仿真
│   │   │   ├── hil/           # HIL 人机协作
│   │   │   ├── llm/           # LLM 调用层
│   │   │   ├── report/        # DO-178C 报告
│   │   │   ├── scade/         # SCADE G-Lustre 输入
│   │   │   ├── streaming/     # WebSocket 流式推送
│   │   │   └── pipeline.py    # 全流程编排
│   │   ├── rag/               # RAG 知识库
│   │   ├── routers/           # 旧路由（待清理）
│   │   ├── schemas/           # 数据模型
│   │   ├── services/          # 服务层
│   │   ├── tests/             # 测试
│   │   └── utils/             # 工具函数
│   ├── .env.dev               # 环境配置
│   └── pyproject.toml         # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── components/        # Vue 组件
│   │   ├── pages/             # 页面
│   │   └── utils/             # 工具函数
│   ├── .env.development       # 前端配置
│   └── package.json           # Node 依赖
├── docker-compose.yml         # Docker 部署
└── start.sh                   # 一键启动脚本（Git Bash / Linux / Mac）
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 代码生成 |
| POST | `/api/upload-scade` | 上传 SCADE 文件 |
| GET | `/api/files` | 获取文件列表 |
| GET | `/api/health` | 健康检查 |
| WS | `/ws/agent-stream` | WebSocket 流式推送 |

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

个人免费使用，请勿商业用途。
