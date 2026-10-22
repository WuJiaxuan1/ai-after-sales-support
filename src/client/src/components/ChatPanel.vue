<!--
  ChatPanel.vue — 对话面板组件
  ==============================
  用户售后端的对话消息展示区域（转人工前使用）。
  展示所有消息（用户、AI 回答、系统提示），自动滚动到最新消息。
  消息来源：stores/case.js 的 messages 数组。
  样式：用户消息靠右绿色气泡，AI/系统消息靠左。
-->
<template>
  <div class="chat-panel" ref="panelRef">
    <!-- 遍历消息列表，按角色应用不同样式 -->
    <div v-for="(msg, i) in store.messages" :key="i" class="chat-msg" :class="'chat-' + msg.role">
      <div class="msg-bubble">
        <span class="msg-content">
          <span v-if="msg.loading" class="loading-spinner" aria-hidden="true"></span>
          {{ msg.content }}
        </span>
        <span class="msg-time">{{ msg.time }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 监听消息列表变化，自动滚动到底部。
 * 确保用户始终看到最新消息。
 */
import { ref, watch, nextTick } from 'vue'
import { useCaseStore } from '../stores/case.js'

const store = useCaseStore()
const panelRef = ref(null)  // 面板 DOM 引用

// 消息数量变化时自动滚动到底部
watch(() => store.messages.map(m => `${m.content}|${m.loading}`).join('||'), async () => {
  await nextTick()
  if (panelRef.value) {
    panelRef.value.scrollTop = panelRef.value.scrollHeight
  }
})
</script>

<style scoped>
.chat-panel {
  /* 根据浏览器视口自适应聊天区高度，桌面端可稳定展示更多历史消息。 */
  height: clamp(380px, 48vh, 560px);
  max-height: none;
  overflow-y: auto;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  scroll-behavior: smooth;
}
.chat-msg { display: flex; }
.chat-user { justify-content: flex-end; }           /* 用户消息靠右 */
.chat-assistant, .chat-system { justify-content: flex-start; }  /* AI/系统消息靠左 */
.msg-bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  position: relative;
}
.chat-user .msg-bubble { background: #0e7c7b; color: #fff; border-bottom-right-radius: 4px; }
.chat-assistant .msg-bubble { background: #e8f5e9; color: #333; border-bottom-left-radius: 4px; }
.chat-system .msg-bubble { background: #fff3cd; color: #856404; font-size: 13px; text-align: center; max-width: 100%; }
.msg-time { display: block; font-size: 11px; opacity: 0.6; margin-top: 4px; }
.loading-spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  margin-right: 7px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  vertical-align: -2px;
  animation: spin 0.8s linear infinite;
  opacity: 0.7;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .chat-panel {
    height: 42vh;
    min-height: 300px;
  }
}
</style>
