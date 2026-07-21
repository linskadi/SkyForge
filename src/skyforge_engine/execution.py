"""Immutable execution configuration and normalized evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvidenceStatus = Literal["observed", "simulated", "unavailable", "failed"]


@dataclass(frozen=True)
class ToolPolicy:
    use_real_gcc: bool = False
    use_real_cppcheck: bool = True
    strict_mode: bool = True


@dataclass(frozen=True)
class ExecutionContext:
    """Per-task snapshot; never mutates process-wide environment variables."""

    profile_id: Literal["cloud", "local"]
    provider: str
    model: str | None
    task_id: str | None = None
    timeout_seconds: int = 120
    max_concurrency: int = 1
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)


@dataclass(frozen=True)
class ToolEvidence:
    status: EvidenceStatus
    engine: str
    version: str | None = None
    duration_ms: int = 0
    exit_code: int | None = None
    output_digest: str | None = None
    findings: tuple[dict[str, Any], ...] = ()
    command: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class StageResult:
    artifact: Any
    status: EvidenceStatus
    duration_ms: int
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
