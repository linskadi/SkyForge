/**
 * 链上证据锚定 - API 服务
 *
 * POST /api/evidence/anchor-info 由 FastAPI 后端计算锚定哈希并返回链信息；
 * 前端页面在此基础上进行钱包签名上链。
 */

import { postJSON } from "@/services/client";
import type { AnchorChainInfo, AnchorContractInfo } from "@/utils/chainAnchor";

export interface AnchorInfoResponse {
	anchor_hash: string;
	chain: AnchorChainInfo;
	contract: AnchorContractInfo;
}

/** 计算 pipeline 结果的证据锚定哈希与链信息 */
export function fetchAnchorInfo(
	pipelineResult: Record<string, unknown>,
): Promise<AnchorInfoResponse> {
	return postJSON<AnchorInfoResponse>("/api/evidence/anchor-info", {
		pipeline_result: pipelineResult,
	});
}
