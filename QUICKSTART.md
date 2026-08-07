# SkyForge 快速开始（Mac 二次开发版）

> 版本：v0.4.0 | 跨平台：Windows / macOS / Linux

## 5 分钟上手

### 1. 环境准备

```bash
# 安装 Homebrew (如未安装)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装必需工具
brew install uv node@18 pnpm

# 可选：安装验证工具
brew install cppcheck cbmc z3
```

### 2. 启动项目

```bash
# 解压后进入目录
cd SkyForge

# 一键启动（自动安装依赖 + 启动服务）
sh start.sh
```

### 3. 访问

- 前端界面：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 后端 API：http://localhost:8000

## 项目结构

```
SkyForge/
├── src/                    # Python 后端源码
│   ├── skyforge_engine/    # 核心引擎（L0-L5 六层架构）
│   ├── skyforge_llm/       # LLM 客户端层
│   └── skyforge_core/      # CLI 工具
├── studio/
│   ├── app/                # FastAPI 后端
│   └── frontend/           # Vue 3 前端
├── docs/                   # 文档
├── tests/                  # 测试
├── contracts/              # 智能合约（链上锚定）
├── examples/               # 示例
└── tools/                  # 辅助工具
```

## 运行测试

```bash
# 后端测试
uv run pytest src/skyforge_engine/tests/ -q

# 前端测试
cd studio/frontend && pnpm test -- --run
```

## 开发模式

```bash
# 后端开发（热重载）
uv run uvicorn app.main:app --app-dir studio --reload

# 前端开发（热重载）
cd studio/frontend && pnpm dev
```

## 注意事项

- 首次启动会自动创建 `.venv` 虚拟环境和安装 `node_modules`
- 外部工具（Cppcheck/CBMC/Z3）缺失时自动降级到 Mock 模式
- LLM 默认使用 Mock 模式，配置 API Key 后可切换到真实 LLM
- macOS 上串口默认值为 `/dev/tty.usbserial`

## 详细文档

- 用户指南：docs/USER_GUIDE.md
- 架构详解：docs/ARCHITECTURE.md
- 插件开发：docs/PLUGIN_DEVELOPMENT.md
- API 文档：http://localhost:8000/docs（启动后）
