/**
 * vite.config.js — Vite 构建配置
 * ================================
 * - vue 插件：支持 .vue 单文件组件
 * - 开发服务器端口：5173
 * - API 代理：/api 请求转发到 FastAPI 后端（localhost:8000）
 *   避免跨域问题，前端只需请求 /api/* 即可
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // FastAPI 后端地址
        changeOrigin: true,
      },
    },
  },
})
