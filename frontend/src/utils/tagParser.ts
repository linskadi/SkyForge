/**
 * 共享标签解析工具
 * 提取 [REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx-XXX-nnn] 内联标签
 */

import { MISRA_RULE_DOCS } from "@/services/mockApi";

/** 行内 Token 类型 */
export type InlineToken =
  | { type: "text"; value: string }
  | { type: "req"; value: string }
  | { type: "misra"; value: string; doc: string }
  | { type: "con"; value: string };

/** 匹配 [REQ-xxx] / [MISRA-Rule-x.x] / [CON-xxx-XXX-nnn] */
const TAG_REGEX = /\[(REQ-\d+|MISRA-Rule-[\d.]+|CON-\d+-[A-Z]+-\d+)\]/g;

/** 把一行文本解析为 token 列表 */
export function parseInlineTags(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  while ((match = TAG_REGEX.exec(text)) !== null) {
    if (match.index > lastIdx) {
      tokens.push({ type: "text", value: text.slice(lastIdx, match.index) });
    }
    const tag = match[1];
    if (tag.startsWith("REQ-")) {
      tokens.push({ type: "req", value: tag });
    } else if (tag.startsWith("MISRA-Rule-")) {
      tokens.push({
        type: "misra",
        value: tag,
        doc: MISRA_RULE_DOCS[tag] ?? `未收录规则说明：${tag}`,
      });
    } else if (tag.startsWith("CON-")) {
      tokens.push({ type: "con", value: tag });
    }
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIdx) });
  }
  return tokens;
}

/** 简化版：只解析 CON 标签（用于 ContractViewer/ContractCheckResult） */
export function parseConTags(
  text: string,
): Array<{ type: "text" | "con"; value: string }> {
  const tokens: Array<{ type: "text" | "con"; value: string }> = [];
  const regex = /\[(CON-\d+-[A-Z]+-\d+)\]/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      tokens.push({ type: "text", value: text.slice(lastIdx, match.index) });
    }
    tokens.push({ type: "con", value: match[1] });
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIdx) });
  }
  return tokens;
}
