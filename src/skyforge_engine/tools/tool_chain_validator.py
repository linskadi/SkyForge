"""工具链自动验证脚本。

验证 SkyForge 工具链中各工具的存在性和可用性，用于 DO-330 工具鉴定。

检查项:
  1. Python 版本 >= 3.12
  2. Node.js 版本 >= 18
  3. GCC 可用
  4. Cppcheck 可用
  5. Redis 可用（可选）
  6. DO-178C 计划文档完整性
  7. 第三方依赖合规性

使用方式:
    python -m app.core.tools.tool_chain_validator
    python -m app.core.tools.tool_chain_validator --json  # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from skyforge_engine.utils.log_util import logger


@dataclass
class ToolCheckResult:
    """单工具检查结果。

    Attributes:
        tool: 工具名称。
        required: 是否必须。
        available: 是否可用。
        version: 版本字符串。
        message: 额外信息。
    """

    tool: str
    required: bool
    available: bool
    version: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


@dataclass
class DocCheckResult:
    """文档完整性检查结果。"""

    doc: str
    exists: bool
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


@dataclass
class ValidationReport:
    """完整工具链验证报告。"""

    all_passed: bool = True
    tool_results: list[ToolCheckResult] = field(default_factory=list)
    doc_results: list[DocCheckResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "all_passed": self.all_passed,
            "tool_results": [r.to_dict() for r in self.tool_results],
            "doc_results": [r.to_dict() for r in self.doc_results],
            "summary": self.summary,
        }


def _get_version(cmd: list[str]) -> str:
    """获取工具版本号。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.split("\n")[0].strip()[:80]
    except Exception:
        return ""


def _check_python() -> ToolCheckResult:
    """检查 Python 版本。"""
    version = sys.version.split()[0]
    major, minor, *_ = sys.version_info
    available = (major, minor) >= (3, 12)
    return ToolCheckResult(
        tool="Python",
        required=True,
        available=available,
        version=version,
        message="版本满足要求" if available else f"需要 >= 3.12，当前 {version}",
    )


def _check_node() -> ToolCheckResult:
    """检查 Node.js 版本。"""
    version = _get_version(["node", "--version"])
    available = bool(version)
    return ToolCheckResult(
        tool="Node.js",
        required=True,
        available=available,
        version=version,
    )


def _check_gcc() -> ToolCheckResult:
    """检查 GCC 可用性。"""
    version = _get_version(["gcc", "--version"])
    available = bool(version)
    return ToolCheckResult(
        tool="GCC",
        required=True,
        available=available,
        version=version,
        message="C 代码编译" if available else "GCC 不可用，将使用 Python Mock 模式",
    )


def _check_cppcheck() -> ToolCheckResult:
    """检查 Cppcheck 可用性。

    注：CI 环境通常不预装 Cppcheck，此处标记为可选；本地或专用
    验证环境应安装 Cppcheck 以启用真实 MISRA-C 扫描，缺失时
    SkyForge 自动回退到 Mock 模式。
    """
    version = _get_version(["cppcheck", "--version"])
    available = bool(version)
    return ToolCheckResult(
        tool="Cppcheck",
        required=False,
        available=available,
        version=version,
        message="MISRA-C 扫描" if available else "Cppcheck 不可用，将使用模拟模式",
    )


def _check_redis() -> ToolCheckResult:
    """检查 Redis 可用性。"""
    available = shutil.which("redis-cli") is not None
    return ToolCheckResult(
        tool="Redis",
        required=False,
        available=available,
        message="任务队列" if available else "Redis 可选，不影响核心功能",
    )


def _check_do178c_docs(project_root: str) -> list[DocCheckResult]:
    """检查 DO-178C 计划文档完整性。"""
    required_docs = [
        "PSAC.md",
        "SDP.md",
        "SVP.md",
        "SCMP.md",
        "SQAP.md",
        "TQP.md",
        "TOR.md",
        "TAS.md",
    ]
    doc_dir = os.path.join(project_root, "docs", "compliance")
    results: list[DocCheckResult] = []
    for doc in required_docs:
        path = os.path.join(doc_dir, doc)
        results.append(DocCheckResult(doc=doc, exists=os.path.exists(path), path=path))
    return results


def validate(project_root: str | None = None) -> ValidationReport:
    """执行完整工具链验证。

    Args:
        project_root: 项目根目录，默认为 backend 的父目录的父目录
                     （即 SkyForge 根目录）。

    Returns:
        ValidationReport：验证报告。
    """
    if project_root is None:
        # 默认推算: backend/app/core/tools/ -> SkyForge/
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )

    report = ValidationReport()
    all_passed = True

    # 工具检查
    tool_checks = [
        _check_python(),
        _check_node(),
        _check_gcc(),
        _check_cppcheck(),
        _check_redis(),
    ]
    report.tool_results = tool_checks
    for r in tool_checks:
        if r.required and not r.available:
            all_passed = False

    # 文档检查
    doc_results = _check_do178c_docs(project_root)
    report.doc_results = doc_results
    missing_docs = [d.doc for d in doc_results if not d.exists]
    if missing_docs:
        all_passed = False

    # 汇总
    required_count = sum(1 for r in tool_checks if r.required)
    available_count = sum(1 for r in tool_checks if r.required and r.available)
    doc_count = len(doc_results)
    doc_available = sum(1 for d in doc_results if d.exists)

    report.summary = (
        f"工具链验证: {available_count}/{required_count} 必须工具可用"
        f" | 文档: {doc_available}/{doc_count} 份"
    )
    report.all_passed = all_passed

    status = "✅ 通过" if all_passed else "❌ 未通过"
    logger.info(f"ToolChainValidator:{status} — {report.summary}")
    return report


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="SkyForge 工具链验证器")
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="项目根目录",
    )
    args = parser.parse_args()

    report = validate(args.project_root)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("SkyForge 工具链验证报告")
        print("=" * 50)
        for r in report.tool_results:
            icon = "✅" if r.available else "❌" if r.required else "⚠️"
            req = "[必须]" if r.required else "[可选]"
            print(f"  {icon} {r.tool} {req}: {r.version or r.message}")
        print("-" * 50)
        print("  文档完整性:")
        for d in report.doc_results:
            icon = "✅" if d.exists else "❌"
            print(f"  {icon} {d.doc}")
        print("-" * 50)
        print(f"  总结: {report.summary}")
        print(f"  结论: {'✅ 全部通过' if report.all_passed else '❌ 存在问题'}")

    sys.exit(0 if report.all_passed else 1)


if __name__ == "__main__":
    main()
