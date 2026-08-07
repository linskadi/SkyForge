#!/usr/bin/env node
/**
 * SkyForge EvidenceAnchor 合约部署脚本（无框架，ethers.js + solc）
 *
 * 用法:
 *   1) 安装依赖:  cd scripts && npm install
 *   2) 配置环境变量（scripts/.env 或 shell）:
 *        PRIVATE_KEY=0x...      # Sepolia 账户私钥（需少量测试 ETH）
 *        RPC_URL=...            # 可选，默认公共 Sepolia RPC
 *        CHAIN_ID=11155111      # 可选，默认 Sepolia
 *   3) 部署:      node deploy_anchor.mjs
 *
 * 成功后输出合约地址，并自动回填 src/skyforge_engine/chain/evidence_anchor.py
 * 中的 EVIDENCE_ANCHOR_ADDRESS，同时打印 Etherscan 链接。
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import solc from "solc";
import { ethers } from "ethers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

// 可选：自动加载 scripts/.env（Node 20.12+ 原生支持，文件不存在时静默跳过）
try {
	process.loadEnvFile(path.join(__dirname, ".env"));
} catch {
	/* .env 不存在时从环境变量读取 */
}

const CONTRACT_PATH = path.join(rootDir, "contracts", "EvidenceAnchor.sol");
const ANCHOR_PY_PATH = path.join(
	rootDir,
	"src",
	"skyforge_engine",
	"chain",
	"evidence_anchor.py",
);

const DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com";
const DEFAULT_CHAIN_ID = 11155111;

function compileContract() {
	const source = fs.readFileSync(CONTRACT_PATH, "utf8");
	const input = {
		language: "Solidity",
		sources: { "EvidenceAnchor.sol": { content: source } },
		settings: {
			optimizer: { enabled: true, runs: 200 },
			outputSelection: {
				"*": { "*": ["abi", "evm.bytecode.object"] },
			},
		},
	};

	const output = JSON.parse(solc.compile(JSON.stringify(input)));
	const errors = (output.errors ?? []).filter(
		(e) => e.severity === "error",
	);
	if (errors.length > 0) {
		console.error("编译失败:");
		for (const err of errors) console.error(`  ${err.formattedMessage}`);
		process.exit(1);
	}

	const contract = output.contracts["EvidenceAnchor.sol"]["EvidenceAnchor"];
	return { abi: contract.abi, bytecode: `0x${contract.evm.bytecode.object}` };
}

function updateAnchorAddress(address) {
	if (!fs.existsSync(ANCHOR_PY_PATH)) return;
	let content = fs.readFileSync(ANCHOR_PY_PATH, "utf8");
	content = content.replace(
		/EVIDENCE_ANCHOR_ADDRESS = ""/,
		`EVIDENCE_ANCHOR_ADDRESS = "${address}"`,
	);
	fs.writeFileSync(ANCHOR_PY_PATH, content);
	console.log(`已回填合约地址到 ${ANCHOR_PY_PATH}`);
}

async function main() {
	if (!process.env.PRIVATE_KEY) {
		console.error("缺少 PRIVATE_KEY 环境变量（Sepolia 部署账户私钥）");
		process.exit(1);
	}

	const rpcUrl = process.env.RPC_URL || DEFAULT_RPC;
	const chainId = Number(process.env.CHAIN_ID || DEFAULT_CHAIN_ID);

	console.log(`编译 ${CONTRACT_PATH} ...`);
	const { abi, bytecode } = compileContract();
	console.log("编译成功");

	const provider = new ethers.JsonRpcProvider(rpcUrl, chainId);
	const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
	const balance = await provider.getBalance(wallet.address);
	console.log(
		`部署账户: ${wallet.address}  余额: ${ethers.formatEther(balance)} ETH`,
	);
	if (balance === 0n) {
		console.error("账户余额为 0，请先向 Sepolia 测试网 faucet 领取测试 ETH");
		process.exit(1);
	}

	const factory = new ethers.ContractFactory(abi, bytecode, wallet);
	console.log("部署中 ...");
	const contract = await factory.deploy();
	const receipt = await contract.deploymentTransaction().wait();
	const address = await contract.getAddress();

	console.log(`合约已部署: ${address}`);
	console.log(`交易哈希: ${receipt.hash}`);
	console.log(`Etherscan: https://sepolia.etherscan.io/address/${address}`);

	updateAnchorAddress(address);

	// 部署后自检：验证合约可读
	const count = await contract.getHashCount();
	console.log(`自检 getHashCount() = ${count.toString()}`);
	console.log("部署完成 ✔");
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
