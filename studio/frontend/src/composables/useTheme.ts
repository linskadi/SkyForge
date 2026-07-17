import { ref, watchEffect } from "vue";

const isDark = ref(false);

function applyTheme(dark: boolean) {
	const root = document.documentElement;
	if (dark) {
		root.classList.add("dark");
	} else {
		root.classList.remove("dark");
	}
	localStorage.setItem("skyforge-theme", dark ? "dark" : "light");
}

/** 初始化主题：读取本地存储 > 系统偏好 */
function initTheme() {
	const saved = localStorage.getItem("skyforge-theme");
	if (saved === "dark" || saved === "light") {
		isDark.value = saved === "dark";
	} else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
		isDark.value = true;
	}
}

function toggleTheme() {
	isDark.value = !isDark.value;
}

export function useTheme() {
	initTheme();

	watchEffect(() => {
		applyTheme(isDark.value);
	});

	return { isDark, toggleTheme };
}
