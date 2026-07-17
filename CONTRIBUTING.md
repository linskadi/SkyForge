# 贡献指南

感谢您对 SkyForge 项目的关注！我们欢迎所有形式的贡献。

## 目录

- [贡献流程](#贡献流程)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [PR规范](#pr规范)
- [测试要求](#测试要求)

## 贡献流程

### 1. Fork 项目

```bash
# Fork 到你的 GitHub 账号
# 然后克隆到本地
git clone https://github.com/your-username/SkyForge.git
cd SkyForge
```

### 2. 创建功能分支

```bash
# 从 main 分支创建新分支
git checkout -b feature/your-feature-name
```

分支命名规范：
- `feature/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档更新
- `refactor/xxx` - 代码重构
- `test/xxx` - 测试相关
- `chore/xxx` - 构建/工具相关

### 3. 开发与测试

```bash
# 安装开发依赖
cd src
uv sync --group dev

# 运行测试
python -m pytest

# 代码检查
ruff check .
ruff format .
```

### 4. 提交代码

```bash
git add .
git commit -m "feat: 添加新功能描述"
```

### 5. 推送并创建 PR

```bash
git push origin feature/your-feature-name
```

然后在 GitHub 上创建 Pull Request。

## 代码规范

### Python 代码规范

项目使用 [Ruff](https://docs.astral.sh/ruff/) 进行代码检查和格式化。

```bash
# 检查代码
ruff check .

# 自动修复
ruff check --fix .

# 格式化
ruff format .
```

**基本要求：**
- 行长度限制：88 字符
- 缩进：4 空格
- 使用双引号字符串
- 类型注解：鼓励使用
- 文档字符串：公开函数/类必须添加

### TypeScript/Vue 代码规范

- 使用 ESLint + Prettier
- 组件命名：PascalCase
- 文件命名：kebab-case

### 通用规范

- 不要提交敏感信息（密钥、密码等）
- 保持代码简洁，避免过度抽象
- 为新功能添加测试
- 更新相关文档

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Type 类型

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 代码重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具相关 |
| `ci` | CI/CD 相关 |

### 示例

```bash
feat(engine): 添加 SCADE 模型解析功能
fix(llm): 修复 LLM 响应解析错误
docs: 更新 API 接口文档
test(engine): 添加管道测试用例
```

## PR规范

### PR 标题

使用与提交规范相同的格式：

```
feat(engine): 添加新功能
```

### PR 描述

请填写 PR 模板中的所有必要信息：

1. **变更说明**：简要描述做了什么
2. **变更类型**：选择合适的类型
3. **测试情况**：说明如何测试
4. **相关 Issue**：关联的 Issue 编号

### PR 要求

- 保持 PR 粒度小，一个 PR 只做一件事
- 确保 CI 检查通过
- 至少需要 1 位维护者审核
- 解决所有 Review 意见后才能合并
- 使用 Squash and Merge 合并

## 测试要求

### 后端测试

```bash
cd src

# 运行所有测试
python -m pytest

# 运行指定测试文件
python -m pytest tests/test_pipeline.py

# 运行指定测试
python -m pytest tests/test_pipeline.py::test_function_name

# 查看测试覆盖率
python -m pytest --cov=skyforge_engine --cov-report=term-missing
```

### 测试覆盖率要求

- 新代码覆盖率：≥ 80%
- 核心模块覆盖率：≥ 90%
- 整体项目覆盖率：≥ 70%

### 测试类型

1. **单元测试**：测试单个函数/类
2. **集成测试**：测试模块间交互
3. **端到端测试**：测试完整流程

### 提交前检查

```bash
# 完整检查流程
ruff check . && ruff format . && python -m pytest
```

## 获取帮助

- 查看 [项目文档](./docs/)
- 提交 [Issue](https://github.com/ch-onboard/SkyForge/issues)
- 参与 [讨论](https://github.com/ch-onboard/SkyForge/discussions)

## 许可证

提交贡献即表示您同意将代码以 [MIT License](./LICENSE) 开源。
