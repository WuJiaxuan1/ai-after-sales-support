# Skill: Workflow 导航器（Workflow Navigator）

> 本 Skill 负责管理确定性售后 Workflow 的节点推进、回退、状态校验和审计事件记录。它是整个售后问题定义流程的核心控制引擎。

---

## Skill 元信息

- **skill_id**: skill-workflow-navigator
- **skill_name**: Workflow 导航器
- **version**: mvp-v1
- **触发条件**: 用户提交按钮选择、确认 AI 映射、请求回退
- **输入来源**: 前端用户操作
- **输出去向**: Case 状态更新 + 前端按钮展示

---

## Workflow 配置结构

### MVP 决策树

```json
{
  "workflow_id": "after_sales_v1",
  "workflow_version": "mvp-v1",
  "start_node": "N0",
  "nodes": {
    "N0": {
      "id": "N0",
      "type": "choice",
      "dimension": "issue_category",
      "question": "您需要什么售后帮助？",
      "options": [
        {"option_id": "ISSUE_USE", "label": "商品使用 / 功能问题", "next": "N1"},
        {"option_id": "ISSUE_REFUND", "label": "退货 / 退款进度或申请", "next": "N2"},
        {"option_id": "ISSUE_REPAIR", "label": "维修 / 保修问题", "next": "N3"},
        {"option_id": "ISSUE_OTHER", "label": "其他", "next": "OTHER_CONFIRM"}
      ]
    },
    "N1": {
      "id": "N1",
      "type": "choice",
      "dimension": "use_symptom",
      "question": "当前现象是什么？",
      "options": [
        {"option_id": "USE_NOT_WORKING", "label": "无法正常使用", "next": "N1A"},
        {"option_id": "USE_GUIDANCE", "label": "不会使用 / 需要操作指导", "next": "AI_RAG_SERVICE"},
        {"option_id": "USE_OTHER", "label": "其他", "next": "OTHER_CONFIRM"}
      ]
    },
    "N1A": {
      "id": "N1A",
      "type": "choice",
      "dimension": "safety_check",
      "question": "是否存在发热、冒烟、漏电或电池鼓包？",
      "options": [
        {"option_id": "SAFETY_YES", "label": "是", "next": "HANDOFF_SAFETY"},
        {"option_id": "SAFETY_NO", "label": "否", "next": "AI_RAG_SERVICE"}
      ]
    },
    "N2": {
      "id": "N2",
      "type": "choice",
      "dimension": "refund_intent",
      "question": "您的诉求是什么？",
      "options": [
        {"option_id": "REFUND_STATUS", "label": "查询退款 / 退货进度", "next": "AI_RAG_SERVICE"},
        {"option_id": "REFUND_REVIEW", "label": "申请复核退款拒绝结果", "next": "HANDOFF_AUTHORITY"},
        {"option_id": "REFUND_OTHER", "label": "其他", "next": "OTHER_CONFIRM"}
      ]
    },
    "N3": {
      "id": "N3",
      "type": "choice",
      "dimension": "repair_intent",
      "question": "您需要什么帮助？",
      "options": [
        {"option_id": "REPAIR_STATUS", "label": "查询保修或维修进度", "next": "AI_RAG_SERVICE"},
        {"option_id": "REPAIR_CLAIM", "label": "申请异常赔付或责任认定", "next": "HANDOFF_AUTHORITY"},
        {"option_id": "REPAIR_OTHER", "label": "其他", "next": "OTHER_CONFIRM"}
      ]
    },
    "OTHER_CONFIRM": {
      "id": "OTHER_CONFIRM",
      "type": "confirm",
      "question": "当前选项中确实没有符合您的情况吗？",
      "options": [
        {"option_id": "OTHER_RETURN", "label": "返回重新选择", "action": "RETURN_PREVIOUS"},
        {"option_id": "OTHER_HANDOFF", "label": "是的，都不符合，转人工", "action": "HANDOFF_NO_MATCH"}
      ]
    },
    "AI_RAG_SERVICE": {
      "id": "AI_RAG_SERVICE",
      "type": "terminal",
      "action": "ENTER_RAG_SERVICE"
    },
    "HANDOFF_SAFETY": {
      "id": "HANDOFF_SAFETY",
      "type": "terminal",
      "action": "HANDOFF",
      "handoff_trigger": "SAFETY_RISK"
    },
    "HANDOFF_AUTHORITY": {
      "id": "HANDOFF_AUTHORITY",
      "type": "terminal",
      "action": "HANDOFF",
      "handoff_trigger": "AUTHORITY_BOUNDARY"
    }
  }
}
```

---

## 输入契约

### 1. 按钮选择

```json
{
  "case_id": "CASE-001",
  "case_version": 3,
  "action": "select_option",
  "node_id": "N0",
  "option_id": "ISSUE_USE",
  "idempotency_key": "uuid-xxx"
}
```

### 2. 确认 AI 映射

```json
{
  "case_id": "CASE-001",
  "case_version": 3,
  "action": "confirm_mapping",
  "confirmed": true,
  "idempotency_key": "uuid-xxx"
}
```

### 3. 请求回退

```json
{
  "case_id": "CASE-001",
  "case_version": 5,
  "action": "go_back",
  "target_node_id": "N0",
  "idempotency_key": "uuid-xxx"
}
```

---

## 输出契约

### 成功推进

```json
{
  "success": true,
  "case_id": "CASE-001",
  "case_version": 4,
  "current_node": {
    "node_id": "N1",
    "question": "当前现象是什么？",
    "options": [
      {"option_id": "USE_NOT_WORKING", "label": "无法正常使用"},
      {"option_id": "USE_GUIDANCE", "label": "不会使用 / 需要操作指导"},
      {"option_id": "USE_OTHER", "label": "其他"}
    ]
  },
  "issue_path": ["商品使用 / 功能问题"],
  "confirmed_facts": [],
  "audit_event": {
    "event_type": "workflow_selected",
    "event_id": "EVT-003",
    "case_id": "CASE-001",
    "node_id": "N0",
    "option_id": "ISSUE_USE",
    "created_at": "2025-01-01T10:00:00Z",
    "actor": "user"
  }
}
```

### 到达终态

```json
{
  "success": true,
  "case_id": "CASE-001",
  "case_version": 6,
  "terminal_action": "ENTER_RAG_SERVICE",
  "issue_path": ["商品使用 / 功能问题", "不会使用 / 需要操作指导"],
  "confirmed_facts": []
}
```

### 非法请求

```json
{
  "success": false,
  "error": "INVALID_OPTION",
  "message": "选项 ISSUE_REPAIR 不属于当前节点 N1",
  "current_case_snapshot": { "..." }
}
```

---

## 核心行为规则

### 1. 选项校验

```python
def validate_selection(case_id, node_id, option_id):
    workflow = load_workflow(case.workflow_version)
    node = workflow.nodes[case.current_node_id]
    
    # 校验当前节点是否匹配
    if node_id != case.current_node_id:
        return error("NODE_MISMATCH", case.snapshot())
    
    # 校验选项是否属于当前节点
    valid_option_ids = [opt.option_id for opt in node.options]
    if option_id not in valid_option_ids:
        return error("INVALID_OPTION", case.snapshot())
    
    return success()
```

### 2. 回退规则

```python
def go_back(case, target_node_id):
    # 校验目标节点是否在已访问路径中
    if target_node_id not in case.visited_nodes:
        return error("INVALID_BACK_TARGET")
    
    # 保留目标节点之前的状态
    # 清除目标节点及之后的所有状态
    case.trim_after(target_node_id)
    
    # 创建审计事件
    audit("selection_revised", case_id=case.case_id, 
          from_node=case.current_node_id, to_node=target_node_id)
    
    case.current_node_id = target_node_id
    return success(case)
```

### 3. 审计事件

每个状态变更必须生成审计事件：

| 事件类型 | 触发时机 | 记录字段 |
|---|---|---|
| `workflow_selected` | 用户点击按钮 | case_id, node_id, option_id, timestamp, actor=user |
| `selection_revised` | 用户回退并修改选择 | case_id, from_node, to_node, before_path, after_path |
| `mapping_pending_confirmation` | AI 映射通过校验 | case_id, user_text, allowed_options, ai_output, threshold |
| `mapping_confirmed` | 用户确认 AI 映射 | case_id, mapped_option_id, actor=user |
| `mapping_rejected` | 用户否认 AI 映射 | case_id, mapped_option_id, actor=user |

---

## 并发与幂等

- 所有状态变更请求携带 `idempotency_key` + `case_version`
- 服务端先校验幂等键（重复请求返回已有结果）
- 再校验版本和当前状态（过期请求返回最新快照）
- 成功后递增版本并追加审计事件
- 防止网络重试造成重复提交，防止旧页面覆盖最新状态

---

## 禁止事项

1. **禁止前端自行计算下一节点** — 必须由服务端根据 Workflow 配置决定
2. **禁止前端传入的选项 ID 直接信任** — 服务端必须重新校验
3. **禁止 AI 动态生成新的核心按钮** — 所有按钮来源为预配置 Workflow
4. **禁止 AI 动态修改 Workflow** — Workflow 只由人工维护
5. **禁止把 SKU 级所有故障穷举成固定按钮** — 超出分类粒度的交给自由文本 + RAG
6. **禁止每次按钮点击都重复弹二次确认** — 按钮点击直接确认
