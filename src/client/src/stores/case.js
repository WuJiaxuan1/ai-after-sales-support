/**
 * stores/case.js — 用户侧 Pinia 状态管理
 * =========================================
 * 用户售后端的单一状态源（Single Source of Truth）。
 * 管理 Case 从创建到解决/转人工的完整生命周期。
 *
 * 状态：
 *   - caseId / caseVersion: Case 标识和乐观并发版本
 *   - state: 当前 CaseState（IN_WORKFLOW / MAPPING_CONFIRMING / AI_RAG_SERVICE / QUEUED / RESOLVED）
 *   - currentNode: 当前 Workflow 节点（含选项列表，供前端渲染按钮）
 *   - issuePath / confirmedFacts: 用户已确认的问题路径和事实
 *   - messages: 对话消息列表（用户/AI/系统/人工客服）
 *   - handoffPacket: 转人工后的交接数据包
 *   - loading / error: 请求状态
 *
 * 关键操作：
 *   - initCase(): 创建新 Case
 *   - selectOption(): 点击 Workflow 按钮
 *   - sendFreeText(): 输入自由文本（触发 AI 映射）
 *   - confirmMappingResult(): 确认/否认 AI 映射
 *   - askAIQuestion(): 向 AI 提问
 *   - markResolved() / markNotResolved(): 反馈 AI 排查结果
 *   - requestHumanHandoff(): 主动转人工
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api/index.js'

export const useCaseStore = defineStore('case', () => {
  // ── 状态 ──────────────────────────────────────────────────────────────
  const caseId = ref(null)           // Case ID
  const caseVersion = ref(0)         // 乐观并发版本号
  const state = ref(null)            // CaseState 枚举值
  const currentNode = ref(null)      // 当前 Workflow 节点 { node_id, question, options }
  const issuePath = ref([])          // 用户确认的问题分类路径
  const visitedNodes = ref([])       // 已访问的 Workflow 节点，用于回退
  const previousNodeId = computed(() => {
  if (!visitedNodes.value.length) return null
  return visitedNodes.value[visitedNodes.value.length - 1]
})
  const confirmedFacts = ref([])     // 用户已确认的事实
  const diagnosis = ref(null)        // AI 疑似判断
  const userIntent = ref(null)       // 用户明确诉求
  const messages = ref([])           // 对话消息列表
  const mappingPending = ref(false)  // 是否有映射待确认
  const mappingMessage = ref('')     // 映射确认提示文案
  const handoffTrigger = ref(null)   // 转人工触发器
  const handoffPacket = ref(null)    // Handoff Packet
  const lastJudgment = ref(null)     // 最近一次 AI 判断结果
  const emotionDetected = ref(false) // 检测到用户情绪
  const loading = ref(false)         // 请求加载状态
  const error = ref(null)            // 错误信息
  const pendingMappingMessageId = ref(null) // 自由文本映射时的同一 AI 占位气泡

  // ── 计算属性 ──────────────────────────────────────────────────────────
  const isWorkflow = computed(() => state.value === 'IN_WORKFLOW')           // 正在走 Workflow
  const isMappingConfirming = computed(() => state.value === 'MAPPING_CONFIRMING')  // AI 映射待确认
  const isRAGService = computed(() => state.value === 'AI_RAG_SERVICE')      // AI 排查阶段
  const isHandoff = computed(() => ['HANDOFF_CREATED', 'QUEUED', 'ASSIGNED', 'RESOLVED'].includes(state.value))  // 已转人工或已解决
  const isTerminal = computed(() => state.value === 'AI_RAG_SERVICE' || isHandoff.value)  // 已离开 Workflow

  // ── 操作 ──────────────────────────────────────────────────────────────

  /** 创建新 Case，初始化对话 */
  async function initCase(productName) {
    loading.value = true; error.value = null
    try {
      const res = await api.createCase(productName)
      _applyCaseResponse(res)
      messages.value = []
      addSystemMessage('欢迎使用售后服务，请选择您遇到的问题类型：')
    } catch (e) { error.value = e.message } finally { loading.value = false }
  }

  /** 用户点击 Workflow 按钮 */
  async function selectOption(optionId) {
    if (!currentNode.value) return

    // 必须在更新 currentNode 之前保存用户刚刚点击的选项
    const selectedOption = currentNode.value.options?.find(
      o => o.option_id === optionId
    )
    const selectedLabel = selectedOption?.label || ''

    loading.value = true
    error.value = null

    try {
      const res = await api.selectOption(
        caseId.value,
        caseVersion.value,
        currentNode.value.node_id,
        optionId,
      )

      if (!res.success) {
        error.value = res.error
        return
      }

      _applyCaseResponse(res)

      // 显示用户刚才点击的按钮
      if (selectedLabel) {
        addUserMessage(selectedLabel)
      }

      // Workflow 已完成分类，进入 AI / RAG 排查时主动承接
      if (res.terminal_action === 'ENTER_RAG_SERVICE') {
        const path = issuePath.value || []
        const currentIssue = path.length
          ? path[path.length - 1]
          : selectedLabel || '当前问题'

        addAssistantMessage(
          `已记录您选择的“${currentIssue}”。请继续说明与该问题直接相关的具体情况，例如当前状态、实际表现、发生时间或页面提示等，我会结合知识库继续为您排查。`
        )
      }

      // 需要人工介入
      if (res.terminal_action === 'HANDOFF' || res.handoff_trigger) {
        addSystemMessage('已为您转接人工客服，请稍候。')
      }

    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  /** 用户输入自由文本（统一触发 Safety / Workflow Path / RAG / Handoff Judge） */
  async function sendFreeText(text) {
    if (!text.trim()) return
    loading.value = true; error.value = null
    addUserMessage(text)
    const pendingId = addLoadingAssistantMessage('正在理解问题并检索相关信息…')
    try {
      const res = await api.mapFreeText(caseId.value, caseVersion.value, text)
      if (!res.success) {
        error.value = res.error
        replaceMessage(pendingId, '暂时未能完成处理，请重试。', 'assistant', false)
        return
      }
      _applyCaseResponse(res)

      // 自动转人工：同一占位气泡原位变成真实业务结果。
      if (state.value === 'QUEUED' || res.handoff_trigger) {
        replaceMessage(pendingId, res.message || '已自动为您转接人工客服。', 'system', false)
        return
      }

      // 最长可靠路径需要用户一次确认。RAG 答案暂存在后端，确认后仍替换这个气泡。
      if (state.value === 'MAPPING_CONFIRMING') {
        pendingMappingMessageId.value = pendingId
        replaceMessage(pendingId, '已完成问题理解与知识检索，请确认下方的问题分类。', 'assistant', false)
        return
      }

      // 无需路径确认时，直接展示普通 RAG 回答。
      if (res.assistant_answer) {
        replaceMessage(pendingId, res.assistant_answer, 'assistant', false)
      } else if (res.message) {
        replaceMessage(pendingId, res.message, 'assistant', false)
      } else {
        replaceMessage(pendingId, '我已完成处理，但暂时没有可展示的回答。', 'assistant', false)
      }
    } catch (e) {
      error.value = e.message
      replaceMessage(pendingId, '暂时未能完成处理，请重试。', 'assistant', false)
    } finally { loading.value = false }
  }

  /** 用户确认或否认 AI 映射结果 */
  async function confirmMappingResult(confirmed) {
    loading.value = true; error.value = null
    const pendingId = pendingMappingMessageId.value
    try {
      const res = await api.confirmMapping(caseId.value, caseVersion.value, confirmed)
      if (!res.success) {
        error.value = res.error
        if (pendingId) replaceMessage(pendingId, '分类确认失败，请重试。', 'assistant', false)
        return
      }
      _applyCaseResponse(res)

      if (!confirmed) {
        if (pendingId) replaceMessage(pendingId, '已取消本次智能分类，请重新选择或补充描述。', 'assistant', false)
        return
      }

      if (res.terminal_action === 'HANDOFF' || res.handoff_trigger) {
        if (pendingId) replaceMessage(pendingId, res.message || '已为您转接人工客服，请稍候。', 'system', false)
        else addSystemMessage(res.message || '已为您转接人工客服，请稍候。')
        return
      }

      if (res.assistant_answer) {
        if (pendingId) replaceMessage(pendingId, res.assistant_answer, 'assistant', false)
        else addAssistantMessage(res.assistant_answer)
      } else if (res.terminal_action === 'ENTER_RAG_SERVICE') {
        const path = issuePath.value || []
        const currentIssue = path.length ? path[path.length - 1] : '当前问题'
        const prompt = `已确认“${currentIssue}”。请继续补充具体表现，我会结合知识库继续排查。`
        if (pendingId) replaceMessage(pendingId, prompt, 'assistant', false)
        else addAssistantMessage(prompt)
      }
    } catch (e) {
      error.value = e.message
      if (pendingId) replaceMessage(pendingId, '分类确认失败，请重试。', 'assistant', false)
    } finally {
      pendingMappingMessageId.value = null
      loading.value = false
    }
  }

  /** 用户向 AI 提问（在 AI_RAG_SERVICE 阶段） */
  async function askAIQuestion(text) {
    if (!text.trim()) return
    loading.value = true; error.value = null
    addUserMessage(text)
    const pendingId = addLoadingAssistantMessage('正在检索知识库并判断是否需要人工介入…')
    try {
      const res = await api.askAI(caseId.value, caseVersion.value, text)
      lastJudgment.value = res.judgment || null

      if (!res.success) {
        replaceMessage(pendingId, res.error || '暂时未能完成处理，请重试。', 'assistant', false)
        return
      }

      if (res.handoff) {
        handoffPacket.value = res.packet
        state.value = 'QUEUED'
        replaceMessage(pendingId, res.answer || '已自动为您转接人工客服。', 'system', false)
        return
      }

      replaceMessage(pendingId, res.answer || '暂时没有可展示的回答。', 'assistant', false)
    } catch (e) {
      error.value = e.message
      replaceMessage(pendingId, '暂时未能完成处理，请重试。', 'assistant', false)
    } finally { loading.value = false }
  }

  /** 用户确认 AI 排查结果：问题已解决 */
  async function markResolved() {
    loading.value = true; error.value = null
    try {
      const res = await api.ragResolve(caseId.value, caseVersion.value, true)
      if (res.state === 'RESOLVED') {
        state.value = 'RESOLVED'
        addSystemMessage('✅ ' + (res.message || '问题已解决，感谢您的反馈！'))
      }
    } catch (e) { error.value = e.message } finally { loading.value = false }
  }

  /** 用户反馈 AI 排查结果：问题未解决（累计 2 次自动转人工） */
  async function markNotResolved() {
    loading.value = true; error.value = null
    addSystemMessage('反馈：问题仍未解决')
    try {
      const res = await api.ragResolve(caseId.value, caseVersion.value, false)
      if (res.handoff) {
        handoffPacket.value = res.packet
        state.value = 'QUEUED'
        addSystemMessage(res.message || '已为您转接人工客服。')
      } else if (res.message) {
        addSystemMessage(res.message)
      }
    } catch (e) { error.value = e.message } finally { loading.value = false }
  }

  /** 用户主动请求转人工 */
  async function requestHumanHandoff() {
    loading.value = true; error.value = null
    try {
      const res = await api.requestHandoff(caseId.value, caseVersion.value)
      if (res.success) {
        handoffPacket.value = res.packet
        state.value = 'QUEUED'
        addSystemMessage('已为您转接人工客服，请稍候。')
      }
    } catch (e) { error.value = e.message } finally { loading.value = false }
  }

  /** 用户回退到之前某个节点 */
  async function goBackToNode(targetNodeId) {
    loading.value = true; error.value = null
    try {
      const res = await api.goBack(caseId.value, caseVersion.value, targetNodeId)
      if (!res.success) { error.value = res.error; return }
      _applyCaseResponse(res)
      addSystemMessage('已返回，请重新选择：')
    } catch (e) { error.value = e.message } finally { loading.value = false }
  }

  /** 返回 Workflow 上一级 */
  async function goBackOneLevel() {
    if (!previousNodeId.value || loading.value) return
    await goBackToNode(previousNodeId.value)
  }

  // ── 辅助方法 ──────────────────────────────────────────────────────────

  /** 将 API 响应同步到本地状态 */
  function _applyCaseResponse(res) {
    caseId.value = res.case_id || caseId.value
    caseVersion.value = res.case_version || caseVersion.value
    state.value = res.state || state.value
    currentNode.value = res.current_node || currentNode.value
    issuePath.value = res.issue_path ?? issuePath.value
    visitedNodes.value = res.visited_nodes ?? visitedNodes.value
    confirmedFacts.value = res.confirmed_facts ?? confirmedFacts.value
    diagnosis.value = res.diagnosis
    userIntent.value = res.user_intent
    handoffTrigger.value = res.handoff_trigger
    mappingPending.value = state.value === 'MAPPING_CONFIRMING'
    if (state.value === 'MAPPING_CONFIRMING' && res.message) {
      mappingMessage.value = res.message
    } else if (state.value !== 'MAPPING_CONFIRMING') {
      mappingMessage.value = ''
    }
  }

  /** 添加用户消息到对话列表 */
  function addUserMessage(text) {
    messages.value.push({ role: 'user', content: text, time: new Date().toLocaleTimeString() })
  }
  /** 添加系统消息到对话列表 */
  function addSystemMessage(text) {
    messages.value.push({ role: 'system', content: text, time: new Date().toLocaleTimeString() })
  }
  /** 添加 AI 回答到对话列表 */
  function addAssistantMessage(text) {
    messages.value.push({ role: 'assistant', content: text, time: new Date().toLocaleTimeString() })
  }
  /** 添加一个可原位替换的 AI Loading 气泡 */
  function addLoadingAssistantMessage(text) {
    const id = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`
    messages.value.push({
      id, role: 'assistant', content: text, time: new Date().toLocaleTimeString(), loading: true,
    })
    return id
  }
  /** 原位替换指定气泡，避免“加载中”和真实答案形成两条消息 */
  function replaceMessage(id, text, role = 'assistant', loadingState = false) {
    const msg = messages.value.find(m => m.id === id)
    if (!msg) return
    msg.content = text
    msg.role = role
    msg.loading = loadingState
    msg.time = new Date().toLocaleTimeString()
  }

  // ── 导出 ──────────────────────────────────────────────────────────────
  return {
    caseId, caseVersion, state, currentNode, issuePath, visitedNodes, confirmedFacts,
    diagnosis, userIntent, messages, mappingPending, mappingMessage,
    handoffTrigger, handoffPacket, lastJudgment, emotionDetected, loading, error,
    isWorkflow, isMappingConfirming, isRAGService, isHandoff, isTerminal,previousNodeId,
    initCase, selectOption, sendFreeText, confirmMappingResult,
    askAIQuestion, markResolved, markNotResolved, requestHumanHandoff, goBackToNode, goBackOneLevel,
    addUserMessage, addSystemMessage, addAssistantMessage,
  }
})
