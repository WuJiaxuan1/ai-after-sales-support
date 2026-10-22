# 售后政策知识库

> 本文件供普通售后 RAG 使用，包含退换货、退款、维修、物流和通用安全政策。具体安全识别与安全处置知识见 `safety-knowledge.md`。

## 1. 退换货

### K-POLICY-001: 七天无理由退货

- source_id: POLICY-RETURN-001
- source_title: 七天无理由退货政策
- source_version: mvp-v2
- chunk_id: RETURN-001-01

适用条件：
- 自签收之日起 7 天内；
- 商品未使用、未损坏且不影响二次销售；
- 商品不属于法律、平台或商品规则明确不适用无理由退货的特殊品类。

用户需要在售后入口提交申请。涉及具体订单是否满足条件时，AI 只能解释规则，不能代替真实订单审核。

### K-POLICY-002: 质量问题换货

- source_id: POLICY-EXCHANGE-001
- source_title: 质量问题换货政策
- source_version: mvp-v2
- chunk_id: EXCHANGE-001-01

商品存在非人为质量问题时，可根据平台流程提交换货申请并提供必要的问题描述或证据。AI 可以说明流程，不能直接认定责任。

## 2. 退款

### K-POLICY-003: 退款规则

- source_id: POLICY-REFUND-001
- source_title: 退款政策
- source_version: mvp-v2
- chunk_id: REFUND-001-01

退款一般按原支付路径返回。具体到账时间受支付渠道影响。

退款被拒绝的常见原因可能包括超过时限、商品状态不符合规则、凭证不足等。

AI 可以：
- 解释一般规则；
- 提醒用户准备材料。

AI 不可以：
- 推翻退款判定；
- 真实执行退款；
- 进行责任认定。

需要真实复核时进入 `AUTHORITY_BOUNDARY` 人工处理。

### K-POLICY-004: 退款未到账

- source_id: POLICY-REFUND-002
- source_title: 退款未到账说明
- source_version: mvp-v2
- chunk_id: REFUND-002-01

如页面已经显示退款成功但长期未到账，可先核对支付渠道的处理周期。需要查询真实资金状态时，系统无查询权限，应转人工。

## 3. 维修 / 保修

### K-POLICY-005: 保修范围

- source_id: POLICY-WARRANTY-001
- source_title: 标准保修政策
- source_version: mvp-v2
- chunk_id: WARRANTY-001-01

AI 可以解释一般保修范围、常见流程和材料要求，但不得对“人为损坏”“责任归属”等争议作最终认定。

### K-POLICY-006: 维修结果异议

- source_id: POLICY-WARRANTY-002
- source_title: 维修结果异议政策
- source_version: mvp-v2
- chunk_id: WARRANTY-002-01

维修后问题仍存在、用户不认可维修责任认定或要求重新审核时，应进入人工权限边界处理。

## 4. 物流

### K-POLICY-007: 物流异常

- source_id: POLICY-LOGISTICS-001
- source_title: 物流异常处理规则
- source_version: mvp-v2
- chunk_id: LOGISTICS-001-01

普通物流问题包括未发货、物流长时间未更新、显示签收但未收到、包裹破损等。

AI 可以提供一般流程说明。需要查询真实订单或物流内部状态时，应转人工。

## 5. 全品类安全政策

### K-POLICY-008: Safety Gate 总原则

- source_id: POLICY-SAFETY-001
- source_title: 全品类安全风险处理政策
- source_version: mvp-v2
- chunk_id: SAFETY-POLICY-001-01

安全风险不限于电器和电池，应覆盖：

- 热与火灾；
- 电气与触电；
- 爆炸、压力与电池；
- 化学、腐蚀和有害物质；
- 食品、摄入和污染；
- 过敏、刺激和皮肤接触；
- 机械伤害和结构失效；
- 儿童误吞、窒息、缠绕和卡困；
- 卫生和生物污染；
- 其他合理的人身或财产安全隐患。

系统采用两层 Safety Gate：

1. 确定性高置信规则；
2. 受限语义安全识别。

只要系统识别到 `SUSPECTED_SAFETY_RISK` 或 `CONFIRMED_SAFETY_RISK`：

- 停止普通 Workflow/RAG 排查；
- 后端自动创建真实人工 Handoff；
- `handoff_trigger = SAFETY_RISK`；
- P0；
- 不要求用户再次点击“转人工”或确认安全风险；
- 只提供必要的预防性安全提示。

## 6. 普通使用咨询

### K-POLICY-009: 使用指导边界

- source_id: KNOWLEDGE-USAGE-001
- source_title: 普通使用指导规则
- source_version: mvp-v2
- chunk_id: USAGE-001-01

普通使用咨询可以包括安装、首次使用、功能设置、规格适配、清洁保养等。

回答必须基于知识库已有内容。知识不足时不得编造。

如果用户描述出现任何安全风险信号，Safety Gate 的优先级高于普通使用指导。
