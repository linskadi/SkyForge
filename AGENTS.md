# AGENTS.md

**SkyForge** — 单仓库：Python 后端（uv workspace + FastAPI，代码在 `studio/app`）+ Vue 3 前端（`studio/frontend`）。后端默认离线 mock 模式，永远不假定外部工具（Cppcheck/Z3/CBMC/GCC）可用。

## 常用命令

**前端**（工作目录 `studio/frontend`）：
- 类型检查：`pnpm vue-tsc -b`
- 代码检查：`pnpm exec biome check --write ./src`
- 单元测试：`pnpm test`（vitest run）
- 完整构建：`pnpm build`（= `vue-tsc -b && vite build`）
- CI 执行顺序：`biome ci ./src` → `vue-tsc -b` → `vitest run` → `build`，修改前端后务必按此顺序跑通。

**后端**（仓库根目录）：
- 代码检查：`uv run ruff check .`
- 单元测试：`uv run pytest -q`
- CI 环境设置 `SKYFORGE_LLM_MODE=mock`、`USE_LLM=false`、`HIL_ENABLED=false`，不依赖任何外部服务。

**根目录 Makefile**：`make dev`、`make test`、`make lint`、`make typecheck`、`make do178c-check`。

## 目录结构要点

- 前端路由视图分两处：大多数页面在 `src/views/*.vue`，但 **dashboard** 和 **misra** 在 `src/pages/{dashboard,misra}/index.vue`。
- 路由 meta：`{ locale: <module>, title: <key> }`，`src/i18n` 在 `router.beforeEach` 中按需懒加载模块并设置 `document.title`。
- 别名 `@` → `src`（vite 和 vitest 均已配置）。
- Pinia store 在 `src/stores/`（5 个），API 层在 `src/services/`，组件在 `src/components/`。

## i18n 规范（重要）

消息文件按路由模块拆分，路径 `src/i18n/locales/{zh-CN,en}/<module>.json`（共 13 个模块：common + 各路由模块 + data）。zh-CN 静态打包；en 在语言切换时通过 `loadLocaleModule` 懒加载。

- **模板**：使用 `$t("key")`
- **script setup**：使用 `const { t } = useI18n()`
- **services / stores**（无法用 Composition API）：使用 `dataT(key, fallback)`——内部调用 `i18n.global.t(key)`，若 key 未解析（data 模块尚未加载）则回退到 fallback 中文字符串。
- **组件测试**：渲染过 i18n 文案的测试必须挂载 i18n 插件：`config.global.plugins = [createTestI18n()]`（来自 `@/test-utils/i18n`）。该 helper 用 `import.meta.glob` 加载真实 zh-CN JSON，**common 排最后**以避免根键冲突（如 `waveform`）。
- **禁止硬编码中文**。mock/test 数据、语言切换按钮标签（"中文"/"EN"）、`<code>` 块中的示例内容除外。

## 代码风格

- Biome：tab 缩进，双引号，`noUnusedImports`/`noUnusedVariables` 在 `*.vue` 中已禁用。
- 测试环境：jsdom + globals（`vitest.config` 设 `test.globals: true`）。
- pyproject 配置 `pythonpath = ["src", "studio"]`，后端测试直接用 `uv run pytest`。
