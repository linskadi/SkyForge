/**
 * 链上证据锚定 - 纯逻辑工具
 *
 * 与后端 src/skyforge_engine/chain/evidence_anchor.py 保持一致的
 * canonical JSON + SHA-256 规则，保证前后端计算同一哈希。
 */

export interface AnchorChainInfo {
	name: string;
	chainId: number;
	rpcUrl: string;
	explorerUrl: string;
}

export interface AnchorContractInfo {
	address: string;
	deployed: boolean;
}

/** ChainHack 2026 部署目标：Ethereum Sepolia 测试网 */
export const EVIDENCE_CHAIN: AnchorChainInfo = {
	name: "Ethereum Sepolia",
	chainId: 11155111,
	rpcUrl: "https://ethereum-sepolia-rpc.publicnode.com",
	explorerUrl: "https://sepolia.etherscan.io",
};

/** 已部署: scripts/deploy_anchor.mjs (Sepolia, 2026-08-03) */
export const EVIDENCE_CONTRACT: AnchorContractInfo = {
	address: "0xC986756935B44b9aaEfCdF1c8E5f6B3e296f0482",
	deployed: true,
};

/** 与 contracts/EvidenceAnchor.sol 一致的 ABI（子集：锚定/校验/查询） */
export const EVIDENCE_ANCHOR_ABI = [
	"function anchor(bytes32 evidenceHash, string evidenceType, string metadataUri) returns (uint256 timestamp)",
	"function verify(bytes32 evidenceHash) view returns (bool)",
	"function getEvidence(bytes32 evidenceHash) view returns (tuple(bytes32 evidenceHash, address submitter, uint256 timestamp, string evidenceType, string metadataUri))",
	"function getHashCount() view returns (uint256)",
	"event EvidenceAnchored(bytes32 indexed evidenceHash, address indexed submitter, uint256 timestamp, string evidenceType, string metadataUri)",
] as const;

function sortValue(value: unknown): unknown {
	if (Array.isArray(value)) return value.map(sortValue);
	if (value !== null && typeof value === "object") {
		const obj = value as Record<string, unknown>;
		const sorted: Record<string, unknown> = {};
		for (const key of Object.keys(obj).sort()) {
			sorted[key] = sortValue(obj[key]);
		}
		return sorted;
	}
	return value;
}

/** canonical JSON：键排序 + 紧凑分隔符（与 Python json.dumps 对齐） */
export function canonicalJson(data: unknown): string {
	return JSON.stringify(sortValue(data));
}

/** 从 pipeline 结果构建可锚定的证据载荷（字段与后端 build_evidence_payload 对齐） */
export interface AnchorPayload {
	evidence_package: {
		pipeline_version: unknown;
		status: unknown;
		language: unknown;
	};
	requirements: { count: number };
	code: { lines: number };
	verification: {
		contract_passed: boolean;
		misra_violations: number;
		statement_coverage: unknown;
		branch_coverage: unknown;
		mcdc_coverage: unknown;
	};
	objectives: {
		satisfied: number;
		partial: number;
		unsatisfied: number;
	};
}

export function buildAnchorPayload(
	pipelineResult: Record<string, unknown>,
): AnchorPayload {
	const metrics =
		(pipelineResult.metrics as Record<string, unknown> | undefined) ??
		(pipelineResult.coverage as Record<string, unknown> | undefined) ??
		{};
	const asInt = (v: unknown): number => {
		const n = Number(v);
		return Number.isFinite(n) ? Math.trunc(n) : 0;
	};

	return {
		evidence_package: {
			pipeline_version: pipelineResult.pipeline_version ?? "unknown",
			status: pipelineResult.status ?? "completed",
			language: pipelineResult.language ?? "",
		},
		requirements: {
			count: asInt(
				pipelineResult.requirement_count ??
					pipelineResult.requirements_count ??
					0,
			),
		},
		code: {
			lines: asInt(metrics.code_lines ?? metrics.lines ?? 0),
		},
		verification: {
			contract_passed: Boolean(
				pipelineResult.contract_verified ?? metrics.contract_passed ?? false,
			),
			misra_violations: asInt(
				metrics.misra_violations ?? metrics.violations ?? 0,
			),
			statement_coverage: metrics.statement_coverage ?? metrics.statement ?? 0,
			branch_coverage: metrics.branch_coverage ?? metrics.branch ?? 0,
			mcdc_coverage: metrics.mcdc_coverage ?? metrics.mcdc ?? 0,
		},
		objectives: {
			satisfied: asInt(pipelineResult.objectives_satisfied ?? 0),
			partial: asInt(pipelineResult.objectives_partial ?? 0),
			unsatisfied: asInt(pipelineResult.objectives_unsatisfied ?? 0),
		},
	};
}

/** 计算 canonical 载荷的 SHA-256 十六进制摘要（WebCrypto） */
export async function computeAnchorHash(
	payload: Record<string, unknown> | AnchorPayload,
): Promise<string> {
	const bytes = new TextEncoder().encode(canonicalJson(payload));
	const digest = await crypto.subtle.digest("SHA-256", bytes);
	return [...new Uint8Array(digest)]
		.map((b) => b.toString(16).padStart(2, "0"))
		.join("");
}

/** 64 位十六进制哈希转 bytes32 形参（0x + 64 hex） */
export function toBytes32(hashHex: string): string {
	const clean = hashHex.toLowerCase().replace(/^0x/, "");
	if (clean.length !== 64) throw new Error("锚定哈希必须是 64 位十六进制");
	return `0x${clean}`;
}

export function isValidHash(hashHex: string): boolean {
	return /^0x[0-9a-f]{64}$/i.test(hashHex);
}

/** 从任意外部哈希规范化到 0x 前缀形式 */
export function normalizeHash(hashHex: string): string {
	return hashHex.toLowerCase().startsWith("0x")
		? hashHex.toLowerCase()
		: `0x${hashHex.toLowerCase()}`;
}
