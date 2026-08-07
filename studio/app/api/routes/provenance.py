"""证据链追溯 API。

提供任务级别的证据链查询和 DO-178C 目标映射查询。
"""

from __future__ import annotations


from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.provenance import (
    DO178CMapping,
    DO178CObjective,
    EvidenceChain,
    ProvenanceNode,
)
from app.utils.log_util import logger

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


def _build_mock_chain(task_id: str) -> EvidenceChain:
    """构建模拟证据链（当前无数据库持久化，使用结构化mock）。"""
    chain = EvidenceChain(task_id=task_id)

    chain.add_node(
        ProvenanceNode(
            id=f"req_{task_id}_001",
            type="requirement",
            description="顶层功能需求",
            metadata={"source": "user_input", "priority": "high"},
        )
    )

    chain.add_node(
        ProvenanceNode(
            id=f"contract_{task_id}_001",
            type="contract",
            description="形式化契约（前置/后置条件）",
            metadata={"method": "hoare_logic"},
        )
    )
    chain.add_edge(f"req_{task_id}_001", f"contract_{task_id}_001")

    chain.add_node(
        ProvenanceNode(
            id=f"code_{task_id}_001",
            type="code",
            description="生成的源代码",
            metadata={"language": "c", "hash": f"sha256:{task_id}"},
        )
    )
    chain.add_edge(f"contract_{task_id}_001", f"code_{task_id}_001")

    chain.add_node(
        ProvenanceNode(
            id=f"verification_{task_id}_001",
            type="verification",
            description="形式化验证 + MISRA 检查",
            metadata={"tools": ["cbmc", "z3", "cppcheck"]},
        )
    )
    chain.add_edge(f"code_{task_id}_001", f"verification_{task_id}_001")

    chain.add_node(
        ProvenanceNode(
            id=f"evidence_{task_id}_001",
            type="evidence",
            description="验证证据包（报告 + 日志 + 追踪）",
            metadata={"format": "zip", "size_kb": 1024},
        )
    )
    chain.add_edge(f"verification_{task_id}_001", f"evidence_{task_id}_001")

    return chain


def _build_mock_do178c(task_id: str) -> DO178CMapping:
    """构建模拟 DO-178C 目标映射。"""

    objectives: list[DO178CObjective] = [
        DO178CObjective(
            objective_id="PSAC.01.01",
            objective_name="软件计划被定义并文档化",
            category="PSAC",
            status="met",
            evidence_refs=[f"evidence_{task_id}_001"],
            notes="生成过程符合 SDP 要求",
        ),
        DO178CObjective(
            objective_id="PSAC.02.01",
            objective_name="需求被正确捕获和追踪",
            category="PSAC",
            status="met",
            evidence_refs=[f"req_{task_id}_001"],
        ),
        DO178CObjective(
            objective_id="SDP.01.01",
            objective_name="形式化方法被正确应用",
            category="SDP",
            status="partially_met",
            evidence_refs=[f"contract_{task_id}_001"],
            notes="契约已生成，需要人工审查确认完整性",
        ),
        DO178CObjective(
            objective_id="SDP.02.01",
            objective_name="代码符合编码标准",
            category="SDP",
            status="met",
            evidence_refs=[f"code_{task_id}_001", f"verification_{task_id}_001"],
        ),
        DO178CObjective(
            objective_id="SVP.01.01",
            objective_name="验证覆盖完整性",
            category="SVP",
            status="not_met",
            evidence_refs=[f"verification_{task_id}_001"],
            notes="需要补充 MC/DC 覆盖率分析",
        ),
    ]

    summary = {"met": 0, "partially_met": 0, "not_met": 0, "total": len(objectives)}
    for obj in objectives:
        summary[obj.status] = summary.get(obj.status, 0) + 1

    return DO178CMapping(task_id=task_id, objectives=objectives, summary=summary)


@router.get("/chain/{task_id}")
async def get_evidence_chain(task_id: str) -> JSONResponse:
    """返回指定任务的完整证据链。

    当前实现为结构化 mock 数据，确保前端可以正常对接和展示。
    后续可替换为从数据库中读取真实的追溯记录。
    """
    try:
        chain = _build_mock_chain(task_id)
        return JSONResponse(
            content=chain.model_dump(),
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        logger.error(f"获取证据链失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"获取证据链失败: {str(e)}"},
        )


@router.get("/do178c/{task_id}")
async def get_do178c_mapping(task_id: str) -> JSONResponse:
    """返回指定任务的 DO-178C 目标矩阵映射。

    当前实现为结构化 mock 数据，确保前端可以正常对接和展示。
    """
    try:
        mapping = _build_mock_do178c(task_id)
        return JSONResponse(
            content=mapping.model_dump(),
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        logger.error(f"获取 DO-178C 映射失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"获取 DO-178C 映射失败: {str(e)}"},
        )
