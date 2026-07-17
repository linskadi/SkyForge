.PHONY: dev dev-up dev-down build test lint lint-fix clean benchmark help

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- 开发 ----

dev: ## 启动本地开发环境
	@bash start.sh

dev-up: ## Docker Compose 启动
	docker compose -f docker/docker-compose.dev.yml up --build

dev-down: ## 停止 Docker
	docker compose -f docker/docker-compose.dev.yml down

# ---- 构建 ----

build: build-frontend ## 构建全部

build-frontend: ## 构建前端
	cd studio/frontend && pnpm install --frozen-lockfile && pnpm build

# ---- 测试 ----

test: test-frontend test-backend ## 运行全部测试

test-frontend: ## 前端测试
	cd studio/frontend && pnpm vitest run

test-backend: ## 后端测试
	cd src && PYTHONPATH=.. uv run python -m unittest discover -s ../studio/app/tests -p "test_*.py"

# ---- 性能基准 ----

benchmark: ## 运行性能基准测试
	cd tools/benchmark && python run_benchmark.py

# ---- 代码质量 ----

lint: lint-frontend lint-backend ## 检查代码质量

lint-frontend: ## 前端 Biome
	cd studio/frontend && pnpm biome ci ./src

lint-backend: ## 后端 Ruff
	cd src && uv run ruff check .

lint-fix: ## 自动修复
	cd studio/frontend && pnpm biome check --write ./src
	cd src && uv run ruff check --fix .

typecheck: ## TypeScript 类型检查
	cd studio/frontend && pnpm vue-tsc -b

# ---- DO-178C 合规 ----

do178c-check: ## DO-178C 合规检查
	@echo "=== DO-178C 文档完整性检查 ==="
	@missing=0; \
	for doc in PSAC SDP SVP SCMP SQAP TQP TOR TAS; do \
		path="docs/compliance/$${doc}.md"; \
		if [ -f "$$path" ]; then \
			echo "  ✅ $${doc}.md"; \
		else \
			echo "  ❌ $${doc}.md (缺失)"; \
			missing=1; \
		fi; \
	done; \
	if [ $$missing -eq 1 ]; then \
		echo "❌ DO-178C 文档不完整！"; \
		exit 1; \
	fi; \
	echo "✅ 全部 DO-178C 文档完整"
	@cd src && PYTHONPATH=.. uv run python -m skyforge_engine.tools.tool_chain_validator --project-root ..

do178c-docs: ## 列出 DO-178C 文档状态
	@for doc in PSAC SDP SVP SCMP SQAP TQP TOR TAS; do \
		path="docs/compliance/$${doc}.md"; \
		if [ -f "$$path" ]; then \
			echo "  ✅ docs/compliance/$${doc}.md"; \
		else \
			echo "  ❌ docs/compliance/$${doc}.md (缺失)"; \
		fi; \
	done

clean: ## 清理构建产物
	cd studio/frontend && rm -rf dist node_modules
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
