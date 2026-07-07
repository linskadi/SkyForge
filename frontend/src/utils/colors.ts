/**
 * 共享颜色常量
 * Agent 徽章颜色 + 日志级别颜色，统一管理
 */

import type { AgentType, LogLevel } from "@/services/mockApi";

/** Agent 徽章颜色（与文档 11.2.1 节对齐） */
export const agentColorMap: Record<AgentType, { bg: string; fg: string }> = {
  "REQ-Parser": { bg: "#1e6fb8", fg: "#d6e8ff" },
  "CON-Gen": { bg: "#7e22ce", fg: "#f0e6ff" },
  "CODE-Gen": { bg: "#15803d", fg: "#dcfce7" },
  REPAIR: { bg: "#ea580c", fg: "#ffedd5" },
  SYSTEM: { bg: "#525252", fg: "#e5e5e5" },
  TERMINAL: { bg: "#0891b2", fg: "#cffafe" },
};

/** 日志级别颜色 */
export const levelColorMap: Record<LogLevel, string> = {
  info: "#d4d4d4",
  success: "#4ec9b0",
  warn: "#cca700",
  error: "#f44747",
};

/** Agent 徽章样式 */
export const badgeStyle = (agent: AgentType) => {
  const c = agentColorMap[agent];
  return { backgroundColor: c.bg, color: c.fg };
};

/** 日志内容颜色 */
export const contentStyle = (level: LogLevel) => ({
  color: levelColorMap[level],
});
