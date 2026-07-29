<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";

type SourceType = "observed" | "simulated" | "unavailable" | "failed";

interface Props {
	source: SourceType;
	label?: string;
	class?: string;
}

const props = withDefaults(defineProps<Props>(), {
	label: undefined,
	class: "",
});

const sourceConfig: Record<
	SourceType,
	{ defaultLabel: string; variant: string }
> = {
	observed: { defaultLabel: "实测", variant: "source-observed" },
	simulated: { defaultLabel: "模拟", variant: "source-simulated" },
	unavailable: { defaultLabel: "暂无", variant: "source-unavailable" },
	failed: { defaultLabel: "失败", variant: "source-failed" },
};

const displayLabel = computed(
	() => props.label ?? sourceConfig[props.source].defaultLabel,
);

const variantClass = computed(() => sourceConfig[props.source].variant);
</script>

<template>
	<span
		:class="
			cn(
				'source-badge inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors',
				variantClass,
				props.class,
			)
		"
	>
		<span class="source-dot" />
		{{ displayLabel }}
	</span>
</template>

<style scoped>
.source-badge {
	border-color: hsl(var(--border) / 0.8);
}

.source-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	display: inline-block;
}

.source-observed {
	background: hsl(var(--success) / 0.12);
	color: hsl(var(--success));
	border-color: hsl(var(--success) / 0.3);
}
.source-observed .source-dot {
	background: hsl(var(--success));
}

.source-simulated {
	background: hsl(var(--warning) / 0.12);
	color: hsl(var(--warning));
	border-color: hsl(var(--warning) / 0.3);
}
.source-simulated .source-dot {
	background: hsl(var(--warning));
}

.source-unavailable {
	background: hsl(var(--muted) / 0.8);
	color: hsl(var(--muted-foreground));
	border-color: hsl(var(--border));
}
.source-unavailable .source-dot {
	background: hsl(var(--muted-foreground));
}

.source-failed {
	background: hsl(var(--destructive) / 0.12);
	color: hsl(var(--destructive));
	border-color: hsl(var(--destructive) / 0.3);
}
.source-failed .source-dot {
	background: hsl(var(--destructive));
}
</style>
