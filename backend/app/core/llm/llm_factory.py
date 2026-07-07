"""LLM 工厂模块，根据配置创建各 Agent 使用的 LLM 实例。"""

from app.config.setting import settings
from app.core.llm.llm import LLM


class LLMFactory:
    """LLM 工厂类，根据配置创建需求解析、契约生成、代码生成和代码修复的 LLM 实例。"""

    task_id: str

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def get_all_llms(self) -> tuple[LLM, LLM, LLM, LLM]:
        """创建所有 Agent 的 LLM 实例。

        Returns:
            包含 (req_parser_llm, con_gen_llm, code_gen_llm, reviewer_llm) 的元组。
        """
        req_parser_llm = LLM(
            api_type=settings.REQ_PARSER_API_TYPE,
            api_key=settings.REQ_PARSER_API_KEY,
            model=settings.REQ_PARSER_MODEL,
            base_url=settings.REQ_PARSER_BASE_URL,
            task_id=self.task_id,
            max_tokens=settings.REQ_PARSER_MAX_TOKENS,
        )

        con_gen_llm = LLM(
            api_type=settings.CON_GEN_API_TYPE,
            api_key=settings.CON_GEN_API_KEY,
            model=settings.CON_GEN_MODEL,
            base_url=settings.CON_GEN_BASE_URL,
            task_id=self.task_id,
            max_tokens=settings.CON_GEN_MAX_TOKENS,
        )

        code_gen_llm = LLM(
            api_type=settings.CODE_GEN_API_TYPE,
            api_key=settings.CODE_GEN_API_KEY,
            model=settings.CODE_GEN_MODEL,
            base_url=settings.CODE_GEN_BASE_URL,
            task_id=self.task_id,
            max_tokens=settings.CODE_GEN_MAX_TOKENS,
        )

        reviewer_llm = LLM(
            api_type=settings.REPAIR_API_TYPE,
            api_key=settings.REPAIR_API_KEY,
            model=settings.REPAIR_MODEL,
            base_url=settings.REPAIR_BASE_URL,
            task_id=self.task_id,
            max_tokens=settings.REPAIR_MAX_TOKENS,
        )

        return req_parser_llm, con_gen_llm, code_gen_llm, reviewer_llm
