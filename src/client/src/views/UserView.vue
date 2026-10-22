<!--
  UserView.vue — 用户售后端视图
  ================================
  售后消费者的完整交互界面，包含：
    1. 欢迎页：开始售后入口
    2. Workflow 按钮：人工预设的固定决策树（问题分类、子类、安全检查、诉求确认）
    3. 自由文本旁路：用户可直接描述问题，AI 映射到已有选项
    4. AI 排查阶段：基于 RAG 知识的问答排查
    5. 转人工后的实时聊天：用户与人工客服双向通信（2秒轮询）
    6. 解决/未解决反馈：用户确认排查结果

  状态由 stores/case.js (Pinia) 管理，API 调用通过 api/index.js 发起。
-->
<template>
  <div class="user-app">
    <!-- ── Header ──────────────────────────────────────────────── -->
    <header class="user-header">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-icon">🛒</span>
          <span class="brand-text">售后服务中心</span>
        </div>
        <div class="header-meta">
          <span v-if="store.state === 'RESOLVED'" class="tag tag-resolved">✅ 服务完成</span>
          <span v-else-if="store.isHandoff" class="tag tag-human">👤 人工服务中</span>
          <span v-else class="tag">AI + 人工客服</span>
        </div>
      </div>
    </header>

    <!-- ── Body ────────────────────────────────────────────────── -->
    <main class="user-body">
      <!-- Step indicator -->
      <div v-if="store.caseId && !store.isHandoff" class="step-bar">
        <div class="step" :class="{ active: !store.isTerminal, done: store.isTerminal }">
          <span class="step-num">1</span><span class="step-label">问题分类</span>
        </div>
        <div class="step-line" :class="{ done: store.isTerminal }"></div>
        <div class="step" :class="{ active: store.isRAGService }">
          <span class="step-num">2</span><span class="step-label">AI 排查</span>
        </div>
        <div class="step-line"></div>
        <div class="step">
          <span class="step-num">3</span><span class="step-label">解决 / 转人工</span>
        </div>
      </div>

      <!-- Welcome card -->
      <div v-if="!store.caseId" class="welcome-card">
        <div class="welcome-icon">👋</div>
        <h1>欢迎使用售后服务中心</h1>
        <p class="welcome-desc">我们将帮您快速解决商品使用、退换货、维修等问题。</p>
        <button class="btn-start" @click="store.initCase()" :disabled="store.loading">
          <span>开始售后服务</span><span class="arrow">→</span>
        </button>
      </div>

      <!-- Working area -->
      <div v-if="store.caseId" class="work-area">
        <div v-if="store.isWorkflow && store.previousNodeId" class="workflow-back">
          <button
            class="btn-back"
            @click="store.goBackOneLevel()"
            :disabled="store.loading"
          >
            ← 返回上一级
          </button>
        </div>

        <div v-if="store.issuePath.length" class="breadcrumb">
          <span class="bc-item" v-for="(p, i) in store.issuePath" :key="i">
            {{ p }}
            <span v-if="i < store.issuePath.length - 1" class="bc-sep"> › </span>
          </span>
        </div>

        <!-- Chat panel (pre-handoff) -->
        <ChatPanel v-if="!store.isHandoff" />

        <!-- Stage 1: Workflow buttons -->
        <div v-if="store.isWorkflow && store.currentNode" class="stage-card">
          <p class="stage-question">{{ store.currentNode.question }}</p>
          <div class="option-grid">
            <button v-for="opt in store.currentNode.options" :key="opt.option_id"
              class="btn-option" :class="{ 'btn-other': opt.label === '其他' }"
              @click="store.selectOption(opt.option_id)" :disabled="store.loading">
              {{ opt.label }}
            </button>
          </div>
          <div class="free-text-area">
            <p class="area-label">没有合适的选项？直接描述您的情况：</p>
            <!-- 情绪检测：转人工/继续自助选择卡片 -->
            <div v-if="store.emotionDetected" class="emotion-card">
              <p class="ec-text">我们理解您的不满，您希望如何处理？</p>
              <div class="ec-actions">
                <button class="btn-confirm-handoff" @click="store.requestHumanHandoff(); store.emotionDetected = false">
                  👤 转人工客服
                </button>
                <button class="btn-continue-ai" @click="store.emotionDetected = false">
                  继续自助服务
                </button>
              </div>
            </div>
            <div class="input-row" v-else>
              <input v-model="freeText" placeholder="例如：鼠标左键点了没反应..."
                @keyup.enter="handleFreeText" :disabled="store.loading" />
              <button class="btn-send" @click="handleFreeText"
                :disabled="store.loading || !freeText.trim()">发送</button>
            </div>
          </div>
        </div>

        <!-- Mapping confirmation -->
        <MappingConfirm v-if="store.isMappingConfirming" />

        <!-- Stage 2: RAG AI service -->
        <div v-if="store.isRAGService" class="stage-card stage-rag">
          <div class="rag-header">
            <span class="rag-icon">🤖</span>
            <div>
              <p class="rag-title">AI 排查助手</p>
              <p class="rag-subtitle">请继续描述具体情况，AI 将基于知识库为您排查</p>
            </div>
          </div>
          <div class="input-row">
            <input v-model="ragText" placeholder="请描述具体情况..."
              @keyup.enter="handleRAGAsk" :disabled="store.loading" />
            <button class="btn-send" @click="handleRAGAsk"
              :disabled="store.loading || !ragText.trim()">发送</button>
          </div>
          <div class="rag-actions">
            <!-- AI 建议转人工确认卡片（中置信度） -->
            <div v-if="store.lastJudgment?.suggested_action === 'ASK_USER_CONFIRM' && store.lastJudgment?.need_human" class="judge-suggest-card">
              <p class="jsc-reason">💡 {{ store.lastJudgment.reason }}</p>
              <p class="jsc-conf">置信度: {{ Math.round(store.lastJudgment.confidence * 100) }}%</p>
              <div class="jsc-actions">
                <button class="btn-confirm-handoff" @click="store.requestHumanHandoff()">确认转人工</button>
                <button class="btn-continue-ai" @click="store.lastJudgment = null">继续 AI 排查</button>
              </div>
            </div>
            <button class="btn-resolved" @click="store.markResolved()" :disabled="store.loading">
              ✅ 问题已解决
            </button>
            <button class="btn-not-resolved" @click="store.markNotResolved()" :disabled="store.loading">
              ❌ 还没解决
            </button>
            <button class="btn-handoff-inline" @click="store.requestHumanHandoff()" :disabled="store.loading">
              👤 转人工客服
            </button>
          </div>
        </div>

        <!-- Resolved state -->
        <div v-if="store.state === 'RESOLVED'" class="stage-card stage-resolved">
          <div class="resolved-icon">✅</div>
          <h3>问题已解决</h3>
          <p class="resolved-desc">感谢您的反馈！如有其他问题，可随时重新开始。</p>
          <button class="btn-start-new" @click="store.initCase()">开始新的售后</button>
        </div>

        <!-- ═══════════════════════════════════════════════════════ -->
        <!-- Stage 3: LIVE CHAT with human agent                    -->
        <!-- ═══════════════════════════════════════════════════════ -->
        <div v-if="store.isHandoff" class="handoff-chat-section">
          <!-- Status banner -->
          <div class="handoff-status-bar">
            <div class="status-left">
              <span class="status-avatar">{{ store.state === 'RESOLVED' ? '✅' : '👤' }}</span>
              <div>
                <span class="status-title">{{ store.state === 'RESOLVED' ? '服务完成' : '人工客服' }}</span>
                <span class="status-desc" v-if="store.state === 'QUEUED'">排队等待中...</span>
                <span class="status-desc" v-else-if="store.state === 'ASSIGNED'">客服已接入，可以对话</span>
                <span class="status-desc" v-else-if="store.state === 'RESOLVED'">问题已解决</span>
              </div>
            </div>
            <span class="status-badge" :class="'sb-' + store.state">
              {{ {QUEUED:'排队中', ASSIGNED:'服务中', RESOLVED:'已解决', HANDOFF_CREATED:'已转接'}[store.state] || '已转接' }}
            </span>
          </div>

          <!-- Chat messages (live with agent) -->
          <div class="live-chat" ref="liveChatRef">
            <div v-for="(msg, i) in liveMessages" :key="i"
              class="lc-msg" :class="'lc-' + msg.role">
              <div class="lc-avatar">
                {{ msg.role === 'user' ? '🧑' : (msg.role === 'human_agent' ? '👤' : '⚙️') }}
              </div>
              <div class="lc-body">
                <span class="lc-name">{{ msg.sender_name || roleLabel(msg.role) }}</span>
                <div class="lc-bubble">{{ msg.content }}</div>
              </div>
            </div>
            <div v-if="liveMessages.length === 0" class="lc-empty">
              <span>正在连接人工客服，请稍候...</span>
            </div>
          </div>

          <!-- Message input (hidden when resolved) -->
          <div class="live-input" v-if="store.state !== 'RESOLVED'">
            <input v-model="liveText" placeholder="输入消息..."
              @keyup.enter="handleLiveSend" :disabled="liveSending" />
            <button class="btn-send" @click="handleLiveSend"
              :disabled="liveSending || !liveText.trim()">发送</button>
          </div>

          <!-- Agent resolved banner -->
          <div v-if="store.state === 'RESOLVED'" class="agent-resolved-banner">
            <div class="arb-icon">✅</div>
            <div class="arb-content">
              <p class="arb-title">人工客服已处理完毕</p>
              <p class="arb-desc">您的问题已被标记为解决，感谢使用售后服务。</p>
            </div>
            <button class="btn-start-new" @click="store.initCase()">开始新的售后</button>
          </div>
        </div>

        <!-- Floating handoff button -->
        <button v-if="store.isWorkflow" class="btn-float-handoff"
          @click="store.requestHumanHandoff()" :disabled="store.loading">
          👤 转人工
        </button>
      </div>
    </main>

    <footer class="user-footer">
      <span>售后服务系统 · 确定性 Workflow + 受限 AI + RAG + Human Handoff</span>
    </footer>
  </div>
</template>

<script setup>
/**
 * UserView 逻辑层
 * - store: Pinia 状态管理（Case 生命周期）
 * - freeText / ragText: 自由文本输入绑定
 * - liveMessages / liveText: 转人工后的实时聊天状态
 * - pollTimer: 消息轮询定时器（每2秒拉取新消息）
 */
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useCaseStore } from '../stores/case.js'
import * as api from '../api/index.js'
import ChatPanel from '../components/ChatPanel.vue'
import MappingConfirm from '../components/MappingConfirm.vue'

const store = useCaseStore()
const freeText = ref('')       // Workflow 阶段的自由文本输入
const ragText = ref('')        // AI 排查阶段的文本输入
const liveText = ref('')       // 转人工后的聊天输入
const liveMessages = ref([])   // 转人工后的消息列表
const liveSending = ref(false) // 发送中状态
const liveChatRef = ref(null)  // 聊天面板 DOM 引用（用于自动滚动）
let pollTimer = null           // 消息轮询定时器

/** 处理 Workflow 阶段的自由文本提交 */
function handleFreeText() {
  if (!freeText.value.trim()) return
  store.sendFreeText(freeText.value)
  freeText.value = ''
}
/** 处理 AI 排查阶段的文本提交 */
function handleRAGAsk() {
  if (!ragText.value.trim()) return
  store.askAIQuestion(ragText.value)
  ragText.value = ''
}

// ── Live chat with agent ──────────────────────────────────────────────

async function handleLiveSend() {
  if (!liveText.value.trim() || !store.caseId) return
  const text = liveText.value
  liveText.value = ''
  liveSending.value = true
  try {
    await api.sendMessage(store.caseId, 'user', text, '用户')
    await loadLiveMessages()
  } catch (e) { console.error(e) }
  finally { liveSending.value = false }
}

async function loadLiveMessages() {
  if (!store.caseId) return
  try {
    const res = await api.getMessages(store.caseId, 0)
    liveMessages.value = res.messages || []
    // Detect agent-side state changes (e.g. agent resolved the case)
    if (res.case_state === 'RESOLVED' && store.state !== 'RESOLVED') {
      store.state = 'RESOLVED'
    }
    await nextTick()
    if (liveChatRef.value) liveChatRef.value.scrollTop = liveChatRef.value.scrollHeight
  } catch (e) { console.error(e) }
}

function startPolling() {
  stopPolling()
  loadLiveMessages()
  pollTimer = setInterval(loadLiveMessages, 2000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// Watch for handoff → start polling
watch(() => store.isHandoff, (val) => {
  if (val) startPolling()
  else stopPolling()
})

// Also watch case state changes for polling lifecycle
watch(() => store.state, (val) => {
  if (val === 'RESOLVED') stopPolling()
})

onUnmounted(stopPolling)

function roleLabel(role) {
  return { user: '用户', human_agent: '人工客服', assistant: 'AI', system: '系统' }[role] || role
}
</script>

<style scoped>
.user-app { min-height: 100vh; display: flex; flex-direction: column; background: #f0f4f3; }

/* Header */
.user-header {
  background: linear-gradient(135deg, #0e7c7b 0%, #0a5b5a 100%);
  color: #fff; padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 800px; margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center; height: 56px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-icon { font-size: 24px; }
.brand-text { font-size: 18px; font-weight: 700; letter-spacing: 1px; }
.tag { font-size: 12px; background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 12px; }
.tag-human { background: rgba(255,255,255,0.35); font-weight: 600; }
.tag-resolved { background: rgba(39,174,96,0.8); font-weight: 600; }

/* Body */
.user-body { flex: 1; max-width: 800px; width: 100%; margin: 0 auto; padding: 20px 16px; }
.workflow-back {
  margin-bottom: 6px;
}

.btn-back {
  border: none;
  background: transparent;
  color: #0e7c7b;
  padding: 4px 0;
  font-size: 13px;
  cursor: pointer;
}

.btn-back:hover {
  text-decoration: underline;
}

.btn-back:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Step bar */
.step-bar { display: flex; align-items: center; justify-content: center; gap: 0; margin-bottom: 20px; }
.step { display: flex; align-items: center; gap: 6px; opacity: 0.4; transition: opacity 0.3s; }
.step.active, .step.done { opacity: 1; }
.step-num {
  width: 26px; height: 26px; border-radius: 50%; background: #ccc; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700;
}
.step.active .step-num { background: #0e7c7b; }
.step.done .step-num { background: #27ae60; }
.step-label { font-size: 13px; color: #555; }
.step-line { width: 40px; height: 2px; background: #ddd; margin: 0 8px; }
.step-line.done { background: #27ae60; }

/* Welcome */
.welcome-card {
  background: #fff; border-radius: 16px; padding: 60px 40px;
  text-align: center; box-shadow: 0 2px 16px rgba(0,0,0,0.06);
}
.welcome-icon { font-size: 48px; margin-bottom: 16px; }
.welcome-card h1 { font-size: 24px; color: #222; margin-bottom: 12px; }
.welcome-desc { color: #666; font-size: 15px; line-height: 1.7; max-width: 480px; margin: 0 auto 32px; }
.btn-start {
  display: inline-flex; align-items: center; gap: 8px;
  background: #0e7c7b; color: #fff; border: none; padding: 14px 40px; border-radius: 10px;
  font-size: 16px; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(14,124,123,0.3);
}
.btn-start:hover { background: #0a5b5a; transform: translateY(-1px); }
.btn-start:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.arrow { font-size: 20px; }

.breadcrumb { margin-bottom: 12px; font-size: 13px; color: #999; }
.bc-item { color: #666; }
.bc-sep { color: #ccc; margin: 0 2px; }

/* Stage cards */
.stage-card {
  background: #fff; border-radius: 12px; padding: 20px; margin-top: 16px;
  box-shadow: 0 1px 8px rgba(0,0,0,0.04);
}
.stage-question { font-size: 16px; font-weight: 600; color: #222; margin-bottom: 14px; }
.option-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
.btn-option {
  background: #f0f7f7; border: 1.5px solid #c8e0e0; padding: 11px 22px; border-radius: 10px;
  cursor: pointer; font-size: 14px; color: #222; transition: all 0.2s;
}
.btn-option:hover { background: #0e7c7b; color: #fff; border-color: #0e7c7b; }
.btn-option:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-other { border-style: dashed; color: #888; }

.free-text-area { border-top: 1px solid #eee; padding-top: 16px; }
.area-label { font-size: 13px; color: #999; margin-bottom: 8px; }
.input-row { display: flex; gap: 8px; }
.input-row input {
  flex: 1; padding: 11px 14px; border: 1.5px solid #ddd; border-radius: 10px;
  font-size: 14px; outline: none; transition: border-color 0.2s;
}
.input-row input:focus { border-color: #0e7c7b; }
.btn-send {
  background: #0e7c7b; color: #fff; border: none; padding: 11px 22px; border-radius: 10px;
  cursor: pointer; font-size: 14px; font-weight: 600;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }

.stage-rag { border-left: 4px solid #0e7c7b; }
.rag-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.rag-icon { font-size: 28px; }
.rag-title { font-size: 15px; font-weight: 700; color: #222; }
.rag-subtitle { font-size: 13px; color: #888; margin-top: 2px; }
.rag-actions {
  margin-top: 14px; padding-top: 14px; border-top: 1px solid #eee;
  display: flex; gap: 8px; flex-wrap: wrap;
}
.btn-resolved {
  background: #27ae60; color: #fff; border: none;
  padding: 9px 20px; border-radius: 10px; cursor: pointer;
  font-size: 14px; font-weight: 600;
}
.btn-resolved:hover { background: #1e8449; }
.btn-not-resolved {
  background: #fff; border: 1.5px solid #f39c12; color: #f39c12;
  padding: 9px 20px; border-radius: 10px; cursor: pointer; font-size: 14px;
}
.btn-not-resolved:hover { background: #f39c12; color: #fff; }
.btn-handoff-inline {
  background: #fff; border: 1.5px solid #e74c3c; color: #e74c3c;
  padding: 9px 22px; border-radius: 10px; cursor: pointer; font-size: 14px;
}
.btn-handoff-inline:hover { background: #e74c3c; color: #fff; }

/* AI 建议转人工确认卡片 */
.judge-suggest-card {
  background: #fff3cd; border: 1.5px solid #f39c12; border-radius: 10px;
  padding: 14px; margin-bottom: 10px;
}
.jsc-reason { font-size: 14px; color: #856404; margin-bottom: 6px; }
.jsc-conf { font-size: 12px; color: #999; margin-bottom: 10px; }
.jsc-actions { display: flex; gap: 8px; }
.btn-confirm-handoff {
  background: #f39c12; color: #fff; border: none;
  padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600;
}
.btn-continue-ai {
  background: #fff; color: #666; border: 1px solid #ddd;
  padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px;
}

/* 情绪检测卡片 */
.emotion-card {
  background: #fff3cd; border: 1.5px solid #f39c12; border-radius: 10px;
  padding: 16px; text-align: center;
}
.ec-text { font-size: 15px; color: #856404; margin-bottom: 12px; }
.ec-actions { display: flex; gap: 10px; justify-content: center; }

/* Resolved state */
.stage-resolved { text-align: center; padding: 48px 24px; border-left: 4px solid #27ae60; }
.resolved-icon { font-size: 48px; margin-bottom: 12px; }
.stage-resolved h3 { font-size: 20px; color: #222; margin-bottom: 8px; }
.resolved-desc { color: #666; margin-bottom: 20px; }
.btn-start-new {
  background: #0e7c7b; color: #fff; border: none;
  padding: 10px 28px; border-radius: 10px; cursor: pointer;
  font-size: 14px; font-weight: 600;
}

/* Agent resolved banner */
.agent-resolved-banner {
  display: flex; align-items: center; gap: 14px;
  padding: 16px 20px; background: #d4edda; border-top: 2px solid #27ae60;
}
.arb-icon { font-size: 32px; }
.arb-content { flex: 1; }
.arb-title { font-size: 15px; font-weight: 700; color: #155724; }
.arb-desc { font-size: 13px; color: #155724; opacity: 0.8; }

/* ════════════════════════════════════════════════════════════════ */
/* Live chat with human agent                                      */
/* ════════════════════════════════════════════════════════════════ */
.handoff-chat-section {
  background: #fff; border-radius: 12px; overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-top: 8px;
}

.handoff-status-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; background: #f8f9fa; border-bottom: 1px solid #eee;
}
.status-left { display: flex; align-items: center; gap: 10px; }
.status-avatar { font-size: 22px; }
.status-title { font-size: 15px; font-weight: 700; color: #222; display: block; }
.status-desc { font-size: 12px; color: #888; }
.status-badge {
  font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 12px;
}
.sb-QUEUED { background: #fff3cd; color: #856404; }
.sb-ASSIGNED { background: #d4edda; color: #155724; }
.sb-RESOLVED { background: #e8e8e8; color: #555; }
.sb-HANDOFF_CREATED { background: #fff3cd; color: #856404; }

.live-chat {
  height: 400px; overflow-y: auto; padding: 16px 20px;
  display: flex; flex-direction: column; gap: 12px;
  background: #fafbfc;
}
.lc-msg { display: flex; gap: 10px; }
.lc-msg.lc-user { flex-direction: row-reverse; }
.lc-avatar {
  width: 36px; height: 36px; border-radius: 50%; background: #e8e8e8;
  display: flex; align-items: center; justify-content: center; font-size: 18px;
  flex-shrink: 0;
}
.lc-body { max-width: 70%; }
.lc-msg.lc-user .lc-body { text-align: right; }
.lc-name { font-size: 12px; color: #999; display: block; margin-bottom: 3px; }
.lc-bubble {
  display: inline-block; padding: 10px 14px; border-radius: 12px;
  font-size: 14px; line-height: 1.5; word-break: break-word;
}
.lc-user .lc-bubble { background: #0e7c7b; color: #fff; border-bottom-right-radius: 4px; }
.lc-human_agent .lc-bubble { background: #fff; color: #333; border: 1px solid #e0e0e0; border-bottom-left-radius: 4px; }
.lc-system .lc-bubble { background: #fff3cd; color: #856404; font-size: 13px; }
.lc-assistant .lc-bubble { background: #e8f5e9; color: #333; }
.lc-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: #aaa; font-size: 14px;
}

.live-input {
  display: flex; gap: 8px; padding: 12px 20px;
  border-top: 1px solid #eee; background: #fff;
}
.live-input input {
  flex: 1; padding: 11px 14px; border: 1.5px solid #ddd; border-radius: 10px;
  font-size: 14px; outline: none;
}
.live-input input:focus { border-color: #0e7c7b; }

.btn-float-handoff {
  position: fixed; bottom: 28px; right: 28px;
  background: #e74c3c; color: #fff; border: none;
  padding: 14px 28px; border-radius: 28px; cursor: pointer;
  font-size: 14px; font-weight: 600;
  box-shadow: 0 4px 16px rgba(231,76,60,0.35); z-index: 50;
}

.user-footer {
  text-align: center; padding: 16px; font-size: 12px; color: #aaa;
  border-top: 1px solid #e8e8e8; background: #fff;
}
</style>
