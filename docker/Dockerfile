# 使用官方推荐的 Python 基础镜像
FROM python:3.12-slim AS builder

# 安装中文字体（确保 matplotlib 图表中文正常显示）
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

# 安装 uv（推荐直接用官方 distroless 镜像复制二进制文件，速度快且干净）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY pyproject.toml ./

# 安装依赖
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r <(uv pip compile pyproject.toml -o -) || \
    uv sync --no-install-project

EXPOSE 8000

# 直接使用 uvicorn，因为依赖已安装到系统 Python
ENV PYTHONPATH=/app/backend:/app/studio
CMD ["uv", "run", "uvicorn", "studio.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-ping-interval", "60", "--ws-ping-timeout", "120"]