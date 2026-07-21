"""需求解析 Agent：将自然语言机载软件需求解析为结构化 JSON，
并强制打 [REQ-xxx] 追溯 Tag。
"""

import re
from typing import Any

try:
    from skyforge_llm.parser import safe_parse_llm_json
except ImportError:
    def safe_parse_llm_json(x):
        return {} 
# LLM 客户端 — 通过 L0 provider 注入（L3 启动时注册自己的单例，
# 引擎独立运行时回退到 L1 skyforge_llm.client）。详见 llm_provider.py。
from skyforge_engine.config import settings as settings  # noqa: F401
from skyforge_engine.llm_provider import get_llm_client as get_lmstudio_client
from skyforge_engine.utils.log_util import logger

# 需求类型关键词映射表（机载软件典型模块）
_TYPE_KEYWORDS: dict[str, list[str]] = {
    "filter": [
        "滤波",
        "低通",
        "高通",
        "带通",
        "filter",
        "low-pass",
        "high-pass",
        "截止频率",
    ],
    "control": ["控制", "pid", "control", "姿态", "altitude control", "伺服", "舵机"],
    "comms": ["通信", "通讯", "总线", "bus", "arinc", "can", "rs422", "数据链"],
    "hmi": ["显示", "hud", "人机界面", "仪表", "告警", "display", "warning", "alert"],
    "sensor_fusion": [
        "卡尔曼",
        "imu",
        "传感器融合",
        "姿态解算",
        "kalman",
        "sensor fusion",
        "attitude estimation",
    ],
    "mission_planning": [
        "航点",
        "任务",
        "航线",
        "调度",
        "飞行计划",
        "waypoint",
        "mission",
        "route",
        "schedule",
        "flight plan",
    ],
    "navigation": [
        "导航",
        "惯导",
        "gps",
        "定位",
        "navigation",
        "inertial",
        "positioning",
    ],
    "power": [
        "电源",
        "电压",
        "电池",
        "能源管理",
        "power",
        "voltage",
        "battery",
        "energy management",
    ],
    "redundancy": [
        "余度",
        "冗余",
        "redundancy",
        "双通道",
        "voting",
        "表决",
    ],
}

# System Prompt（参考设计文档 1.6 节，四段式骨架：角色/工具/输出/禁忌）
_SYSTEM_PROMPT = """你是 DO-178C 适航需求工程师，专职将自然语言机载软件需求
解析为结构化 JSON，识别 DAL 等级（DAL-A~E）与功能/非功能需求。
你必须以适航视角工作，确保需求可追溯、可验证。

## 可用工具
- parse_requirement(text) 提取功能需求与参数（截止频率/采样率/量程等）
- extract_safety_level(text) 识别 DAL 等级
  （A= catastrophic / B= hazardous / C= major / D= minor / E= no-effect）

## 输出格式（严格 JSON，禁止前后缀文字）
{
  "type": "filter",
  "module_name": "lowpass_filter_10hz",
  "safety_level": "DAL-B",
  "params": {"cutoff_hz": 10.0, "sample_rate_hz": 100.0},
  "constraints": ["WCET <= 1ms", "禁止动态内存（MISRA Rule-21.3）"]
}

## 禁忌
1. 禁止臆造 DAL 等级，必须依据 DO-178C 危害等级表推断
2. 禁止遗漏非功能需求（WCET/内存/采样率等约束）
3. 禁止输出 JSON 以外的任何文字（含解释、Markdown 包裹）
4. 禁止使用动态内存相关字段
5. type 字段必须为 filter/control/comms/hmi/sensor_fusion/mission_planning/navigation/power 之一"""


class RequirementParserAgent:
    """需求解析 Agent。

    输入：自然语言需求字符串。
    输出：结构化需求 JSON（dict），强制打 Tag `[REQ-xxx]` 供 Patch 3 追溯链使用。

    由 ``SKYFORGE_LLM_MODE`` 决定运行方式：
    - ``mock``：直接调用正则 Mock 实现。
    - ``api`` / ``local``：调用真实 LLM，异常直接抛出，禁止静默降级。
    """

    def __init__(self, strategy=None) -> None:
        # 进程内自增计数器，保证单次 pipeline 内 REQ-xxx 唯一
        self._counter = 0
        if strategy is None:
            from skyforge_engine.core.strategies import get_strategy_for_mode
            strategy = get_strategy_for_mode()
        self.strategy = strategy

    async def run(self, requirement: str) -> dict[str, Any]:
        """解析自然语言需求，返回结构化需求字典。

        Args:
            requirement: 自然语言需求字符串。

        Returns:
            结构化需求字典，至少包含 req_id / desc / type 字段。
        """
        logger.info("RequirementParserAgent:开始:解析需求")
        self._counter += 1
        req_id = f"REQ-{self._counter:03d}"

        result = await self.strategy.run(
            requirement, req_id=req_id, input_type="requirement"
        )
        if not result.success:
            if len(result.warnings) == 1:
                raise RuntimeError(result.warnings[0])
            raise RuntimeError(
                f"RequirementParserAgent 执行失败: {result.warnings}"
            )
        logger.info(
            f"RequirementParserAgent:完成:生成 {req_id} "
            f"(type={result.output.get('type')})"
        )
        return result.output

    async def _llm_run(self, requirement: str, req_id: str) -> dict[str, Any]:
        """LLM 实现：调用 LLM 解析需求。"""
        client = get_lmstudio_client()
        response = await client.chat_async(
            prompt=f"请解析以下机载软件需求：\n{requirement}",
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.3,
        )
        if not response:
            raise RuntimeError("RequirementParserAgent:LLM 调用返回空响应")
        result = self._parse_llm_response(response, requirement, req_id)
        if result is None:
            raise RuntimeError("RequirementParserAgent:LLM 输出解析失败")
        result["req_id"] = req_id
        result["desc"] = requirement.strip()
        return result

    def _mock_run(self, requirement: str, req_id: str) -> dict[str, Any]:
        """Mock 实现：正则提取关键句与参数。"""
        req_type = self._detect_type(requirement)
        params = self._extract_params(requirement)
        module_name = self._derive_module_name(req_type, params)

        return {
            "req_id": req_id,
            "desc": requirement.strip(),
            "type": req_type,
            "module_name": module_name,
            "safety_level": "DAL-B",
            "params": params,
            "constraints": self._derive_constraints(req_type, params),
        }

    def _parse_llm_response(
        self, response: str, requirement: str, req_id: str
    ) -> dict[str, Any] | None:
        """解析 LLM 输出为结构化需求字典（失败返回 None）。"""
        try:
            parsed = safe_parse_llm_json(response)
        except ValueError:
            logger.warning("RequirementParserAgent:LLM 输出解析失败")
            return None

        # 校验并补全必要字段
        req_type = parsed.get("type", "generic")
        if req_type not in (
            "filter",
            "control",
            "comms",
            "hmi",
            "sensor_fusion",
            "mission_planning",
            "navigation",
            "power",
            "redundancy",
            "generic",
        ):
            req_type = self._detect_type(requirement)

        params = parsed.get("params", {})
        if not isinstance(params, dict):
            params = self._extract_params(requirement)
        else:
            # 用正则补充 LLM 可能遗漏的数值参数
            regex_params = self._extract_params(requirement)
            for k, v in regex_params.items():
                if k not in params:
                    params[k] = v

        module_name = parsed.get("module_name")
        if not module_name:
            module_name = self._derive_module_name(req_type, params)

        constraints = parsed.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = self._derive_constraints(req_type, params)
        else:
            regex_cons = self._derive_constraints(req_type, params)
            for c in regex_cons:
                if c not in constraints:
                    constraints.append(c)

        safety_level = parsed.get("safety_level", "DAL-B")

        return {
            "req_id": req_id,
            "desc": requirement.strip(),
            "type": req_type,
            "module_name": module_name,
            "safety_level": safety_level,
            "params": params,
            "constraints": constraints,
        }

    def _detect_type(self, text: str) -> str:
        """根据关键词识别需求类型。"""
        lower = text.lower()
        for rtype, keywords in _TYPE_KEYWORDS.items():
            if any(kw.lower() in lower for kw in keywords):
                return rtype
        # 默认归为 generic（通用类型，Task 8 会完善模板）
        return "generic"

    def _extract_params(self, text: str) -> dict[str, Any]:
        """正则提取数值参数（截止频率/采样率等）。"""
        params: dict[str, Any] = {}
        # 截止频率：如 "截止频率10Hz" / "截止频率 10 Hz" / "cutoff 10Hz"
        m = re.search(
            r"(?:截止频率|cutoff)[^\d]*(\d+(?:\.\d+)?)\s*hz?", text, re.IGNORECASE
        )
        if m:
            params["cutoff_hz"] = float(m.group(1))
        # 采样率：如 "采样率100Hz"
        m = re.search(
            r"(?:采样率|sample\s*rate)[^\d]*(\d+(?:\.\d+)?)\s*hz?", text, re.IGNORECASE
        )
        if m:
            params["sample_rate_hz"] = float(m.group(1))
        else:
            params["sample_rate_hz"] = 100.0  # 机载默认 100Hz
        # 量程：如 "范围0~20000m" / "range [0, 20000]"
        m = re.search(
            r"(?:范围|range)\s*\(?\[?\s*(\d+(?:\.\d+)?)\s*[~\-到至,]\s*(\d+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if m:
            params["range_min"] = float(m.group(1))
            params["range_max"] = float(m.group(2))
        # 电压：如 "电压28V" / "voltage 28V"
        m = re.search(
            r"(?:电压|voltage)[^\d]*(\d+(?:\.\d+)?)\s*v?", text, re.IGNORECASE
        )
        if m:
            params["voltage_v"] = float(m.group(1))
        # 电池容量：如 "电池容量10Ah" / "battery capacity 10Ah"
        m = re.search(
            r"(?:电池容量|battery\s*capacity)[^\d]*(\d+(?:\.\d+)?)\s*ah?",
            text,
            re.IGNORECASE,
        )
        if m:
            params["battery_capacity_ah"] = float(m.group(1))
        # 航点数量：如 "航点10个" / "waypoints 10"
        m = re.search(
            r"(?:航点|waypoint)[^\d]*(\d+)", text, re.IGNORECASE
        )
        if m:
            params["waypoint_count"] = int(m.group(1))
        # 定位精度：如 "定位精度1m" / "positioning accuracy 1m"
        m = re.search(
            r"(?:定位精度|positioning\s*accuracy)[^\d]*(\d+(?:\.\d+)?)\s*m?",
            text,
            re.IGNORECASE,
        )
        if m:
            params["positioning_accuracy_m"] = float(m.group(1))
        return params

    def _derive_module_name(self, req_type: str, params: dict[str, Any]) -> str:
        """根据类型推导模块名（用作 .contract 的 component 字段）。"""
        if req_type == "filter":
            cutoff = params.get("cutoff_hz")
            if cutoff is not None:
                return f"lowpass_filter_{int(cutoff)}hz"
            return "signal_filter"
        if req_type == "control":
            return "control_law"
        if req_type == "comms":
            return "comms_handler"
        if req_type == "hmi":
            return "hmi_display"
        if req_type == "sensor_fusion":
            return "sensor_fusion_module"
        if req_type == "mission_planning":
            return "mission_planner"
        if req_type == "navigation":
            return "navigation_module"
        if req_type == "power":
            return "power_management"
        if req_type == "redundancy":
            return "redundancy_manager"
        return "generic_module"

    def _derive_constraints(self, req_type: str, params: dict[str, Any]) -> list[str]:
        """推导非功能约束。"""
        cons = ["WCET <= 1ms", "禁止动态内存（MISRA Rule-21.3）"]
        if req_type == "filter":
            cons.append(f"采样率固定 {params.get('sample_rate_hz', 100.0)}Hz")
        elif req_type == "hmi":
            cons.append("显示刷新率 >= 30Hz")
            cons.append("告警响应时间 <= 100ms")
        elif req_type == "sensor_fusion":
            cons.append("融合算法延迟 <= 5ms")
            cons.append("姿态解算精度 <= 0.1度")
        elif req_type == "mission_planning":
            cons.append("航点规划时间 <= 1s")
            cons.append("支持最大航点数 >= 100")
        elif req_type == "navigation":
            cons.append("定位更新率 >= 10Hz")
            cons.append("惯导漂移 <= 1nm/h")
        elif req_type == "power":
            cons.append("电源效率 >= 90%")
            cons.append("电池管理精度 <= 5%")
        elif req_type == "redundancy":
            cons.append("双通道表决延迟 <= 5ms")
            cons.append("通道间同步偏差 <= 1ms")
            cons.append("故障切换时间 <= 50ms")
        return cons
