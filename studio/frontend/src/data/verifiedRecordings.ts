export interface VerifiedRecordingSummary {
	id: string;
	title: string;
	profile: "cloud" | "local";
	model: string;
	status: "verified" | "verified_with_degradation";
	recordedAt: string;
	sha256: string;
	note: string;
}

/**
 * This catalog mirrors committed manifests, so the demo homepage can remain
 * fully offline. Details are verified again by `/api/v1/recordings/{id}` when
 * the backend is available.
 */
export const VERIFIED_RECORDINGS: VerifiedRecordingSummary[] = [
	{
		id: "cloud-deepseek-20260721",
		title: "云端 DeepSeek-V4 低通滤波器运行",
		profile: "cloud",
		model: "deepseek-v4-pro · DeepSeek",
		status: "verified",
		recordedAt: "2026-07-21 09:10",
		sha256: "8271b971db23b0269935fb3fc8e1e2f8032a859034414b0c3b07a463a39c02b6",
		note: "云端 DeepSeek API 真实运行记录，全链路 observed。",
	},
	{
		id: "local-ollama-20260721",
		title: "本地 Ollama qwen3:8b 低通滤波器运行",
		profile: "local",
		model: "qwen3:8b · Ollama",
		status: "verified",
		recordedAt: "2026-07-21 09:10",
		sha256: "6ed695ab4a0a88a972e2085e801bf5cd2c1acae2e60b8c9de6396f9290036410",
		note: "本地 Ollama 真实运行记录，全链路 observed。",
	},
];
