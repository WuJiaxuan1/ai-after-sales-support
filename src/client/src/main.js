/**
 * main.js — Vue 应用入口
 * ========================
 * 创建 Vue 应用实例，注册 Pinia（状态管理）和 Vue Router（路由）。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router/index.js'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())  // 注册状态管理
app.use(router)         // 注册路由
app.mount('#app')       // 挂载到 DOM
