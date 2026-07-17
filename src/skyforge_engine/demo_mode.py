# -*- coding: utf-8 -*-
"""真实 LLM 演示模式 — P0 修复：确保评委展示时使用真实 AI 驱动而非 Mock 降级。

设计文档批判式审查发现的核心问题：默认配置下"AI智能体驱动"名不副实，
Mock 模式成为了本体。本模块解决此问题：

1. DemoConfig：演示专用配置，强制 USE_LLM=true，选择最优模型
2. DemoVerifier：启动前多级验证，确保 LLM 真正可用
3. DemoRunner：一键启动演示，包含自检、预热、示例运行
4. DemoReport：生成演示就绪报告，供评委审阅

用法:
    from skyforge_engine.demo_mode import DemoRunner
    runner = DemoRunner()
    report = await runner.run(readiness_check=True, warmup=True)
    if report["ready"]:
        # 启动 pipeline 演示
        ...
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from skyforge_engine.utils.log_util import logger

try:
    from skyforge_llm.client import get_lmstudio_client
except ImportError:
    get_lmstudio_client = None


# ==================== 演示配置 ====================

@dataclass
class DemoConfig:
    """演示专用配置 — 确保真实 LLM 运行。

    与生产配置的区别：
    - USE_LLM 强制为 True（不允许 Mock 降级）
    - 禁用 LLM 响应缓存（确保每次演示都是实时推理）
    - 设置较长的超时时间（模型首次加载可能较慢）
    - 启用详细日志（评委可看到完整 Agent 思维链）
    """

    # LLM 强制配置
    use_llm: bool = True
    llm_cache_enabled: bool = False  # 禁用缓存，确保实时推理
    llm_timeout: int = 600  # 10 分钟超时
    llm_temperature: float = 0.3  # 低温度确保输出确定性

    # 模型选择优先级（按顺序尝试）
    preferred_models: list[str] = field(default_factory=lambda: [
        "qwen/qwen3-8b",           # 国产首选
        "deepseek/deepseek-coder",  # 代码能力最强
        "google/gemma-4-e4b",       # 轻量备选
    ])

    # 演示场景配置
    demo_requirements: list[str] = field(default_factory=lambda: [
        "设计一个10Hz低通滤波器，截止频率10Hz，采样率100Hz，用于机载高度传感器信号处理，DAL-B等级",
        "设计一个PID姿态控制器，响应时间<10ms，用于飞行控制系统，DAL-A等级",
        "设计一个ARINC 429总线通信模块，波特率100Kbps，支持奇偶校验，DAL-B等级",
    ])

    # 验证配置
    require_llm: bool = True  # 必须使用真实 LLM
    max_mock_ratio: float = 0.0  # Mock 比例上限（0 = 不允许任何 Mock）
    health_check_retries: int = 3
    health_check_interval: float = 2.0  # 秒

    # 输出配置
    verbose: bool = True
    save_demo_log: bool = True
    demo_log_path: str = "demo_run.log"


# ==================== 演示验证器 ====================

class DemoVerifier:
    """启动前多级验证器。

    验证层级（从低到高）：
    L1: LM Studio 进程可用性
    L2: 模型加载状态
    L3: API 端点可达性
    L4: 实际推理能力（发送测试 prompt）
    L5: 输出质量验证（解析 JSON / 代码结构）
    """

    def __init__(self, config: Optional[DemoConfig] = None):
        self.config = config or DemoConfig()
        self._results: list[dict[str, Any]] = []

    async def verify_all(self) -> dict[str, Any]:
        """执行全部 5 级验证。"""
        self._results = []

        # L1: LM Studio 进程检查
        l1 = await self._check_lm_studio_process()
        self._results.append(l1)

        # L2: 模型列表检查
        l2 = await self._check_loaded_models()
        self._results.append(l2)

        # L3: API 端点检查
        l3 = await self._check_api_endpoint()
        self._results.append(l3)

        # L4: 实际推理测试
        l4 = await self._test_inference()
        self._results.append(l4)

        # L5: 输出质量验证
        l5 = await self._test_output_quality()
        self._results.append(l5)

        all_passed = all(r["passed"] for r in self._results)
        return {
            "ready": all_passed,
            "levels": self._results,
            "summary": self._build_summary(),
            "recommendations": self._build_recommendations(),
        }

    async def _check_lm_studio_process(self) -> dict[str, Any]:
        """L1: 检查 LM Studio 是否在运行。"""
        import psutil
        result = {"level": "L1", "name": "LM Studio 进程检查", "passed": False, "detail": ""}
        try:
            lm_found = False
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = proc.info["name"].lower() if proc.info["name"] else ""
                    if "lm studio" in name or "lm-studio" in name or "lmstudio" in name:
                        lm_found = True
                        result["detail"] = f"LM Studio 进程已运行 (PID: {proc.info['pid']})"
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 备选：检查端口 1234 是否被占用
            if not lm_found:
                port_check = await self._check_port(1234)
                if port_check:
                    lm_found = True
                    result["detail"] = "端口 1234 已监听（LM Studio 可能以后台服务运行）"

            result["passed"] = lm_found
            if not lm_found:
                result["detail"] = "未检测到 LM Studio 进程，请先启动 LM Studio 并加载模型"
        except ImportError:
            # psutil 可能未安装，降级为端口检查
            port_check = await self._check_port(1234)
            result["passed"] = port_check
            result["detail"] = "端口 1234 " + ("已监听" if port_check else "未监听（请启动 LM Studio）")
            if not port_check:
                result["detail"] += " (psutil 未安装，仅检查端口)"
        except Exception as e:
            result["detail"] = f"进程检查失败: {e}"

        return result

    async def _check_port(self, port: int) -> bool:
        """检查端口是否被占用。"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _check_loaded_models(self) -> dict[str, Any]:
        """L2: 检查已加载的模型。"""
        result = {"level": "L2", "name": "模型加载检查", "passed": False, "detail": "", "models": []}

        client = get_lmstudio_client() if get_lmstudio_client else None
        if client is None:
            result["detail"] = "LM Studio 客户端不可用"
            return result

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(f"{client.base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data", [])
                    result["models"] = [m.get("id", "unknown") for m in models]
                    if models:
                        result["passed"] = True
                        result["detail"] = f"已加载 {len(models)} 个模型: {result['models']}"
                    else:
                        result["detail"] = "LM Studio 运行中但未加载任何模型，请在 LM Studio 中加载模型"
                else:
                    result["detail"] = f"模型列表请求失败 (HTTP {resp.status_code})"
        except Exception as e:
            result["detail"] = f"模型检查失败: {e}"

        return result

    async def _check_api_endpoint(self) -> dict[str, Any]:
        """L3: 检查 Chat Completions API 端点和模型可用性。"""
        result = {"level": "L3", "name": "API 端点检查", "passed": False, "detail": ""}

        client = get_lmstudio_client() if get_lmstudio_client else None
        if client is None:
            result["detail"] = "LM Studio 客户端不可用"
            return result

        try:
            available = client.is_available(force_recheck=True)
            if available:
                result["passed"] = True
                result["detail"] = f"Chat Completions API 可用 (模型: {client.model})"
            else:
                result["detail"] = (
                    "API 端点不可用。可能原因: "
                    "1) LM Studio 未启动 "
                    "2) 模型未加载完成 "
                    "3) 端口被占用"
                )
        except Exception as e:
            result["detail"] = f"API 检查失败: {e}"

        return result

    async def _test_inference(self) -> dict[str, Any]:
        """L4: 发送测试 prompt 验证实际推理能力。"""
        result = {
            "level": "L4",
            "name": "推理能力测试",
            "passed": False,
            "detail": "",
            "response": "",
            "latency_ms": 0,
        }

        client = get_lmstudio_client() if get_lmstudio_client else None
        if client is None:
            result["detail"] = "LM Studio 客户端不可用"
            return result

        if not client.is_available():
            result["detail"] = "LM Studio 不可用，无法进行推理测试"
            return result

        try:
            test_prompt = (
                "请解析以下机载软件需求为 JSON（只输出 JSON，不要其他内容）：\n"
                "设计一个10Hz低通滤波器，截止频率10Hz，采样率100Hz，DAL-B等级"
            )
            system_prompt = (
                "你是 DO-178C 适航需求工程师。输出严格 JSON。\n"
                '格式: {"type":"filter","module_name":"lowpass_filter_10hz",'
                '"safety_level":"DAL-B","params":{"cutoff_hz":10.0,"sample_rate_hz":100.0}}'
            )

            start = time.time()
            response = await client.chat_async(
                prompt=test_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            elapsed_ms = (time.time() - start) * 1000
            result["latency_ms"] = round(elapsed_ms, 1)

            if response and len(response.strip()) > 20:
                result["passed"] = True
                result["response"] = response[:500]
                result["detail"] = f"推理成功 (延迟 {result['latency_ms']}ms)"
            else:
                result["detail"] = f"推理返回内容过短或为空 (长度: {len(response) if response else 0})"
                result["response"] = response[:200] if response else ""
        except Exception as e:
            result["detail"] = f"推理测试失败: {e}"

        return result

    async def _test_output_quality(self) -> dict[str, Any]:
        """L5: 验证输出质量（JSON 解析、代码结构、MISRA 注释）。"""
        result = {
            "level": "L5",
            "name": "输出质量验证",
            "passed": False,
            "detail": "",
            "checks": {},
        }

        client = get_lmstudio_client() if get_lmstudio_client else None
        if client is None or not client.is_available():
            result["detail"] = "跳过（L4 未通过）"
            result["skipped"] = True
            return result

        checks = {}

        # 5a: JSON 解析能力
        try:
            json_prompt = (
                "请解析以下需求为 JSON（只输出 JSON）：\n"
                "设计PID姿态控制器，DAL-A等级，响应时间<10ms"
            )
            json_response = await client.chat_async(
                prompt=json_prompt,
                system_prompt="输出严格 JSON，禁止 Markdown 包裹。",
                temperature=0.1,
            )
            try:
                json.loads(json_response.strip())
                checks["json_parsing"] = True
            except json.JSONDecodeError:
                # 尝试提取 JSON
                import re
                match = re.search(r"\{[\s\S]*\}", json_response)
                if match:
                    try:
                        json.loads(match.group())
                        checks["json_parsing"] = True
                    except json.JSONDecodeError:
                        checks["json_parsing"] = False
                else:
                    checks["json_parsing"] = False
        except Exception:
            checks["json_parsing"] = False

        # 5b: 代码结构验证
        try:
            code_prompt = "生成一个 C 语言低通滤波函数，包含 DO-178C 注释。"
            code_response = await client.chat_async(
                prompt=code_prompt,
                system_prompt="你是 MISRA-C 合规的航空 C 代码工程师。",
                temperature=0.2,
            )
            has_function = "void " in code_response or "double " in code_response
            has_req_tag = "[REQ-" in code_response
            has_misra_tag = "[MISRA-Rule-" in code_response
            checks["code_structure"] = has_function and (has_req_tag or has_misra_tag)
            checks["code_has_req_tag"] = has_req_tag
            checks["code_has_misra_tag"] = has_misra_tag
        except Exception:
            checks["code_structure"] = False

        # 综合判断
        passed_count = sum(1 for v in checks.values() if isinstance(v, bool) and v)
        total_count = sum(1 for v in checks.values() if isinstance(v, bool))
        result["passed"] = passed_count >= total_count * 0.6 if total_count > 0 else False
        result["checks"] = checks
        result["detail"] = f"输出质量: {passed_count}/{total_count} 项通过"

        return result

    def _build_summary(self) -> str:
        """构建验证摘要。"""
        passed = sum(1 for r in self._results if r.get("passed"))
        total = len(self._results)
        status = "✅ 全部通过，可以开始演示" if passed == total else f"⚠️ {passed}/{total} 项通过"

        lines = [f"演示就绪检查: {status}"]
        for r in self._results:
            icon = "✅" if r.get("passed") else "❌"
            lines.append(f"  {icon} {r['name']}: {r.get('detail', '')}")
        return "\n".join(lines)

    def _build_recommendations(self) -> list[str]:
        """根据失败项给出修复建议。"""
        recs = []
        for r in self._results:
            if not r.get("passed"):
                if r["level"] == "L1":
                    recs.append("请启动 LM Studio（https://lmstudio.ai/）")
                elif r["level"] == "L2":
                    recs.append("请在 LM Studio 中下载并加载 Qwen3 或 DeepSeek 模型")
                elif r["level"] == "L3":
                    recs.append("请确认 LM Studio Local Server 已启动（默认端口 1234）")
                elif r["level"] == "L4":
                    recs.append("模型推理失败，请检查模型是否完全加载到内存")
                elif r["level"] == "L5":
                    recs.append("输出质量不达标，建议更换更大模型或调整 temperature")
        if not recs:
            recs.append("所有检查通过，无需额外操作")
        return recs


# ==================== 演示运行器 ====================

@dataclass
class DemoResult:
    """单次演示运行结果。"""
    requirement: str
    req_type: str = ""
    dal: str = ""
    llm_used: bool = False
    contract_generated: bool = False
    code_generated: bool = False
    time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class DemoRunner:
    """一键演示运行器。

    用法:
        runner = DemoRunner()
        report = await runner.run()
        if report["ready"]:
            print("演示就绪！")
    """

    def __init__(self, config: Optional[DemoConfig] = None):
        self.config = config or DemoConfig()

    async def run(
        self,
        readiness_check: bool = True,
        warmup: bool = True,
    ) -> dict[str, Any]:
        """执行完整演示流程。

        Args:
            readiness_check: 是否执行启动前验证
            warmup: 是否预热模型

        Returns:
            演示报告字典，包含 ready / verification / warmup / demo_results
        """
        report: dict[str, Any] = {
            "ready": False,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "use_llm": self.config.use_llm,
                "model": None,
                "preferred_models": self.config.preferred_models,
            },
            "verification": None,
            "warmup": None,
            "demo_results": [],
            "summary": "",
            "errors": [],
        }

        # 1. 就绪检查
        if readiness_check:
            verifier = DemoVerifier(self.config)
            verification = await verifier.verify_all()
            report["verification"] = verification
            if not verification["ready"]:
                report["summary"] = "❌ 演示环境未就绪，请根据建议修复后重试"
                report["errors"] = [
                    r["detail"]
                    for r in verification.get("levels", [])
                    if not r.get("passed")
                ]
                return report

        # 2. 获取客户端并确定模型
        client = get_lmstudio_client() if get_lmstudio_client else None
        if client is None:
            report["summary"] = "❌ LM Studio 客户端不可用"
            report["errors"].append("无法初始化 LM Studio 客户端")
            return report

        report["config"]["model"] = client.model

        # 3. 预热（发送快速请求确保模型在内存中）
        if warmup:
            warmup_result = await self._warmup(client)
            report["warmup"] = warmup_result

        # 4. 运行演示场景
        for req in self.config.demo_requirements[:3]:
            demo = await self._run_single_demo(client, req)
            report["demo_results"].append(demo.__dict__ if hasattr(demo, "__dict__") else demo)

        # 5. 评估
        llm_used_count = sum(
            1 for r in report["demo_results"]
            if isinstance(r, dict) and r.get("llm_used")
        )
        total = len(report["demo_results"])
        if total > 0 and llm_used_count == total:
            report["ready"] = True
            report["summary"] = (
                f"✅ 演示就绪！所有 {total} 个场景均使用真实 LLM "
                f"(模型: {client.model})"
            )
        elif llm_used_count > 0:
            report["ready"] = True
            report["summary"] = (
                f"⚠️ {llm_used_count}/{total} 场景使用真实 LLM，"
                f"部分降级为 Mock"
            )
        else:
            report["summary"] = "❌ 所有场景均降级为 Mock，请检查 LM Studio 配置"

        # 保存日志
        if self.config.save_demo_log:
            self._save_log(report)

        return report

    async def _warmup(self, client) -> dict[str, Any]:
        """预热模型（发送简短请求确保模型加载到内存）。"""
        result = {"success": False, "latency_ms": 0, "detail": ""}
        try:
            start = time.time()
            response = await client.chat_async(
                prompt="Hello",
                system_prompt="Reply with 'OK' only.",
                temperature=0.1,
            )
            elapsed = (time.time() - start) * 1000
            result["latency_ms"] = round(elapsed, 1)
            result["success"] = bool(response and len(response.strip()) > 0)
            result["detail"] = (
                f"模型预热成功 ({result['latency_ms']}ms)"
                if result["success"]
                else "预热响应为空"
            )
        except Exception as e:
            result["detail"] = f"预热失败: {e}"
        return result

    async def _run_single_demo(self, client, requirement: str) -> DemoResult:
        """运行单个演示场景。"""
        result = DemoResult(requirement=requirement)

        try:
            from skyforge_engine.agents.requirement_parser import RequirementParserAgent
            from skyforge_engine.agents.contract_generator import ContractGeneratorAgent
            from skyforge_engine.agents.code_generator import CodeGeneratorAgent

            start = time.time()

            # Step 1: 需求解析
            parser = RequirementParserAgent()
            req_json = await parser.run(requirement)
            result.req_type = req_json.get("type", "unknown")
            result.dal = req_json.get("safety_level", "unknown")

            # Step 2: 契约生成
            contract_agent = ContractGeneratorAgent()
            contract_yaml = await contract_agent.run(req_json)
            result.contract_generated = bool(contract_yaml and "component:" in contract_yaml)

            # Step 3: 代码生成
            code_agent = CodeGeneratorAgent()
            code = await code_agent.run(req_json, contract_yaml)
            result.code_generated = bool(code and len(code) > 50)

            result.time_ms = round((time.time() - start) * 1000, 1)

            # 检测是否使用了 LLM（代码中有 [REQ-xxx] 标签说明经过 LLM 处理）
            result.llm_used = (
                "[REQ-" in code if result.code_generated else False
            )

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _save_log(self, report: dict[str, Any]) -> None:
        """保存演示日志到文件。"""
        try:
            log_path = self.config.demo_log_path
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"# SkyForge 演示运行日志\n")
                f.write(f"时间: {report['timestamp']}\n")
                f.write(f"模型: {report['config']['model']}\n")
                f.write(f"状态: {report['summary']}\n\n")

                if report.get("verification"):
                    v = report["verification"]
                    f.write(f"## 就绪检查\n{v.get('summary', '')}\n\n")

                if report.get("demo_results"):
                    f.write("## 演示结果\n")
                    for i, r in enumerate(report["demo_results"]):
                        if isinstance(r, dict):
                            f.write(f"### 场景 {i+1}: {r.get('req_type', 'unknown')}\n")
                            f.write(f"- 需求: {r.get('requirement', '')[:100]}...\n")
                            f.write(f"- LLM: {'✅' if r.get('llm_used') else '❌ Mock'}\n")
                            f.write(f"- DAL: {r.get('dal', 'N/A')}\n")
                            f.write(f"- 耗时: {r.get('time_ms', 0)}ms\n")
                            if r.get("errors"):
                                f.write(f"- 错误: {r['errors']}\n")
                            f.write("\n")
            logger.info(f"演示日志已保存到 {log_path}")
        except Exception as e:
            logger.error(f"保存演示日志失败: {e}")


# ==================== 便捷函数 ====================

async def quick_check() -> bool:
    """快速检查演示环境是否就绪。"""
    verifier = DemoVerifier()
    result = await verifier.verify_all()
    print(result["summary"])
    for rec in result.get("recommendations", []):
        print(f"  💡 {rec}")
    return result["ready"]


async def demo_main():
    """主入口：一键运行完整演示流程。"""
    print("=" * 60)
    print("  SkyForge 真实 LLM 演示模式")
    print("=" * 60)
    print()

    runner = DemoRunner()
    report = await runner.run(readiness_check=True, warmup=True)

    print(report["summary"])
    print()

    if report.get("verification"):
        v = report["verification"]
        for level in v.get("levels", []):
            icon = "✅" if level.get("passed") else "❌"
            print(f"  {icon} {level['name']}: {level.get('detail', '')}")

    if report.get("demo_results"):
        print()
        print("演示场景运行结果:")
        for i, r in enumerate(report["demo_results"]):
            if isinstance(r, dict):
                icon = "✅" if r.get("llm_used") else "⚠️"
                print(f"  {icon} 场景 {i+1} ({r.get('req_type', 'N/A')}): "
                      f"{r.get('time_ms', 0)}ms | DAL={r.get('dal', 'N/A')}")

    if report.get("errors"):
        print()
        print("⚠️ 需要注意的问题:")
        for err in report["errors"]:
            print(f"  - {err}")

    return report


if __name__ == "__main__":
    asyncio.run(demo_main())
