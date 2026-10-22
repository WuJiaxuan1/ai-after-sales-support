# AI Agent 知识库（Knowledge Base）

> 本目录存放售后系统使用的知识文档。知识库分为“用户回答知识”和“系统控制规则”两类，二者必须分离使用。

## 知识库结构

| 文件 | 类型 | 用途 | 是否进入用户回答 RAG |
|---|---|---|---|
| `after-sales-policies.md` | 用户回答知识 | 退换货、退款、维修、物流等售后政策 | 是 |
| `troubleshooting-knowledge.md` | 用户回答知识 | 全品类普通问题的基础排查与使用指导 | 是 |
| `safety-knowledge.md` | 安全知识 | 全品类安全风险分类、风险提示与安全处置知识 | 仅 Safety Gate / Safety RAG |
| `handoff-rules.md` | 系统控制规则 | Human Handoff 的触发条件和禁止事项 | 否 |
| `priority-policy.md` | 系统控制规则 | P0-P3 计算与队列排序 | 否 |

## 核心边界

1. Workflow 决定合法业务路径，AI 不得创建 Workflow 中不存在的节点或连接。
2. 用户主动输入普通自由文本时，可以同时进行 Longest Reliable Existing Path 推断与普通 RAG 检索。
3. RAG 只提供知识依据，不负责修改 Workflow，不负责真正创建人工工单。
4. Safety Gate 位于普通 Workflow / 普通 RAG 之前。
5. Safety Gate 采用两层识别：
   - 第一层：确定性高置信规则，捕获明确或典型安全表达；
   - 第二层：受限语义安全分类器，识别没有固定关键词但语义上存在安全隐患的表达。
6. 只要系统认定存在 `SUSPECTED_SAFETY_RISK` 或 `CONFIRMED_SAFETY_RISK`，都必须由后端直接创建人工工单并触发 `SAFETY_RISK`。不要求用户再次点击确认。
7. 安全问题不得继续执行普通故障排查。系统只提供必要的预防性安全提示，然后转人工。
8. AI 生成“已转人工”“已创建工单”等文字不代表业务动作成功。只有后端 Handoff Manager 成功创建队列项后才能向用户宣告成功。

## RAG 加载建议

普通售后回答 RAG 只加载：

- `after-sales-policies.md`
- `troubleshooting-knowledge.md`

Safety RAG 只加载：

- `safety-knowledge.md`

以下文档不要作为用户回答 RAG 的语料：

- `handoff-rules.md`
- `priority-policy.md`

这些文档属于系统控制规则，应由确定性后端逻辑执行。

## 知识片段标识规范

每个知识片段包含：

```text
source_id
source_title
source_version
chunk_id
```

知识内容由人工维护。AI 不得自动新增、修改或删除知识库规则。
