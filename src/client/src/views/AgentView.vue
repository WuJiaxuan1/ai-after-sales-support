<!--
  AgentView.vue — 人工客服工作台
  =================================
  人工客服的独立操作界面，深色主题，左右分栏布局：
    左栏 — 优先级队列：按 P0>P1>P2>P3 排序，同级 FIFO
    右栏 — Case 详情：
      - Handoff Packet（核心问题、触发器、优先级、已确认事实、用户原话等）
      - 实时聊天（与用户双向通信，2秒轮询）
      - 审计日志（Case 完整演变记录）
      - 操作按钮（接单、标记解决）

  轮询机制：选中 Case 后每 2 秒拉取新消息，切换 Case 时重启轮询。
-->
<template>
  <div class="agent-app">
    <!-- ── Header ──────────────────────────────────────────────── -->
    <header class="agent-header">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-icon">🎧</span>
          <div class="brand-titles">
            <span class="brand-text">人工客服工作台</span>
            <span class="brand-sub">客服服务工作区</span>
          </div>
        </div>
        <div class="header-right">
          <span class="agent-id">AGENT-001</span>
          <span class="status-dot"></span>
          <span class="status-text">在线</span>
        </div>
      </div>
    </header>

    <main class="agent-body">
      <div class="agent-layout">
        <!-- ── Left: Queue panel ──────────────────────────────── -->
        <aside class="queue-panel">
          <div class="panel-header">
            <h3>待处理队列</h3>
            <div class="panel-actions">
              <span class="queue-count" v-if="queue.length">{{ queue.length }}</span>
              <button class="btn-icon" @click="loadQueue" :disabled="loading" title="刷新">⟳</button>
            </div>
          </div>

          <div v-if="queue.length === 0" class="empty-state">
            <span class="empty-icon">📭</span>
            <p>暂无待处理工单</p>
          </div>

          <div v-else class="queue-list">
            <div
              v-for="item in queue"
              :key="item.case_id"
              class="queue-card"
              :class="[
                'priority-' + item.priority,
                { selected: selectedCaseId === item.case_id }
              ]"
              @click="selectCase(item)"
            >
              <div class="card-top">
                <span class="priority-tag" :class="'p-' + item.priority">{{ item.priority }}</span>
                <span class="case-id">{{ item.case_id }}</span>
              </div>
              <p class="core-issue">{{ item.core_issue || '未明确' }}</p>
              <div class="card-bottom">
                <span class="time">{{ formatTime(item.queued_at) }}</span>
                <span v-if="item.missing_exposure_data" class="flag-missing">⚠ 金额待核验</span>
                <span v-else-if="item.verified_exposure_amount" class="amount">
                  ¥{{ item.verified_exposure_amount }}
                </span>
              </div>
            </div>
          </div>
        </aside>

        <!-- ── Right: Case detail ─────────────────────────────── -->
        <section class="detail-panel">

          <!-- Empty state -->
          <div v-if="!selectedCaseId" class="detail-empty">
            <span class="empty-icon">👈</span>
            <p>请从左侧队列中选择一个 Case</p>
          </div>

          <div v-else class="detail-content">
            <!-- Top bar -->
            <div class="detail-top-bar">
              <div class="detail-title">
                <span class="priority-tag" :class="'p-' + (packet?.priority || 'P3')">{{ packet?.priority || '-' }}</span>
                <h3>{{ selectedCaseId }}</h3>
                <span class="case-state-tag">{{ caseStateLabel }}</span>
              </div>
              <div class="detail-btns">
                <button class="btn-assign" @click="handleAssign" :disabled="assigning || caseState !== 'QUEUED'">
                  {{ caseState === 'ASSIGNED' ? '✓ 已接单' : '✓ 接单' }}
                </button>
                <button class="btn-resolve" @click="handleResolve"
                  :disabled="resolving || caseState !== 'ASSIGNED' || !hasAgentReply"
                  :title="resolveDisabledReason">
                  ✓ 标记解决
                </button>
              </div>
            </div>

            <!-- Packet card -->
            <div v-if="packet" class="packet-card">
              <div class="pkt-section">
                <h4>核心问题</h4>
                <p class="pkt-core">{{ packet.core_issue }}</p>
              </div>

              <div class="pkt-grid">
                <div class="pkt-cell">
                  <label>转人工原因</label>
                  <div>
                    <span class="trigger-tag">{{ triggerLabel(packet.handoff_trigger) }}</span>
                    <span class="trigger-desc">{{ packet.handoff_trigger_detail }}</span>
                  </div>
                </div>
                <div class="pkt-cell">
                  <label>优先级</label>
                  <div>
                    <span class="priority-tag" :class="'p-' + packet.priority">{{ packet.priority }}</span>
                    <span class="pkt-note">{{ priorityReasonLabel(packet.priority_reason) }}</span>
                  </div>
                </div>
                <div class="pkt-cell">
                  <label>问题路径</label>
                  <span>{{ (packet.issue_path || []).join(' › ') || '无' }}</span>
                </div>
                <div class="pkt-cell" v-if="packet.diagnosis">
                  <label>疑似判断</label>
                  <span>{{ packet.diagnosis }}</span>
                </div>
                <div class="pkt-cell" v-if="packet.user_intent">
                  <label>用户诉求</label>
                  <span class="intent-text">{{ packet.user_intent }}</span>
                </div>
              </div>

              <!-- Structured Handoff Judgment -->
              <div v-if="packet.handoff_judgment" class="judgment-panel">
                <div class="judgment-head">
                  <span class="judgment-title">AI 转人工判断</span>
                  <span class="judgment-result" :class="packet.handoff_judgment.need_human ? 'jr-human' : 'jr-continue'">
                    {{ packet.handoff_judgment.need_human ? '需要人工' : '可继续自动处理' }}
                  </span>
                </div>
                <div class="judgment-grid">
                  <div><label>判断类型</label><span>{{ reasonCodeLabel(packet.handoff_judgment.reason_code) }}</span></div>
                  <div><label>判断层级</label><span>{{ judgmentLayerLabel(packet.handoff_judgment.layer) }}</span></div>
                  <div><label>置信度</label><span>{{ formatConfidence(packet.handoff_judgment.confidence) }}</span></div>
                  <div v-if="packet.handoff_judgment.workflow_reachable !== null && packet.handoff_judgment.workflow_reachable !== undefined">
                    <label>流程可定位</label><span>{{ packet.handoff_judgment.workflow_reachable ? '是' : '否' }}</span>
                  </div>
                </div>
                <div class="judgment-reason">
                  <label>判断理由</label>
                  <p>{{ packet.handoff_judgment.reason || '无' }}</p>
                </div>
                <div v-if="packet.handoff_judgment.evidence?.length" class="judgment-evidence">
                  <label>判断依据</label>
                  <ul><li v-for="(e, i) in packet.handoff_judgment.evidence" :key="i">{{ e }}</li></ul>
                </div>
              </div>

              <div v-if="packet.safety_hazard_type" class="safety-panel">
                <strong>安全风险</strong>
                <span>{{ hazardTypeLabel(packet.safety_hazard_type) }}</span>
                <span class="safety-cert">{{ safetyCertaintyLabel(packet.safety_certainty) }}</span>
                <p v-if="packet.safety_evidence">依据：{{ packet.safety_evidence }}</p>
              </div>

              <div class="pkt-lists">
                <div class="pkt-list">
                  <label>已确认事实</label>
                  <ul v-if="packet.confirmed_facts?.length">
                    <li v-for="(f, i) in packet.confirmed_facts" :key="i">{{ f }}</li>
                  </ul>
                  <p v-else class="muted">无</p>
                </div>
                <div class="pkt-list">
                  <label>AI 已执行操作</label>
                  <ul v-if="packet.ai_actions?.length">
                    <li v-for="(a, i) in packet.ai_actions" :key="i">{{ a }}</li>
                  </ul>
                  <p v-else class="muted">无</p>
                </div>
                <div class="pkt-list">
                  <label>未确认信息</label>
                  <ul v-if="packet.unconfirmed_information?.length">
                    <li v-for="(u, i) in packet.unconfirmed_information" :key="i">{{ u }}</li>
                  </ul>
                  <p v-else class="muted">无</p>
                </div>
                <div class="pkt-list">
                  <label>关键用户原话</label>
                  <ul v-if="packet.key_quotes?.length">
                    <li v-for="(q, i) in packet.key_quotes" :key="i" class="quote">「{{ q }}」</li>
                  </ul>
                  <p v-else class="muted">无</p>
                </div>
              </div>

              <div class="pkt-exposure">
                <template v-if="packet.missing_exposure_data">
                  <span class="flag-missing">⚠ 金额数据缺失，需人工核验</span>
                </template>
                <template v-else-if="packet.verified_exposure_amount !== null">
                  <label>可验证经济暴露：</label>
                  <span class="amount">¥{{ packet.verified_exposure_amount }}</span>
                </template>
              </div>
            </div>

            <!-- Live Chat with User -->
            <div class="agent-chat-card">
              <h4>💬 与用户对话</h4>
              <div class="agent-chat-messages" ref="chatRef">
                <div v-for="(msg, i) in chatMessages" :key="i"
                  class="ac-msg" :class="'ac-' + msg.role">
                  <span class="ac-badge">{{ msg.sender_name || roleLabel(msg.role) }}</span>
                  <div class="ac-bubble">{{ msg.content }}</div>
                </div>
                <p v-if="!chatMessages.length" class="muted">暂无对话</p>
              </div>
              <div class="agent-chat-input">
                <input v-model="agentReplyText"
                  :placeholder="caseState === 'ASSIGNED' ? '输入回复...' : '请先接单后再回复用户'"
                  @keyup.enter="handleAgentReply" :disabled="replySending || caseState !== 'ASSIGNED'" />
                <button class="btn-reply" @click="handleAgentReply"
                  :disabled="replySending || caseState !== 'ASSIGNED' || !agentReplyText.trim()">发送</button>
              </div>
              <p v-if="caseState !== 'ASSIGNED'" class="chat-lock-hint">🔒 工单接单后才能向用户发送消息。</p>
              <p v-else-if="!hasAgentReply" class="chat-lock-hint">回复用户至少一次后，才可标记工单已解决。</p>
            </div>

            <!-- Audit log -->
            <div v-if="auditLog.length" class="audit-card">
              <h4>审计日志 <span class="audit-count">{{ auditLog.length }}</span></h4>
              <div class="audit-list">
                <div v-for="(evt, i) in auditLog" :key="i" class="audit-row">
                  <span class="audit-type">{{ auditEventLabel(evt.event_type) }}</span>
                  <span class="audit-actor">{{ actorLabel(evt.actor) }}</span>
                  <span class="audit-time">{{ formatTime(evt.created_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as api from '../api/index.js'

const queue = ref([])
const selectedCaseId = ref(null)
const packet = ref(null)
const conversation = ref(null)
const auditLog = ref([])
const loading = ref(false)
const assigning = ref(false)
const resolving = ref(false)
const caseState = ref(null)

// Agent chat
const chatMessages = ref([])
const agentReplyText = ref('')
const replySending = ref(false)
const chatRef = ref(null)
let chatPollTimer = null

const hasAgentReply = computed(() => chatMessages.value.some(m => m.role === 'human_agent'))
const caseStateLabel = computed(() => ({
  QUEUED: '待接单', ASSIGNED: '服务中', RESOLVED: '已解决'
}[caseState.value] || '未知状态'))
const resolveDisabledReason = computed(() => {
  if (caseState.value !== 'ASSIGNED') return '请先接单'
  if (!hasAgentReply.value) return '请至少回复用户一次'
  return ''
})

onMounted(loadQueue)
onUnmounted(stopChatPolling)

async function loadQueue() {
  loading.value = true
  try { queue.value = await api.getQueue() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function selectCase(item) {
  selectedCaseId.value = item.case_id
  caseState.value = 'QUEUED'
  try {
    const [pktRes, auditRes] = await Promise.all([
      api.getHandoffPacket(item.case_id),
      api.getAuditLog(item.case_id),
    ])
    packet.value = pktRes.packet
    conversation.value = pktRes.conversation
    auditLog.value = auditRes
    startChatPolling()
  } catch (e) { console.error(e) }
}

async function handleAssign() {
  assigning.value = true
  try {
    await api.assignCase(selectedCaseId.value, 'AGENT-001')
    caseState.value = 'ASSIGNED'
    await loadQueue()
    await loadChatMessages()
  } catch (e) { alert('接单失败: ' + e.message) }
  finally { assigning.value = false }
}

async function handleResolve() {
  resolving.value = true
  try {
    await api.resolveCase(selectedCaseId.value, 'AGENT-001', '已处理')
    stopChatPolling()
    await loadQueue()
    selectedCaseId.value = null
    packet.value = null
    conversation.value = null
    auditLog.value = []
    chatMessages.value = []
    caseState.value = null
    alert('已标记为解决')
  } catch (e) { alert('操作失败: ' + e.message) }
  finally { resolving.value = false }
}

async function handleAgentReply() {
  if (!agentReplyText.value.trim() || !selectedCaseId.value || caseState.value !== 'ASSIGNED') return
  const text = agentReplyText.value
  agentReplyText.value = ''
  replySending.value = true
  try {
    await api.sendMessage(selectedCaseId.value, 'human_agent', text, '人工客服')
    await loadChatMessages()
  } catch (e) { console.error(e) }
  finally { replySending.value = false }
}

async function loadChatMessages() {
  if (!selectedCaseId.value) return
  try {
    const res = await api.getMessages(selectedCaseId.value, 0)
    chatMessages.value = res.messages || []
    caseState.value = res.case_state || caseState.value
    await nextTick()
    if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
  } catch (e) { console.error(e) }
}

function startChatPolling() {
  stopChatPolling()
  loadChatMessages()
  chatPollTimer = setInterval(loadChatMessages, 2000)
}
function stopChatPolling() {
  if (chatPollTimer) { clearInterval(chatPollTimer); chatPollTimer = null }
}

function formatTime(t) {
  if (!t) return '-'
  // 后端 datetime.utcnow() 输出无时区后缀；补 Z 后按 UTC 解析，再转浏览器本地时区。
  const raw = String(t)
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw) ? raw : raw + 'Z'
  return new Date(normalized).toLocaleString('zh-CN', { hour12: false })
}
function formatConfidence(v) {
  const n = Number(v)
  return Number.isFinite(n) ? `${Math.round(n * 100)}%` : '-'
}
function judgmentLayerLabel(layer) {
  return { hard_rule: '确定性边界', ai_judge: 'AI 语义判断', deterministic_fallback: '系统兜底' }[layer] || layer || '-'
}
function triggerLabel(v) {
  return {
    SAFETY_RISK: '安全风险',
    AUTHORITY_BOUNDARY: '人工权限边界',
    USER_REQUEST: '用户主动请求人工',
    NO_MATCH_CONFIRMED: '无匹配选项并确认转人工',
    KNOWLEDGE_OR_CAPABILITY_GAP: '知识或能力不足',
    AUTOMATION_NO_PROGRESS: '自动排查无有效进展',
  }[v] || v || '-'
}
function reasonCodeLabel(v) {
  return {
    CONTINUE: '可继续自动处理',
    KNOWLEDGE_GAP: '知识依据不足',
    CAPABILITY_GAP: '系统能力不足',
    AUTHORITY_BOUNDARY: '人工权限边界',
    AUTOMATION_NO_PROGRESS: '自动排查无有效进展',
    OUT_OF_SCOPE: '超出当前服务范围',
    USER_REQUEST: '用户主动请求人工',
    SAFETY_RISK: '安全风险',
  }[v] || v || '-'
}
function hazardTypeLabel(v) {
  return {
    THERMAL_FIRE: '异常发热 / 火灾风险',
    ELECTRICAL: '电气 / 触电风险',
    EXPLOSION_PRESSURE: '爆炸 / 压力风险',
    CHEMICAL_TOXIC: '化学 / 有害物质风险',
    FOOD_INGESTION: '食品 / 摄入安全风险',
    ALLERGIC_IRRITATION: '过敏 / 刺激风险',
    MECHANICAL_INJURY: '机械 / 结构伤害风险',
    CHILD_CHOKING_ENTRAPMENT: '儿童误吞 / 窒息 / 卡困风险',
    BIOLOGICAL_CONTAMINATION: '卫生 / 生物污染风险',
    OTHER_SAFETY: '其他安全风险',
  }[v] || v || '-'
}
function safetyCertaintyLabel(v) {
  return { SUSPECTED: '疑似风险', CONFIRMED: '明确风险', NONE: '未发现风险' }[v] || v || '-'
}
function priorityReasonLabel(v) {
  if (!v) return '-'
  const text = String(v)
  if (text === 'Safety risk confirmed') return '安全风险触发，按最高优先级处理'
  if (text.includes('verified_exposure_amount missing')) return '缺少已核验经济暴露金额，暂按 P3 入队等待人工核验'
  const p1 = text.match(/amount ([\d.]+) >= P1 threshold ([\d.]+)/)
  if (p1) return `已核验经济暴露金额 ${p1[1]} 元达到 P1 阈值 ${p1[2]} 元`
  const p2 = text.match(/amount ([\d.]+) >= P2 threshold ([\d.]+)/)
  if (p2) return `已核验经济暴露金额 ${p2[1]} 元达到 P2 阈值 ${p2[2]} 元`
  const p3 = text.match(/amount ([\d.]+) < P2 threshold ([\d.]+)/)
  if (p3) return `已核验经济暴露金额 ${p3[1]} 元低于 P2 阈值 ${p3[2]} 元`
  return text
}
function auditEventLabel(v) {
  return {
    CASE_CREATED: '工单创建',
    USER_CLICKED_OPTION: '用户选择固定选项',
    USER_FREE_TEXT: '用户输入自由文本',
    MAPPING_PENDING_CONFIRMATION: 'AI 候选路径待确认',
    MAPPING_CONFIRMED: '用户确认候选路径',
    MAPPING_REJECTED: '用户否认候选路径',
    MAPPING_FAILED: '路径识别失败',
    RAG_RETRIEVED: '知识库检索',
    AI_JUDGMENT: 'AI 判断',
    USER_REQUEST_HANDOFF: '用户请求转人工',
    HANDOFF_CREATED: '人工工单创建',
    CASE_ASSIGNED: '客服接单',
    CASE_RESOLVED: '工单解决',
    AUTOMATION_NO_PROGRESS: '自动排查无进展',
  }[v] || v || '-'
}
function actorLabel(v) {
  return { user: '用户', ai: 'AI', system: '系统', human_agent: '人工客服' }[v] || v || '-'
}
function roleLabel(role) {
  return { user: '用户', assistant: 'AI', system: '系统', human_agent: '人工' }[role] || role
}
</script>

<style scoped>
/* ── Layout ───────────────────────────────────────────────── */
.agent-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1d23;
}

/* ── Header ───────────────────────────────────────────────── */
.agent-header {
  background: #22262e;
  color: #fff;
  padding: 0 24px;
  border-bottom: 1px solid #333;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 56px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-icon { font-size: 24px; }
.brand-titles { display: flex; flex-direction: column; }
.brand-text { font-size: 16px; font-weight: 700; }
.brand-sub { font-size: 11px; color: #b8c2cd; }
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.agent-id {
  font-size: 13px;
  background: #333;
  padding: 3px 10px;
  border-radius: 6px;
  color: #d7dde4;
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #27ae60;
}
.status-text { font-size: 13px; color: #27ae60; }

/* ── Body ─────────────────────────────────────────────────── */
.agent-body {
  flex: 1;
  padding: 16px;
}
.agent-layout {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
  min-height: calc(100vh - 88px);
}

/* ── Queue panel (left) ───────────────────────────────────── */
.queue-panel {
  background: #22262e;
  border-radius: 12px;
  padding: 16px;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.panel-header h3 {
  font-size: 14px;
  color: #d7dde4;
  font-weight: 600;
}
.panel-actions { display: flex; align-items: center; gap: 8px; }
.queue-count {
  background: #e74c3c;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 10px;
}
.btn-icon {
  background: none;
  border: 1px solid #444;
  color: #aaa;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
}
.btn-icon:hover { background: #333; }

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #aab4bf;
}
.empty-icon { font-size: 32px; display: block; margin-bottom: 8px; }

.queue-list { display: flex; flex-direction: column; gap: 8px; }
.queue-card {
  background: #2a2e36;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 4px solid transparent;
}
.queue-card:hover { background: #303540; }
.queue-card.selected { border-color: #0e7c7b; background: #2a3a3a; }
.queue-card.priority-P0 { border-left-color: #e74c3c; }
.queue-card.priority-P1 { border-left-color: #f39c12; }
.queue-card.priority-P2 { border-left-color: #3498db; }
.queue-card.priority-P3 { border-left-color: #555; }
.card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.case-id { font-size: 12px; color: #b7c1cc; }
.core-issue {
  font-size: 13px;
  color: #f0f3f6;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}
.time { color: #a7b1bc; }

/* ── Priority tags ────────────────────────────────────────── */
.priority-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  color: #fff;
  display: inline-block;
}
.p-P0 { background: #e74c3c; }
.p-P1 { background: #f39c12; }
.p-P2 { background: #3498db; }
.p-P3 { background: #555; }

/* ── Detail panel (right) ─────────────────────────────────── */
.detail-panel {
  background: #22262e;
  border-radius: 12px;
  padding: 20px;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}
.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #9da8b5;
}

/* ── Detail top bar ───────────────────────────────────────── */
.detail-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #333;
}
.detail-title { display: flex; align-items: center; gap: 10px; }
.detail-title h3 { font-size: 15px; color: #f2f5f7; }
.detail-btns { display: flex; gap: 8px; }
.btn-assign {
  background: #0e7c7b;
  color: #fff;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.btn-assign:hover { background: #0a5b5a; }
.btn-resolve {
  background: #27ae60;
  color: #fff;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.btn-resolve:hover { background: #1e8449; }

/* ── Agent state / Handoff Judge ─────────────────────────── */

.case-state-tag {
  font-size: 11px; color: #9edbd8; border: 1px solid #365d5c;
  padding: 2px 7px; border-radius: 999px;
}
.btn-assign:disabled, .btn-resolve:disabled { opacity: 0.45; cursor: not-allowed; }
.judgment-panel {
  background: #20252c; border: 1px solid #3a4653; border-radius: 9px;
  padding: 12px; margin: 12px 0 14px;
}
.judgment-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.judgment-title { color: #eee; font-size: 13px; font-weight: 700; }
.judgment-result { font-size: 11px; padding: 3px 8px; border-radius: 999px; font-weight: 700; }
.jr-human { background: #5c2b2b; color: #ffb3aa; }
.jr-continue { background: #214b3a; color: #9fe0bd; }
.judgment-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
.judgment-grid div { background: #272d35; border-radius: 6px; padding: 8px; }
.judgment-panel label { display: block; color: #aeb8c4; font-size: 10px; margin-bottom: 3px; }
.judgment-grid span, .judgment-reason p, .judgment-evidence li { color: #edf1f5; font-size: 12px; }
.judgment-reason { margin-bottom: 8px; }
.judgment-reason p { margin: 0; line-height: 1.5; }
.judgment-evidence ul { margin: 0; padding-left: 18px; }
.safety-panel {
  margin: 0 0 14px; padding: 10px 12px; border-radius: 8px;
  border: 1px solid #7a3b32; background: #352422; color: #f0b3a9; font-size: 12px;
}
.safety-panel strong { margin-right: 10px; }
.safety-cert { margin-left: 8px; padding: 2px 6px; background: #6b332d; border-radius: 4px; }
.safety-panel p { margin: 6px 0 0; color: #f0b8ae; }
.chat-lock-hint { margin: 8px 0 0; color: #adb7c2; font-size: 11px; }

/* ── Packet card ──────────────────────────────────────────── */
.packet-card {
  background: #2a2e36;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.pkt-section { margin-bottom: 14px; }
.pkt-section h4, .conv-card h4, .audit-card h4 {
  font-size: 12px;
  color: #c1cad4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.pkt-core { font-size: 15px; color: #eee; font-weight: 600; }

.pkt-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.pkt-cell label {
  display: block;
  font-size: 11px;
  color: #b8c2cd;
  margin-bottom: 4px;
}
.pkt-cell span, .pkt-cell div { font-size: 13px; color: #e7ebef; }
.pkt-note { font-size: 11px; color: #aeb8c3; margin-left: 6px; }
.trigger-tag {
  background: #e74c3c;
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 6px;
}
.trigger-desc { font-size: 12px; color: #c8d0d8; }
.intent-text { color: #f39c12; font-weight: 600; }

.pkt-lists {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.pkt-list label {
  display: block;
  font-size: 11px;
  color: #b8c2cd;
  margin-bottom: 4px;
}
.pkt-list ul { margin: 0; padding-left: 16px; }
.pkt-list li { font-size: 13px; color: #e7ebef; margin-bottom: 2px; }
.pkt-list li.quote { color: #d4dae0; font-style: italic; }
.muted { color: #9ea9b5; font-size: 13px; }

.pkt-exposure {
  padding-top: 10px;
  border-top: 1px solid #333;
}
.pkt-exposure label {
  color: #e1e7ec;
  font-size: 13px;
  font-weight: 600;
}
.flag-missing { color: #ff6b5f; font-weight: 600; font-size: 13px; }
.amount { color: #55d88a; font-weight: 700; font-size: 15px; }

/* ── Conversation card ────────────────────────────────────── */
.conv-card {
  background: #2a2e36;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.msg-list { display: flex; flex-direction: column; gap: 6px; }
.msg {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
}
.msg-user { background: #1a3a3a; }
.msg-assistant { background: #1a2a1a; }
.msg-system { background: #3a3a1a; }
.msg-badge {
  font-size: 11px;
  color: #b8c2cd;
  min-width: 36px;
  padding-top: 2px;
}
.msg-text { color: #e7ebef; line-height: 1.5; flex: 1; }

/* ── Audit card ───────────────────────────────────────────── */
.audit-card {
  background: #2a2e36;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 16px;
}
.audit-count {
  background: #333;
  color: #d4dbe2;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 6px;
  margin-left: 6px;
}
.audit-list { font-size: 12px; }
.audit-row {
  display: flex;
  gap: 12px;
  padding: 5px 0;
  border-bottom: 1px solid #2a2e36;
}
.audit-type { color: #55d4d0; font-weight: 600; min-width: 220px; }
.audit-actor { color: #b8c2cd; min-width: 80px; }
.audit-time { color: #9faab6; }

/* ── Agent chat ────────────────────────────────────────────── */
.agent-chat-card {
  background: #2a2e36;
  border: 1px solid #333;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.agent-chat-card h4 {
  font-size: 12px;
  color: #c1cad4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}
.agent-chat-messages {
  height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
  margin-bottom: 10px;
}
.ac-msg { display: flex; gap: 8px; }
.ac-msg.ac-user { flex-direction: row-reverse; }
.ac-badge {
  font-size: 11px;
  color: #b8c2cd;
  min-width: 48px;
  text-align: center;
  padding-top: 4px;
}
.ac-bubble {
  max-width: 75%;
  padding: 9px 13px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}
.ac-user .ac-bubble { background: #1a3a3a; color: #f0f3f5; border-bottom-right-radius: 4px; }
.ac-human_agent .ac-bubble { background: #0e7c7b; color: #fff; border-bottom-left-radius: 4px; }
.ac-system .ac-bubble { background: #3a3a1a; color: #eef1f3; font-size: 12px; }
.ac-assistant .ac-bubble { background: #1a2a1a; color: #eef1f3; }

.agent-chat-input {
  display: flex;
  gap: 8px;
}
.agent-chat-input input {
  flex: 1;
  padding: 10px 12px;
  background: #1a1d23;
  border: 1px solid #444;
  border-radius: 8px;
  color: #eee;
  font-size: 13px;
  outline: none;
}
.agent-chat-input input:focus { border-color: #0e7c7b; }
.btn-reply {
  background: #0e7c7b;
  color: #fff;
  border: none;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.btn-reply:hover { background: #0a5b5a; }
.btn-reply:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
