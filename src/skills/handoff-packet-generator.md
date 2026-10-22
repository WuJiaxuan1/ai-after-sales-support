# Skill: 转人工数据包生成（Handoff Packet Generator）

> 本 Skill 负责在触发 Handoff 条件时，生成结构化的 Handoff Packet，供人工客服工作台使用。它是 AI → 人工交接的核心数据结构。

---

## Skill 元信息

- **skill_id**: skill-handoff-generator
- **skill_name**: Handoff Packet 生成
- **version**: mvp-v1
- **触发条件**: 任一 Handoff 触发器被激活
- **输入来源**: FastAPI Workflow / Rule Engine（Case 完整状态）
- **输出去向**: 人工客服工作台 + 审计日志

---

## 输入契约

```json
{
  "case_id": "CASE-001",
  "case_version": 5,
  "workflow_version": "mvp-v1",
  "case_state": "AI_RAG_SERVICE",
  "issue_path": ["退款相关", "退款申请被拒绝"],
  "confirmed_facts": ["用户确认退款申请被拒绝", "用户希望重新审核"],
  "diagnosis": null,
  "user_intent": "申请人工复核退款结果",
  "handoff_trigger": "AUTHORITY_BOUNDARY",
  "conversation_history": [
    {"role": "user", "content": "退款被拒绝了", "timestamp": "2025-01-01T10:00:00Z"},
    {"role": "system", "content": "AI: 查询退款被拒的常见原因...", "timestamp": "2025-01-01T10:00:05Z"},
    {"role": "user", "content": "我想请人工重新审核", "timestamp": "2025-01-01T10:01:00Z"}
  ],
  "ai_actions_taken": ["检索退款复核规则", "解释常见拒绝原因"],
  "rag_retrieval_ids": ["RET-001"],
  "order_data": {
    "order_id": "ORD-12345",
    "product_name": "小米无线鼠标",
    "product_price": 899.00,
    "refund_amount": 899.00
  },
  "verified_exposure_amount": 899.00,
  "claimed_amount": null,
  "is_safety_risk": false
}
```

---

## 输出契约（Handoff Packet）

```json
{
  "packet_version": "mvp-v1",
  "case_id": "CASE-001",
  "workflow_version": "mvp-v1",
  "issue_path": ["退款相关", "退款申请被拒绝"],
  "core_issue": "用户申请对退款拒绝结果进行人工复核",
  "confirmed_facts": [
    "用户确认退款申请被拒绝",
    "用户希望重新审核"
  ],
  "diagnosis": null,
  "user_intent": "申请人工复核退款结果",
  "handoff_trigger": "AUTHORITY_BOUNDARY",
  "handoff_trigger_detail": "退款复核属于权限边界，AI 无权推翻退款判定",
  "ai_actions": [
    "检索退款复核规则",
    "解释常见拒绝原因"
  ],
  "unconfirmed_information": [
    "商品是否已完成线下检测",
    "退款被拒的具体原因"
  ],
  "key_quotes": [
    "退款被拒绝了，我想请人工重新审核"
  ],
  "conversation_id": "CONV-001",
  "retrieval_ids": ["RET-001"],
  "priority": "P2",
  "priority_policy_version": "mvp-v1",
  "priority_reason": "verified_exposure_amount = 899.00，属于 P2 区间",
  "verified_exposure_amount": 899.00,
  "claimed_amount": null,
  "missing_exposure_data": false,
  "created_at": "2025-01-01T10:01:30Z"
}
```

---

## 生成规则

### 1. core_issue（核心问题）生成

- 从 `confirmed_facts` 和 `user_intent` 综合生成
- 不超过一句话
- 不包含 AI 推断内容

**Prompt:**
```
根据以下已确认信息，生成一句简短的核心问题描述（不超过30字）：
- 已确认事实: {confirmed_facts}
- 用户诉求: {user_intent}
- 问题路径: {issue_path}
只输出核心问题描述，不加任何前缀。
```

### 2. unconfirmed_information（未确认信息）提取

- 从对话历史中识别用户提及但未确认的信息
- 从 issue_path 推断可能需要但缺失的信息
- 不包含 AI 自行推测的内容

### 3. key_quotes（关键用户原话）提取

- 从 `conversation_history` 中提取用户的关键发言
- 优先选择：表达诉求的语句、描述问题的语句、情绪表达
- 保留原始文本，不做改写
- 每条 quote 带时间戳

### 4. priority 计算

调用 Priority Calculator Skill（见 priority-calculator.md）

### 5. 审计事件记录

生成以下审计事件：

```json
{
  "event_type": "handoff_created",
  "case_id": "CASE-001",
  "event_id": "EVT-001",
  "created_at": "2025-01-01T10:01:30Z",
  "actor": "system",
  "data": {
    "handoff_trigger": "AUTHORITY_BOUNDARY",
    "priority": "P2",
    "packet_snapshot": { "...完整 Packet..." }
  }
}
```

---

## 幂等性约束

- `HANDOFF_CREATED` 是不可重复的终止性自动状态
- 相同 `case_id` + `case_version` 的重复请求只返回既有 Packet
- 不生成第二个队列项
- 所有状态变更接口携带 `idempotency_key` 和 `case_version`

---

## 数据完整性要求

| 字段 | 必须包含 | 说明 |
|---|---|---|
| confirmed_facts | 是 | 仅用户确认的事实 |
| diagnosis | 可为 null | AI 疑似判断，单独标注 |
| user_intent | 可为 null | 用户未表达时为空 |
| handoff_trigger | 是 | 必须为预定义触发器之一 |
| ai_actions | 是 | 列出 AI 已执行的操作 |
| unconfirmed_information | 是 | 明确标注缺失信息 |
| key_quotes | 是 | 保留用户原话 |
| verified_exposure_amount | 可为 null | 缺失时标记 MISSING_EXPOSURE_DATA |
| priority | 是 | 按规则计算 |

---

## 禁止事项

1. **禁止将 AI 推断写入 confirmed_facts**
2. **禁止删除原始用户对话**
3. **禁止在 verified_exposure_amount 缺失时由 AI 估算金额**
4. **禁止因为用户情绪强烈而调整 priority（只看安全和金额）**
5. **禁止 AI 摘要取代完整聊天原文（两者都必须保留）**
