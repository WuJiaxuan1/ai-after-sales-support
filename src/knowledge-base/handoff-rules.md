# 转人工规则知识库

> 本文件属于系统控制规则，不进入普通用户回答 RAG。

## 1. Handoff 触发器

### K-HANDOFF-001: 触发器定义

- source_id: RULE-HANDOFF-001
- source_title: Handoff 触发器定义
- source_version: mvp-v2
- chunk_id: HANDOFF-001-01

| 触发器 | 触发条件 | 处理 |
|---|---|---|
| SAFETY_RISK | Safety Gate 输出 SUSPECTED 或 CONFIRMED 安全风险 | 系统自动创建 Handoff，P0 |
| AUTHORITY_BOUNDARY | 退款复核、责任认定、异常赔付等 AI 无权限执行 | 自动 Handoff，优先级按既有策略 |
| USER_REQUEST | 用户点击转人工，或自由文本明确要求人工/真人客服 | 自动 Handoff |
| NO_MATCH_CONFIRMED | 用户在“其他”二次确认中明确选择转人工 | 自动 Handoff |
| KNOWLEDGE_OR_CAPABILITY_GAP | RAG 无足够依据，或请求需要系统不具备的查询/执行能力 | 自动 Handoff |
| AUTOMATION_NO_PROGRESS | 连续无有效推进，达到系统配置条件 | 自动 Handoff |

## 2. SAFETY_RISK

### K-HANDOFF-002: 安全风险自动转人工

- source_id: RULE-HANDOFF-SAFETY-001
- source_title: 安全风险自动转人工规则
- source_version: mvp-v2
- chunk_id: HANDOFF-SAFETY-001-01

Safety Gate 覆盖全品类风险，并采用：

1. 确定性高置信规则；
2. 受限语义安全分类器。

系统允许区分：

- `SUSPECTED_SAFETY_RISK`
- `CONFIRMED_SAFETY_RISK`

但两者的业务动作相同：

```text
Safety signal
→ handoff_trigger = SAFETY_RISK
→ 后端真实创建 Handoff Packet 和人工队列项
→ P0
→ 返回安全提示
```

安全转人工不要求用户点击“确认风险”或“转人工”按钮。

安全风险问题不得继续进入普通故障排查。

## 3. USER_REQUEST

### K-HANDOFF-003: 用户主动请求人工

- source_id: RULE-HANDOFF-USER-001
- source_title: 用户主动请求人工规则
- source_version: mvp-v2
- chunk_id: HANDOFF-USER-001-01

以下两种方式均属于 USER_REQUEST：

- 用户点击页面“转人工客服”按钮；
- 用户自由文本明确表达“找人工、找客服、找真人、转人工、真人客服”等人工服务意图。

系统应直接创建真实 Handoff，不要求用户再次点击转人工按钮。

普通叙述中仅仅提到“客服”不等于人工请求，例如：

- “昨天客服说可以退款”
- “客服页面写着三天到账”

## 4. NO_MATCH_CONFIRMED

### K-HANDOFF-004: 其他选项二次确认

- source_id: RULE-HANDOFF-NOMATCH-001
- source_title: 无匹配二次确认规则
- source_version: mvp-v2
- chunk_id: HANDOFF-NOMATCH-001-01

“其他”仍保持二次确认：

```text
[返回重新选择]
[是的，都不符合，转人工]
```

只有用户明确选择第二项后创建 Handoff。

自由文本映射失败本身不直接转人工，应继续允许固定按钮和新的自由文本输入。

## 5. KNOWLEDGE_OR_CAPABILITY_GAP

### K-HANDOFF-005: 知识与能力边界

- source_id: RULE-HANDOFF-GAP-001
- source_title: 知识和能力不足转人工
- source_version: mvp-v2
- chunk_id: HANDOFF-GAP-001-01

以下情况应停止无依据回答并转人工：

- RAG 没有能够支持当前回答的相关知识；
- 用户要求查询真实资金状态、订单内部状态等系统未接入能力；
- 用户要求真实退款、赔付、责任认定等 AI 无执行权限的操作。

## 6. Handoff Packet

### K-HANDOFF-006: Handoff Packet 要求

- source_id: RULE-HANDOFF-PACKET-001
- source_title: Handoff Packet 结构要求
- source_version: mvp-v2
- chunk_id: HANDOFF-PACKET-001-01

必须区分：

- `issue_path`：用户已经确认的 Workflow 路径
- `confirmed_facts`：用户明确表达或确认的事实
- `diagnosis`：AI 推断，不能混入事实
- `user_intent`：用户明确处理诉求
- `handoff_trigger`
- `key_quotes`：关键用户原话
- `retrieval_ids`
- `priority`

安全场景建议额外记录：

```text
hazard_type
safety_certainty
safety_evidence
```

## 7. 禁止事项

- 禁止由 RAG 文本本身控制业务路由。
- 禁止 AI 自己声称已经创建工单而后端未真正建单。
- 禁止用用户情绪直接产生 P0。
- 禁止因为 Mapping 失败直接转人工。
- 禁止 Safety Gate 命中后继续普通故障排查。
- 禁止要求已识别的安全风险用户再手动点击“转人工”。
