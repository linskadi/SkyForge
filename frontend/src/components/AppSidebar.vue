<script setup lang="ts">
import {
	BILLBILL,
	DISCORD,
	GITHUB_LINK,
	QQ_GROUP,
	TWITTER,
	XHS,
} from "@/utils/const";
import NavUser from "./NavUser.vue";
import { useTheme } from "@/composables/useTheme";
import { Moon, Sun } from "lucide-vue-next";

import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	type SidebarProps,
	SidebarRail,
} from "@/components/ui/sidebar";

// ---- Props ----

const props = defineProps<SidebarProps>();
const { isDark, toggleTheme } = useTheme();

// ---- Reactive State ----

/** 导航菜单数据 */
const data = {
	navMain: [
		{
			title: "SkyForge 天锻",
			url: "#",
			items: [
				{
					title: "生成代码",
					url: "/generate",
					isActive: false,
				},
				{
					title: "组合验证",
					url: "/compose",
					isActive: false,
				},
				{
					title: "HIL 审批",
					url: "/hil",
					isActive: false,
				},
			],
		},
	],
};

const socialMedia = [
	{
		name: "QQ",
		url: QQ_GROUP,
		icon: "/qq.svg",
	},
	{
		name: "Twitter",
		url: TWITTER,
		icon: "/twitter.svg",
	},
	{
		name: "GitHub",
		url: GITHUB_LINK,
		icon: "/github.svg",
	},
	{
		name: "哔哩哔哩",
		url: BILLBILL,
		icon: "/bilibili.svg",
	},
	{
		name: "小红书",
		url: XHS,
		icon: "/xiaohongshu.svg",
	},
	{
		name: "Discord",
		url: DISCORD,
		icon: "/discord.svg",
	},
];
</script>

<template>
  <Sidebar v-bind="props">
    <SidebarHeader>
      <!-- 图标 -->
      <div class="flex items-center gap-2 h-15">
        <router-link to="/" class="flex items-center gap-2">
          <img src="@/assets/icon.png" alt="logo" class="w-10 h-10">
          <div class="text-lg font-bold">SkyForge</div>
        </router-link>
      </div>
    </SidebarHeader>
    <SidebarContent>
      <SidebarGroup v-for="item in data.navMain" :key="item.title">
        <SidebarGroupLabel>{{ item.title }}</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="childItem in item.items" :key="childItem.title">
              <SidebarMenuButton as-child :is-active="childItem.isActive">
                <!-- 仅对以 / 开头的内部路由使用 router-link，避免整页刷新 -->
                <router-link v-if="childItem.url.startsWith('/')" :to="childItem.url">
                  {{ childItem.title }}
                </router-link>
                <a v-else :href="childItem.url">{{ childItem.title }}</a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
    <SidebarRail />
    <SidebarFooter>
      <NavUser />
    </SidebarFooter>
    <SidebarFooter>
      <!-- 主题切换 + 社交媒体图标 -->
      <div class="flex items-center gap-3 justify-center mb-4 border-t border-border pt-3">
        <button
          @click="toggleTheme"
          class="p-2 rounded-lg hover:bg-accent transition-colors"
          :title="isDark ? '切换亮色模式' : '切换深色模式'"
        >
          <Sun v-if="isDark" class="w-4 h-4 text-accent" />
          <Moon v-else class="w-4 h-4 text-muted-foreground" />
        </button>
        <a v-for="item in socialMedia" :key="item.url" :href="item.url" target="_blank">
          <img :src="item.icon" :alt="item.name" width="24" height="24" class="icon">
        </a>
      </div>
    </SidebarFooter>
  </Sidebar>
</template>