/** Agent 类型枚举 */
export enum AgentType {
	REQ_PARSER = "REQ-Parser",
	CON_GEN = "CON-Gen",
	CODE_GEN = "CODE-Gen",
	REPAIR = "REPAIR",
	SYSTEM = "SYSTEM",
	TERMINAL = "TERMINAL",
}

/** LLM API 类型枚举 */
export enum ApiType {
	OPENAI_CHAT = "openai-chat",
	OPENAI_RESPONSES = "openai-responses",
	ANTHROPIC = "anthropic",
}
