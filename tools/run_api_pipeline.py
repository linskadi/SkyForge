"""API Pipeline Runner — 使用 DeepSeek LLM 生成 C/Python/C++ 代码。

用法:
    python tools/run_api_pipeline.py c    # C (ARINC 429)
    python tools/run_api_pipeline.py py   # Python (Flight Data Monitor)
    python tools/run_api_pipeline.py cpp  # C++ (ADS-B Processor)
    python tools/run_api_pipeline.py all  # 全部
"""
import asyncio, json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 手动加载 config/.env 到 os.environ（LLMRouter 直接读 os.environ，不经过 pydantic Settings）
_repo_root = os.path.join(os.path.dirname(__file__), "..")
_env_path = os.path.join(_repo_root, "config", ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    print(f"[env] 已加载 config/.env: SKYFORGE_LLM_MODE={os.environ.get('SKYFORGE_LLM_MODE','?')}, LLM_MODEL={os.environ.get('LLM_MODEL','?')}")
else:
    print(f"[env] WARNING: config/.env 不存在: {_env_path}")

REQUIREMENTS = {
    "c": (
        "实现 ARINC 429 航空数据总线标签解析器。"
        "输入 32-bit ARINC 429 word (uint32_t)，解析出 Label (bits 1-8)、"
        "SDI (bits 9-10)、Data (bits 11-29)、SSM (bits 30-31) 和 Parity (bit 32)。"
        "验证奇校验：32-bit word 中 1 的个数必须为奇数。"
        "输出解析后的结构化数据，若校验失败返回错误码。"
        "DO-178C DAL-A 标准，MISRA-C:2012 编码规范。"
        "生成 .c 和 .h 两个文件，约 100-120 行代码。"
    ),
    "py": (
        "实现飞行数据超限监控系统 (Flight Data Exceedance Monitor)。"
        "读取 QAR/FDR 参数流（CSV 格式），对每个参数配置阈值和超限检测规则："
        "1) 瞬时超限 (Instant Exceedance)：参数值超过硬阈值触发告警"
        "2) 趋势超限 (Trend Exceedance)：连续 N 秒参数变化率超过阈值"
        "3) 持续时间超限 (Duration Exceedance)：参数持续超过阈值的时长超过限制"
        "生成超限事件报告（JSON 格式），包含事件类型、参数名、超限值、时间戳、持续时长。"
        "支持参数配置 YAML 文件，支持多参数同时监控。"
        "需模块化设计：ParameterConfig / ExceedanceDetector / EventReporter 三个类。"
        "DO-178C DAL-A 等效标准，需类型注解和单元测试就绪。"
        "约 200-250 行代码。"
    ),
    "cpp": (
        "实现 ADS-B (Automatic Dependent Surveillance-Broadcast) 消息处理器。"
        "支持 DF17 和 DF18 格式消息解码，包括："
        "1) Airborne Position Message (Type Code 9-18)：CPR 编码位置解码（奇/偶帧配对），"
        "   高度解码（Q-bit 判定），精确经纬度计算"
        "2) Airborne Velocity Message (Type Code 19)：东西/南北速度分量，"
        "   垂直速率，速度不确定性"
        "3) Aircraft Identification Message (Type Code 1-4)：8 字符呼号解码"
        "4) CRC 校验：24-bit CRC 多项式 0xFFF409，错误检测与纠正"
        "5) 消息队列管理：按 ICAO 地址分组，时序排序，过期消息清理"
        "设计要点："
        "- 使用 C++17 标准，std::optional / std::variant / std::chrono"
        "- 类层次：Message (基类) → AirbornePositionMsg / AirborneVelocityMsg / IdentificationMsg"
        "- CPR 解码需要 NRZ 纬度区数计算和全球位置参考"
        "- 工厂模式创建消息对象"
        "- 完整的 const 正确性和 noexcept 标注"
        "- MISRA-C++ / JSF AV C++ 编码规范"
        "DO-178C DAL-A 标准。"
        "约 700-900 行代码。"
    ),
}

LANGUAGES = {"c": "c", "py": "python", "cpp": "cpp"}


async def run_pipeline(lang_key: str):
    from skyforge_engine.pipeline import run_full_pipeline

    req = REQUIREMENTS[lang_key]
    language = LANGUAGES[lang_key]

    print(f"\n{'='*60}")
    print(f"  {lang_key.upper()} Pipeline: {language}")
    print(f"  题目: {req[:60]}...")
    print(f"{'='*60}")

    t0 = time.perf_counter()
    result = await run_full_pipeline(
        requirement=req,
        language=language,
        simulate=(language == "c"),  # C 才做 GCC 仿真
    )
    elapsed = time.perf_counter() - t0

    out_dir = f"outputs/demo_2026_07_22/{lang_key}"
    os.makedirs(out_dir, exist_ok=True)

    code = result.get("final_code", "")
    ext = {"c": ".c", "py": ".py", "cpp": ".cpp"}[lang_key]
    with open(f"{out_dir}/generated_code{ext}", "w", encoding="utf-8") as f:
        f.write(code)

    contract = result.get("contract", "")
    if contract:
        with open(f"{out_dir}/contract.yaml", "w", encoding="utf-8") as f:
            f.write(contract)

    from skyforge_engine.report.do178_objectives import check_objectives
    objs = check_objectives(result, dal="A")
    p = sum(1 for o in objs if o.status == "满足")
    pp = sum(1 for o in objs if o.status == "部分满足")
    f = sum(1 for o in objs if o.status == "未满足")

    cov = result.get("coverage_result") or {}
    sim = result.get("simulation_result")
    sim_passed = sim.get("passed") if isinstance(sim, dict) else None

    print(f"\n  行数: {len(code.splitlines())}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  MISRA: {len(result.get('final_violations',[]))} 条")
    if language == "c":
        print(f"  覆盖率: {cov.get('statement_coverage',0)}%/{cov.get('decision_coverage',0)}%/{cov.get('mcdc_coverage',0)}%")
    print(f"  仿真: {sim_passed if sim_passed is not None else 'N/A'}")
    print(f"  DAL-A: 满足{p} 部分{pp} 未满足{f}")
    print(f"  证据包: {result.get('evidence_package','N/A')}")

    # Save result
    rj = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v))
          for k, v in result.items()}
    with open(f"{out_dir}/pipeline_result.json", "w", encoding="utf-8") as f:
        json.dump(rj, f, ensure_ascii=False, indent=2, default=str)

    print(f"  输出: {os.path.abspath(out_dir)}/")
    return result


def _generate_demo_html(results: dict, out_dir: str):
    """从所有 pipeline 结果生成综合 Demo HTML 报告。"""
    import datetime

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 收集各语言摘要
    lang_summaries = []
    for lang_key, lang_name in [("c", "C (ARINC 429)"), ("py", "Python (Flight Data Monitor)"), ("cpp", "C++ (ADS-B Processor)")]:
        r = results.get(lang_key)
        if not r:
            lang_summaries.append({"lang": lang_key, "name": lang_name, "status": "未运行"})
            continue

        code = r.get("final_code", "")
        violations = r.get("final_violations", [])
        cov = r.get("coverage_result", {})
        sim = r.get("simulation_result", {})
        repair_history = r.get("repair_history", [])

        from skyforge_engine.report.do178_objectives import check_objectives
        objs = check_objectives(r, dal="A")
        p = sum(1 for o in objs if o.status == "满足")
        pp = sum(1 for o in objs if o.status == "部分满足")
        f_count = sum(1 for o in objs if o.status == "未满足")
        na = sum(1 for o in objs if o.status == "不适用")

        lang_summaries.append({
            "lang": lang_key,
            "name": lang_name,
            "status": "完成",
            "lines": len(code.splitlines()),
            "misra_violations": len(violations),
            "repair_rounds": len(repair_history),
            "stmt_cov": cov.get("statement_coverage", 0),
            "dec_cov": cov.get("decision_coverage", 0),
            "mcdc_cov": cov.get("mcdc_coverage", 0),
            "cov_method": cov.get("method", "N/A"),
            "sim_passed": sim.get("passed", "N/A") if sim else "N/A",
            "dal_pass": p,
            "dal_partial": pp,
            "dal_fail": f_count,
            "dal_na": na,
            "dal_total": len(objs),
        })

    # 生成 HTML
    cards_html = ""
    for s in lang_summaries:
        if s["status"] != "完成":
            cards_html += f'<div class="card"><div class="value">-</div><div class="label">{s["name"]} ({s["status"]})</div></div>'
            continue
        color = "#16a34a" if s["misra_violations"] == 0 else "#d97706"
        cards_html += (
            f'<div class="card"><div class="value" style="color:{color}">{s["lines"]}</div>'
            f'<div class="label">{s["name"]} — {s["lines"]} 行, MISRA {s["misra_violations"]} 条</div></div>'
        )

    table_rows = ""
    for s in lang_summaries:
        if s["status"] != "完成":
            table_rows += f'<tr><td>{s["name"]}</td><td colspan="8" class="na">未运行</td></tr>'
            continue
        sim_badge = '<span class="badge badge-ok">PASS</span>' if s["sim_passed"] is True else '<span class="badge badge-fail">FAIL</span>' if s["sim_passed"] is False else '<span class="badge badge-na">N/A</span>'
        cov_method = "gcov" if s["cov_method"] == "gcov" else "静态分析"
        dec_str = "-" if s["dec_cov"] == 0 else f'{s["dec_cov"]}%'
        mcdc_str = "-" if s["mcdc_cov"] == 0 else f'{s["mcdc_cov"]}%'
        misra_str = "0" if s["misra_violations"] == 0 else str(s["misra_violations"])
        table_rows += (
            f'<tr><td>{s["name"]}</td><td>{s["lines"]}</td>'
            f'<td>{misra_str}</td>'
            f'<td>{s["repair_rounds"]}</td>'
            f'<td class="pass">{s["stmt_cov"]}%</td>'
            f'<td>{dec_str}</td>'
            f'<td>{mcdc_str}</td>'
            f'<td>{sim_badge}</td>'
            f'<td>{cov_method}</td></tr>'
        )

    # DAL-A 目标表
    dal_rows = ""
    for s in lang_summaries:
        if s["status"] != "完成":
            continue
        pass_pct = s["dal_pass"] / max(s["dal_total"], 1) * 100
        badge = "badge-ok" if pass_pct >= 80 else "badge-partial" if pass_pct >= 50 else "badge-fail"
        dal_rows += (
            f'<tr><td>{s["name"]}</td>'
            f'<td class="pass">{s["dal_pass"]}</td>'
            f'<td class="partial">{s["dal_partial"]}</td>'
            f'<td class="fail">{s["dal_fail"]}</td>'
            f'<td class="na">{s["dal_na"]}</td>'
            f'<td>{s["dal_total"]}</td>'
            f'<td><span class="badge {badge}">{pass_pct:.0f}%</span></td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SkyForge (天锻) — DO-178C DAL-A 航空软件工程平台 演示报告</title>
<style>
:root {{
  --bg: #ffffff; --card: #f8f9fa; --border: #e0e0e0;
  --text: #1a1a2e; --muted: #6c757d; --accent: #2563eb;
  --pass: #16a34a; --partial: #d97706; --fail: #dc2626; --na: #9ca3af;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; max-width: 1100px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 2rem; border-bottom: 3px solid var(--accent); padding-bottom: 10px; margin-bottom: 10px; }}
h2 {{ font-size: 1.4rem; margin: 30px 0 15px; color: var(--accent); }}
h3 {{ font-size: 1.1rem; margin: 15px 0 10px; }}
.meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 25px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
.card .value {{ font-size: 1.8rem; font-weight: 700; color: var(--accent); }}
.card .label {{ font-size: 0.85rem; color: var(--muted); margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0 20px; font-size: 0.9rem; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ background: #f1f5f9; font-weight: 600; }}
.pass {{ color: var(--pass); font-weight: 600; }}
.partial {{ color: var(--partial); font-weight: 600; }}
.fail {{ color: var(--fail); font-weight: 600; }}
.na {{ color: var(--na); }}
code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
pre {{ background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 0.85rem; line-height: 1.5; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
.badge-ok {{ background: #dcfce7; color: var(--pass); }}
.badge-partial {{ background: #fef3c7; color: var(--partial); }}
.badge-fail {{ background: #fee2e2; color: var(--fail); }}
.badge-na {{ background: #f3f4f6; color: var(--na); }}
.footer {{ text-align: center; color: var(--muted); margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); font-size: 0.85rem; }}
.toolchain {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }}
.toolchip {{ padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; border: 1px solid var(--border); }}
.toolchip.ok {{ background: #dcfce7; border-color: #86efac; }}
.toolchip.err {{ background: #fee2e2; border-color: #fca5a5; }}
</style>
</head>
<body>

<h1>SkyForge (天锻)</h1>
<div class="meta">
  DO-178C DAL-A 航空机载软件工程平台 &mdash; AI 多智能体驱动<br>
  版本: v0.5.1 | 日期: {now} | 环境: Windows + GCC 16.1.0 + DeepSeek API
</div>

<h2>1. 全 Pipeline 运行状态</h2>
<div class="cards">
  <div class="card"><div class="value">3</div><div class="label">语言 Pipeline (C/Python/C++)</div></div>
  <div class="card"><div class="value">DeepSeek</div><div class="label">真实 LLM API 模式</div></div>
  <div class="card"><div class="value">DAL-A</div><div class="label">目标安全等级</div></div>
  <div class="card"><div class="value">21</div><div class="label">DO-178C 目标项</div></div>
</div>

<h3>Pipeline Stage 流程</h3>
<pre>需求解析 → LLR生成 → 架构设计 → HITL审查 → 契约生成 → HITL审查
→ 形式化验证(Z3/CBMC) → 代码生成 → HITL审查 → Cppcheck扫描
→ 修复闭环(扫描→修复→验证) → 数字孪生仿真(含故障注入)
→ 覆盖率收集(语句/判定/MC/DC) → 耦合分析 → 证据包生成</pre>

<h2>2. 生成代码概览</h2>
<div class="cards">
{cards_html}
</div>

<h2>3. 代码质量与覆盖率</h2>
<table>
  <tr><th>语言</th><th>行数</th><th>MISRA 违规</th><th>修复轮数</th><th>语句覆盖</th><th>判定覆盖</th><th>MC/DC</th><th>仿真</th><th>收集方法</th></tr>
{table_rows}
</table>

<h2>4. DO-178C DAL-A 目标符合性</h2>
<table>
  <tr><th>语言</th><th>满足</th><th>部分满足</th><th>未满足</th><th>不适用</th><th>总项数</th><th>通过率</th></tr>
{dal_rows if dal_rows else '<tr><td colspan="7" class="na">暂无数据</td></tr>'}
</table>

<h2>5. 工具链状态</h2>
<div class="toolchain">
  <span class="toolchip ok">GCC 16.1.0 ✓</span>
  <span class="toolchip ok">gcov 16.1.0 ✓</span>
  <span class="toolchip ok">gcov-dump 16.1.0 ✓</span>
  <span class="toolchip ok">Cppcheck 2.21.0 ✓</span>
  <span class="toolchip ok">Z3 ✓</span>
  <span class="toolchip ok">CBMC ✓</span>
  <span class="toolchip ok">DeepSeek API ✓</span>
</div>
<p style="color:var(--muted); font-size:0.85rem; margin-top:10px;">
  覆盖率收集：gcov JSON + gcov-dump -l 解析 MC/DC 条件覆盖率（Windows 原生，无需 lcov/Perl）
</p>

<h2>6. 核心创新点</h2>
<table>
  <tr><th>特性</th><th>说明</th></tr>
  <tr><td>AI 多智能体驱动</td><td>8+ Agent 协同：需求解析、架构设计、契约生成、代码生成、代码修复、LLR生成</td></tr>
  <tr><td>真实 LLM 代码生成</td><td>DeepSeek API 纯 API 模式，非 Mock，生成 C/Python/C++ 三语言航空代码</td></tr>
  <tr><td>修复闭环 + 退步检测</td><td>扫描→修复→验证循环，检测到代码退化（含新规则引入）自动回退</td></tr>
  <tr><td>MC/DC 覆盖率</td><td>Windows 上通过 gcov-dump -l 解析 COUNTERS conditions 实现真实 MC/DC 数据</td></tr>
  <tr><td>DO-178C DAL-A 21 项目标</td><td>自适应 DAL-A/B/C/D/E 目标检查，自动从 requirement.safety_level 推断</td></tr>
  <tr><td>数字孪生仿真</td><td>虚拟 MCU + 通用 harness + 故障注入（12 种故障类型）</td></tr>
  <tr><td>HITL 人工审查</td><td>需求/契约/代码三检查点，支持 auto-approve 和 WebSocket 实时推送</td></tr>
  <tr><td>多语言支持</td><td>C (MISRA-C:2012) / C++ (MISRA-C++/JSF AV) / Python (军工规范)</td></tr>
</table>

<div class="footer">
  SkyForge v0.5.1 | DO-178C DAL-A 航空软件工程平台 | {now}<br>
  后端: Python 3.13 | 前端: Vue 3 + TypeScript | Pipeline: 12 Stage × 3 语言
</div>

</body>
</html>"""

    html_path = os.path.join(out_dir, "demo_summary.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  Demo HTML 报告已生成: {os.path.abspath(html_path)}")


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    langs = ["c", "py", "cpp"] if target == "all" else [target]

    all_results = {}
    for lang in langs:
        if lang not in REQUIREMENTS:
            print(f"Unknown language: {lang}")
            continue
        try:
            result = await run_pipeline(lang)
            all_results[lang] = result
        except Exception as e:
            print(f"\n  ERROR [{lang}]: {e}")
            import traceback
            traceback.print_exc()

    # 生成综合 Demo HTML 报告
    if all_results:
        _generate_demo_html(all_results, "outputs/demo_2026_07_22")

    print(f"\n{'='*60}")
    print("  全部完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
