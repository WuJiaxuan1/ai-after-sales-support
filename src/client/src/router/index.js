/**
 * router/index.js — Vue Router 路由配置
 * ========================================
 * 两个完全独立的视图：
 *   /user  → UserView（售后消费者端）
 *   /agent → AgentView（人工客服工作台）
 * 默认重定向到 /user。
 */
import { createRouter, createWebHistory } from 'vue-router'
import UserView from '../views/UserView.vue'
import AgentView from '../views/AgentView.vue'

const routes = [
  { path: '/', redirect: '/user' },
  {
    path: '/user',
    name: 'user',
    component: UserView,
    meta: { title: '用户端｜售后服务中心' },
  },
  {
    path: '/agent',
    name: 'agent',
    component: AgentView,
    meta: { title: '客服端｜人工客服工作台' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 让两个独立页面在浏览器标签页中也能明确区分角色。
// 这里只修改展示标题，不影响任何路由、Case 或 API 逻辑。
router.afterEach((to) => {
  document.title = to.meta.title || '售后服务中心'
})

export default router
