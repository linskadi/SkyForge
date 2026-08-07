import { createPinia } from "pinia";
import { createApp } from "vue";
import "@/assets/style.css";
import "@/assets/styles/global.css";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import App from "@/App.vue";
import i18n from "@/i18n";
import { initLocale } from "@/i18n/useLocale";
import router from "@/router";

const keysToRemove = ["skyforge-task-history"];
for (const key of keysToRemove) {
	localStorage.removeItem(key);
}

const profileKey = "skyforge-execution-profile";
const saved = localStorage.getItem(profileKey);
if (saved === "demo" || (saved !== "cloud" && saved !== "local")) {
	localStorage.setItem(profileKey, "cloud");
}

initLocale();

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);
const app = createApp(App);

app.use(router);
app.use(pinia);
app.use(i18n);
app.mount("#app");
