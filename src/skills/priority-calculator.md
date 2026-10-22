# Skill: 优先级计算器（Priority Calculator）

> 本 Skill 负责在 Handoff 创建时计算人工客服接入优先级。优先级基于安全风险和可验证经济暴露金额，不受 AI 主观判断影响。

---

## Skill 元信息

- **skill_id**: skill-priority-calculator
- **skill_name**: 优先级计算器
- **version**: mvp-v1
- **触发条件**: HANDOFF 创建时自动调用
- **输入来源**: Case 数据 + 模拟业务数据
- **输出去向**: Handoff Packet + 人工客服队列排序

---

## 输入契约

```json
{
  "case_id": "CASE-001",
  "is_safety_risk": false,
  "verified_exposure_amount": 899.00,
  "claimed_amount": null,
  "priority_policy": {
    "priority_policy_version": "mvp-v1",
    "p1_min_exposure": 2000,
    "p2_min_exposure": 500,
    "p3_min_exposure": 0,
    "aging_interval_minutes": 60,
    "aging_ceiling": "P1"
  }
}
```

---

## 输出契约

```json
{
  "priority": "P2",
  "priority_reason": "verified_exposure_amount = 899.00，>= p2_min_exposure(500) 且 < p1_min_exposure(2000)，映射为 P2",
  "missing_exposure_data": false,
  "priority_policy_version": "mvp-v1"
}
```

---

## 计算逻辑（伪代码）

```python
def calculate_priority(case, policy):
    # Step 1: 安全风险检查
    if case.is_safety_risk:
        return {
            "priority": "P0",
            "priority_reason": "存在已确认安全风险",
            "missing_exposure_data": False
        }
    
    # Step 2: 读取可验证经济暴露金额
    amount = case.verified_exposure_amount
    
    # Step 3: 金额缺失处理
    if amount is None:
        return {
            "priority": "P3",
            "priority_reason": "verified_exposure_amount 缺失，临时 P3 等待人工核验",
            "missing_exposure_data": True
        }
    
    # Step 4: 按金额区间映射
    if amount >= policy.p1_min_exposure:
        return {"priority": "P1", "priority_reason": f"金额 {amount} >= P1 阈值 {policy.p1_min_exposure}", "missing_exposure_data": False}
    elif amount >= policy.p2_min_exposure:
        return {"priority": "P2", "priority_reason": f"金额 {amount} >= P2 阈值 {policy.p2_min_exposure}", "missing_exposure_data": False}
    else:
        return {"priority": "P3", "priority_reason": f"金额 {amount} < P2 阈值", "missing_exposure_data": False}
```

---

## 关键约束

1. **P0 只能由安全风险产生** — 不因投诉、强烈情绪、金额大小产生
2. **verified_exposure_amount 必须来自系统数据** — 订单、退款、维修、赔付等结构化数据
3. **claimed_amount 不参与排序** — 用户自述金额只保存为参考
4. **AI 不得估算金额** — 数据缺失时标记 `MISSING_EXPOSURE_DATA`，以 P3 入队
5. **金额区间可配置** — 通过 `priority_policy` 动态读取，不硬编码

---

## 老化升级逻辑

```python
def age_priority(current_priority, queued_at, now, policy):
    if current_priority == "P0":
        return current_priority  # P0 不参与老化
    
    elapsed_minutes = (now - queued_at).total_minutes()
    age_steps = int(elapsed_minutes // policy.aging_interval_minutes)
    
    priority_order = ["P3", "P2", "P1"]
    current_index = priority_order.index(current_priority)
    new_index = min(current_index + age_steps, priority_order.index(policy.aging_ceiling))
    
    return priority_order[new_index]
```

---

## 验收用例

| 场景 | verified_exposure_amount | is_safety_risk | 期望 priority |
|---|---|---|---|
| 电池鼓包 | 任意 | true | P0 |
| 高金额退款 | 3000 | false | P1 |
| 中金额退款 | 899 | false | P2 |
| 低金额退款 | 50 | false | P3 |
| 金额缺失 | null | false | P3 + MISSING_EXPOSURE_DATA |
| 安全风险 + 高金额 | 3000 | true | P0（安全优先） |
| 等待 2 小时的 P3 | - | false | P1（P3→P2→P1） |
| 等待 2 小时的 P2 | - | false | P1（P2→P1） |
| 等待 2 小时的 P1 | - | false | P1（已达天花板） |
| 等待 2 小时的 P0 | - | true | P0（不参与老化） |
