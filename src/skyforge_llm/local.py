"""本地 LLM 客户端：支持 GGUF 模型的本地推理。

使用 llama-cpp-python 实现本地模型推理，支持：
- 首次启动自动下载模型
- 流式生成
- GPU/CPU 自动选择
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator
from skyforge_engine.utils.log_util import logger


# 默认模型配置
DEFAULT_MODEL_REPO = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
DEFAULT_MODEL_FILE = "qwen2.5-coder-1.5b-instruct-q5_k_m.gguf"
DEFAULT_MODEL_DIR = Path.home() / ".skyforge" / "models"


class LocalLLMClient:
    """本地 LLM 客户端，支持 GGUF 模型推理。"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        verbose: bool = False,
    ):
        """初始化本地 LLM 客户端。

        Args:
            model_path: GGUF 模型文件路径，None 则自动下载
            n_ctx: 上下文窗口大小
            n_gpu_layers: GPU 层数，-1 为自动选择
            verbose: 是否输出详细日志
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.verbose = verbose
        self._llm = None
        self._available: Optional[bool] = None
        self._last_check: float = 0.0
        self._cache_ttl: int = 300  # 5分钟缓存

    def _ensure_model(self) -> Optional[Path]:
        """确保模型文件存在，不存在则下载。"""
        if self.model_path:
            path = Path(self.model_path)
            if path.exists():
                return path
            logger.error(f"模型文件不存在: {self.model_path}")
            return None

        # 自动下载模型
        model_dir = DEFAULT_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / DEFAULT_MODEL_FILE

        if model_path.exists():
            logger.info(f"使用已有模型: {model_path}")
            return model_path

        # 下载模型
        logger.info(f"首次启动，正在下载模型 {DEFAULT_MODEL_REPO}...")
        logger.info(f"模型将保存到: {model_path}")

        try:
            from huggingface_hub import hf_hub_download

            hf_hub_download(
                repo_id=DEFAULT_MODEL_REPO,
                filename=DEFAULT_MODEL_FILE,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )
            logger.info("模型下载完成")
            return model_path
        except ImportError:
            logger.error("请安装 huggingface_hub: pip install huggingface_hub")
            return None
        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            return None

    def _init_llm(self) -> bool:
        """初始化 LLM 模型。"""
        if self._llm is not None:
            return True

        try:
            from llama_cpp import Llama

            model_path = self._ensure_model()
            if model_path is None:
                return False

            logger.info(f"加载模型: {model_path}")
            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
                n_threads=os.cpu_count() or 4,
            )
            logger.info("模型加载完成")
            return True
        except ImportError:
            logger.warning(
                "llama-cpp-python 未安装，"
                "请运行: pip install llama-cpp-python"
            )
            return False
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False

    def is_available(self, force_recheck: bool = False) -> bool:
        """检查本地 LLM 是否可用。"""
        # TTL 缓存
        if not force_recheck and self._available is not None:
            if time.time() - self._last_check < self._cache_ttl:
                return self._available

        self._available = self._init_llm()
        self._last_check = time.time()
        return self._available

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[list[str]] = None,
    ) -> str:
        """同步生成文本。

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            stop: 停止词列表

        Returns:
            生成的文本
        """
        if not self.is_available():
            return ""

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
            )

            content = response["choices"][0]["message"]["content"]
            tokens_used = response.get("usage", {}).get("total_tokens", 0)
            logger.info(f"本地 LLM 响应: tokens={tokens_used}")
            return content
        except Exception as e:
            logger.error(f"本地 LLM 生成失败: {e}")
            return ""

    async def generate_async(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[list[str]] = None,
    ) -> str:
        """异步生成文本（在线程池中执行）。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.generate(
                prompt, system_prompt, temperature, max_tokens, stop
            ),
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """流式生成文本。

        Yields:
            每个 token 的文本片段
        """
        if not self.is_available():
            return

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # llama-cpp-python 的流式输出
            stream = self._llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk["choices"][0].get("delta", {}).get("content"):
                    yield chunk["choices"][0]["delta"]["content"]
        except Exception as e:
            logger.error(f"本地 LLM 流式生成失败: {e}")

    def get_model_info(self) -> dict:
        """获取模型信息。"""
        if not self.is_available():
            return {"available": False}

        return {
            "available": True,
            "model_path": str(self._ensure_model()),
            "n_ctx": self.n_ctx,
            "n_gpu_layers": self.n_gpu_layers,
        }


# 全局单例
_local_llm_client: Optional[LocalLLMClient] = None


def get_local_llm_client() -> LocalLLMClient:
    """获取本地 LLM 客户端单例。"""
    global _local_llm_client
    if _local_llm_client is None:
        _local_llm_client = LocalLLMClient()
    return _local_llm_client
