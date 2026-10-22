# 全品类普通售后排查知识库

> 本文件供普通售后 RAG 使用。安全问题不在本文件中排查；一旦 Safety Gate 命中，应立即退出普通排查并自动转人工。

## 1. 数码 / 家电

### K-TROUBLE-001: 数码家电无法工作

- source_id: TROUBLE-DIGITAL-001
- source_title: 数码家电完全无法工作基础排查
- source_version: mvp-v2
- chunk_id: T-DIGITAL-001-01

在不存在任何安全风险信号的前提下，可依次确认电源、连接状态、基础设置和说明书要求。每次只建议一个低风险步骤并等待用户反馈。

如果出现冒烟、火花、漏电、异常发热、鼓包、漏液、焦糊味等安全信号，立即停止本流程。

### K-TROUBLE-002: 数码家电部分功能异常

- source_id: TROUBLE-DIGITAL-002
- source_title: 数码家电部分功能异常基础排查
- source_version: mvp-v2
- chunk_id: T-DIGITAL-002-01

可确认：
- 是否仅单个功能异常；
- 是否存在设置、连接或兼容性因素；
- 是否能在不拆机、不继续危险测试的前提下复现。

不得凭症状直接认定硬件损坏。

### K-TROUBLE-003: 鼠标与外设功能异常

- source_id: TROUBLE-PERIPHERAL-001
- source_title: 鼠标键盘耳机等外设基础排查
- source_version: mvp-v2
- chunk_id: T-PERIPHERAL-001-01

鼠标按键、滚轮、连接等问题可先确认电源/电量、连接、其他设备测试、清洁外部可见区域等低风险因素。

---

## 2. 服饰 / 鞋包

### K-TROUBLE-004: 尺码与版型问题

- source_id: TROUBLE-APPAREL-001
- source_title: 服饰鞋包尺码与版型问题
- source_version: mvp-v2
- chunk_id: T-APPAREL-001-01

可帮助用户区分：
- 尺码偏大或偏小；
- 版型与预期不符；
- 商品实际尺寸与页面标注存在疑问。

不得仅凭“穿着不舒服”认定商品质量问题。涉及退换货条件时引用售后政策知识。

### K-TROUBLE-005: 面料、做工与外观问题

- source_id: TROUBLE-APPAREL-002
- source_title: 服饰鞋包面料做工与外观问题
- source_version: mvp-v2
- chunk_id: T-APPAREL-002-01

可询问开线、脱胶、五金、面料、颜色、变形等具体表现。若存在尖锐部件外露、严重结构断裂等可能伤人的信号，退出普通排查并进入 Safety Gate。

---

## 3. 家居 / 生活用品

### K-TROUBLE-006: 安装组装与结构问题

- source_id: TROUBLE-HOME-001
- source_title: 家居生活用品安装与结构问题
- source_version: mvp-v2
- chunk_id: T-HOME-001-01

普通安装问题可以基于说明书确认零部件、安装顺序和规格适配。

若用户描述倾倒、承重部件断裂、尖锐部件外露、夹伤风险等，应立即退出普通安装指导并进入 Safety Gate。

### K-TROUBLE-007: 尺寸规格与使用适配

- source_id: TROUBLE-HOME-002
- source_title: 家居用品尺寸规格与适配问题
- source_version: mvp-v2
- chunk_id: T-HOME-002-01

可帮助核对页面规格、用户实际空间与商品尺寸描述，但不得凭文本推断页面不存在的参数。

---

## 4. 美妆 / 个护

### K-TROUBLE-008: 使用方法与产品说明

- source_id: TROUBLE-BEAUTY-001
- source_title: 美妆个护普通使用咨询
- source_version: mvp-v2
- chunk_id: T-BEAUTY-001-01

可基于产品知识回答使用顺序、保存方式、规格说明等。

若用户描述明显灼烧、刺痛、红肿、疑似过敏或强烈刺激，应立即进入 Safety Gate，不继续建议试用。

---

## 5. 食品 / 消耗品

### K-TROUBLE-009: 保存、日期与产品说明

- source_id: TROUBLE-FOOD-001
- source_title: 食品消耗品普通咨询
- source_version: mvp-v2
- chunk_id: T-FOOD-001-01

可回答保存方式、规格、生产日期与保质期规则等普通问题。

如果用户描述腐败、霉变、危险异物、疑似污染、食用后明显不适等，应立即进入 Safety Gate，不建议继续食用验证。

---

## 6. 通用售后原则

### K-TROUBLE-010: 普通 RAG 行为规范

- source_id: TROUBLE-GENERAL-001
- source_title: 普通售后 RAG 行为规范
- source_version: mvp-v2
- chunk_id: T-GENERAL-001-01

- 普通 RAG 只提供知识和低风险排查建议。
- 每次建议应清楚、短而可执行。
- 不得编造知识库不存在的规格、政策和处理权限。
- 不得把 AI 推断直接写成用户已确认事实。
- 用户主动输入自由文本时可调用本知识库，同时由 Semantic Mapper 进行 Longest Reliable Existing Path 推断。
- RAG 不能修改 Workflow。
- Safety Gate 优先于普通 RAG；安全风险不做普通排查。
