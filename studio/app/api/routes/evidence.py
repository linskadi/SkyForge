"""链上证据锚定路由。

POST /api/evidence/anchor-info — 计算 pipeline 结果的证据锚定哈希与链信息
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from skyforge_engine.chain.evidence_anchor import (
    CHAIN_ID,
    CHAIN_NAME,
    EVIDENCE_ANCHOR_ADDRESS,
    EXPLORER_URL,
    RPC_URL,
    compute_anchor_hash_from_report,
)
from skyforge_engine.utils.log_util import logger

router = APIRouter()


class AnchorInfoRequest(BaseModel):
    """锚定请求体：复用 pipeline 结果字典。"""

    pipeline_result: dict[str, Any]


@router.post("/api/evidence/anchor-info")
async def anchor_info(req: AnchorInfoRequest) -> dict[str, Any]:
    """计算证据锚定哈希（SHA-256 canonical），返回链上锚定所需信息。

    该接口只计算哈希、不发起链上交易；上链由前端通过钱包完成，
    确保锚定的提交者身份可审计（msg.sender 即钱包地址）。
    """
    pipeline_result = req.pipeline_result
    anchor_hash = compute_anchor_hash_from_report(pipeline_result)

    logger.info(
        f"/api/evidence/anchor-info 计算锚定哈希: {anchor_hash[:16]}... "
        f"(keys={len(pipeline_result)})"
    )

    return {
        "anchor_hash": anchor_hash,
        "chain": {
            "name": CHAIN_NAME,
            "chain_id": CHAIN_ID,
            "rpc_url": RPC_URL,
            "explorer_url": EXPLORER_URL,
        },
        "contract": {
            "address": EVIDENCE_ANCHOR_ADDRESS or "",
            "deployed": bool(EVIDENCE_ANCHOR_ADDRESS),
        },
    }
