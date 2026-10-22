# Skill: RAG 售后知识问答（RAG QA Service）

> 本 Skill 负责在售后问题明确后，基于 RAG 检索到的知识片段，为用户提供解释、使用指导和故障排查。它不参与 Workflow 路径控制。

---

## Skill 元信息

- **skill_id**: skill-rag-qa
- **skill_name**: RAG 售后知识问答
- **version**: mvp-v1
- **触发条件**: Workflow 进入 AI_RAG_SERVICE 终态后
- **输入来源**: FastAPI + RAG 检索结果
- **输出去向**: 用户售后端对话展示

---

## 输入契约

```json
{
  "case_id": "CASE-001",
  "issue_path": ["商品功能异常", "部分功能异常"],
  "confirmed_facts": ["鼠标左键点击无响应"],
  "diagnosis": "疑似功能异常",
  "user_intent": null,
  "product_info": {
    "product_name": "小米无线鼠标",
    "product_model": "XM-MS-001",
    "purchase_date": "2025-12-01",
    "warranty_status": "在保"
  },
  "rag_results": [
    {
      "source_id": "TROUBLE-MOUSE-001",
      "source_title": "鼠标常见问题排查",
      "chunk_id": "T-MOUSE-001-01",
      "content": "左键/右键无响应排查步骤：1.确认鼠标底部开关已开启...",
      "score": 0.92
    }
  ],
  "user_message": "鼠标左键没有反应，其他都正常",
  "conversation_history": []
}
```

---

## 输出契约

```json
{
  "answer": "根据您的描述，鼠标左键无响应但其他功能正常。建议您先尝试以下排查步骤：\n1. 确认鼠标底部开关已开启\n2. 更换电池或充电后重试\n3. 尝试在其他设备上使用，确认是否为兼容性问题\n\n请问排查后情况如何？",
  "used_sources": ["TROUBLE-MOUSE-001"],
  "suggested_next_actions": ["continue_troubleshooting", "request_repair", "request_exchange", "request_refund", "handoff"],
  "knowledge_sufficient": true,
  "capability_within_bounds": true,
  "is_safety_risk": false
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `answer` | string | 基于 RAG 知识的回答文本 |
| `used_sources` | string[] | 引用的 source_id 列表，必须可追溯 |
| `suggested_next_actions` | string[] | 建议的后续动作选项 |
| `knowledge_sufficient` | bool | RAG 是否提供了足够的知识依据 |
| `capability_within_bounds` | bool | 当前请求是否在 AI 能力范围内 |
| `is_safety_risk` | bool | 是否识别到安全风险（辅助信号） |

---

## Prompt 模板

```
你是一个售后客服 AI。你的任务是基于 RAG 检索到的知识，为用户提供准确的售后帮助。

## 当前问题
- 问题路径: {issue_path}
- 已确认事实: {confirmed_facts}
- 疑似判断: {diagnosis}
- 用户诉求: {user_intent 或 "尚未明确"}

## 产品信息
{product_info}

## RAG 检索结果
{rag_results，每项含 source_id, source_title, content, score}

## 用户当前消息
{user_message}

## 对话历史
{conversation_history}

## 你的任务
1. 基于 RAG 检索结果回答用户问题
2. 引用知识来源（source_id）
3. 判断是否需要进一步排查或已可给出解决方案
4. 判断当前请求是否仍在你的能力范围内

## 严格约束
- 只能基于 RAG 返回的知识片段回答，不得编造信息
- 未达到检索阈值的资料不得作为依据
- 不得生成知识库中不存在的政策
- RAG 检索到政策不等于你有执行权限
- 你可以：解释政策、指导排查、说明流程
- 你不可以：执行退款、复核判定、责任认定、异常赔付
- 安全风险问题不做常规排查
- 每次只给一个排查步骤，等用户反馈后再继续

## 输出格式
严格按 JSON 格式输出。
```

---

## RAG 检索规则

### 检索策略

1. **构造 Query**: 基于 `confirmed_facts` + `diagnosis` + `issue_path` 构造检索查询
2. **检索范围**: 按 `issue_path` 匹配对应知识类别
3. **阈值过滤**: 只返回 score >= retrieval_threshold 的片段
4. **Top-K**: 默认返回 Top-3 最相关片段
5. **来源记录**: 每次检索保存 `retrieval_id`、查询条件、返回片段 ID、分数和是否采用

### 检索失败处理

| 情况 | 处理方式 |
|---|---|
| 无片段达到阈值 | `knowledge_sufficient = false`，不得编造回答 |
| 片段与 issue_path 不匹配 | 不使用该片段，标记来源不匹配 |
| 需要真实订单/资金查询 | `capability_within_bounds = false`，建议转人工 |

---

## AI 行为规范

### 可以做的

- 基于 RAG 知识解释产品使用方法
- 引导用户按步骤排查故障
- 说明退换货、维修、退款的政策和流程
- 告知用户需要准备哪些材料
- 在排查未解决时提供后续选项

### 不可以做的

- 编造知识库中不存在的信息
- 根据检索到的政策直接执行业务动作
- 自动推断用户处理诉求（如从症状推断退款）
- 忽略安全风险继续常规排查
- 在知识不足时仍生成确定性结论
- 每次给出多个排查步骤让用户一次性尝试

---

## 验收用例

### Case A: 正常排查流程

**输入**: 用户说"鼠标左键没有反应"
**期望**: 给出第一步排查建议（检查开关/电量），等待用户反馈
**禁止**: 一次性列出所有排查步骤

### Case B: 知识不足

**输入**: 用户问一个知识库中没有的问题
**期望**: 告知用户当前无法解答，建议转人工
**禁止**: 编造答案

### Case C: 安全风险

**输入**: 用户说"电池鼓起来了，很烫"
**期望**: 首先提醒用户安全（断电、远离），然后转人工
**禁止**: 尝试常规排查
