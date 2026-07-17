"""LLM 审计日志 — 记录所有云端 API 调用，支撑 DO-178C 工具鉴定。

记录内容:
  - 时间戳 + 调用者标识
  - Provider + Model
  - 输入长度 + 输出长度
  - 净化后输入的 hash (SHA-256)
  - 输出校验结果
  - 响应时间 + Token 消耗
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LLMCallRecord:
    timestamp: str = ""
    provider: str = ""
    model: str = ""
    input_hash: str = ""
    input_len: int = 0
    output_len: int = 0
    passed_validation: bool = True
    violations: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    tokens_used: int = 0
    cached: bool = False


class AuditLogger:
    """审计日志管理器。"""

    def __init__(self):
        self._records: list[LLMCallRecord] = []

    def log(self, record: LLMCallRecord) -> None:
        """记录一次 LLM 调用。"""
        record.timestamp = datetime.now(timezone.utc).isoformat()
        self._records.append(record)

    def compute_hash(self, content: str) -> str:
        """计算输入内容的 SHA-256 哈希。"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def get_records(self) -> list[dict]:
        """获取所有审计记录。"""
        return [
            {
                "timestamp": r.timestamp,
                "provider": r.provider,
                "model": r.model,
                "input_hash": r.input_hash,
                "input_len": r.input_len,
                "output_len": r.output_len,
                "passed_validation": r.passed_validation,
                "duration_ms": r.duration_ms,
                "tokens_used": r.tokens_used,
                "cached": r.cached,
            }
            for r in self._records
        ]

    def get_summary(self) -> dict:
        """获取审计摘要。"""
        if not self._records:
            return {"total_calls": 0}
        return {
            "total_calls": len(self._records),
            "total_tokens": sum(r.tokens_used for r in self._records),
            "total_duration_ms": sum(r.duration_ms for r in self._records),
            "failed_validation": sum(1 for r in self._records if not r.passed_validation),
            "cached": sum(1 for r in self._records if r.cached),
        }


_auditor: AuditLogger | None = None


def get_auditor() -> AuditLogger:
    global _auditor
    if _auditor is None:
        _auditor = AuditLogger()
    return _auditor
