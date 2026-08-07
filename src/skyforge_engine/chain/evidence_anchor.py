# -*- coding: utf-8 -*-
"""SkyForge 链上证据锚定（Evidence Anchoring）模块。

将 DO-178C 验证证据包哈希锚定到链上，为适航追溯证据提供不可篡改的
时间戳与可审计来源。

设计要点：
- 锚定对象：证据包 `index.json`（或 pipeline 结果的规范化摘要）的
  canonical SHA-256 哈希，与 EvidenceAnchor 合约 `anchor(bytes32)` 一致。
- canonical 规则：`json.dumps(sort_keys=True, separators=(",", ":"))`，
  保证相同内容的证据在任何机器上生成相同哈希。
- 写链是开放入口（任何运行者都可锚定），链上时间戳即审计事实。

用法:
    from skyforge_engine.chain.evidence_anchor import compute_anchor_hash_from_package

    hash_hex = compute_anchor_hash_from_package("evidence_package/xxx")
    # 前端通过钱包调用合约: anchor(bytes32(hash_hex), "evidence_package", uri)
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# ==================== 链配置 ====================
# ChainHack 2026 部署目标：Ethereum Sepolia 测试网（EVM）
CHAIN_NAME = "Ethereum Sepolia"
CHAIN_ID = 11155111
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
EXPLORER_URL = "https://sepolia.etherscan.io"

# 部署后回填；scripts/deploy_anchor.mjs 部署成功会自动写入本文件
EVIDENCE_ANCHOR_ADDRESS = "0xC986756935B44b9aaEfCdF1c8E5f6B3e296f0482"

# 与 contracts/EvidenceAnchor.sol 保持一致的 ABI（用于前端/校验工具）
EVIDENCE_ANCHOR_ABI = [
    {
        "type": "function",
        "name": "anchor",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "evidenceHash", "type": "bytes32"},
            {"name": "evidenceType", "type": "string"},
            {"name": "metadataUri", "type": "string"},
        ],
        "outputs": [{"name": "timestamp", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "verify",
        "stateMutability": "view",
        "inputs": [{"name": "evidenceHash", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "type": "function",
        "name": "getEvidence",
        "stateMutability": "view",
        "inputs": [{"name": "evidenceHash", "type": "bytes32"}],
        "outputs": [
            {
                "type": "tuple",
                "components": [
                    {"name": "evidenceHash", "type": "bytes32"},
                    {"name": "submitter", "type": "address"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "evidenceType", "type": "string"},
                    {"name": "metadataUri", "type": "string"},
                ],
            }
        ],
    },
    {
        "type": "function",
        "name": "getHashCount",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "event",
        "name": "EvidenceAnchored",
        "inputs": [
            {"name": "evidenceHash", "indexed": True, "type": "bytes32"},
            {"name": "submitter", "indexed": True, "type": "address"},
            {"name": "timestamp", "indexed": False, "type": "uint256"},
            {"name": "evidenceType", "indexed": False, "type": "string"},
            {"name": "metadataUri", "indexed": False, "type": "string"},
        ],
    },
]


# ==================== canonical 序列化 ====================

def canonical_json(data: dict[str, Any]) -> str:
    """将证据载荷序列化为 canonical JSON 字符串。

    键排序 + 紧凑分隔符 + UTF-8 原样输出，保证跨机器哈希一致。
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_payload(data: dict[str, Any]) -> bytes:
    """canonical JSON 的 UTF-8 字节序列。"""
    return canonical_json(data).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """SHA-256 十六进制摘要。"""
    return hashlib.sha256(data).hexdigest()


# ==================== 锚定哈希计算 ====================

def compute_anchor_hash(index_data: dict[str, Any]) -> str:
    """对证据索引（index.json 内容）计算链上锚定哈希。

    Args:
        index_data: 证据索引字典（`generate_package()` 产出的 index.json）。

    Returns:
        SHA-256 十六进制字符串（64 位），即合约 `anchor()` 的 evidenceHash。
    """
    return sha256_hex(canonical_payload(index_data))


def compute_anchor_hash_from_package(package_dir: str) -> str:
    """读取证据包目录中的 index.json 并计算锚定哈希。

    Args:
        package_dir: `EvidenceCollector.generate_package()` 返回的目录。

    Returns:
        SHA-256 哈希；index.json 不存在时抛出 FileNotFoundError。
    """
    index_path = os.path.join(package_dir, "index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
    return compute_anchor_hash(index_data)


def build_evidence_payload(pipeline_result: dict[str, Any]) -> dict[str, Any]:
    """从 pipeline 结果构建可锚定的证据载荷。

    仅提取可复现的客观指标，字段名稳定，便于跨运行对比；
    不包含随机/时间字段，保证同一输入生成同一哈希。
    """
    metrics = pipeline_result.get("metrics", pipeline_result.get("coverage", {}))
    if not isinstance(metrics, dict):
        metrics = {}

    return {
        "evidence_package": {
            "pipeline_version": pipeline_result.get("pipeline_version", "unknown"),
            "status": pipeline_result.get("status", "completed"),
            "language": pipeline_result.get("language", ""),
        },
        "requirements": {
            "count": _as_int(pipeline_result.get("requirement_count", pipeline_result.get("requirements_count", 0))),
        },
        "code": {
            "lines": _as_int(metrics.get("code_lines", metrics.get("lines", 0))),
        },
        "verification": {
            "contract_passed": bool(pipeline_result.get("contract_verified", metrics.get("contract_passed", False))),
            "misra_violations": _as_int(metrics.get("misra_violations", metrics.get("violations", 0))),
            "statement_coverage": metrics.get("statement_coverage", metrics.get("statement", 0)),
            "branch_coverage": metrics.get("branch_coverage", metrics.get("branch", 0)),
            "mcdc_coverage": metrics.get("mcdc_coverage", metrics.get("mcdc", 0)),
        },
        "objectives": {
            "satisfied": _as_int(pipeline_result.get("objectives_satisfied", 0)),
            "partial": _as_int(pipeline_result.get("objectives_partial", 0)),
            "unsatisfied": _as_int(pipeline_result.get("objectives_unsatisfied", 0)),
        },
    }


def compute_anchor_hash_from_report(pipeline_result: dict[str, Any]) -> str:
    """从 pipeline 结果摘要计算锚定哈希（无需完整证据包）。

    适用于 Studio 的 POST /api/evidence/anchor-info 接口。
    """
    payload = build_evidence_payload(pipeline_result)
    return compute_anchor_hash(payload)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def verify_anchor(package_dir: str, expected_hash: str | None = None) -> dict[str, Any]:
    """本地自检：验证证据包哈希完整性。

    Returns:
        { "package_dir", "hash", "matches" }
    """
    actual = compute_anchor_hash_from_package(package_dir)
    return {
        "package_dir": package_dir,
        "hash": actual,
        "matches": expected_hash is None or actual == expected_hash,
    }
