<script setup lang="ts">
/**
 * MisraSearch MISRA-C 规则搜索组件
 *
 * - 搜索框：输入关键词（规则 ID / 标题 / 描述）
 * - 结果列表：每条结果显示规则 ID + 标题 + 描述 + 分类徽章
 * - 点击规则：展开详情（违规示例代码 + 合规示例代码）
 *
 * 通过 apiSwitcher 调用 searchMisra，支持 mock/真实 API 切换
 */
import { ref, computed, watch, nextTick, onBeforeUpdate } from "vue";
import {
  Search,
  ChevronDown,
  ChevronRight,
  BookOpen,
  XCircle,
  CheckCircle2,
  Loader2,
} from "lucide-vue-next";
import { useVirtualizer } from "@tanstack/vue-virtual";
import { Button } from "@/components/ui/button";
import { getApi } from "@/services/apiSwitcher";
import type { MisraRule } from "@/services/mockApi";

/** 搜索关键词 */
const query = ref<string>("");
/** 搜索结果列表 */
const results = ref<MisraRule[]>([]);
/** 加载状态 */
const loading = ref<boolean>(false);
/** 错误信息 */
const errorMsg = ref<string>("");
/** 当前展开的规则 ID */
const expandedId = ref<string>("");
/** 是否已执行过搜索（用于区分初始空状态） */
const hasSearched = ref<boolean>(false);

/** 防抖计时器 */
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** 执行搜索 */
const doSearch = async (q: string) => {
  loading.value = true;
  errorMsg.value = "";
  hasSearched.value = true;
  try {
    const res = await getApi().searchMisra(q);
    results.value = res;
  } catch (err) {
    console.error("[MisraSearch] 搜索失败：", err);
    errorMsg.value = err instanceof Error ? err.message : "搜索失败";
    results.value = [];
  } finally {
    loading.value = false;
  }
};

/** 输入变化时防抖触发搜索 */
const onInput = (e: Event) => {
  const value = (e.target as HTMLInputElement).value;
  query.value = value;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    doSearch(value);
  }, 350);
};

/** 点击搜索按钮立即搜索 */
const onSearch = () => {
  if (debounceTimer) clearTimeout(debounceTimer);
  doSearch(query.value);
};

/** 切换规则展开 */
const toggleExpand = (ruleId: string) => {
  if (expandedId.value === ruleId) {
    expandedId.value = "";
  } else {
    expandedId.value = ruleId;
  }
};

/** 分类徽章样式 */
const categoryClass = (cat: MisraRule["category"]): string => {
  return `cat-${cat.toLowerCase()}`;
};

/** 分类中文标签 */
const categoryLabel = (cat: MisraRule["category"]): string => {
  switch (cat) {
    case "Required":
      return "Required 必选";
    case "Mandatory":
      return "Mandatory 强制";
    case "Advisory":
      return "Advisory 建议";
    default:
      return cat;
  }
};

/** 结果数量文案 */
const resultCountText = computed(() => {
  if (!hasSearched.value) return "";
  if (results.value.length === 0) return "无匹配结果";
  return `找到 ${results.value.length} 条规则`;
});

/** 虚拟滚动容器引用 */
const ruleListRef = ref<HTMLDivElement | null>(null);

/** 每个 rule-item 的 DOM ref，用于动态测量高度 */
const itemRefs = ref<Map<string, HTMLDivElement>>(new Map());
const setItemRef = (el: HTMLDivElement | null, ruleId: string) => {
  if (el) itemRefs.value.set(ruleId, el);
  else itemRefs.value.delete(ruleId);
};

onBeforeUpdate(() => { itemRefs.value.clear(); });

/** 虚拟滚动（动态高度） */
const virtualizer = useVirtualizer({
  count: results.value.length,
  getScrollElement: () => ruleListRef.value,
  estimateSize: (i) => {
    const rule = results.value[i];
    if (!rule) return 120;
    // 展开项更高：header + description + detail(代码块)
    return expandedId.value === rule.rule_id ? 360 : 120;
  },
  overscan: 5,
  getItemKey: (i) => results.value[i]?.rule_id ?? String(i),
});

watch(results, () => {
  nextTick(() => {
    virtualizer.value.setOptions({
      ...virtualizer.value.options,
      count: results.value.length,
    });
  });
});

/** 展开/折叠时重新测量并更新 */
watch(expandedId, () => {
  nextTick(() => {
    virtualizer.value.measure();
  });
});
</script>

<template>
  <div class="misra-search">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <div class="input-wrap">
        <Search class="search-icon" />
        <input
          type="text"
          class="search-input"
          :value="query"
          @input="onInput"
          @keyup.enter="onSearch"
          placeholder="搜索 MISRA-C 规则：按规则 ID（如 8.1）、标题、关键词查询"
        />
      </div>
      <Button :disabled="loading" @click="onSearch">
        <Loader2 v-if="loading" class="animate-spin" />
        <Search v-else />
        搜索
      </Button>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-msg">
      <XCircle class="error-icon" />
      <span>{{ errorMsg }}</span>
    </div>

    <!-- 结果计数 -->
    <div v-if="resultCountText" class="result-count">
      <BookOpen class="count-icon" />
      {{ resultCountText }}
    </div>

    <!-- 结果列表（虚拟滚动） -->
    <div v-if="results.length > 0" ref="ruleListRef" class="rule-list">
      <div
        :style="{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }"
      >
        <div
          v-for="virtualRow in virtualizer.getVirtualItems()"
          :key="String(virtualRow.key)"
          :ref="(el) => setItemRef(el as HTMLDivElement, results[virtualRow.index].rule_id)"
          class="rule-item"
          :style="{
            position: 'absolute',
            top: `${virtualRow.start}px`,
            left: 0,
            right: 0,
          }"
        >
          <!-- 规则头部（点击展开） -->
          <div class="rule-header" @click="toggleExpand(results[virtualRow.index].rule_id)">
            <component
              :is="expandedId === results[virtualRow.index].rule_id ? ChevronDown : ChevronRight"
              class="chevron"
            />
            <code class="rule-id">{{ results[virtualRow.index].rule_id }}</code>
            <span class="rule-title">{{ results[virtualRow.index].title }}</span>
            <span :class="['category-badge', categoryClass(results[virtualRow.index].category)]">
              {{ categoryLabel(results[virtualRow.index].category) }}
            </span>
            <span v-if="results[virtualRow.index].section" class="rule-section">{{ results[virtualRow.index].section }}</span>
          </div>

          <!-- 规则描述 -->
          <div class="rule-description">
            {{ results[virtualRow.index].description }}
          </div>

          <!-- 展开后的示例代码 -->
          <div v-if="expandedId === results[virtualRow.index].rule_id" class="rule-detail">
            <div v-if="results[virtualRow.index].bad_example" class="example-block bad">
              <div class="example-label">
                <XCircle class="example-icon" />
                违规示例
              </div>
              <pre class="example-code">{{ results[virtualRow.index].bad_example }}</pre>
            </div>
            <div v-if="results[virtualRow.index].good_example" class="example-block good">
              <div class="example-label">
                <CheckCircle2 class="example-icon" />
                合规示例
              </div>
              <pre class="example-code">{{ results[virtualRow.index].good_example }}</pre>
            </div>
            <div v-if="!results[virtualRow.index].bad_example && !results[virtualRow.index].good_example" class="no-example">
              暂无示例代码
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="hasSearched && !loading && !errorMsg" class="empty-state">
      <BookOpen class="empty-icon" />
      <p>未找到匹配的 MISRA 规则</p>
      <p class="empty-hint">尝试搜索 "8.1"、"初始化"、"指针" 等关键词</p>
    </div>

    <!-- 初始状态提示 -->
    <div v-else-if="!hasSearched && !loading" class="initial-state">
      <BookOpen class="initial-icon" />
      <p>输入关键词搜索 MISRA-C 规则</p>
      <p class="initial-hint">支持规则 ID、标题、描述模糊匹配</p>
    </div>
  </div>
</template>

<style scoped>
.misra-search {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.input-wrap {
  position: relative;
  flex: 1;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--muted-foreground, #9ca3af);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 8px 12px 8px 34px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 6px;
  font-size: 13px;
  background: var(--background, #fff);
  color: var(--foreground, #1f2937);
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.search-input:focus {
  border-color: #16a34a;
  box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.15);
}

.result-count {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted-foreground, #6b7280);
  padding: 4px 0;
}

.count-icon {
  width: 14px;
  height: 14px;
  color: #16a34a;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 480px;
  overflow-y: auto;
}

.rule-item {
  border: 1px solid var(--border, #e5e7eb);
  border-left: 3px solid #16a34a;
  border-radius: 6px;
  background: var(--background, #fff);
  transition: box-shadow 0.15s;
}

.rule-item:hover {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  flex-wrap: wrap;
}

.chevron {
  width: 14px;
  height: 14px;
  color: var(--muted-foreground, #9ca3af);
  flex-shrink: 0;
}

.rule-id {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 11px;
  font-weight: 600;
  background: #1f2937;
  color: #fbbf24;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.rule-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--foreground, #1f2937);
  flex: 1;
  min-width: 0;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 600;
  border-radius: 10px;
  flex-shrink: 0;
}

.category-badge.cat-required {
  background: #dbeafe;
  color: #1d4ed8;
}

.category-badge.cat-mandatory {
  background: #fee2e2;
  color: #b91c1c;
}

.category-badge.cat-advisory {
  background: #fef3c7;
  color: #b45309;
}

.rule-section {
  font-size: 11px;
  color: var(--muted-foreground, #9ca3af);
  font-family: 'Consolas', 'Courier New', monospace;
}

.rule-description {
  padding: 0 12px 8px 34px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted-foreground, #4b5563);
}

.rule-detail {
  padding: 8px 12px 12px 34px;
  border-top: 1px dashed var(--border, #e5e7eb);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.example-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.example-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.example-block.bad .example-label {
  color: #b91c1c;
}

.example-block.good .example-label {
  color: #15803d;
}

.example-icon {
  width: 12px;
  height: 12px;
}

.example-code {
  margin: 0;
  padding: 8px 10px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
}

.no-example {
  font-size: 12px;
  color: var(--muted-foreground, #9ca3af);
  font-style: italic;
  padding: 4px 0;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #991b1b;
  font-size: 13px;
}

.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.empty-state,
.initial-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 32px 16px;
  color: var(--muted-foreground, #9ca3af);
  text-align: center;
  background: var(--secondary, #f9fafb);
  border-radius: 8px;
  border: 1px dashed var(--border, #d4d4d8);
}

.empty-icon,
.initial-icon {
  width: 32px;
  height: 32px;
  color: #9ca3af;
}

.empty-state p,
.initial-state p {
  margin: 0;
  font-size: 13px;
}

.empty-hint,
.initial-hint {
  font-size: 11px !important;
  color: var(--muted-foreground, #c4c4c8);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
