# AI Agent Skills（能力模块）

> 本目录定义 AI Agent 的各项能力模块（Skill）。每个 Skill 包含输入/输出契约、Prompt 模板、行为规则、校验逻辑和验收用例。

---

## Skills 总览

| 文件 | Skill | 职责 | 核心约束 |
|---|---|---|---|
| `semantic-mapper.md` | 语义映射 | 将自由文本映射到当前节点已有选项 | 只能映射已有选项，必须用户确认 |
| `rag-qa-service.md` | RAG 知识问答 | 基于 RAG 知识回答售后问题 | 只用 RAG 依据，不执行业务动作 |
| `handoff-packet-generator.md` | Handoff 包生成 | 生成结构化转人工数据包 | 不篡改事实，不估算金额 |
| `priority-calculator.md` | 优先级计算 | 计算 P0-P3 人工接入优先级 | 只看安全和可验证金额 |
| `workflow-navigator.md` | Workflow 导航 | 管理决策树节点推进和回退 | 服务端校验，不信任前端 |
| `case-state-machine.md` | Case 状态机 | 管理 Case 全生命周期状态流转 | 幂等、版本校验、审计留痕 |

---

## Skill 间调用关系

```
用户操作
    │
    ▼
┌─────────────────┐
│ Workflow Navigator│ ── 推进/回退 Workflow
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
[按钮路径]  [自由文本]
    │         │
    │         ▼
    │   ┌──────────────┐
    │   │ Semantic Mapper│ ── 映射到已有选项
    │   └──────┬───────┘
    │          │ 用户确认
    │          ▼
    └──────────┤
               ▼
        ┌─────────────┐
        │ Case State   │ ── 管理状态流转
        │ Machine      │
        └──────┬──────┘
               │
          ┌────┴────┐
          │         │
          ▼         ▼
    [AI_RAG_SERVICE] [HANDOFF]
          │              │
          ▼              ▼
    ┌───────────┐  ┌──────────────────┐
    │ RAG QA    │  │ Handoff Packet   │
    │ Service   │  │ Generator        │
    └───────────┘  └────────┬─────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Priority     │
                    │ Calculator   │
                    └──────────────┘
```

---

## 通用约束

所有 Skill 必须遵守以下通用约束：

### 1. 分层原则
```
Facts ≠ Diagnosis ≠ User Intent ≠ Action
```
- Facts：用户明确确认的事实
- Diagnosis：AI 疑似判断
- User Intent：用户明确表达的处理诉求
- Action：系统允许执行的动作

### 2. 确认原则
```
用户自己选择的 → 直接确认
AI 推断的      → 必须确认
AI 无法确定的  → 不继续猜
RAG 没有依据的 → 不自由补充
AI 知道规则 ≠ AI 拥有执行权限
```

### 3. 审计原则
- 所有状态变更必须生成审计事件
- 历史事件不覆盖
- AI 生成内容标记 `actor=ai`，不覆盖用户确认事实

### 4. 幂等原则
- 状态变更请求携带 `idempotency_key` + `case_version`
- 重复请求返回已有结果
- 过期请求返回最新快照
