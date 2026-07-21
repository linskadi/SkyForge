<script setup lang="ts">
import {
	AlertTriangle,
	ArrowLeft,
	CheckCircle,
	Info,
	Search,
	X,
} from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getApi } from "@/services/apiSwitcher";
import type { MisraRule, RuleStandard } from "@/types/domain";

const router = useRouter();

const query = ref<string>("");
const results = ref<MisraRule[]>([]);
const loading = ref<boolean>(false);
const searched = ref<boolean>(false);
const expandedRule = ref<string | null>(null);

// 规则集列表与当前选中的规则集
const standards = ref<RuleStandard[]>([]);
const currentStandardId = ref<string>("misra_c_2012");
const standardsLoading = ref<boolean>(false);

// 各规则集的展示配置（placeholder / hint-tags / 标签）
interface StandardDisplayConfig {
	/** 搜索框 placeholder */
	placeholder: string;
	/** 空状态提示语 */
	emptyHint: string;
	/** 快捷搜索标签 */
	hintTags: string[];
}

const STANDARD_DISPLAY_CONFIG: Record<string, StandardDisplayConfig> = {
	misra_c_2012: {
		placeholder: "搜索 MISRA-C 规则 ID、标题或描述...",
		emptyHint: "输入关键词搜索 MISRA-C:2012 规则",
		hintTags: ["Rule 8.1", "初始化", "指针", "Required"],
	},
	jsf_av_cpp: {
		placeholder: "搜索 MISRA-C++ / JSF AV C++ 规则...",
		emptyHint: "输入关键词搜索 C++ 编码标准规则",
		hintTags: ["new/delete", "异常", "RAII", "Mandatory"],
	},
	python_safety: {
		placeholder: "搜索 Python 军工规范规则...",
		emptyHint: "输入关键词搜索 Python 军工软件编程规范",
		hintTags: ["eval", "exec", "global", "强制"],
	},
};

// 当前规则集的展示配置（带兜底）
const currentDisplayConfig = computed<StandardDisplayConfig>(() => {
	return (
		STANDARD_DISPLAY_CONFIG[currentStandardId.value] ??
		STANDARD_DISPLAY_CONFIG.misra_c_2012
	);
});

// 当前规则集的名称（用于标题区域）
const currentStandardName = computed<string>(() => {
	const std = standards.value.find((s) => s.id === currentStandardId.value);
	if (std) {
		const langLabel =
			std.language === "c"
				? "C 语言"
				: std.language === "cpp"
					? "C++ 语言"
					: "Python 语言";
		return `${std.name} (${langLabel})`;
	}
	return "MISRA-C:2012 (C 语言)";
});

const categoryColors: Record<
	string,
	{ bg: string; text: string; border: string }
> = {
	Mandatory: {
		bg: "bg-red-50",
		text: "text-red-700",
		border: "border-red-200",
	},
	Required: {
		bg: "bg-amber-50",
		text: "text-amber-700",
		border: "border-amber-200",
	},
	Advisory: {
		bg: "bg-blue-50",
		text: "text-blue-700",
		border: "border-blue-200",
	},
	// Python 军工规范使用中文分类
	必须: {
		bg: "bg-red-50",
		text: "text-red-700",
		border: "border-red-200",
	},
	要求: {
		bg: "bg-amber-50",
		text: "text-amber-700",
		border: "border-amber-200",
	},
	建议: {
		bg: "bg-blue-50",
		text: "text-blue-700",
		border: "border-blue-200",
	},
	强制: {
		bg: "bg-red-50",
		text: "text-red-700",
		border: "border-red-200",
	},
};

const categoryIcons: Record<string, typeof AlertTriangle> = {
	Mandatory: AlertTriangle,
	Required: Info,
	Advisory: CheckCircle,
	必须: AlertTriangle,
	要求: Info,
	建议: CheckCircle,
	强制: AlertTriangle,
};

// 获取分类样式（未命中时回退到灰色中性样式）
const getCategoryStyle = (category: string) => {
	return (
		categoryColors[category] ?? {
			bg: "bg-gray-50",
			text: "text-gray-700",
			border: "border-gray-200",
		}
	);
};

const getCategoryIcon = (category: string) => {
	return categoryIcons[category] ?? Info;
};

const onSearch = async () => {
	const q = query.value.trim();
	if (!q) return;
	loading.value = true;
	searched.value = true;
	expandedRule.value = null;
	try {
		results.value = await getApi().searchRules(q, currentStandardId.value);
	} catch {
		results.value = [];
	} finally {
		loading.value = false;
	}
};

const toggleExpand = (ruleId: string) => {
	expandedRule.value = expandedRule.value === ruleId ? null : ruleId;
};

const clearSearch = () => {
	query.value = "";
	results.value = [];
	searched.value = false;
	expandedRule.value = null;
};

// 切换规则集：清空当前搜索结果并重置状态
const onSwitchStandard = (standardId: string) => {
	if (standardId === currentStandardId.value) return;
	currentStandardId.value = standardId;
	clearSearch();
};

// 点击快捷标签搜索
const onHintTagClick = (tag: string) => {
	query.value = tag;
	onSearch();
};

// 页面挂载时加载规则集列表
onMounted(async () => {
	standardsLoading.value = true;
	try {
		standards.value = await getApi().getRuleStandards();
		// 若后端返回为空，回退到内置 3 个规则集
		if (standards.value.length === 0) {
			standards.value = [
				{
					id: "misra_c_2012",
					name: "MISRA-C:2012",
					language: "c",
					version: "2012",
				},
				{
					id: "jsf_av_cpp",
					name: "MISRA-C++ / JSF AV C++",
					language: "cpp",
					version: "2023",
				},
				{
					id: "python_safety",
					name: "Python 军工软件编程规范",
					language: "python",
					version: "2023",
				},
			];
		}
	} catch {
		// 加载失败时回退到内置规则集
		standards.value = [
			{
				id: "misra_c_2012",
				name: "MISRA-C:2012",
				language: "c",
				version: "2012",
			},
			{
				id: "jsf_av_cpp",
				name: "MISRA-C++ / JSF AV C++",
				language: "cpp",
				version: "2023",
			},
			{
				id: "python_safety",
				name: "Python 军工软件编程规范",
				language: "python",
				version: "2023",
			},
		];
	} finally {
		standardsLoading.value = false;
	}
});
</script>

<template>
  <div class="misra-page">
    <header class="page-header">
      <div class="title-area">
        <div class="title-row">
          <button class="back-btn" @click="router.push('/')" title="返回首页">
            <ArrowLeft class="icon" />
          </button>
          <h1 class="page-title">
            <Search class="title-icon" />
            规则实验室
          </h1>
        </div>
        <p class="subtitle">搜索和浏览多种编程语言的编码标准规则</p>
      </div>
    </header>

    <!-- 规则集切换器 -->
    <div class="standards-tabs">
      <button
        v-for="std in standards"
        :key="std.id"
        :class="['standard-tab', { active: std.id === currentStandardId }]"
        :disabled="standardsLoading"
        @click="onSwitchStandard(std.id)"
      >
        <span class="tab-name">{{ std.name }}</span>
        <span class="tab-lang">{{ std.language === 'c' ? 'C' : std.language === 'cpp' ? 'C++' : 'Python' }}</span>
      </button>
    </div>

    <div class="current-standard">{{ currentStandardName }}</div>

    <div class="search-bar">
      <div class="search-input-wrapper">
        <Search class="search-icon" />
        <input
          v-model="query"
          class="search-input"
          :placeholder="currentDisplayConfig.placeholder"
          @keydown.enter="onSearch"
        />
        <button v-if="query" class="clear-btn" @click="clearSearch">
          <X class="w-4 h-4" />
        </button>
      </div>
      <button class="search-btn" :disabled="!query.trim() || loading" @click="onSearch">
        {{ loading ? '搜索中...' : '搜索' }}
      </button>
    </div>

    <div v-if="!searched" class="empty-state">
      <Search class="w-12 h-12 text-muted-foreground/40" />
      <p class="text-muted-foreground">{{ currentDisplayConfig.emptyHint }}</p>
      <div class="hint-tags">
        <span
          v-for="tag in currentDisplayConfig.hintTags"
          :key="tag"
          class="hint-tag"
          @click="onHintTagClick(tag)"
        >{{ tag }}</span>
      </div>
    </div>

    <div v-else-if="loading" class="loading-state">
      <div class="loading-spinner" />
      <p>正在搜索...</p>
    </div>

    <div v-else-if="results.length === 0" class="empty-state">
      <Search class="w-12 h-12 text-muted-foreground/40" />
      <p class="text-muted-foreground">未找到匹配的规则</p>
    </div>

    <div v-else class="results-list">
      <div class="results-count">找到 {{ results.length }} 条规则</div>
      <div v-for="rule in results" :key="rule.rule_id" class="rule-card" @click="toggleExpand(rule.rule_id)">
        <div class="rule-header">
          <div class="rule-id-badge">{{ rule.rule_id }}</div>
          <div class="rule-title">{{ rule.title }}</div>
          <span class="category-badge" :class="[getCategoryStyle(rule.category).bg, getCategoryStyle(rule.category).text, getCategoryStyle(rule.category).border]">
            <component :is="getCategoryIcon(rule.category)" class="w-3 h-3" />
            {{ rule.category }}
          </span>
          <span v-if="rule.section" class="section-text">{{ rule.section }}</span>
        </div>
        <p class="rule-desc">{{ rule.description }}</p>

        <div v-if="expandedRule === rule.rule_id" class="rule-detail" @click.stop>
          <div v-if="rule.bad_example" class="example-block bad">
            <div class="example-label">违规示例</div>
            <pre class="example-code">{{ rule.bad_example }}</pre>
          </div>
          <div v-if="rule.good_example" class="example-block good">
            <div class="example-label">合规示例</div>
            <pre class="example-code">{{ rule.good_example }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.misra-page {
  max-width: 100%;
  margin: 0 auto;
  padding: 24px 32px 64px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.page-header { padding-bottom: 8px; border-bottom: 1px solid hsl(var(--border)); }
.title-area { display: flex; flex-direction: column; gap: 4px; }
.title-row { display: flex; align-items: center; gap: 12px; }
.back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--card));
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.back-btn:hover {
  border-color: hsl(220, 70%, 50%);
  color: hsl(220, 70%, 50%);
  background: hsla(220, 70%, 50%, 0.05);
}
.back-btn .icon { width: 16px; height: 16px; }
.page-title { font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.title-icon { width: 22px; height: 22px; color: hsl(260, 60%, 55%); }
.subtitle { margin: 4px 0 0; font-size: 13px; color: hsl(var(--muted-foreground)); }

/* 规则集切换器 */
.standards-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 4px;
}
.standard-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
  background: hsl(var(--background));
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.standard-tab:hover {
  border-color: hsl(260, 60%, 55%);
  color: hsl(260, 60%, 55%);
  background: hsla(260, 60%, 55%, 0.05);
}
.standard-tab.active {
  border-color: hsl(260, 60%, 55%);
  background: hsl(260, 60%, 55%);
  color: #fff;
}
.standard-tab:disabled { opacity: 0.5; cursor: not-allowed; }
.tab-name { font-weight: 600; }
.tab-lang {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: hsla(0, 0%, 0%, 0.1);
}
.standard-tab.active .tab-lang {
  background: hsla(0, 0%, 100%, 0.25);
}

.current-standard {
  font-size: 13px;
  color: hsl(var(--muted-foreground));
  padding: 4px 0 0;
}

.search-bar { display: flex; gap: 8px; }
.search-input-wrapper {
  flex: 1; position: relative; display: flex; align-items: center;
}
.search-icon { position: absolute; left: 12px; width: 16px; height: 16px; color: hsl(var(--muted-foreground)); }
.search-input {
  width: 100%; padding: 10px 36px 10px 36px; border: 1px solid hsl(var(--border));
  border-radius: 8px; font-size: 14px; background: hsl(var(--background));
  color: hsl(var(--foreground)); outline: none; transition: border-color 0.15s;
}
.search-input:focus { border-color: hsl(260, 60%, 55%); box-shadow: 0 0 0 2px hsla(260, 60%, 55%, 0.15); }
.clear-btn {
  position: absolute; right: 8px; display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border: none; background: transparent; color: hsl(var(--muted-foreground));
  cursor: pointer; border-radius: 4px;
}
.clear-btn:hover { background: hsl(var(--secondary)); }
.search-btn {
  padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;
  background: hsl(260, 60%, 55%); color: #fff; cursor: pointer; white-space: nowrap;
  transition: all 0.15s;
}
.search-btn:hover { background: hsl(260, 60%, 48%); }
.search-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.empty-state, .loading-state {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 64px 16px; color: hsl(var(--muted-foreground)); text-align: center;
}
.hint-tags { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
.hint-tag {
  padding: 4px 12px; border: 1px solid hsl(var(--border)); border-radius: 16px;
  font-size: 12px; cursor: pointer; transition: all 0.15s; background: hsl(var(--background));
}
.hint-tag:hover { border-color: hsl(260, 60%, 55%); background: hsla(260, 60%, 55%, 0.05); }
.loading-spinner {
  width: 32px; height: 32px; border: 3px solid hsl(var(--border));
  border-top-color: hsl(260, 60%, 55%); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.results-count { font-size: 13px; color: hsl(var(--muted-foreground)); }
.results-list { display: flex; flex-direction: column; gap: 12px; }
.rule-card {
  border: 1px solid hsl(var(--border)); border-radius: 10px; padding: 16px;
  cursor: pointer; transition: all 0.15s; background: hsl(var(--background));
}
.rule-card:hover { border-color: hsl(260, 60%, 55%); box-shadow: 0 2px 8px hsla(260, 60%, 55%, 0.08); }
.rule-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rule-id-badge {
  font-family: 'Consolas', monospace; font-size: 12px; font-weight: 700;
  padding: 3px 8px; border-radius: 4px; background: #0F1623; color: #F0F4F8;
}
.rule-title { font-size: 15px; font-weight: 600; flex: 1; }
.category-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; font-size: 11px; font-weight: 600; border-radius: 4px; border: 1px solid;
}
.section-text { font-size: 11px; color: hsl(var(--muted-foreground)); }
.rule-desc { margin: 8px 0 0; font-size: 13px; line-height: 1.6; color: hsl(var(--muted-foreground)); }

.rule-detail { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.example-block { border-radius: 6px; overflow: hidden; border: 1px solid; }
.example-block.bad { border-color: #fca5a5; background: #fef2f2; }
.example-block.good { border-color: #86efac; background: #f0fdf4; }
.example-label {
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
  padding: 4px 10px;
}
.example-block.bad .example-label { color: #991b1b; background: #fee2e2; }
.example-block.good .example-label { color: #166534; background: #dcfce7; }
.example-code {
  margin: 0; padding: 10px 12px; font-family: 'Consolas', monospace; font-size: 12px;
  line-height: 1.5; white-space: pre-wrap; word-break: break-all;
}
</style>
