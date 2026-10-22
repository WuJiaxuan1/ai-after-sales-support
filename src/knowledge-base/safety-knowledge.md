# 全品类安全风险知识库

> 本文件用于 Safety Gate 与 Safety RAG。它不是普通故障排查手册。
> 一旦识别为 `SUSPECTED_SAFETY_RISK` 或 `CONFIRMED_SAFETY_RISK`，系统应停止普通排查并自动转人工。
> 本知识库覆盖全品类，不以充电宝、电池或电器作为唯一安全场景。

---

## 1. 安全风险分类体系

### K-SAFETY-001: 热、火灾与高温风险

- source_id: SAFETY-THERMAL-001
- source_title: 热与火灾风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-THERMAL-001-01

**典型风险信号：**
- 冒烟、起火、火花、烧焦、熔化
- 明显异常发热、越来越烫、烫手
- 出现焦糊味、烧塑料味或其他异常高温气味
- 充电、运行或待机时温度明显异常

**可能涉及品类：**
数码、电器、插座、电源设备、照明设备、加热用品、厨房用品、儿童电器等。

**系统动作：**
- `CONFIRMED` 与 `SUSPECTED` 均自动转人工；
- 不继续要求用户尝试充电、通电、重启或拆机；
- 在真实 Handoff 创建成功后，提示用户停止使用并远离明显异常热源。

---

### K-SAFETY-002: 电气与触电风险

- source_id: SAFETY-ELECTRICAL-001
- source_title: 电气与触电风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-ELECTRICAL-001-01

**典型风险信号：**
- 漏电、触电、麻手、电击感
- 插头、插座或设备异常火花
- 电线破损并露出导体
- 通电后有异常噼啪声、明显电气异味

**系统动作：**
- 自动转人工；
- 不建议继续插拔、通电测试或自行拆修；
- 如可在不接触危险部位的前提下安全断电，可提示停止继续使用。

---

### K-SAFETY-003: 爆炸、压力与电池风险

- source_id: SAFETY-PRESSURE-001
- source_title: 爆炸压力与电池风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-PRESSURE-001-01

**典型风险信号：**
- 爆炸、爆裂、炸开、异常喷射
- 电池鼓包、膨胀、外壳被顶起
- 电池明显异常发热、漏液
- 压力容器出现异常变形、膨胀或泄漏

**系统动作：**
- 自动转人工；
- 不建议继续充电、挤压、刺穿、拆卸或自行处理异常电池/压力部件；
- 优先给出远离异常商品的安全提示。

---

### K-SAFETY-004: 化学、腐蚀与有害物质风险

- source_id: SAFETY-CHEMICAL-001
- source_title: 化学与有害物质风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-CHEMICAL-001-01

**典型风险信号：**
- 清洁剂、化学用品、电池液等异常泄漏
- 强烈刺激性气味
- 接触后出现明显灼烧、刺痛或腐蚀迹象
- 容器破损导致不明液体或粉末外泄

**可能涉及品类：**
清洁用品、个护产品、美妆、家居消耗品、电池、汽车用品等。

**系统动作：**
- 自动转人工；
- 不指导用户混合、加热、闻嗅或自行测试未知物质；
- 只提供停止继续接触、避免扩大暴露等一般安全提示。

---

### K-SAFETY-005: 食品、摄入与污染风险

- source_id: SAFETY-FOOD-001
- source_title: 食品摄入与污染风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-FOOD-001-01

**典型风险信号：**
- 明显腐败、霉变、异常鼓包、异常气味
- 食品中出现玻璃、金属、尖锐物或其他危险异物
- 怀疑受到化学品、清洁剂等污染
- 食用后出现明显不适并怀疑与商品相关
- 婴幼儿食品存在明显异常

**系统动作：**
- 自动转人工；
- 不建议继续食用、试吃或通过再次食用验证；
- 不由 AI 做医学诊断，只记录用户原始描述并完成售后转接。

---

### K-SAFETY-006: 过敏、刺激与皮肤接触风险

- source_id: SAFETY-ALLERGY-001
- source_title: 过敏刺激与皮肤接触风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-ALLERGY-001-01

**典型风险信号：**
- 使用美妆、个护、服饰、清洁用品后出现明显红肿、灼烧、刺痛
- 出现明显皮疹、肿胀或强烈不适
- 用户明确表示怀疑商品引起过敏或刺激

**系统动作：**
- 自动转人工；
- 不建议继续试用以确认是否过敏；
- AI 不做医疗诊断，不判断严重程度，只提供停止继续接触等一般性安全提醒。

---

### K-SAFETY-007: 机械伤害与结构失效风险

- source_id: SAFETY-MECHANICAL-001
- source_title: 机械伤害与结构失效风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-MECHANICAL-001-01

**典型风险信号：**
- 家具、架体、儿童用品存在倾倒或坍塌迹象
- 椅腿、支架、承重部件开裂、断裂、松脱
- 尖锐金属、玻璃、刀刃等异常外露
- 夹手、割伤、卡住、卷入等危险
- 运动或承重用品出现可能导致跌落的结构异常

**系统动作：**
- 自动转人工；
- 不建议用户继续承重、摇晃测试或自行验证极限；
- 提醒停止继续使用存在结构危险的商品。

---

### K-SAFETY-008: 儿童误吞、窒息、缠绕与卡困风险

- source_id: SAFETY-CHILD-001
- source_title: 儿童误吞窒息缠绕与卡困风险
- source_version: mvp-v2
- chunk_id: SAFETY-CHILD-001-01

**典型风险信号：**
- 玩具或儿童用品小零件容易脱落
- 存在误吞、窒息、勒颈、缠绕风险
- 孔洞、夹缝或结构可能导致儿童手脚、头部卡住
- 儿童用品承重或固定结构明显异常

**系统动作：**
- 自动转人工；
- 不建议继续让儿童接触或试用以确认问题。

---

### K-SAFETY-009: 卫生、生物污染与异常污染风险

- source_id: SAFETY-BIO-001
- source_title: 卫生与生物污染风险识别及处置
- source_version: mvp-v2
- chunk_id: SAFETY-BIO-001-01

**典型风险信号：**
- 商品出现明显霉菌、虫害、异常分泌物或疑似生物污染
- 与皮肤、食品或个人护理直接接触的商品存在严重卫生异常
- 包装破损并伴随明显污染迹象

**系统动作：**
- 自动转人工；
- 不要求用户继续接触、使用或食用以验证。

---

## 2. Safety Gate 两层识别规则

### K-SAFETY-010: 第一层确定性规则

- source_id: SAFETY-GATE-RULE-001
- source_title: Safety Gate 确定性高置信规则
- source_version: mvp-v2
- chunk_id: SAFETY-GATE-RULE-001-01

第一层用于捕获明显或典型安全表达。包括但不限于：

- 冒烟、起火、爆炸、爆裂、火花
- 漏电、触电、电击、麻手
- 鼓包、膨胀、漏液
- 烫手、特别烫、越来越烫、异常发热
- 焦糊味、烧焦味、刺激性异味
- 腐蚀、灼烧、强烈刺痛、明显红肿
- 食品腐败、霉变、危险异物、疑似污染
- 家具倾倒、承重断裂、尖锐部件外露
- 误吞、窒息、缠绕、卡住
- 明显霉菌、虫害或严重污染

命中第一层规则后可直接形成安全信号，不需要用户再次点击“确认安全风险”。

**注意语境：**
系统应尽量避免被明显否定或引用语境误触发，例如：
- “没有冒烟，只是不会开机”
- “说明书说如果冒烟要断电，但我的没有”
- “我想问冒烟是什么意思”

---

### K-SAFETY-011: 第二层受限语义识别

- source_id: SAFETY-GATE-SEMANTIC-001
- source_title: Safety Gate 受限语义分类规则
- source_version: mvp-v2
- chunk_id: SAFETY-GATE-SEMANTIC-001-01

第二层用于识别没有固定关键词、但语义上存在合理安全隐患的表达。

受限语义分类器只允许输出预设风险类别，例如：

```text
THERMAL_FIRE
ELECTRICAL
EXPLOSION_PRESSURE
CHEMICAL_TOXIC
FOOD_INGESTION
ALLERGIC_IRRITATION
MECHANICAL_INJURY
CHILD_CHOKING_ENTRAPMENT
BIOLOGICAL_CONTAMINATION
OTHER_SAFETY
```

同时输出：

```text
safety_signal: true / false
certainty: SUSPECTED / CONFIRMED / NONE
hazard_type
evidence
```

AI 不得创造新的 Handoff 类型，也不得自行执行业务动作。

只要 `safety_signal=true` 且 certainty 为 `SUSPECTED` 或 `CONFIRMED`，后端统一执行：

```text
SAFETY_RISK
→ 创建真实 Handoff
→ P0
→ 返回安全提示
```

---

## 3. 安全回答原则

### K-SAFETY-012: 安全场景回答边界

- source_id: SAFETY-RESPONSE-001
- source_title: 安全风险回答边界
- source_version: mvp-v2
- chunk_id: SAFETY-RESPONSE-001-01

安全场景只允许提供低风险、通用、预防性的提示，例如：

- 停止继续使用异常商品
- 不继续通电、充电、加热、承重、食用或试用
- 避免自行拆卸、刺穿、挤压或测试明显异常部件
- 避免儿童继续接触存在疑似安全隐患的商品
- 保留商品、包装、订单和能够安全取得的问题证据，供人工客服后续处理

禁止：

- 让用户继续使用以验证问题
- 让用户自行拆机、拆电池、拆承重结构
- 对医疗症状作诊断
- 对化学物质给出危险的中和、混合、加热操作
- 在真实人工工单尚未创建时声称“已经转人工”或“已经创建紧急工单”
