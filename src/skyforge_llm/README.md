# Layer 1 — skyforge-llm · LLM 抽象层

> **可选剥离 · +50MB · 多 Provider · 本地 + 云端**

```bash
pip install skyforge-llm
```

## 功能

- **多 Provider 支持** — DeepSeek / Qwen / OpenAI / Anthropic / Ollama / LM Studio / 通用兼容
- **本地 Provider 自动检测** — 根据 Base URL 端口自动识别：11434→ollama，1234→lmstudio，其他→local
- **安全封装** — sanitizer (输入脱敏) + validator (输出验证) + auditor (审计日志)
- **智能降级** — LLM 不可用时 Agent 自动降级为规则引擎 Mock
- **响应缓存** — 进程级 TTL 缓存，相同 prompt 命中即返回
- **流式推送** — chat_stream 支持 WebSocket 实时推送

## 安装

```bash
# 安装 LLM 层（自动依赖 engine 层）
pip install skyforge-llm

# 仅 engine 层可独立运行（无 LLM 时使用 Mock 降级）
pip install skyforge-engine
```

## 使用

```python
from skyforge_llm import get_lmstudio_client

client = get_lmstudio_client()
if client.is_available():
    response = client.chat("设计一个低通滤波器")
else:
    response = "LM Studio 不可用，请启动本地服务或配置云端 API"
```

## 兼容 Provider

| Provider | 接入方式 | 用途 |
|----------|---------|------|
| DeepSeek | OpenAI 兼容 API | 默认，高性价比 |
| Qwen (通义千问) | OpenAI 兼容 API | 国产首选 |
| OpenAI GPT-4o | OpenAI API | 最高精度 |
| Anthropic Claude | Anthropic API | 备选 |
| **Ollama** | 本地 localhost:11434/v1 | 离线推理，默认推荐 |
| LM Studio | 本地 localhost:1234/v1 | 离线降级 |
| 通用兼容 | 任何 `/v1/chat/completions` | vLLM / 其他 |

## 架构

```
skyforge_llm/
├── client.py            # 统一客户端
├── cache.py             # 响应缓存
├── parser.py            # JSON 解析
├── router.py            # 模型路由
├── types.py             # 类型定义
├── providers/           # OpenAI/Anthropic/通用
├── security/            # sanitizer/validator/auditor
└── pyproject.toml       # 独立包
```

> 此层可选。移除后 engine 层仍可正常运行（使用规则引擎降级）。
