.PHONY: dev dev-up dev-down build test lint lint-fix clean help

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- 开发 ----

dev: ## 启动本地开发环境（前端 + 后端 + Redis）
	@bash start.sh

dev-up: ## 使用 Docker Compose 启动开发环境
	docker compose -f docker-compose.dev.yml up --build

dev-down: ## 停止 Docker 开发环境
	docker compose -f docker-compose.dev.yml down

# ---- 构建 ----

build: build-frontend build-backend ## 构建全部

build-frontend: ## 构建前端
	cd frontend && pnpm install --frozen-lockfile && pnpm build

build-backend: ## 构建后端（检查依赖）
	cd backend && uv sync

# ---- 测试 ----

test: test-frontend test-backend ## 运行全部测试

test-frontend: ## 运行前端测试
	cd frontend && pnpm vitest run

test-backend: ## 运行后端测试
	cd backend && uv run python -m unittest discover -s app/tests -p "test_*.py"

# ---- 代码质量 ----

lint: lint-frontend lint-backend ## 检查全部代码质量

lint-frontend: ## 前端 Biome 检查
	cd frontend && pnpm biome ci ./src

lint-backend: ## 后端 Ruff 检查
	cd backend && uv run ruff check app/

lint-fix: ## 自动修复代码格式
	cd frontend && pnpm biome check --write ./src
	cd backend && uv run ruff check --fix app/

typecheck: ## TypeScript 类型检查
	cd frontend && pnpm vue-tsc -b

# ---- 清理 ----

clean: ## 清理构建产物
	cd frontend && rm -rf dist node_modules
	cd backend && rm -rf .venv __pycache__ .pytest_cache
