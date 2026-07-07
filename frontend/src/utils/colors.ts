/**
 * 共享颜色常量
 * Agent 徽章颜色 + 日志级别颜色，统一管理
 */

import type { AgentType, LogLevel } from "@/services/mockApi";

/** Agent 徽章颜色（航空信号灯语义系统 - 深沉专业色调） */
export const agentColorMap: Record<AgentType, { bg: string; fg: string }> = {
  "REQ-Parser": { bg: "#1d4ed8", fg: "#dbeafe" },      /* 深蓝色 - 需求解析 */
  "CON-Gen": { bg: "#6d28d9", fg: "#ede9fe" },         /* 紫色 - 合约生成 */
  "CODE-Gen": { bg: "#047857", fg: "#d1fae5" },        /* 深绿色 - 代码生成 */
  REPAIR: { bg: "#c2410c", fg: "#ffedd5" },            /* 深橙色 - 修复 */
  SYSTEM: { bg: "#475569", fg: "#f1f5f9" },            /* 石灰色 - 系统 */
  TERMINAL: { bg: "#0e7490", fg: "#cffafe" },          /* 深青色 - 终端 */
};

/** 日志级别颜色（深沉专业色调） */
export const levelColorMap: Record<LogLevel, string> = {
  info: "#94a3b8",    /* 石灰色 - 信息 */
  success: "#059669", /* 深绿色 - 成功 */
  warn: "#d97706",    /* 深橙色 - 警告 */
  error: "#dc2626",   /* 深红色 - 错误 */
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
