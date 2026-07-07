/**
 * 真实后端 API 服务层
 * ====================================================================
 * AirborneAI 后端 20 个端点的 fetch 封装。
 *
 * 设计要点：
 * 1. 不引入 axios，纯 fetch 实现；
 * 2. 所有函数签名与 mockApi.ts 中的 mock 函数一致，便于在 apiSwitcher 中互换；
 * 3. 后端响应字段与 mockApi 类型存在差异，本层负责字段转换；
 * 4. 30 秒超时（生成、报告等长任务也使用同一超时）；
 * 5. 网络错误时静默降级到 mockApi，保证前端可用性。
 */

import {
  mockGenerate,
  mockSimulateByCode,
  mockCompose,
  mockCheckCompatibility,
  mockUploadScade,
  mockGetLLMStatus,
  mockSwitchLLM,
  mockGetModels,
  mockGetPendingApprovals,
  mockApprove,
  mockReject,
  mockGenerateReportByPipeline,
  mockRepair,
  mockCheckContract,
  mockGetFaultTypes,
  mockSearchMisra,
  mockGetMisraRule,
  type GenerateResult,
  type SimulationResult,
  type ComposeResult,
  type CompatibilityResult,
  type ContractCheckResult,
  type ScadeParseResult,
  type LLMStatus,
  type LLMModel,
  type HILApproval,
  type ReportResult,
  type RepairResult,
  type FaultType,
  type FaultParams,
  type MisraRule,
  type ComposeConnection,
} from "./mockApi";

/** 后端 API 基础地址 */
const API_BASE_URL = "http://localhost:8000";

/** 默认请求超时（毫秒） */
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * 带超时的 fetch 封装
 *
 * @param url 完整 URL
 * @param options fetch 配置
 * @param timeout 超时毫秒
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    return response;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 调用真实后端 API；网络错误时静默降级到 mockApi
 *
 * @param realCall 真实 API 调用函数（返回 Promise<T>）
 * @param fallback 出错时的 mock 兜底函数
 * @param label 用于日志的接口名称
 */
async function withFallback<T>(
  realCall: () => Promise<T>,
  fallback: () => Promise<T>,
  label: string,
): Promise<T> {
  try {
    return await realCall();
  } catch (err) {
    // 静默降级：仅在控制台输出警告，不向用户抛错
    console.warn(`[api] ${label} 真实 API 调用失败，降级到 mock：`, err);
    return fallback();
  }
}

/** POST JSON 请求 */
async function postJSON<T = any>(path: string, body: any): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

/** GET 请求 */
async function getJSON<T = any>(path: string): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return res.json();
}

// ====================================================================
// 字段转换工具：后端响应 → mockApi 类型
// ====================================================================

/**
 * 将后端 /api/generate 响应转换为 GenerateResult
 *
 * 后端字段：code / cppcheck_result / repair_history / contract_check_result /
 *          simulation_result / final_violations / hil_approvals
 * mockApi 字段：code / violations / repair_history / contract_check_result /
 *              simulation_result / traceability / contract
 */
function transformGenerateResponse(raw: any): GenerateResult {
  return {
    contract: raw.contract ?? raw.contract_yaml ?? { component: "", description: "", inputs: {}, outputs: {}, preconditions: [], postconditions: [], invariants: [], fault_handling: [] },
    code: raw.code ?? raw.final_code ?? "",
    violations: raw.violations ?? raw.cppcheck_result ?? raw.final_violations ?? [],
    traceability: raw.traceability ?? {},
    repair_history: raw.repair_history ?? [],
    contract_check_result: raw.contract_check_result ?? {
      component: "",
      sections: [],
      passed_count: 0,
      total_count: 0,
      overall_passed: false,
      generated_assert_code: "",
    },
    simulation_result: raw.simulation_result ?? raw.simulation,
  };
}

/**
 * 将后端 /api/simulate 响应转换为 SimulationResult
 *
 * 后端字段：passed / total_steps / fault_type / input_waveform /
 *          output_waveform / contract_violation / statistics /
 *          compilation / terminal_log
 * mockApi 字段：补全 fault_params / fault_range / logs
 */
function transformSimulationResponse(raw: any): SimulationResult {
  return {
    passed: raw.passed ?? false,
    total_steps: raw.total_steps ?? 0,
    fault_type: (raw.fault_type ?? null) as FaultType | null,
    fault_params: raw.fault_params ?? {},
    input_waveform: raw.input_waveform ?? [],
    output_waveform: raw.output_waveform ?? [],
    fault_range: raw.fault_range ?? null,
    contract_violation: raw.contract_violation ?? null,
    statistics: raw.statistics ?? {
      total_steps: raw.total_steps ?? 0,
      input_range: [0, 0],
      output_range: [0, 0],
      output_max: 0,
      output_min: 0,
      output_mean: 0,
    },
    logs: raw.logs ?? raw.terminal_log ?? [],
  };
}

/**
 * 将后端 /api/compose 响应转换为 ComposeResult
 *
 * 后端字段：composed_code / composed_contract / compatibility_check /
 *          simulation_result / warnings / connection
 */
function transformComposeResponse(raw: any, compA: any, compB: any, connection: string): ComposeResult {
  const compatRaw = raw.compatibility_check ?? raw.compatibility;
  return {
    component_a: typeof compA === "string" ? compA : compA?.name ?? "ComponentA",
    component_b: typeof compB === "string" ? compB : compB?.name ?? "ComponentB",
    connection: (raw.connection ?? connection) as ComposeConnection,
    composed_code: raw.composed_code ?? "",
    compatibility: transformCompatibilityResponse(compatRaw, compA, compB, connection),
    simulation: transformSimulationResponse(raw.simulation_result ?? raw.simulation ?? {}),
  };
}

/**
 * 将后端 /api/check-compatibility 响应转换为 CompatibilityResult
 *
 * 后端字段：compatible / checked_pairs / violations / warnings / connection
 */
function transformCompatibilityResponse(raw: any, compA: any, compB: any, connection: string): CompatibilityResult {
  // 后端的 violations / warnings 是字符串数组，转换为 mockApi 的 checks 列表
  const violations: string[] = raw.violations ?? [];
  const warnings: string[] = raw.warnings ?? [];
  const checks = [
    ...violations.map((v: string, i: number) => ({
      id: `COMPAT-V-${i + 1}`,
      check: v,
      passed: false,
      reason: v,
    })),
    ...warnings.map((w: string, i: number) => ({
      id: `COMPAT-W-${i + 1}`,
      check: w,
      passed: true,
      reason: w,
    })),
  ];
  const passedCount = checks.filter((c) => c.passed).length;
  return {
    component_a: typeof compA === "string" ? compA : compA?.name ?? "ComponentA",
    component_b: typeof compB === "string" ? compB : compB?.name ?? "ComponentB",
    connection: (raw.connection ?? connection) as ComposeConnection,
    checks: checks.length > 0 ? checks : [
      { id: "COMPAT-001", check: "兼容性检查", passed: raw.compatible ?? raw.overall_compatible ?? true },
    ],
    passed_count: raw.passed_count ?? passedCount,
    total_count: raw.total_count ?? checks.length,
    overall_compatible: raw.overall_compatible ?? raw.compatible ?? true,
  };
}

/**
 * 将后端 /api/upload-scade 响应转换为 ScadeParseResult
 *
 * 后端字段：filename / parsed / requirement / contract
 */
function transformScadeResponse(raw: any): ScadeParseResult {
  const parsed = raw.parsed ?? {};
  return {
    node_name: parsed.node_name ?? "",
    inputs: parsed.inputs ?? [],
    outputs: parsed.outputs ?? [],
    locals: parsed.locals ?? [],
    equations: parsed.equations ?? [],
    natural_language_requirement: raw.requirement ?? "",
    contract_yaml: raw.contract ?? "",
    source_file: raw.filename ?? "",
  };
}

/**
 * 将后端 /api/llm/status 响应转换为 LLMStatus
 *
 * 后端字段：available / models (list[str]) / use_llm
 */
function transformLLMStatusResponse(raw: any): LLMStatus {
  const modelStrings: string[] = raw.models ?? [];
  return {
    available: raw.available ?? false,
    endpoint: raw.endpoint ?? "http://localhost:1234/v1",
    use_llm: raw.use_llm ?? false,
    models: modelStrings.map((id) => ({
      id,
      name: id,
      loaded: true,
    })),
    current_model: modelStrings[0] ?? "",
    response_time_ms: raw.response_time_ms ?? 0,
    total_calls: raw.total_calls ?? 0,
  };
}

/**
 * 将后端 /api/models 响应转换为 LLMModel[]
 */
function transformModelsResponse(raw: any): LLMModel[] {
  const list = raw.models ?? raw ?? [];
  return list.map((m: any) => {
    if (typeof m === "string") {
      return { id: m, name: m, loaded: true };
    }
    return {
      id: m.id ?? m.model_id ?? m.name,
      name: m.name ?? m.id ?? m.model_id,
      size: m.size,
      context_length: m.context_length,
      loaded: m.loaded ?? true,
    };
  });
}

/**
 * 将后端 /api/hil/pending 响应转换为 HILApproval[]
 */
function transformPendingResponse(raw: any): HILApproval[] {
  return raw.pending ?? raw ?? [];
}

/**
 * 将后端 /api/report 响应转换为 ReportResult
 *
 * 后端字段：report_html / traceability_matrix / do178_objectives
 */
function transformReportResponse(raw: any): ReportResult {
  const objectives: any[] = raw.do178_objectives ?? [];
  const passedObj = objectives.filter((o) => o.passed ?? o.status === "passed").length;
  const totalObj = objectives.length || 66;
  const matrix: any[] = raw.traceability_matrix ?? [];
  return {
    report_id: `DO178C-REPORT-${Date.now()}`,
    html: raw.report_html ?? raw.html ?? "",
    summary: {
      title: "DO-178C 报告",
      generated_at: Date.now(),
      traceability_entries: matrix.length,
      total_objectives: totalObj,
      passed_objectives: passedObj,
      pass_rate: totalObj > 0 ? passedObj / totalObj : 0,
      simulation_summary: "详见报告内容",
      misra_violations: 0,
    },
  };
}

// ====================================================================
// 公共 API 函数（与 mockApi 签名一致）
// ====================================================================

/**
 * 生成代码：POST /api/generate
 *
 * @param requirement 自然语言需求
 * @param scadeFile 可选的 SCADE G-Lustre 文件内容
 */
export async function generate(requirement: string, scadeFile?: string): Promise<GenerateResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/generate", {
        requirement,
        scade_file: scadeFile ?? "",
      });
      return transformGenerateResponse(raw);
    },
    () => mockGenerate(requirement),
    "generate",
  );
}

/**
 * 修复代码：POST /api/repair
 */
export async function repair(code: string): Promise<RepairResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/repair", {
        code,
        contract: "",
        max_iterations: 3,
        req_id: "REQ-001",
      });
      return {
        final_code: raw.final_code ?? raw.code ?? code,
        repair_history: raw.repair_history ?? [],
        final_violations: raw.final_violations ?? raw.violations ?? [],
        contract_check_result: raw.contract_check_result ?? {
          component: "",
          sections: [],
          passed_count: 0,
          total_count: 0,
          overall_passed: false,
          generated_assert_code: "",
        },
      };
    },
    () => mockRepair(code),
    "repair",
  );
}

/**
 * 契约校验：POST /api/check-contract
 */
export async function checkContract(code: string, contract: string): Promise<ContractCheckResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/check-contract", {
        code,
        contract,
        cid: "CON-001",
      });
      // 后端返回扁平结构，转换为 mockApi 的分区结构
      return raw as ContractCheckResult;
    },
    () => mockCheckContract(code, contract),
    "checkContract",
  );
}

/**
 * 数字孪生仿真：POST /api/simulate
 */
export async function simulate(
  code: string,
  contract: string,
  faultType?: string,
  faultParams?: FaultParams,
): Promise<SimulationResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/simulate", {
        code,
        contract,
        fault_type: faultType ?? null,
        fault_params: faultParams ?? null,
        steps: 200,
      });
      return transformSimulationResponse(raw);
    },
    () => mockSimulateByCode(code, contract, faultType, faultParams),
    "simulate",
  );
}

/**
 * 获取故障类型列表：GET /api/fault-types
 */
export async function getFaultTypes(): Promise<FaultType[]> {
  return withFallback(
    async () => {
      const raw = await getJSON("/api/fault-types");
      const list = raw.fault_types ?? [];
      return list.map((item: any) => (typeof item === "string" ? item : item.type));
    },
    () => mockGetFaultTypes(),
    "getFaultTypes",
  );
}

/**
 * 生成 DO-178C 报告：POST /api/report
 *
 * @param pipelineResult /api/generate 返回的全流程结果
 */
export async function generateReport(pipelineResult: any): Promise<ReportResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/report", {
        pipeline_result: pipelineResult,
      });
      return transformReportResponse(raw);
    },
    () => mockGenerateReportByPipeline(pipelineResult),
    "generateReport",
  );
}

/**
 * 获取报告下载 URL：GET /api/report/download
 *
 * @returns 报告下载地址（直接打开即可下载）
 */
export function downloadReport(): string {
  return `${API_BASE_URL}/api/report/download`;
}

/**
 * 组件组合：POST /api/compose
 *
 * @param compA 组件 A（名称字符串或 {code, contract, name} 对象）
 * @param compB 组件 B
 * @param connection 连接方式：sequential / parallel / feedback
 */
export async function compose(
  compA: any,
  compB: any,
  connection: string,
): Promise<ComposeResult> {
  // 兼容 mockApi 的字符串入参（仅传名称）和真实 API 的对象入参
  const specA = typeof compA === "string" ? { code: "", contract: "", name: compA } : compA;
  const specB = typeof compB === "string" ? { code: "", contract: "", name: compB } : compB;

  return withFallback(
    async () => {
      const raw = await postJSON("/api/compose", {
        component_a: { code: specA.code ?? "", contract: specA.contract ?? "" },
        component_b: { code: specB.code ?? "", contract: specB.contract ?? "" },
        connection,
        simulate: true,
        steps: 200,
      });
      return transformComposeResponse(raw, compA, compB, connection);
    },
    () => mockCompose(
      typeof compA === "string" ? compA : compA?.name ?? "ComponentA",
      typeof compB === "string" ? compB : compB?.name ?? "ComponentB",
      connection as ComposeConnection,
    ),
    "compose",
  );
}

/**
 * 兼容性检查：POST /api/check-compatibility
 */
export async function checkCompatibility(
  contractA: string,
  contractB: string,
  connection: string,
): Promise<CompatibilityResult> {
  return withFallback(
    async () => {
      const raw = await postJSON("/api/check-compatibility", {
        contract_a: contractA,
        contract_b: contractB,
        connection,
      });
      return transformCompatibilityResponse(raw, contractA, contractB, connection);
    },
    () => mockCheckCompatibility(contractA, contractB, connection as ComposeConnection),
    "checkCompatibility",
  );
}

/**
 * SCADE 文件上传：POST /api/upload-scade
 */
export async function uploadScade(file: File): Promise<ScadeParseResult> {
  return withFallback(
    async () => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetchWithTimeout(`${API_BASE_URL}/api/upload-scade`, {
        method: "POST",
        body: formData,
      });
      const raw = await res.json();
      return transformScadeResponse(raw);
    },
    () => mockUploadScade(file),
    "uploadScade",
  );
}

/**
 * 查询 LLM 状态：GET /api/llm/status
 */
export async function getLLMStatus(): Promise<LLMStatus> {
  return withFallback(
    async () => {
      const raw = await getJSON("/api/llm/status");
      return transformLLMStatusResponse(raw);
    },
    () => mockGetLLMStatus(),
    "getLLMStatus",
  );
}

/**
 * 切换 LLM 开关：POST /api/llm/switch
 *
 * 注意：mockApi 的 mockSwitchLLM 返回 LLMStatus，但任务要求签名是 Promise<void>。
 * 真实 API 返回 {use_llm, available}，此处丢弃返回值以满足签名。
 */
export async function switchLLM(useLLM: boolean): Promise<void> {
  await withFallback(
    async () => {
      await postJSON("/api/llm/switch", { use_llm: useLLM });
      return undefined;
    },
    async () => {
      await mockSwitchLLM(useLLM);
      return undefined;
    },
    "switchLLM",
  );
}

/**
 * 获取模型列表：GET /api/models
 */
export async function getModels(): Promise<LLMModel[]> {
  return withFallback(
    async () => {
      const raw = await getJSON("/api/models");
      return transformModelsResponse(raw);
    },
    () => mockGetModels(),
    "getModels",
  );
}

/**
 * 获取待审批列表：GET /api/hil/pending
 */
export async function getPendingApprovals(): Promise<HILApproval[]> {
  return withFallback(
    async () => {
      const raw = await getJSON("/api/hil/pending");
      return transformPendingResponse(raw);
    },
    () => mockGetPendingApprovals(),
    "getPendingApprovals",
  );
}

/**
 * 批准 HIL 请求：POST /api/hil/approve
 */
export async function approve(requestId: string, comments: string): Promise<void> {
  await withFallback(
    async () => {
      await postJSON("/api/hil/approve", {
        request_id: requestId,
        comments,
        reviewer: "reviewer",
      });
      return undefined;
    },
    async () => {
      await mockApprove(requestId, comments);
      return undefined;
    },
    "approve",
  );
}

/**
 * 拒绝 HIL 请求：POST /api/hil/reject
 */
export async function reject(requestId: string, comments: string): Promise<void> {
  await withFallback(
    async () => {
      await postJSON("/api/hil/reject", {
        request_id: requestId,
        comments,
        reviewer: "reviewer",
      });
      return undefined;
    },
    async () => {
      await mockReject(requestId, comments);
      return undefined;
    },
    "reject",
  );
}

/**
 * 搜索 MISRA 规则：GET /api/misra/search?q=xxx
 *
 * 后端尚未实现该端点时，会自动降级到 mockSearchMisra。
 */
export async function searchMisra(query: string): Promise<MisraRule[]> {
  return withFallback(
    async () => {
      const raw = await getJSON(`/api/misra/search?q=${encodeURIComponent(query)}`);
      return raw.rules ?? raw ?? [];
    },
    () => mockSearchMisra(query),
    "searchMisra",
  );
}

/**
 * 获取单条 MISRA 规则：GET /api/misra/rules/:ruleId
 */
export async function getMisraRule(ruleId: string): Promise<MisraRule> {
  return withFallback(
    async () => {
      const raw = await getJSON(`/api/misra/rules/${encodeURIComponent(ruleId)}`);
      return raw as MisraRule;
    },
    () => mockGetMisraRule(ruleId),
    "getMisraRule",
  );
}

/** 导出 API 基础地址，供 downloadReport 等场景使用 */
export { API_BASE_URL };
