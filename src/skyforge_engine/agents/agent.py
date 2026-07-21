"""Agent 基类模块（已废弃）。

为什么没有使用继承：
pipeline 的 4 个 Agent（RequirementParser、ContractGenerator、
CodeGenerator、CodeRepairer）
与基类 Agent 设计模式不同：
- 基类 Agent：多轮对话、维护 chat_history、
  使用 LLM（多 Provider 抽象层）+ Redis 流式推送
- Pipeline Agent：单轮调用、无历史管理、
  使用 LMStudioClient（本地 httpx 直连本地 LLM 服务，如 LM Studio）、带 Mock 降级

两者底层 LLM 客户端也不同（LLM vs LMStudioClient），强行继承会引入不必要的耦合。
各 Agent 保持独立实现，按需使用 get_local_llm_client() 单例（保留 get_lmstudio_client 别名兼容）。"""
