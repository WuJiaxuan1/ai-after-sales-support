# 优先级策略知识库

> 本文档定义人工客服接入优先级的计算规则。优先级仅在 HANDOFF 创建后计算，用于人工客服工作台的 Case 排序。

---

## 1. 优先级定义

### K-PRIORITY-001: 优先级等级

- source_id: RULE-PRIORITY-001
- source_title: 人工接入优先级规则
- source_version: mvp-v1
- chunk_id: PRI-001-01

| 等级 | 产生条件 | 说明 |
|---|---|---|
| **P0** | 已确认的安全风险（电池鼓包、冒烟、漏电、过热、漏液等） | 最高优先级，只能由安全风险产生 |
| **P1** | verified_exposure_amount >= P1 阈值 | 高经济暴露 |
| **P2** | verified_exposure_amount >= P2 阈值 | 中经济暴露 |
| **P3** | verified_exposure_amount >= 0 或缺失 | 低经济暴露或无法验证 |

---

## 2. 优先级计算规则

### K-PRIORITY-002: 计算流程

- source_id: RULE-PRIORITY-002
- source_title: 优先级计算流程
- source_version: mvp-v1
- chunk_id: PRI-002-01

**计算顺序（固定）：**

```
1. 是否存在已确认安全风险？
   → 是：P0，结束
   → 否：继续

2. 读取 verified_exposure_amount
   → 存在且 >= p1_min_exposure：P1
   → 存在且 >= p2_min_exposure：P2
   → 存在且 >= 0：P3
   → 缺失：标记 MISSING_EXPOSURE_DATA，临时 P3，Packet 中注明
```

**关键约束：**
- `verified_exposure_amount` 必须来自模拟订单、退款、维修或赔付数据
- 用户自述金额只保存为 `claimed_amount`，不得参与排序
- AI 不得估算金额
- 金额缺失时不得跳过人工，标记风险后以 P3 入队

---

## 3. 优先级老化机制

### K-PRIORITY-003: 等待升级规则

- source_id: RULE-PRIORITY-003
- source_title: 优先级老化升级规则
- source_version: mvp-v1
- chunk_id: PRI-003-01

**规则：**
- 非 P0 Case 进入 QUEUED 状态后，每等待满 60 分钟提升一级
- P3 → P2 → P1
- 最高提升至 P1
- P0 只能由安全风险产生，不会因老化产生

**配置参数：**

```json
{
  "priority_policy_version": "mvp-v1",
  "p1_min_exposure": "可配置",
  "p2_min_exposure": "可配置",
  "p3_min_exposure": 0,
  "aging_interval_minutes": 60,
  "aging_ceiling": "P1"
}
```

---

## 4. 队列排序规则

### K-PRIORITY-004: 排序逻辑

- source_id: RULE-PRIORITY-004
- source_title: 人工客服队列排序
- source_version: mvp-v1
- chunk_id: PRI-004-01

**排序规则：**
1. 先按优先级排序：P0 > P1 > P2 > P3
2. 同一优先级内按 `queued_at` 升序（FIFO，先进先出）
3. 优先级提升时更新排序位置

**人工接单规则：**
- 同一 Case 不允许两位客服同时接单
- 使用原子状态转换（ASSIGNED 前的 CAS 操作）
- 已被接单的 Case 从队列中移除
