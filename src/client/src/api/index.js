/**
 * api/index.js — 前端 API 服务层
 * ================================
 * 所有 HTTP 请求的统一入口，使用 axios 封装。
 * 职责：纯数据传输，不含业务逻辑。
 *
 * 端点分组：
 *   1. Case 生命周期（createCase, getCase）
 *   2. Workflow 导航（selectOption, goBack）
 *   3. 自由文本映射（mapFreeText, confirmMapping）
 *   4. RAG / AI（askAI, ragResolve）
 *   5. Handoff（requestHandoff）
 *   6. 人工队列（getQueue, assignCase, resolveCase）
 *   7. 消息通信（sendMessage, getMessages）
 *   8. 查询（getAuditLog, getConversation, getHandoffPacket）
 */
import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 90000 })  // 90s: MiMo reasoning model needs ~40s

// ══════════════════════════════════════════════════════════════════════════
// 1. Case 生命周期
// ══════════════════════════════════════════════════════════════════════════

/** 创建新 Case，返回起始节点信息 */
export async function createCase(productName) {
  const { data } = await http.post('/cases', {
    idempotency_key: crypto.randomUUID(),
    product_name: productName || null,
  })
  return data
}

/** 查询 Case 当前状态 */
export async function getCase(caseId) {
  const { data } = await http.get(`/cases/${caseId}`)
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 2. Workflow 导航
// ══════════════════════════════════════════════════════════════════════════

/** 用户点击 Workflow 按钮，推进到下一节点 */
export async function selectOption(caseId, caseVersion, nodeId, optionId) {
  const { data } = await http.post(`/cases/${caseId}/select`, {
    case_id: caseId, case_version: caseVersion,
    node_id: nodeId, option_id: optionId,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

/** 用户回退到之前某个节点 */
export async function goBack(caseId, caseVersion, targetNodeId) {
  const { data } = await http.post(`/cases/${caseId}/go-back`, {
    case_id: caseId, case_version: caseVersion,
    target_node_id: targetNodeId,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 3. 自由文本映射
// ══════════════════════════════════════════════════════════════════════════

/** 用户输入自由文本，触发 AI 语义映射 */
export async function mapFreeText(caseId, caseVersion, userText) {
  const { data } = await http.post(`/cases/${caseId}/map-text`, {
    case_id: caseId, case_version: caseVersion,
    user_text: userText,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

/** 用户确认或否认 AI 映射结果 */
export async function confirmMapping(caseId, caseVersion, confirmed) {
  const { data } = await http.post(`/cases/${caseId}/confirm-mapping`, {
    case_id: caseId, case_version: caseVersion, confirmed,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 4. RAG / AI
// ══════════════════════════════════════════════════════════════════════════

/** 用户向 AI 提问（在 AI_RAG_SERVICE 阶段） */
export async function askAI(caseId, caseVersion, userMessage) {
  const { data } = await http.post(`/cases/${caseId}/ask`, {
    case_id: caseId, case_version: caseVersion,
    user_message: userMessage,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

/** 用户反馈 AI 排查结果（已解决 / 未解决） */
export async function ragResolve(caseId, caseVersion, resolved) {
  const { data } = await http.post(`/cases/${caseId}/rag-resolve`, {
    case_id: caseId, case_version: caseVersion, resolved,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 5. Handoff
// ══════════════════════════════════════════════════════════════════════════

/** 用户主动请求转人工 */
export async function requestHandoff(caseId, caseVersion) {
  const { data } = await http.post(`/cases/${caseId}/handoff`, {
    case_id: caseId, case_version: caseVersion,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 6. 人工队列
// ══════════════════════════════════════════════════════════════════════════

/** 获取人工客服队列 */
export async function getQueue() {
  const { data } = await http.get('/queue')
  return data
}

/** 人工客服接单 */
export async function assignCase(caseId, agentId) {
  const { data } = await http.post('/queue/assign', {
    case_id: caseId, agent_id: agentId,
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

/** 人工客服标记 Case 解决 */
export async function resolveCase(caseId, agentId, note) {
  const { data } = await http.post(`/cases/${caseId}/resolve`, {
    case_id: caseId, agent_id: agentId,
    resolution_note: note || '',
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 7. 消息通信（用户 ↔ 人工客服）
// ══════════════════════════════════════════════════════════════════════════

/** 发送消息（user 或 human_agent） */
export async function sendMessage(caseId, role, content, senderName) {
  const { data } = await http.post(`/cases/${caseId}/messages`, {
    case_id: caseId, role, content,
    sender_name: senderName || '',
    idempotency_key: crypto.randomUUID(),
  })
  return data
}

/** 获取消息列表（支持增量拉取，afterIndex 为起始 index） */
export async function getMessages(caseId, afterIndex) {
  const params = afterIndex !== undefined ? { after: afterIndex } : {}
  const { data } = await http.get(`/cases/${caseId}/messages`, { params })
  return data
}

// ══════════════════════════════════════════════════════════════════════════
// 8. 查询（审计、对话、Handoff Packet）
// ══════════════════════════════════════════════════════════════════════════

/** 获取 Case 审计日志 */
export async function getAuditLog(caseId) {
  const { data } = await http.get(`/cases/${caseId}/audit`)
  return data
}

/** 获取完整对话记录 */
export async function getConversation(caseId) {
  const { data } = await http.get(`/cases/${caseId}/conversation`)
  return data
}

/** 获取 Handoff Packet + 对话 + 审计日志 */
export async function getHandoffPacket(caseId) {
  const { data } = await http.get(`/cases/${caseId}/handoff-packet`)
  return data
}
