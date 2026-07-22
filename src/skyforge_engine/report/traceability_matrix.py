"""追溯矩阵构建器：从 pipeline_result 提取四层追溯链
HLR ([REQ-xxx]) → LLR ([LLR-xxx]) → CODE → TST ([TST-xxx])。

V3.2 增强:
  - 新增 HLR↔LLR 追溯层（从 llr_result 提取）
  - 支持反向追溯：代码 → LLR → HLR
  - TraceEntry 新增 llr_id / llr_desc 字段
  - build_matrix 新增 include_llr 参数

数据来源：
- HLR：pipeline_result["structured_reqs"]（列表）
  或 pipeline_result["requirement"]（单条 dict）
- LLR：pipeline_result["llr_result"]["llrs"]（V3.2 新增）
- 契约：pipeline_result["contract"]（YAML 字符串），
  从 traceability 字段反查 REQ ↔ CON
- 代码：pipeline_result["final_code"] 或 ["code"]，
  提取含 [REQ-xxx] [LLR-xxx] [MISRA-Rule-x.x] 的注释行号
- 测试：pipeline_result["contract_check_result"] + pipeline_result["simulation_result"]
  合成 [TST-xxx]：每个契约检查项 + 仿真运行各算一个测试点
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

import yaml

from skyforge_engine.utils.log_util import logger

# Tag 正则：[REQ-xxx] / [LLR-xxx] / [CON-xxx] / [MISRA-Rule-x.x]
_REQ_TAG_RE = re.compile(r"\[(REQ-\d+)\]")
_LLR_TAG_RE = re.compile(r"\[(LLR-\d+)\]")
_CON_TAG_RE = re.compile(r"\[(CON-\d+)\]")
_MISRA_TAG_RE = re.compile(r"\[MISRA-Rule-([\d.]+)\]")


@dataclass
class TraceEntry:
    """追溯矩阵单行：HLR → LLR → Contract → Code → Test（四层追溯）。

    Attributes:
        req_id: HLR Tag（如 REQ-001）。
        req_desc: HLR 描述（自然语言）。
        llr_id: LLR Tag（如 LLR-001），V3.2 新增。
        llr_desc: LLR 描述，V3.2 新增。
        contract_id: 契约 Tag（如 CON-001）。
        code_line: 代码含 Tag 注释的行号（1-based；0 表示无匹配）。
        code_snippet: 该行代码文本（去前后空白）。
        test_id: 测试 Tag（如 TST-001）。
        test_result: 测试结果（"通过" / "失败" / ""）。
    """

    req_id: str = ""
    req_desc: str = ""
    llr_id: str = ""
    llr_desc: str = ""
    contract_id: str = ""
    code_line: int = 0
    code_snippet: str = ""
    test_id: str = ""
    test_result: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


@dataclass
class ReverseTraceEntry:
    """反向追溯条目：从代码/测试回溯到 LLR/HLR。

    Attributes:
        source_type: 来源类型（"code" / "test"）。
        source_id: 来源标识（行号 / TST-xxx）。
        llr_id: 对应的 LLR Tag。
        req_id: 对应的 HLR Tag。
    """

    source_type: str = ""
    source_id: str = ""
    llr_id: str = ""
    req_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


def build_matrix(
    pipeline_result: dict[str, Any],
    include_llr: bool = True,
) -> list[TraceEntry]:
    """构建四层追溯矩阵：HLR → LLR → Code → Test。

    Args:
        pipeline_result: 全流程结果字典。
        include_llr: 是否包含 LLR 层（V3.2 新增，默认 True）。

    Returns:
        list[TraceEntry]：追溯表行列表，每行对应一个 [REQ-xxx]。
    """
    requirements = _extract_requirements(pipeline_result)
    req_to_con = _extract_contract_mapping(pipeline_result, requirements)
    req_to_code = _extract_code_trace_lines(pipeline_result)
    req_to_tests = _extract_test_mapping(pipeline_result, req_to_con)

    # V3.2: 提取 LLR 映射
    req_to_llrs: dict[str, list[dict[str, Any]]] = {}
    if include_llr:
        req_to_llrs = _extract_llr_mapping(pipeline_result, requirements)

    entries: list[TraceEntry] = []
    for req in requirements:
        req_id = req.get("req_id", "")
        req_desc = req.get("desc", "")

        # V3.2: 取该 REQ 对应的第一条 LLR
        llr_list = req_to_llrs.get(req_id, [])
        if llr_list:
            first_llr = llr_list[0]
            llr_id = first_llr.get("llr_id", "")
            llr_desc = first_llr.get("description", "")
        else:
            llr_id, llr_desc = "", ""

        # 取该 REQ 对应的第一条代码行
        code_lines = req_to_code.get(req_id, [])
        if code_lines:
            code_line, code_snippet = code_lines[0]
        else:
            code_line, code_snippet = 0, ""

        # 取该 REQ 对应的第一个测试点
        tests = req_to_tests.get(req_id, [])
        if tests:
            test_id, test_result = tests[0]
        else:
            test_id, test_result = "", ""

        entries.append(
            TraceEntry(
                req_id=req_id,
                req_desc=req_desc,
                llr_id=llr_id,
                llr_desc=llr_desc,
                contract_id=req_to_con.get(req_id, ""),
                code_line=code_line,
                code_snippet=code_snippet,
                test_id=test_id,
                test_result=test_result,
            )
        )

    logger.info(
        f"TraceabilityMatrix:构建完成: {len(entries)} 行 "
        f"（含 LLR={any(e.llr_id for e in entries)}）"
    )
    return entries


def build_reverse_matrix(
    pipeline_result: dict[str, Any],
) -> list[ReverseTraceEntry]:
    """构建反向追溯矩阵：代码/测试 → LLR → HLR。

    用于验证"每一行代码/每一个测试都可追溯到需求"。

    Args:
        pipeline_result: 全流程结果字典。

    Returns:
        list[ReverseTraceEntry]：反向追溯条目列表。
    """
    # 先构建正向矩阵做索引
    forward = build_matrix(pipeline_result, include_llr=True)
    code_to_llr: dict[int, str] = {}  # line_no → llr_id
    test_to_llr: dict[str, str] = {}  # test_id → llr_id
    llr_to_req: dict[str, str] = {}  # llr_id → req_id

    for entry in forward:
        if entry.llr_id and entry.req_id:
            llr_to_req[entry.llr_id] = entry.req_id
        if entry.code_line and entry.llr_id:
            code_to_llr[entry.code_line] = entry.llr_id
        if entry.test_id and entry.llr_id:
            test_to_llr[entry.test_id] = entry.llr_id

    # 生成反向条目
    entries: list[ReverseTraceEntry] = []

    for line_no, llr_id in code_to_llr.items():
        entries.append(ReverseTraceEntry(
            source_type="code",
            source_id=str(line_no),
            llr_id=llr_id,
            req_id=llr_to_req.get(llr_id, ""),
        ))

    for test_id, llr_id in test_to_llr.items():
        entries.append(ReverseTraceEntry(
            source_type="test",
            source_id=test_id,
            llr_id=llr_id,
            req_id=llr_to_req.get(llr_id, ""),
        ))

    logger.info(
        f"TraceabilityMatrix:反向追溯完成: {len(entries)} 条 "
        f"（code={len(code_to_llr)} test={len(test_to_llr)}）"
    )
    return entries


def _extract_llr_mapping(
    pipeline_result: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """从 pipeline_result 提取 LLR 映射：REQ → LLR 列表。

    Args:
        pipeline_result: 全流程结果字典。
        requirements: HLR 列表。

    Returns:
        {req_id: [{llr_id, description, category}, ...]}。
    """
    result: dict[str, list[dict[str, Any]]] = {}

    llr_result = pipeline_result.get("llr_result")
    if not isinstance(llr_result, dict):
        requirement = pipeline_result.get("requirement", {})
        if isinstance(requirement, dict):
            llr_result = requirement.get("llr_result")
    if not isinstance(llr_result, dict):
        return result

    llrs = llr_result.get("llrs", []) or []
    if not isinstance(llrs, list):
        return result

    for llr in llrs:
        if not isinstance(llr, dict):
            continue
        hlr_ref = llr.get("hlr_ref", "")
        if hlr_ref:
            entry = {
                "llr_id": llr.get("llr_id", ""),
                "description": llr.get("description", ""),
                "category": llr.get("category", ""),
            }
            result.setdefault(hlr_ref, []).append(entry)

    # 为没有 LLR 的 REQ 生成空列表
    for req in requirements:
        req_id = req.get("req_id", "")
        if req_id and req_id not in result:
            result[req_id] = []

    return result


def _extract_requirements(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """从 pipeline_result 提取结构化需求列表。

    优先取 structured_reqs（列表），否则将 requirement（单条 dict）包成单元素列表。
    """
    structured = pipeline_result.get("structured_reqs")
    if isinstance(structured, list):
        return [r for r in structured if isinstance(r, dict)]
    requirement = pipeline_result.get("requirement")
    if isinstance(requirement, dict):
        return [requirement]
    return []


def _extract_contract_mapping(
    pipeline_result: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> dict[str, str]:
    """从契约 YAML 的 traceability 字段反查 REQ → CON 映射。

    契约模板格式：
        traceability: [REQ-001]

    若 YAML 缺失 traceability，则按出现顺序将 CON-001/CON-002/... 分配给 requirements。
    若契约 YAML 含 contract_id 字段，则使用之；否则默认 CON-001。
    """
    contract_yaml: str = pipeline_result.get("contract", "") or ""
    req_to_con: dict[str, str] = {}

    if contract_yaml.strip():
        try:
            contract = yaml.safe_load(contract_yaml) or {}
        except yaml.YAMLError as e:
            logger.warning(f"TraceabilityMatrix:契约 YAML 解析失败: {e}")
            contract = {}

        # 契约 ID：优先取 contract_id，否则默认 CON-001
        con_id = (
            str(contract.get("contract_id", "CON-001"))
            if isinstance(contract, dict)
            else "CON-001"
        )

        # traceability 可能是字符串 "REQ-001" 或列表 ["REQ-001", "REQ-002"]
        traceability = (
            contract.get("traceability", []) if isinstance(contract, dict) else []
        )
        if isinstance(traceability, str):
            trace_list = [traceability]
        else:
            trace_list = list(traceability or [])

        # 解析出 REQ-xxx Tag
        req_tags: list[str] = []
        for item in trace_list:
            for m in _REQ_TAG_RE.finditer(str(item)):
                req_tags.append(m.group(1))

        if req_tags:
            # 一对一映射（若多个 REQ，按顺序使用同一个 con_id）
            for tag in req_tags:
                req_to_con[tag] = con_id
        else:
            # 兜底：按 requirements 顺序分配 CON-001/CON-002/...
            for i, req in enumerate(requirements, start=1):
                req_to_con[req.get("req_id", "")] = f"CON-{i:03d}"

    # 兜底：未在契约 YAML 中找到的 REQ，按顺序补 CON-xxx
    next_con_idx = 1
    for req in requirements:
        rid = req.get("req_id", "")
        if rid and rid not in req_to_con:
            req_to_con[rid] = f"CON-{next_con_idx:03d}"
            next_con_idx += 1

    return req_to_con


def _extract_code_trace_lines(
    pipeline_result: dict[str, Any],
) -> dict[str, list[tuple[int, str]]]:
    """从 C 代码中提取含 [REQ-xxx] 的注释行号。

    Returns:
        {req_id: [(line_no, snippet), ...]}，line_no 为 1-based。
    """
    code: str = pipeline_result.get("final_code") or pipeline_result.get("code") or ""
    result: dict[str, list[tuple[int, str]]] = {}
    if not code:
        return result

    for idx, line in enumerate(code.splitlines(), start=1):
        # 跳过空行
        stripped = line.strip()
        if not stripped:
            continue
        # 匹配 [REQ-xxx]
        for m in _REQ_TAG_RE.finditer(stripped):
            req_id = m.group(1)
            result.setdefault(req_id, []).append((idx, stripped))

    return result


def _extract_test_mapping(
    pipeline_result: dict[str, Any],
    req_to_con: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    """从契约校验结果 + 仿真结果合成 [TST-xxx] 测试点。

    规则：
      - contract_check_result 的每个检查项（pre/post/inv/fh）算一个 TST-xxx
      - simulation_result 算一个 TST-xxx（代表数字孪生仿真整体测试）
      - 通过 REQ ← CON 反查映射回 [REQ-xxx]

    Returns:
        {req_id: [(test_id, test_result), ...]}，test_result 为 "通过" / "失败"。
    """
    con_to_req: dict[str, str] = {con: req for req, con in req_to_con.items()}
    result: dict[str, list[tuple[str, str]]] = {}

    test_counter = 0

    def _add_test(con_id: str, passed: bool) -> None:
        nonlocal test_counter
        test_counter += 1
        test_id = f"TST-{test_counter:03d}"
        test_result = "通过" if passed else "失败"
        req_id = con_to_req.get(con_id, "")
        if req_id:
            result.setdefault(req_id, []).append((test_id, test_result))
        else:
            # 找不到对应 REQ，归到首条 REQ（若存在）
            for rid in req_to_con:
                result.setdefault(rid, []).append((test_id, test_result))
                break

    # 1) 契约校验项 → TST
    ccr = pipeline_result.get("contract_check_result")
    if isinstance(ccr, dict):
        # 提取契约 ID（默认 CON-001）
        con_id = "CON-001"
        # 从 preconditions[0].id 反推 CON-xxx（形如 CON-001-PRE-000）
        for section in (
            "preconditions",
            "postconditions",
            "invariants",
            "fault_handling",
        ):
            items = ccr.get(section, []) or []
            for item in items:
                if isinstance(item, dict):
                    item_id = str(item.get("id", ""))
                    m = _CON_TAG_RE.match(item_id)
                    if m:
                        con_id = m.group(1)
                        break
            if con_id != "CON-001":
                break

        for section in (
            "preconditions",
            "postconditions",
            "invariants",
            "fault_handling",
        ):
            items = ccr.get(section, []) or []
            for item in items:
                if isinstance(item, dict):
                    passed = bool(item.get("passed", False))
                    _add_test(con_id, passed)

    # 2) 仿真结果 → TST（整体算一个测试点）
    sim = pipeline_result.get("simulation_result")
    if isinstance(sim, dict):
        passed = bool(sim.get("passed", False))
        # 仿真对应的契约 ID 默认 CON-001（与 pipeline.py run_full_pipeline 调用一致）
        _add_test("CON-001", passed)

    return result


# ---- V0.4 P7: ReqIF 标准化需求追溯导出 ----

def export_to_reqif(matrices: list[dict[str, Any]], output_path: str = "traceability.reqif") -> str:
    """将追溯矩阵导出为 ReqIF 格式，可导入 DOORS/StrictDoc。"""
    import xml.etree.ElementTree as ET

    root = ET.Element("REQ-IF", attrib={
        "xmlns": "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd",
    })
    header = ET.SubElement(root, "THE-HEADER")
    ET.SubElement(header, "REQ-IF-COMMENT").text = "Generated by SkyForge v0.4"

    core = ET.SubElement(root, "CORE-CONTENT")
    specs = ET.SubElement(core, "SPEC-OBJECTS")

    for entry in matrices:
        spec = ET.SubElement(specs, "SPEC-OBJECT", IDENTIFIER=entry.get("req_id", ""))
        values = ET.SubElement(spec, "VALUES")
        for label, key in [("HLR", "req_id"), ("LLR", "llr_id"), ("Contract", "contract_id"),
                           ("Code", "code_snippet"), ("Test", "test_id")]:
            val = ET.SubElement(values, "ATTRIBUTE-VALUE-STRING", LABEL=label)
            val.set("THE-VALUE", str(entry.get(key, "")))

    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    logger.info(f"TraceabilityMatrix:ReqIF exported → {output_path} ({len(matrices)} entries)")
    return output_path


def export_to_pdf(html_report_path: str, output_path: str = "report.pdf") -> str:
    """将 HTML 合规报告转换为 PDF。"""
    try:
        from weasyprint import HTML
        HTML(html_report_path).write_pdf(output_path)
        logger.info(f"ReportGenerator:PDF exported → {output_path}")
        return output_path
    except ImportError:
        logger.warning("WeasyPrint 不可用，跳过 PDF 导出")
        import shutil
        shutil.copy(html_report_path, output_path)
        return output_path
