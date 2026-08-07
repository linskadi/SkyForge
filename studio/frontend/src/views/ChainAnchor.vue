<script setup lang="ts">
import {
	BadgeCheck,
	CheckCircle2,
	Copy,
	ExternalLink,
	FileCheck2,
	Link2,
	Loader2,
	RefreshCw,
	ShieldCheck,
	Wallet,
} from "@lucide/vue";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast/use-toast";
import { fetchAnchorInfo } from "@/services/chainAnchorService";
import { API_BASE_URL } from "@/services/client";
import {
	buildAnchorPayload,
	canonicalJson,
	computeAnchorHash,
	EVIDENCE_CHAIN,
	EVIDENCE_CONTRACT,
	normalizeHash,
	toBytes32,
} from "@/utils/chainAnchor";

const { toast } = useToast();
const { t } = useI18n();

const SAMPLE_PIPELINE = JSON.stringify(
	{
		pipeline_version: "v0.5.0",
		language: "C",
		status: "completed",
		requirement_count: 4,
		metrics: {
			code_lines: 128,
			misra_violations: 0,
			contract_passed: true,
			statement_coverage: 1.0,
			branch_coverage: 1.0,
			mcdc_coverage: 1.0,
		},
		objectives_satisfied: 15,
		objectives_partial: 6,
		objectives_unsatisfied: 0,
	},
	null,
	2,
);

const inputText = ref(SAMPLE_PIPELINE);
const payloadPreview = ref("");
const anchorHash = ref("");
const hashComputedFromBackend = ref(false);
const computing = ref(false);
const parseError = ref("");

const walletAddress = ref("");
const txHash = ref("");
const anchoring = ref(false);
const verifying = ref(false);
const verified = ref<boolean | null>(null);
const anchorCount = ref<number | null>(null);
const contractAddress = ref("");

type WalletProvider = {
	getSigner: () => Promise<{ address: string }>;
};

let walletProvider: WalletProvider | null = null;

const explorerLink = computed(() =>
	txHash.value ? `${EVIDENCE_CHAIN.explorerUrl}/tx/${txHash.value}` : "",
);
const contractLink = computed(() =>
	contractAddress.value
		? `${EVIDENCE_CHAIN.explorerUrl}/address/${contractAddress.value}`
		: "",
);

function parseInput(): Record<string, unknown> {
	parseError.value = "";
	try {
		const parsed = JSON.parse(inputText.value);
		if (
			parsed === null ||
			typeof parsed !== "object" ||
			Array.isArray(parsed)
		) {
			throw new Error(t("anchor.inputJsonObject"));
		}
		return parsed as Record<string, unknown>;
	} catch (err) {
		parseError.value = err instanceof Error ? err.message : String(err);
		throw err;
	}
}

async function computeHash() {
	let pipelineResult: Record<string, unknown>;
	try {
		pipelineResult = parseInput();
	} catch {
		return;
	}

	computing.value = true;
	hashComputedFromBackend.value = false;
	verified.value = null;
	try {
		const payload = buildAnchorPayload(pipelineResult);
		payloadPreview.value = canonicalJson(payload);

		// 优先使用后端计算（与 Python 引擎同源）；失败时本地 WebCrypto 兜底
		try {
			const info = await fetchAnchorInfo(pipelineResult);
			anchorHash.value = normalizeHash(info.anchor_hash);
			contractAddress.value = info.contract.address ?? "";
			hashComputedFromBackend.value = true;
		} catch {
			anchorHash.value = await computeAnchorHash(payload);
			hashComputedFromBackend.value = false;
		}
		toast({
			title: t("anchor.computeHashSuccessTitle"),
			description: hashComputedFromBackend.value
				? t("anchor.computeHashBackendDesc")
				: t("anchor.computeHashLocalDesc"),
		});
	} catch (err) {
		toast({
			title: t("anchor.computeFailed"),
			description: err instanceof Error ? err.message : String(err),
			variant: "destructive",
		});
	} finally {
		computing.value = false;
	}
}

async function connectWallet() {
	try {
		const { BrowserProvider } = await import("ethers");
		const ethereum = (window as unknown as { ethereum?: object }).ethereum;
		if (!ethereum) {
			toast({
				title: t("anchor.noWalletDetected"),
				description: t("anchor.installWalletDesc"),
				variant: "destructive",
			});
			return;
		}
		const provider = new BrowserProvider(ethereum as never);
		const network = await provider.getNetwork();
		if (Number(network.chainId) !== EVIDENCE_CHAIN.chainId) {
			try {
				await provider.send("wallet_switchEthereumChain", [
					{ chainId: `0x${EVIDENCE_CHAIN.chainId.toString(16)}` },
				]);
			} catch (switchError) {
				const err = switchError as { code?: number };
				if (err.code === 4902) {
					await provider.send("wallet_addEthereumChain", [
						{
							chainId: `0x${EVIDENCE_CHAIN.chainId.toString(16)}`,
							chainName: EVIDENCE_CHAIN.name,
							rpcUrls: [EVIDENCE_CHAIN.rpcUrl],
							nativeCurrency: {
								name: "Sepolia ETH",
								symbol: "ETH",
								decimals: 18,
							},
							blockExplorerUrls: [EVIDENCE_CHAIN.explorerUrl],
						},
					]);
				} else {
					throw switchError;
				}
			}
		}
		const signer = await provider.getSigner();
		walletAddress.value = await signer.getAddress();
		walletProvider = { getSigner: async () => signer };
		toast({
			title: t("anchor.walletConnected"),
			description: walletAddress.value,
		});
	} catch (err) {
		toast({
			title: t("anchor.connectWalletFailed"),
			description: err instanceof Error ? err.message : String(err),
			variant: "destructive",
		});
	}
}

async function anchorOnChain() {
	if (!anchorHash.value) {
		toast({ title: t("anchor.computeHashFirst"), variant: "destructive" });
		return;
	}
	if (!walletProvider) {
		await connectWallet();
		if (!walletProvider) return;
	}
	let address = contractAddress.value;
	if (!address) {
		address = EVIDENCE_CONTRACT.address;
	}
	if (!address) {
		toast({
			title: t("anchor.contractNotDeployed"),
			description: t("anchor.deployContractDesc"),
			variant: "destructive",
		});
		return;
	}

	anchoring.value = true;
	try {
		const { Contract } = await import("ethers");
		const signer = await walletProvider.getSigner();
		const contract = new Contract(
			address,
			[
				"function anchor(bytes32 evidenceHash, string evidenceType, string metadataUri) returns (uint256 timestamp)",
			],
			signer as never,
		);
		const tx = await contract.anchor(
			toBytes32(anchorHash.value),
			"evidence_package",
			`${API_BASE_URL}/api/evidence/anchor-info`,
		);
		toast({ title: t("anchor.txSubmitted"), description: tx.hash });
		await tx.wait();
		txHash.value = tx.hash;
		verified.value = true;
		await refreshAnchorCount(address);
		toast({
			title: t("anchor.anchorSuccessTitle"),
			description: t("anchor.anchorSuccessDesc"),
		});
	} catch (err) {
		toast({
			title: t("anchor.anchorFailed"),
			description: err instanceof Error ? err.message : String(err),
			variant: "destructive",
		});
	} finally {
		anchoring.value = false;
	}
}

async function verifyOnChain() {
	if (!anchorHash.value) {
		toast({ title: t("anchor.computeHashFirst"), variant: "destructive" });
		return;
	}
	let address = contractAddress.value;
	if (!address) {
		address = EVIDENCE_CONTRACT.address;
	}
	if (!address) {
		toast({ title: t("anchor.contractNotDeployed"), variant: "destructive" });
		return;
	}
	verifying.value = true;
	try {
		const { Contract } = await import("ethers");
		const provider = new (await import("ethers")).JsonRpcProvider(
			EVIDENCE_CHAIN.rpcUrl,
			EVIDENCE_CHAIN.chainId,
		);
		const contract = new Contract(
			address,
			["function verify(bytes32) view returns (bool)"],
			provider,
		);
		verified.value = await contract.verify(toBytes32(anchorHash.value));
		await refreshAnchorCount(address);
		toast({
			title: verified.value
				? t("anchor.verifyPassed")
				: t("anchor.verifyNotFound"),
			variant: verified.value ? "default" : "destructive",
		});
	} catch (err) {
		toast({
			title: t("anchor.verifyFailed"),
			description: err instanceof Error ? err.message : String(err),
			variant: "destructive",
		});
	} finally {
		verifying.value = false;
	}
}

async function refreshAnchorCount(address: string) {
	try {
		const { Contract } = await import("ethers");
		const provider = new (await import("ethers")).JsonRpcProvider(
			EVIDENCE_CHAIN.rpcUrl,
			EVIDENCE_CHAIN.chainId,
		);
		const contract = new Contract(
			address,
			["function getHashCount() view returns (uint256)"],
			provider,
		);
		anchorCount.value = Number(await contract.getHashCount());
	} catch {
		anchorCount.value = null;
	}
}

function useSample() {
	inputText.value = SAMPLE_PIPELINE;
	parseError.value = "";
}

async function copyHash() {
	if (!anchorHash.value) return;
	try {
		await navigator.clipboard.writeText(anchorHash.value);
		toast({ title: t("anchor.hashCopied") });
	} catch {
		toast({ title: t("anchor.copyFailed"), variant: "destructive" });
	}
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-6 p-6">
    <Card>
      <CardHeader>
        <div class="flex items-center gap-2">
          <Link2 class="size-5 text-emerald-500" />
          <CardTitle>{{ $t("anchor.title") }}</CardTitle>
        </div>
        <CardDescription>
          {{ $t("anchor.description", { chain: EVIDENCE_CHAIN.name }) }}
        </CardDescription>
        <div class="flex flex-wrap gap-2 pt-2">
          <Badge variant="secondary">{{ EVIDENCE_CHAIN.name }}</Badge>
          <Badge variant="secondary">{{ $t("anchor.chainId", { chainId: EVIDENCE_CHAIN.chainId }) }}</Badge>
          <Badge variant="secondary">{{ EVIDENCE_CHAIN.explorerUrl }}</Badge>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium">{{ $t("anchor.pipelineJsonLabel") }}</label>
          <Button variant="outline" size="sm" @click="useSample">{{ $t("anchor.loadSample") }}</Button>
        </div>
        <Textarea
          v-model="inputText"
          class="min-h-56 font-mono text-xs"
          spellcheck="false"
          :aria-label="$t('anchor.pipelineJsonLabel')"
        />
        <p v-if="parseError" class="text-sm text-destructive">{{ parseError }}</p>

        <Button :disabled="computing" @click="computeHash">
          <Loader2 v-if="computing" class="size-4 animate-spin" />
          <FileCheck2 v-else class="size-4" />
          {{ $t("anchor.computeHash") }}
        </Button>

        <div v-if="anchorHash" class="space-y-3 rounded-lg border p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <ShieldCheck class="size-4 text-emerald-500" />
              <span class="text-sm font-medium">{{ $t("anchor.anchorHashLabel") }}</span>
              <Badge variant="secondary">
                {{ hashComputedFromBackend ? $t("anchor.backendComputed") : $t("anchor.localComputed") }}
              </Badge>
            </div>
            <Button variant="ghost" size="sm" @click="copyHash">
              <Copy class="size-4" />
            </Button>
          </div>
          <code class="block break-all rounded bg-muted p-2 font-mono text-xs">
            {{ anchorHash }}
          </code>
          <details>
            <summary class="cursor-pointer text-xs text-muted-foreground">
              {{ $t("anchor.viewPayload") }}
            </summary>
            <pre class="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-xs">{{ payloadPreview }}</pre>
          </details>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <div class="flex items-center gap-2">
          <Wallet class="size-5 text-sky-500" />
          <CardTitle>{{ $t("anchor.walletTitle") }}</CardTitle>
        </div>
        <CardDescription>
          {{ $t("anchor.walletDesc") }}
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex flex-wrap items-center gap-3">
          <Button variant="outline" :disabled="!!walletAddress" @click="connectWallet">
            <Wallet class="size-4" />
            {{ walletAddress ? $t("anchor.connected") : $t("anchor.connectWallet") }}
          </Button>
          <code v-if="walletAddress" class="font-mono text-xs">{{ walletAddress }}</code>
        </div>

        <div class="flex flex-wrap gap-3">
          <Button :disabled="anchoring || !anchorHash" @click="anchorOnChain">
            <Loader2 v-if="anchoring" class="size-4 animate-spin" />
            <BadgeCheck v-else class="size-4" />
            {{ $t("anchor.anchorBtn") }}
          </Button>
          <Button
            variant="outline"
            :disabled="verifying || !anchorHash"
            @click="verifyOnChain"
          >
            <Loader2 v-if="verifying" class="size-4 animate-spin" />
            <RefreshCw v-else class="size-4" />
            {{ $t("anchor.verifyBtn") }}
          </Button>
        </div>

        <div v-if="verified !== null" class="flex items-center gap-2 text-sm">
          <CheckCircle2
            class="size-4"
            :class="verified ? 'text-emerald-500' : 'text-destructive'"
          />
          <span :class="verified ? 'text-emerald-600' : 'text-destructive'">
            {{ verified ? $t("anchor.verifiedOk") : $t("anchor.verifiedNotFound") }}
          </span>
        </div>

        <div v-if="txHash" class="space-y-1 rounded-lg border p-3">
          <div class="flex items-center gap-2 text-sm font-medium">
            <BadgeCheck class="size-4 text-emerald-500" />
            {{ $t("anchor.onChainSuccess") }}
          </div>
          <code class="block break-all font-mono text-xs">{{ txHash }}</code>
          <a
            :href="explorerLink"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-xs text-sky-600 hover:underline"
          >
            <ExternalLink class="size-3" />
            {{ $t("anchor.viewOnExplorer") }}
          </a>
        </div>

        <div v-if="contractAddress || anchorCount !== null" class="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span v-if="contractAddress">
            {{ $t("anchor.contract") }}
            <a
              :href="contractLink"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 text-sky-600 hover:underline"
            >
              <code class="font-mono">{{ contractAddress }}</code>
              <ExternalLink class="size-3" />
            </a>
          </span>
          <span v-if="anchorCount !== null">{{ $t("anchor.anchorCount", { count: anchorCount }) }}</span>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
