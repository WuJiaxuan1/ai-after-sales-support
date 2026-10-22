# Skill: 自由文本语义映射（Semantic Mapper）

> 本 Skill 负责将用户的自由文本输入映射到当前 Workflow 节点已有的固定选项。它是固定按钮 Workflow 的旁路入口，不是独立业务路径。

---

## Skill 元信息

- **skill_id**: skill-semantic-mapper
- **skill_name**: 自由文本语义映射
- **version**: mvp-v1
- **触发条件**: 用户在任意 Workflow 节点不点击固定按钮，直接输入自然语言
- **输入来源**: FastAPI Workflow / Rule Engine
- **输出去向**: 前端确认卡片 → 用户确认 → Workflow 推进

---

## 输入契约

调用本 Skill 时，必须传入以下最小上下文：

```json
{
  "case_id": "CASE-001",
  "node_id": "N2",
  "question": "您的诉求是什么？",
  "allowed_options": [
    {"option_id": "REFUND_STATUS", "label": "查询退款 / 退货进度"},
    {"option_id": "REFUND_REVIEW", "label": "申请复核退款拒绝结果"},
    {"option_id": "REFUND_OTHER", "label": "其他"}
  ],
  "user_text": "退款被拒绝了，我想请人工重新审核"
}
```

**约束：**
- `allowed_options` 必须是当前节点服务端配置中存在的合法选项
- 不传入完整 Workflow 历史或下游节点信息
- 不传入用户画像或历史偏好

---

## 输出契约

AI 必须返回且仅返回以下结构化输出：

```json
{
  "decision": "MATCH | NO_MATCH",
  "mapped_option_id": "REFUND_REVIEW | null",
  "confidence": 0.93,
  "reason": "用户描述退款被拒绝且希望重新审核，与'申请复核退款拒绝结果'匹配"
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `decision` | string | `"MATCH"` 或 `"NO_MATCH"` |
| `mapped_option_id` | string or null | 匹配到的选项 ID，必须属于 `allowed_options`；不匹配时为 `null` |
| `confidence` | float | 0.0-1.0 的置信度，是辅助信号而非唯一判定依据 |
| `reason` | string | 不超过一句话的用户可读解释，用于前端确认卡片 |

---

## Prompt 模板

```
你是一个售后系统的语义映射模块。你的唯一任务是判断用户输入对应当前节点的哪一个已有选项。

## 当前节点
节点问题: {question}

## 合法选项
{allowed_options 列表，每项含 option_id 和 label}

## 用户输入
{user_text}

## 你的任务
1. 理解用户输入的含义
2. 判断其最可能对应的合法选项
3. 返回结构化的映射结果

## 严格约束
- 你只能从上述合法选项中选择，不得创建新选项
- 你不得跳过当前节点
- 你不得根据症状推断用户的处理诉求（如退款、换货）
- 你不得修改用户已确认的前序状态
- 如果无法可靠映射，返回 NO_MATCH
- 不要在 reason 中暴露内部术语（如 option_id、node_id）

## 输出格式
严格按 JSON 格式输出：
{"decision": "MATCH 或 NO_MATCH", "mapped_option_id": "选项ID 或 null", "confidence": 0.0-1.0, "reason": "一句话解释"}
```

---

## 服务端校验规则

AI 返回结果后，服务端必须执行以下校验：

1. **JSON 解析**：输出是否为合法 JSON
2. **字段完整性**：是否包含 `decision`、`mapped_option_id`、`confidence`、`reason` 四个字段
3. **选项合法性**：`mapped_option_id` 是否属于当前节点的 `allowed_options`
4. **置信度阈值**：`confidence` 是否 >= `mapping_confidence_threshold`（默认 0.80，可配置）

**校验结果处理：**

| 情况 | 服务端动作 | 用户看到的界面 |
|---|---|---|
| 全部通过 | 暂存映射，状态设为 MAPPING_CONFIRMING | "我理解您选择的是 [label]，是否继续？[确认] [不对，重新选择]" |
| 用户确认 | 以该 option_id 执行与点击按钮相同的校验，推进 Workflow | 进入下一节点 |
| 用户否认 | 记录 mapping_rejected，清空暂存 | 回到当前节点按钮 |
| 低置信/NO_MATCH/输出非法 | 记录失败原因 | 回到当前节点按钮，可选择"其他" |
| 模型超时/调用失败 | 记录 AI_MAPPING_UNAVAILABLE | 立即回到当前节点按钮，不阻塞用户 |

---

## 禁止事项

1. **禁止 AI 新建当前不存在的选项**
2. **禁止 AI 跳过当前节点进入下游节点**
3. **禁止根据症状推断退款、换货、维修诉求**
4. **禁止修改用户已确认的前序状态**
5. **禁止根据完整上下文自行重写 Workflow**
6. **禁止在低置信情况下开放式追问并创造新分支**
7. **禁止把 AI 映射结果静默写入业务状态（必须经用户确认）**

---

## 验收用例

### Case A: 成功映射

**输入：**
```
节点问题: 目前的异常情况更接近哪一种？
合法选项: [完全无法使用, 部分功能异常, 连接/配对异常, 供电/充电异常, 外观异常, 其他]
用户文本: "其他功能都可以，就是左键点了没反应"
```

**期望输出：**
```json
{
  "decision": "MATCH",
  "mapped_option_id": "partial_malfunction",
  "confidence": 0.93,
  "reason": "您描述的是部分功能异常，其他功能正常但左键无法使用"
}
```

### Case B: 低置信 / 无法映射

**输入：**
```
节点问题: 当前退款状态属于哪一种？
合法选项: [未申请, 处理中, 被拒绝, 已退款未到账, 金额有疑问, 其他]
用户文本: "东西不好用"
```

**期望输出：**
```json
{
  "decision": "NO_MATCH",
  "mapped_option_id": "null",
  "confidence": 0.25,
  "reason": "您的描述与当前退款相关选项不匹配，请从按钮中选择"
}
```

### Case C: 防止症状推断诉求

**输入：**
```
节点问题: 目前的异常情况更接近哪一种？
合法选项: [完全无法使用, 部分功能异常, 连接/配对异常, 供电/充电异常, 外观异常, 其他]
用户文本: "鼠标左键没反应，我要退款"
```

**期望输出：**
```json
{
  "decision": "MATCH",
  "mapped_option_id": "partial_malfunction",
  "confidence": 0.90,
  "reason": "您描述的是部分功能异常（左键无响应），退款诉求将在问题确认后处理"
}
```

> 注意：即使用户提到"退款"，在当前节点只能映射到"部分功能异常"。退款诉求需要在后续 User Intent 节点由用户明确确认。
