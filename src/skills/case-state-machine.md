# Skill: Case 状态机（Case State Machine）

> 本 Skill 定义 Case 的状态流转规则，管理从创建到解决或转人工的完整生命周期。所有状态转换必须经过服务端校验。

---

## Skill 元信息

- **skill_id**: skill-case-state-machine
- **skill_name**: Case 状态机
- **version**: mvp-v1
- **触发条件**: 所有改变 Case 状态的操作
- **输入来源**: 前端操作 + AI 处理结果 + Handoff 触发器
- **输出去向**: Case 持久化 + 审计日志

---

## Case 状态定义

```
IN_WORKFLOW          — 正在走固定按钮决策树
MAPPING_CONFIRMING   — AI 映射结果等待用户确认
AI_RAG_SERVICE       — 进入 RAG 知识问答阶段
HANDOFF_CREATED      — 已创建 Handoff（瞬态，立即进入 QUEUED）
QUEUED               — 在人工客服队列中等待
ASSIGNED             — 已分配给人工客服
RESOLVED             — 已解决
```

---

## 状态流转图

```text
IN_WORKFLOW ──自由文本通过校验──> MAPPING_CONFIRMING
     │                                   │
     │ 按钮选择 / 用户确认               ├──用户否认、低置信、失败──> IN_WORKFLOW
     ▼                                   │
AI_RAG_SERVICE <────────────────────────┘
     │
     ├──完成当前可处理的解释或指导──> AI_RAG_SERVICE
     ├──触发人工边界────────────────> HANDOFF_CREATED ──计算优先级──> QUEUED
     └──用户结束 / 已解决───────────> RESOLVED

QUEUED ──人工接单──> ASSIGNED ──人工完成──> RESOLVED
```

---

## 状态转换前置条件

| 当前状态 | 触发事件 | 目标状态 | 前置条件 |
|---|---|---|---|
| IN_WORKFLOW | 用户输入自由文本 | MAPPING_CONFIRMING | AI 映射通过结构合法、选项合法、置信度 >= 阈值 |
| IN_WORKFLOW | 用户点击按钮 | IN_WORKFLOW 或 AI_RAG_SERVICE | 选项属于当前节点，校验通过 |
| IN_WORKFLOW | 触发 Handoff | HANDOFF_CREATED | 满足 Handoff 触发器条件 |
| MAPPING_CONFIRMING | 用户确认映射 | AI_RAG_SERVICE 或 IN_WORKFLOW | 映射有效且用户确认 |
| MAPPING_CONFIRMING | 用户否认映射 | IN_WORKFLOW | 清空暂存映射 |
| MAPPING_CONFIRMING | 低置信/失败 | IN_WORKFLOW | 记录失败原因 |
| AI_RAG_SERVICE | AI 完成回答 | AI_RAG_SERVICE | 回答基于 RAG 依据 |
| AI_RAG_SERVICE | 触发 Handoff | HANDOFF_CREATED | 满足任一 Handoff 触发器 |
| AI_RAG_SERVICE | 用户结束 | RESOLVED | 用户确认问题已解决 |
| HANDOFF_CREATED | 优先级计算完成 | QUEUED | 自动生成，不需要用户操作 |
| QUEUED | 人工接单 | ASSIGNED | Case 尚未被其他客服接单 |
| ASSIGNED | 人工完成处理 | RESOLVED | 人工客服确认处理完成 |

---

## 并发与幂等处理

| 场景 | 处理方式 |
|---|---|
| 重复提交（相同 idempotency_key） | 返回第一次处理结果，不重复推进 |
| 过期请求（case_version 不匹配） | 拒绝请求，返回最新 Case 快照 |
| AI 回答时 Case 已 HANDOFF | 丢弃过期回答，不写入用户可见回复 |
| 两位客服同时接单 | CAS 原子操作，只有首个请求成功 |
| 用户回退并修改选择 | 清除下游状态，保留上游有效状态 |

---

## 审计事件完整性

每个状态转换必须记录：

```json
{
  "event_id": "EVT-xxx",
  "event_type": "状态变更类型",
  "case_id": "CASE-xxx",
  "case_version": "变更后的版本号",
  "from_state": "变更前状态",
  "to_state": "变更后状态",
  "actor": "user | system | ai | human_agent",
  "created_at": "ISO 8601 时间戳",
  "data": { "变更相关数据" }
}
```

历史事件不覆盖，以便复原任一 Case 的演变。
