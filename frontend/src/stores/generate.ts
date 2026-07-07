/**
 * Generate 页面状态管理 Store
 * 支持导航离开后恢复生成状态
 */
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type {
  Contract,
  ContractCheckResult,
  SimulationResult,
  RepairIteration,
  GenerateResult,
} from "@/services/mockApi";

export const useGenerateStore = defineStore("generate", () => {
  // ---- State ----

  /** 当前需求文本 */
  const requirement = ref("");

  /** 是否正在生成 */
  const isGenerating = ref(false);

  /** 生成结果 */
  const generateResult = ref<GenerateResult | null>(null);

  /** 契约数据 */
  const contract = ref<Contract | null>(null);

  /** 生成的代码 */
  const generatedCode = ref("");

  /** 修复迭代历史 */
  const repairIterations = ref<RepairIteration[]>([]);

  /** 契约校验结果 */
  const contractCheckResult = ref<ContractCheckResult | null>(null);

  /** 仿真结果 */
  const simulationResult = ref<SimulationResult | null>(null);

  /** SCADE 文件 */
  const scadeFile = ref<File | null>(null);

  /** 当前活跃的 Agent */
  const activeAgent = ref<string | null>(null);

  /** 已完成的 Agent 列表 */
  const completedAgents = ref<string[]>([]);

  // ---- Computed ----

  /** 是否有生成结果 */
  const hasResult = computed(() => generateResult.value !== null);

  /** 合规检查通过率 */
  const complianceRate = computed(() => {
    if (!contractCheckResult.value) return null;
    return `${contractCheckResult.value.passed_count}/${contractCheckResult.value.total_count}`;
  });

  /** 数字孪生状态 */
  const twinStatus = computed(() => {
    if (!simulationResult.value) return "idle" as const;
    return simulationResult.value.passed ? ("passed" as const) : ("failed" as const);
  });

  // ---- Actions ----

  /** 设置需求文本 */
  function setRequirement(text: string) {
    requirement.value = text;
  }

  /** 开始生成 */
  function startGeneration() {
    isGenerating.value = true;
    generateResult.value = null;
    contract.value = null;
    generatedCode.value = "";
    repairIterations.value = [];
    contractCheckResult.value = null;
    simulationResult.value = null;
    activeAgent.value = "REQ-Parser";
    completedAgents.value = [];
  }

  /** 完成生成 */
  function completeGeneration(result: GenerateResult) {
    generateResult.value = result;
    isGenerating.value = false;
    activeAgent.value = null;
  }

  /** 更新 Agent 状态 */
  function updateAgentStatus(agent: string, status: "running" | "completed") {
    if (status === "running") {
      activeAgent.value = agent;
    } else if (status === "completed") {
      completedAgents.value.push(agent);
      activeAgent.value = null;
    }
  }

  /** 设置契约 */
  function setContract(data: Contract) {
    contract.value = data;
  }

  /** 设置代码 */
  function setCode(code: string) {
    generatedCode.value = code;
  }

  /** 添加修复迭代 */
  function addRepairIteration(iteration: RepairIteration) {
    repairIterations.value.push(iteration);
  }

  /** 设置契约校验结果 */
  function setContractCheckResult(result: ContractCheckResult) {
    contractCheckResult.value = result;
  }

  /** 设置仿真结果 */
  function setSimulationResult(result: SimulationResult) {
    simulationResult.value = result;
  }

  /** 设置 SCADE 文件 */
  function setScadeFile(file: File | null) {
    scadeFile.value = file;
  }

  /** 重置所有状态 */
  function reset() {
    requirement.value = "";
    isGenerating.value = false;
    generateResult.value = null;
    contract.value = null;
    generatedCode.value = "";
    repairIterations.value = [];
    contractCheckResult.value = null;
    simulationResult.value = null;
    scadeFile.value = null;
    activeAgent.value = null;
    completedAgents.value = [];
  }

  return {
    // State
    requirement,
    isGenerating,
    generateResult,
    contract,
    generatedCode,
    repairIterations,
    contractCheckResult,
    simulationResult,
    scadeFile,
    activeAgent,
    completedAgents,
    // Computed
    hasResult,
    complianceRate,
    twinStatus,
    // Actions
    setRequirement,
    startGeneration,
    completeGeneration,
    updateAgentStatus,
    setContract,
    setCode,
    addRepairIteration,
    setContractCheckResult,
    setSimulationResult,
    setScadeFile,
    reset,
  };
});
