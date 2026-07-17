"""DO-178C 合规报告生成器。

基于 pipeline_result 渲染 HTML 报告
（内嵌 CSS，支持浏览器打印 PDF）。

报告共 7 章节：
  1. 封面（项目名 / 日期 / 版本号 / 生成时间）
  2. 需求追溯矩阵（[REQ-xxx] → desc → [CON-xxx] → 代码行号 → [TST-xxx]）
  3. 契约验证结果（pre / post / inv / fh 各项通过/失败）
  4. MISRA-C 合规摘要（Cppcheck 扫描 + 修复历史 + 最终违规数）
  5. 数字孪生仿真结果（步数 / 输入输出波形范围 / 故障注入 / 契约违约）
  6. DO-178C 目标符合性表（Level C 12 项目标）
  7. 签名页（开发者 / 审核者 / 批准者 空白签名行）

技术约束：
  - 使用 Jinja2 Template（已安装）渲染，模板字符串内嵌于本文件
  - 内嵌 CSS（不引入外部库），支持 @media print
  - 代码用 <pre><code> 包裹
  - [REQ-xxx] [CON-xxx] [TST-xxx] [MISRA-Rule-x.x] Tag 用彩色 Badge
"""

from datetime import datetime
from typing import Any

from jinja2 import Template

from skyforge_engine.utils.log_util import logger

from .do178_objectives import ObjectiveResult, check_objectives
from .traceability_matrix import TraceEntry, build_matrix

# Jinja2 HTML 模板：内嵌 CSS（@media print 适配 A4）
_REPORT_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>DO-178C 合规报告 - {{ project_name }}</title>
<style>
/* ===== 基础 ===== */
* { box-sizing: border-box; }
body {
  font-family: "Microsoft YaHei", "SimHei", "Helvetica Neue", Arial, sans-serif;
  margin: 0 auto;
  max-width: 980px;
  padding: 32px 28px 64px;
  color: #1f2937;
  background: #ffffff;
  line-height: 1.6;
  font-size: 14px;
}
h1, h2, h3 { color: #0f172a; margin-top: 28px; }
h1 { font-size: 26px; border-bottom: 3px solid #1e40af; padding-bottom: 8px; }
h2 {
  font-size: 20px;
  border-left: 5px solid #1e40af;
  padding-left: 12px;
  margin-top: 48px;
  page-break-after: avoid;
}
h3 { font-size: 16px; margin-top: 24px; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #cbd5e1;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
th { background: #1e3a8a; color: #ffffff; font-weight: 600; }
tr:nth-child(even) td { background: #f1f5f9; }

/* ===== Tag 彩色 Badge ===== */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-family: "Consolas", "Courier New", monospace;
  color: #ffffff;
  margin: 0 2px;
  white-space: nowrap;
}
.badge-req  { background: #2563eb; }   /* 蓝色：REQ */
.badge-llr { background: #0891b2; }   /* 青色：LLR */
.badge-con  { background: #7c3aed; }   /* 紫色：CON */
.badge-tst  { background: #059669; }   /* 绿色：TST */
.badge-misra{ background: #ea580c; }  /* 橙色：MISRA-Rule */
.badge-pass { background: #16a34a; color: #ffffff; }
.badge-fail { background: #dc2626; color: #ffffff; }
.badge-partial { background: #d97706; color: #ffffff; }

/* ===== 状态标签 ===== */
.status-pass { color: #16a34a; font-weight: 600; }
.status-fail { color: #dc2626; font-weight: 600; }
.status-partial { color: #d97706; font-weight: 600; }

/* ===== 代码块 ===== */
pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 12.5px;
  line-height: 1.5;
  page-break-inside: avoid;
}
pre code { background: transparent; color: inherit; padding: 0; }
code {
  background: #f1f5f9;
  color: #0f172a;
  padding: 2px 5px;
  border-radius: 3px;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 13px;
}

/* ===== 封面 ===== */
.cover {
  text-align: center;
  padding: 80px 0 40px;
  page-break-after: always;
}
.cover h1 {
  font-size: 32px;
  border: none;
  display: inline-block;
  padding: 0 0 12px;
  border-bottom: 4px double #1e40af;
}
.cover .meta {
  margin-top: 32px;
  font-size: 15px;
  color: #475569;
}
.cover .meta div { margin: 6px 0; }
.cover .meta strong { color: #0f172a; }

/* ===== 签名页 ===== */
.signature-block {
  margin-top: 48px;
  page-break-before: always;
}
.signature-row {
  display: flex;
  margin: 32px 0;
  align-items: flex-end;
}
.signature-row .role {
  width: 120px;
  font-weight: 600;
  color: #0f172a;
}
.signature-row .line {
  flex: 1;
  border-bottom: 1.5px solid #0f172a;
  height: 36px;
  margin: 0 16px;
}
.signature-row .date {
  width: 220px;
  color: #64748b;
  font-size: 13px;
}

/* ===== 摘要块 ===== */
.summary-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px 20px;
  margin: 16px 0;
}
.summary-card .stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 8px;
}
.summary-card .stat {
  text-align: center;
}
.summary-card .stat .num {
  font-size: 24px;
  font-weight: 700;
  color: #1e40af;
}
.summary-card .stat .label {
  font-size: 12px;
  color: #64748b;
}

/* ===== 打印适配 ===== */
@media print {
  body { max-width: none; padding: 0; font-size: 11pt; }
  h2 { page-break-before: always; }
  .cover + h2, h2:first-of-type { page-break-before: avoid; }
  table, pre, .signature-block { page-break-inside: avoid; }
  .no-print { display: none; }
}
</style>
</head>
<body>

<!-- ========== 1. 封面 ========== -->
<section class="cover">
  <h1>DO-178C 合规报告</h1>
  <div style="margin-top: 16px; font-size: 18px; color: #475569;">
    机载软件安全合规 AI 中台 自动生成
  </div>
  <div class="meta">
    <div><strong>项目名称：</strong>{{ project_name }}</div>
    <div><strong>软件版本：</strong>{{ version }}</div>
    <div><strong>安全等级：</strong>{{ safety_level }}</div>
    <div><strong>生成日期：</strong>{{ gen_date }}</div>
    <div><strong>生成时间：</strong>{{ gen_time }}</div>
    <div><strong>报告 ID：</strong>RPT-{{ gen_timestamp }}</div>
  </div>
  <div style="margin-top: 64px; color: #94a3b8; font-size: 13px;">
    本报告由 AI 中台流水线自动生成，依据 DO-178C Level C 关键目标进行符合性评估。
  </div>
</section>

<!-- ========== 2. 需求追溯矩阵 ========== -->
<h2>1. 需求追溯矩阵 (四层追溯: HLR→LLR→Code→Test)</h2>
<p>
下表展示 DO-178C 四层双向追溯链：
HLR [REQ-xxx] → LLR [LLR-xxx] → 契约 [CON-xxx] →
代码行号 → 测试 [TST-xxx]：
</p>
{% if trace_matrix %}
<table>
  <thead>
    <tr>
      <th style="width: 8%;">HLR Tag</th>
      <th style="width: 20%;">HLR 描述</th>
      <th style="width: 8%;">LLR Tag</th>
      <th style="width: 15%;">LLR 描述</th>
      <th style="width: 8%;">契约 Tag</th>
      <th style="width: 6%;">代码行</th>
      <th style="width: 18%;">代码片段</th>
      <th style="width: 7%;">测试 Tag</th>
      <th style="width: 10%;">测试结果</th>
    </tr>
  </thead>
  <tbody>
  {% for e in trace_matrix %}
    <tr>
      <td><span class="badge badge-req">{{ e.req_id }}</span></td>
      <td>{{ e.req_desc }}</td>
      <td>
        {% if e.llr_id %}
        <span class="badge badge-llr">{{ e.llr_id }}</span>
        {% else %}-{% endif %}
      </td>
      <td>{{ e.llr_desc or "-" }}</td>
      <td>
        {% if e.contract_id %}
        <span class="badge badge-con">{{ e.contract_id }}</span>
        {% endif %}
      </td>
      <td>{% if e.code_line %}L{{ e.code_line }}{% else %}-{% endif %}</td>
      <td><code>{{ e.code_snippet }}</code></td>
      <td>
        {% if e.test_id %}
        <span class="badge badge-tst">{{ e.test_id }}</span>
        {% else %}-{% endif %}
      </td>
      <td>
        {% if e.test_result == "通过" %}<span class="status-pass">通过</span>
        {% elif e.test_result == "失败" %}<span class="status-fail">失败</span>
        {% else %}-{% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p style="color: #94a3b8;">无追溯数据。</p>
{% endif %}

<!-- ========== 3. 契约验证结果 ========== -->
<h2>2. 契约验证结果</h2>
{% if contract_check_result %}
<p>整体契约校验结果：
  {% if contract_check_result.passed %}
    <span class="badge badge-pass">PASSED</span>
  {% else %}
    <span class="badge badge-fail">FAILED</span>
  {% endif %}
</p>

<h3>2.1 前置条件（Preconditions）</h3>
{% if contract_check_result.preconditions %}
<table>
  <thead><tr><th>ID</th><th>描述</th><th>结果</th><th>详情</th></tr></thead>
  <tbody>
  {% for item in contract_check_result.preconditions %}
    <tr>
      <td><span class="badge badge-con">{{ item.id }}</span></td>
      <td>{{ item.desc }}</td>
      <td>
        {% if item.passed %}
        <span class="status-pass">通过</span>
        {% else %}
        <span class="status-fail">失败</span>
        {% endif %}
      </td>
      <td>{{ item.detail }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p>无前置条件。</p>{% endif %}

<h3>2.2 后置条件（Postconditions）</h3>
{% if contract_check_result.postconditions %}
<table>
  <thead><tr><th>ID</th><th>描述</th><th>结果</th><th>详情</th></tr></thead>
  <tbody>
  {% for item in contract_check_result.postconditions %}
    <tr>
      <td><span class="badge badge-con">{{ item.id }}</span></td>
      <td>{{ item.desc }}</td>
      <td>
        {% if item.passed %}
        <span class="status-pass">通过</span>
        {% else %}
        <span class="status-fail">失败</span>
        {% endif %}
      </td>
      <td>{{ item.detail }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p>无后置条件。</p>{% endif %}

<h3>2.3 不变式（Invariants）</h3>
{% if contract_check_result.invariants %}
<table>
  <thead><tr><th>ID</th><th>描述</th><th>结果</th><th>详情</th></tr></thead>
  <tbody>
  {% for item in contract_check_result.invariants %}
    <tr>
      <td><span class="badge badge-con">{{ item.id }}</span></td>
      <td>{{ item.desc }}</td>
      <td>
        {% if item.passed %}
        <span class="status-pass">通过</span>
        {% else %}
        <span class="status-fail">失败</span>
        {% endif %}
      </td>
      <td>{{ item.detail }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p>无不变式。</p>{% endif %}

<h3>2.4 故障处理（Fault Handling）</h3>
{% if contract_check_result.fault_handling %}
<table>
  <thead><tr><th>ID</th><th>描述</th><th>结果</th><th>详情</th></tr></thead>
  <tbody>
  {% for item in contract_check_result.fault_handling %}
    <tr>
      <td><span class="badge badge-con">{{ item.id }}</span></td>
      <td>{{ item.desc }}</td>
      <td>
        {% if item.passed %}
        <span class="status-pass">通过</span>
        {% else %}
        <span class="status-fail">失败</span>
        {% endif %}
      </td>
      <td>{{ item.detail }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p>无故障处理。</p>{% endif %}

<h3>2.5 自动生成的契约断言插桩代码</h3>
<pre><code>{{ contract_check_result.assert_code }}</code></pre>

{% else %}
<p style="color: #94a3b8;">未执行契约校验。</p>
{% endif %}

<!-- ========== 4. MISRA-C 合规摘要 ========== -->
<h2>3. MISRA-C 合规摘要</h2>
<div class="summary-card">
  <div><strong>Cppcheck 扫描结果：</strong>初次扫描 {{ cppcheck_count }} 条违规</div>
  <div><strong>修复轮次：</strong>{{ repair_rounds }} 轮</div>
  <div><strong>最终残留违规：</strong>
    {% if final_violations_count == 0 %}
      <span class="status-pass">{{ final_violations_count }} 条（合规）</span>
    {% else %}
      <span class="status-fail">{{ final_violations_count }} 条</span>
    {% endif %}
  </div>
  <div class="stat-grid">
    <div class="stat">
      <div class="num">{{ cppcheck_count }}</div>
      <div class="label">初次违规</div>
    </div>
    <div class="stat">
      <div class="num">{{ repair_rounds }}</div>
      <div class="label">修复轮次</div>
    </div>
    <div class="stat">
      <div class="num">{{ total_actions }}</div>
      <div class="label">修复动作</div>
    </div>
    <div class="stat">
      <div class="num">{{ final_violations_count }}</div>
      <div class="label">残留违规</div>
    </div>
  </div>
</div>

{% if repair_history %}
<h3>3.1 修复历史</h3>
<table>
  <thead>
    <tr>
      <th>轮次</th><th>违规前</th><th>修复动作</th><th>契约校验</th>
    </tr>
  </thead>
  <tbody>
  {% for entry in repair_history %}
    <tr>
      <td>{{ entry.iteration }}</td>
      <td>{{ entry.violations_count_before }} 条</td>
      <td>{{ entry.actions_count }} 处</td>
      <td>
        {% if entry.contract_passed is none %}未校验
        {% elif entry.contract_passed %}<span class="status-pass">通过</span>
        {% else %}<span class="status-fail">失败</span>{% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

{% if final_violations %}
<h3>3.2 残留违规列表</h3>
<table>
  <thead><tr><th>文件</th><th>行号</th><th>规则</th><th>严重度</th><th>描述</th></tr></thead>
  <tbody>
  {% for v in final_violations %}
    <tr>
      <td>{{ v.file }}</td>
      <td>L{{ v.line }}</td>
      <td><span class="badge badge-misra">{{ v.rule_id }}</span></td>
      <td>{{ v.severity }}</td>
      <td>{{ v.message }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

<h3>3.3 最终 C 代码</h3>
<pre><code>{{ final_code }}</code></pre>

<!-- ========== 5. 数字孪生仿真结果 ========== -->
<h2>4. 数字孪生仿真结果</h2>
{% if simulation_result %}
<div class="summary-card">
  <div class="stat-grid">
    <div class="stat">
      <div class="num">{{ simulation_result.total_steps }}</div>
      <div class="label">仿真步数</div>
    </div>
    <div class="stat">
      <div class="num">{{ sim_input_min }}</div>
      <div class="label">输入最小</div>
    </div>
    <div class="stat">
      <div class="num">{{ sim_input_max }}</div>
      <div class="label">输入最大</div>
    </div>
    <div class="stat">
      <div class="num">{{ sim_output_min }}</div>
      <div class="label">输出最小</div>
    </div>
  </div>
  <div class="stat-grid" style="margin-top: 12px;">
    <div class="stat">
      <div class="num">{{ sim_output_max }}</div>
      <div class="label">输出最大</div>
    </div>
    <div class="stat">
      <div class="num">{{ sim_duration_ms }} ms</div>
      <div class="label">运行时长</div>
    </div>
    <div class="stat">
      <div class="num">
        {% if simulation_result.passed %}<span class="status-pass">PASS</span>
        {% else %}<span class="status-fail">FAIL</span>{% endif %}
      </div>
      <div class="label">仿真结果</div>
    </div>
    <div class="stat">
      <div class="num">{{ simulation_result.fault_type or '无' }}</div>
      <div class="label">故障类型</div>
    </div>
  </div>
</div>

<h3>4.1 输入波形（前 20 采样点）</h3>
<pre><code>{{ sim_input_preview }}</code></pre>
<h3>4.2 输出波形（前 20 采样点）</h3>
<pre><code>{{ sim_output_preview }}</code></pre>

<h3>4.3 故障注入结果</h3>
{% if simulation_result.fault_type %}
<p>
  已注入故障：
  <strong>{{ simulation_result.fault_type }}</strong>，
  参数：<code>{{ simulation_result.fault_params }}</code>
</p>
{% else %}
<p>本次仿真未注入故障。</p>
{% endif %}

<h3>4.4 契约违约情况</h3>
{% if simulation_result.contract_violation %}
<table>
  <thead><tr><th>契约 ID</th><th>失败步数</th><th>断言消息</th></tr></thead>
  <tbody>
    <tr>
      <td>
        <span class="badge badge-con">
          {{ simulation_result.contract_violation.contract_id }}
        </span>
      </td>
      <td>{{ simulation_result.contract_violation.failed_step }}</td>
      <td>{{ simulation_result.contract_violation.assertion_message }}</td>
    </tr>
  </tbody>
</table>
{% else %}
<p><span class="status-pass">无契约违约。</span></p>
{% endif %}

<h3>4.5 编译信息</h3>
<table>
  <thead><tr><th>编译成功</th><th>使用 mock</th><th>错误信息</th></tr></thead>
  <tbody>
    <tr>
      <td>{% if simulation_result.compilation.success %}✓{% else %}✗{% endif %}</td>
      <td>{{ simulation_result.compilation.used_mock }}</td>
      <td>{{ simulation_result.compilation.errors or '无' }}</td>
    </tr>
  </tbody>
</table>

<h3>4.6 终端日志</h3>
<pre><code>{{ simulation_result.terminal_log }}</code></pre>

{% else %}
<p style="color: #94a3b8;">未执行数字孪生仿真。</p>
{% endif %}

<!-- ========== 6. DO-178C 目标符合性表 ========== -->
<h2>5. DO-178C 目标符合性表</h2>
<p>依据 DO-178C Level C 关键目标（Table A-2 ~ A-9）自动评估：</p>
<div class="summary-card">
  <div class="stat-grid">
    <div class="stat">
      <div class="num">{{ obj_pass_count }}</div>
      <div class="label">满足</div>
    </div>
    <div class="stat">
      <div class="num">{{ obj_partial_count }}</div>
      <div class="label">部分满足</div>
    </div>
    <div class="stat">
      <div class="num">{{ obj_fail_count }}</div>
      <div class="label">未满足</div>
    </div>
    <div class="stat">
      <div class="num">{{ objectives | length }}</div>
      <div class="label">总目标数</div>
    </div>
  </div>
</div>
<table>
  <thead>
    <tr>
      <th style="width: 8%;">ID</th>
      <th style="width: 18%;">名称</th>
      <th style="width: 32%;">描述</th>
      <th style="width: 12%;">状态</th>
      <th style="width: 30%;">证据</th>
    </tr>
  </thead>
  <tbody>
  {% for obj in objectives %}
    <tr>
      <td>{{ obj.obj_id }}</td>
      <td>{{ obj.name }}</td>
      <td>{{ obj.description }}</td>
      <td>
        {% if obj.status == "满足" %}<span class="badge badge-pass">满足</span>
        {% elif obj.status == "部分满足" %}
        <span class="badge badge-partial">部分满足</span>
        {% else %}<span class="badge badge-fail">未满足</span>{% endif %}
      </td>
      <td>{{ obj.evidence }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<!-- ========== 7. 签名页 ========== -->
<h2>6. 签名页</h2>
<div class="signature-block">
  <p>本报告经下列人员审核确认：</p>

  <div class="signature-row">
    <div class="role">开发者：</div>
    <div class="line"></div>
    <div class="date">日期：____ / ____ / ________</div>
  </div>

  <div class="signature-row">
    <div class="role">审核者：</div>
    <div class="line"></div>
    <div class="date">日期：____ / ____ / ________</div>
  </div>

  <div class="signature-row">
    <div class="role">批准者：</div>
    <div class="line"></div>
    <div class="date">日期：____ / ____ / ________</div>
  </div>

  <div class="signature-row">
    <div class="role">质量保证：</div>
    <div class="line"></div>
    <div class="date">日期：____ / ____ / ________</div>
  </div>

  <p style="margin-top: 64px; color: #94a3b8; font-size: 12px;">
    — 报告结束 —<br>
    本报告由 AI 中台流水线自动生成，签名处由人工填写。
  </p>
</div>

</body>
</html>
""")


def generate_report(pipeline_result: dict[str, Any]) -> str:
    """生成 DO-178C 合规报告（HTML 格式）。

    Args:
        pipeline_result: 全流程结果字典，至少包含 requirement / contract / final_code
            （或 code）/ contract_check_result / simulation_result / repair_history /
            final_violations / cppcheck_result 字段。

    Returns:
        完整 HTML 报告字符串（含内嵌 CSS，可直接写入 .html 文件）。
    """
    logger.info("ReportGenerator:开始生成 DO-178C 合规报告")

    # ---- 1) 构建追溯矩阵 ----
    trace_matrix: list[TraceEntry] = build_matrix(pipeline_result)

    # ---- 2) 检查 DO-178C 目标 ----
    objectives: list[ObjectiveResult] = check_objectives(pipeline_result)

    # ---- 3) 提取封面元信息 ----
    requirement = pipeline_result.get("requirement") or {}
    project_name = (
        requirement.get("module_name") or requirement.get("module") or "airborne_module"
    )
    contract_yaml: str = pipeline_result.get("contract", "") or ""
    version = _extract_version(contract_yaml) or "1.0.0"
    safety_level = requirement.get("safety_level") or "DAL-B"

    now = datetime.now()
    gen_date = now.strftime("%Y-%m-%d")
    gen_time = now.strftime("%H:%M:%S")
    gen_timestamp = now.strftime("%Y%m%d%H%M%S")

    # ---- 4) 提取仿真摘要 ----
    sim = pipeline_result.get("simulation_result") or {}
    sim_stats = sim.get("statistics", {}) or {} if isinstance(sim, dict) else {}
    sim_input_min = _fmt_float(sim_stats.get("input_min"))
    sim_input_max = _fmt_float(sim_stats.get("input_max"))
    sim_output_min = _fmt_float(sim_stats.get("output_min"))
    sim_output_max = _fmt_float(sim_stats.get("output_max"))
    sim_duration_ms = _fmt_float(sim_stats.get("duration_ms"))

    sim_input_preview = _preview_waveform(sim.get("input_waveform", []))
    sim_output_preview = _preview_waveform(sim.get("output_waveform", []))

    # ---- 5) 提取 MISRA 摘要 ----
    cppcheck_result = pipeline_result.get("cppcheck_result", []) or []
    cppcheck_count = len(cppcheck_result)
    repair_history = pipeline_result.get("repair_history", []) or []
    repair_rounds = len(repair_history)
    total_actions = sum(
        len(entry.get("actions", [])) if isinstance(entry, dict) else 0
        for entry in repair_history
    )
    final_violations = pipeline_result.get("final_violations", []) or []
    final_violations_count = len(final_violations)
    final_code = pipeline_result.get("final_code") or pipeline_result.get("code") or ""

    # ---- 6) 契约校验结果 ----
    contract_check_result = pipeline_result.get("contract_check_result")

    # ---- 7) 渲染 HTML ----
    html = _REPORT_TEMPLATE.render(
        # 封面
        project_name=project_name,
        version=version,
        safety_level=safety_level,
        gen_date=gen_date,
        gen_time=gen_time,
        gen_timestamp=gen_timestamp,
        # 追溯矩阵
        trace_matrix=trace_matrix,
        # 契约校验
        contract_check_result=contract_check_result,
        # MISRA 摘要
        cppcheck_count=cppcheck_count,
        repair_rounds=repair_rounds,
        total_actions=total_actions,
        final_violations=final_violations,
        final_violations_count=final_violations_count,
        final_code=final_code,
        repair_history=repair_history,
        # 仿真结果
        simulation_result=sim,
        sim_input_min=sim_input_min,
        sim_input_max=sim_input_max,
        sim_output_min=sim_output_min,
        sim_output_max=sim_output_max,
        sim_duration_ms=sim_duration_ms,
        sim_input_preview=sim_input_preview,
        sim_output_preview=sim_output_preview,
        # DO-178C 目标
        objectives=objectives,
        obj_pass_count=sum(1 for o in objectives if o.status == "满足"),
        obj_partial_count=sum(1 for o in objectives if o.status == "部分满足"),
        obj_fail_count=sum(1 for o in objectives if o.status == "未满足"),
    )

    logger.info(
        f"ReportGenerator:完成 HTML 报告生成: {len(html)} 字符, "
        f"追溯 {len(trace_matrix)} 行, 目标 {len(objectives)} 项"
    )
    return html


def _extract_version(contract_yaml: str) -> str:
    """从契约 YAML 中提取 version 字段（简易正则，避免 YAML 解析开销）。"""
    import re

    m = re.search(r"^version:\s*(\S+)", contract_yaml, re.MULTILINE)
    return m.group(1) if m else ""


def _fmt_float(value: Any) -> str:
    """格式化浮点数（保留 2 位小数）。"""
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _preview_waveform(waveform: list, n: int = 20) -> str:
    """取前 n 个采样点，格式化为多行字符串。"""
    if not waveform:
        return "(无波形数据)"
    head = list(waveform[:n])
    lines = [f"  [{i:3d}] {v:.6f}" for i, v in enumerate(head)]
    if len(waveform) > n:
        lines.append(f"  ... 共 {len(waveform)} 个采样点")
    return "\n".join(lines)
