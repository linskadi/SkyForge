import { createPinia } from "pinia";
import { createApp } from "vue";
import "@/assets/style.css";
import "@/assets/styles/global.css";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import App from "@/App.vue";
import router from "@/router";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);
const app = createApp(App);

app.use(router);
app.use(pinia);
app.mount("#app");
