"""
Default MVP configuration — workflow tree, priority policy, system thresholds.
Loaded at startup; can be overridden by passing a different JSON file.
"""
import os

from ..models.schemas import (
    WorkflowConfig, WorkflowNode, WorkflowOption,
    PriorityPolicy, SystemConfig,
)

MVP_WORKFLOW = WorkflowConfig(
    workflow_id="after_sales_v2",
    workflow_version="mvp-v2",
    start_node="N0",
    nodes={

        # ================================================================
        # 第一层：售后业务问题
        # ================================================================
        "N0": WorkflowNode(
            id="N0",
            type="choice",
            dimension="issue_category",
            question="您需要什么售后帮助？",
            options=[
                WorkflowOption(
                    option_id="ISSUE_GUIDANCE",
                    label="使用 / 操作咨询",
                    next_node="GUIDANCE_CATEGORY",
                ),
                WorkflowOption(
                    option_id="ISSUE_PRODUCT",
                    label="商品本身问题",
                    next_node="PRODUCT_CATEGORY",
                ),
                WorkflowOption(
                    option_id="ISSUE_MISMATCH",
                    label="商品与描述不符",
                    next_node="MISMATCH_TYPE",
                ),
                WorkflowOption(
                    option_id="ISSUE_MISSING_WRONG",
                    label="缺件 / 错件 / 数量问题",
                    next_node="MISSING_WRONG_TYPE",
                ),
                WorkflowOption(
                    option_id="ISSUE_LOGISTICS",
                    label="物流 / 配送问题",
                    next_node="LOGISTICS_STATUS",
                ),
                WorkflowOption(
                    option_id="ISSUE_REFUND",
                    label="退货 / 退款问题",
                    next_node="REFUND_STATUS",
                ),
                WorkflowOption(
                    option_id="ISSUE_WARRANTY",
                    label="维修 / 保修问题",
                    next_node="WARRANTY_STATUS",
                ),
                WorkflowOption(
                    option_id="ISSUE_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 使用 / 操作咨询：先确定商品类别
        # ================================================================
        "GUIDANCE_CATEGORY": WorkflowNode(
            id="GUIDANCE_CATEGORY",
            type="choice",
            dimension="product_category",
            question="您咨询的商品属于哪一类？",
            options=[
                WorkflowOption(
                    option_id="GUIDANCE_DIGITAL",
                    label="数码 / 家电",
                    next_node="GUIDANCE_DIGITAL_TYPE",
                ),
                WorkflowOption(
                    option_id="GUIDANCE_APPAREL",
                    label="服饰 / 鞋包",
                    next_node="GUIDANCE_APPAREL_TYPE",
                ),
                WorkflowOption(
                    option_id="GUIDANCE_HOME",
                    label="家居 / 生活用品",
                    next_node="GUIDANCE_HOME_TYPE",
                ),
                WorkflowOption(
                    option_id="GUIDANCE_BEAUTY",
                    label="美妆 / 个护",
                    next_node="GUIDANCE_BEAUTY_TYPE",
                ),
                WorkflowOption(
                    option_id="GUIDANCE_FOOD",
                    label="食品 / 消耗品",
                    next_node="GUIDANCE_FOOD_TYPE",
                ),
                WorkflowOption(
                    option_id="GUIDANCE_OTHER_CATEGORY",
                    label="其他商品",
                    next_node="GUIDANCE_GENERAL_TYPE",
                ),
            ],
        ),

        "GUIDANCE_DIGITAL_TYPE": WorkflowNode(
            id="GUIDANCE_DIGITAL_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的使用帮助？",
            options=[
                WorkflowOption(
                    option_id="GD_SETUP",
                    label="首次使用 / 安装",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GD_PAIRING",
                    label="连接 / 配对",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GD_SETTINGS",
                    label="功能设置",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GD_OPERATION",
                    label="操作方法",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GD_CARE",
                    label="清洁 / 保养",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GD_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "GUIDANCE_APPAREL_TYPE": WorkflowNode(
            id="GUIDANCE_APPAREL_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的帮助？",
            options=[
                WorkflowOption(
                    option_id="GA_SIZE",
                    label="尺码 / 适配咨询",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GA_WEAR",
                    label="穿着 / 使用方法",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GA_WASH",
                    label="洗涤 / 清洁",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GA_CARE",
                    label="保养 / 存放",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GA_MATERIAL",
                    label="材质 / 产品说明",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GA_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "GUIDANCE_HOME_TYPE": WorkflowNode(
            id="GUIDANCE_HOME_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的使用帮助？",
            options=[
                WorkflowOption(
                    option_id="GH_INSTALL",
                    label="安装 / 组装",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GH_OPERATION",
                    label="使用方法",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GH_SIZE",
                    label="尺寸 / 规格适配",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GH_CLEAN",
                    label="清洁 / 保养",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GH_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "GUIDANCE_BEAUTY_TYPE": WorkflowNode(
            id="GUIDANCE_BEAUTY_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的使用帮助？",
            options=[
                WorkflowOption(
                    option_id="GB_METHOD",
                    label="使用方法 / 步骤",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GB_AMOUNT",
                    label="使用量 / 使用频率",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GB_INFO",
                    label="成分 / 产品说明",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GB_STORAGE",
                    label="保存 / 保质期",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GB_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "GUIDANCE_FOOD_TYPE": WorkflowNode(
            id="GUIDANCE_FOOD_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的帮助？",
            options=[
                WorkflowOption(
                    option_id="GF_USE",
                    label="食用 / 使用方法",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GF_STORAGE",
                    label="保存方式",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GF_EXPIRY",
                    label="生产日期 / 保质期",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GF_INFO",
                    label="规格 / 产品说明",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GF_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "GUIDANCE_GENERAL_TYPE": WorkflowNode(
            id="GUIDANCE_GENERAL_TYPE",
            type="choice",
            dimension="guidance_type",
            question="您主要需要哪方面的帮助？",
            options=[
                WorkflowOption(
                    option_id="GG_USE",
                    label="使用方法",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GG_INSTALL",
                    label="安装 / 组装",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GG_SPEC",
                    label="规格 / 适配",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GG_CARE",
                    label="清洁 / 保养",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="GG_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 商品本身问题：先确定商品类别
        # ================================================================
        "PRODUCT_CATEGORY": WorkflowNode(
            id="PRODUCT_CATEGORY",
            type="choice",
            dimension="product_category",
            question="您的商品属于哪一类？",
            options=[
                WorkflowOption(
                    option_id="PRODUCT_DIGITAL",
                    label="数码 / 家电",
                    next_node="PRODUCT_DIGITAL_TYPE",
                ),
                WorkflowOption(
                    option_id="PRODUCT_APPAREL",
                    label="服饰 / 鞋包",
                    next_node="PRODUCT_APPAREL_TYPE",
                ),
                WorkflowOption(
                    option_id="PRODUCT_HOME",
                    label="家居 / 生活用品",
                    next_node="PRODUCT_HOME_TYPE",
                ),
                WorkflowOption(
                    option_id="PRODUCT_BEAUTY",
                    label="美妆 / 个护",
                    next_node="PRODUCT_BEAUTY_TYPE",
                ),
                WorkflowOption(
                    option_id="PRODUCT_FOOD",
                    label="食品 / 消耗品",
                    next_node="PRODUCT_FOOD_TYPE",
                ),
                WorkflowOption(
                    option_id="PRODUCT_OTHER_CATEGORY",
                    label="其他商品",
                    next_node="PRODUCT_GENERAL_TYPE",
                ),
            ],
        ),

        # 数码 / 家电
        "PRODUCT_DIGITAL_TYPE": WorkflowNode(
            id="PRODUCT_DIGITAL_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PD_NOT_WORKING",
                    label="完全无法工作",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_PARTIAL",
                    label="部分功能异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_CONNECTION",
                    label="连接 / 配对异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_POWER",
                    label="供电 / 充电异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_DISPLAY_SOUND",
                    label="显示 / 声音异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_PERFORMANCE",
                    label="性能异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_STRUCTURE",
                    label="外观 / 结构异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PD_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # 服饰 / 鞋包
        "PRODUCT_APPAREL_TYPE": WorkflowNode(
            id="PRODUCT_APPAREL_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PA_SIZE",
                    label="尺码 / 版型问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_MATERIAL",
                    label="面料 / 材质问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_WORKMANSHIP",
                    label="做工 / 缝线 / 五金问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_DEFORMATION",
                    label="缩水 / 变形 / 起球",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_APPEARANCE",
                    label="颜色 / 外观问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_EXPERIENCE",
                    label="穿着 / 使用体验问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PA_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # 家居 / 生活用品
        "PRODUCT_HOME_TYPE": WorkflowNode(
            id="PRODUCT_HOME_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PH_STRUCTURE",
                    label="结构松动 / 损坏",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_INSTALL",
                    label="安装 / 组装异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_SIZE",
                    label="尺寸 / 规格问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_MATERIAL",
                    label="材质问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_APPEARANCE",
                    label="表面 / 外观问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_EFFECT",
                    label="使用效果问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PH_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # 美妆 / 个护
        "PRODUCT_BEAUTY_TYPE": WorkflowNode(
            id="PRODUCT_BEAUTY_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PB_PACKAGE",
                    label="包装 / 容器问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PB_TEXTURE",
                    label="质地 / 气味 / 颜色异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PB_LEAK",
                    label="破损 / 漏液",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PB_SPEC",
                    label="容量 / 规格问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PB_EFFECT",
                    label="使用效果异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PB_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # 食品 / 消耗品
        "PRODUCT_FOOD_TYPE": WorkflowNode(
            id="PRODUCT_FOOD_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PF_PACKAGE",
                    label="包装破损 / 异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PF_EXPIRY",
                    label="生产日期 / 保质期问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PF_APPEARANCE",
                    label="外观 / 气味 / 口感异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PF_STORAGE",
                    label="受潮 / 融化 / 状态异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PF_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # 其他商品的兜底模板
        "PRODUCT_GENERAL_TYPE": WorkflowNode(
            id="PRODUCT_GENERAL_TYPE",
            type="choice",
            dimension="product_problem",
            question="商品主要存在什么问题？",
            options=[
                WorkflowOption(
                    option_id="PG_STRUCTURE",
                    label="结构 / 部件损坏",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PG_SPEC",
                    label="尺寸 / 规格问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PG_MATERIAL",
                    label="材质 / 外观问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PG_EFFECT",
                    label="使用效果异常",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="PG_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 商品与描述不符：商品类别通常不是决定业务路径的必要条件
        # ================================================================
        "MISMATCH_TYPE": WorkflowNode(
            id="MISMATCH_TYPE",
            type="choice",
            dimension="mismatch_type",
            question="商品主要在哪方面与描述不符？",
            options=[
                WorkflowOption(
                    option_id="MISMATCH_SPEC",
                    label="规格 / 型号不符",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MISMATCH_APPEARANCE",
                    label="颜色 / 外观不符",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MISMATCH_MATERIAL",
                    label="材质 / 成分不符",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MISMATCH_FUNCTION",
                    label="功能 / 性能与描述不符",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MISMATCH_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 缺件 / 错件 / 数量
        # ================================================================
        "MISSING_WRONG_TYPE": WorkflowNode(
            id="MISSING_WRONG_TYPE",
            type="choice",
            dimension="missing_wrong_type",
            question="您的情况属于哪一种？",
            options=[
                WorkflowOption(
                    option_id="MW_MISSING_PRODUCT",
                    label="缺少商品",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MW_MISSING_ACCESSORY",
                    label="缺少配件",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MW_WRONG_PRODUCT",
                    label="收到错误商品",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MW_QUANTITY",
                    label="商品数量不符",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MW_GIFT",
                    label="赠品 / 附件问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="MW_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 物流 / 配送
        # ================================================================
        "LOGISTICS_STATUS": WorkflowNode(
            id="LOGISTICS_STATUS",
            type="choice",
            dimension="logistics_status",
            question="当前物流或配送问题属于哪一种？",
            options=[
                WorkflowOption(
                    option_id="LG_NOT_SHIPPED",
                    label="一直未发货",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="LG_NO_UPDATE",
                    label="物流长时间未更新",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="LG_SIGNED_MISSING",
                    label="显示已签收但未收到",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="LG_DAMAGED",
                    label="包裹 / 外包装破损",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="LG_ADDRESS",
                    label="配送地址 / 配送方式问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="LG_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 退货 / 退款
        # ================================================================
        "REFUND_STATUS": WorkflowNode(
            id="REFUND_STATUS",
            type="choice",
            dimension="refund_status",
            question="当前退货或退款情况属于哪一种？",
            options=[
                WorkflowOption(
                    option_id="RF_NOT_APPLIED",
                    label="还没有申请退货 / 退款",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="RF_PROCESSING",
                    label="申请处理中",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="RF_REJECTED",
                    label="退货 / 退款申请被拒绝",
                    next_node="REFUND_REJECTED_INTENT",
                ),
                WorkflowOption(
                    option_id="RF_SUCCESS_NOT_RECEIVED",
                    label="显示退款成功但未到账",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="RF_AMOUNT",
                    label="退款金额有疑问",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="RF_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        "REFUND_REJECTED_INTENT": WorkflowNode(
            id="REFUND_REJECTED_INTENT",
            type="choice",
            dimension="user_intent",
            question="关于申请被拒绝，您希望如何处理？",
            options=[
                WorkflowOption(
                    option_id="RF_REASON",
                    label="了解拒绝原因或相关规则",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="RF_REVIEW",
                    label="申请重新审核处理结果",
                    next_node="HANDOFF_AUTHORITY",
                    handoff_trigger="AUTHORITY_BOUNDARY",
                ),
                WorkflowOption(
                    option_id="RF_REJECT_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # 维修 / 保修
        # ================================================================
        "WARRANTY_STATUS": WorkflowNode(
            id="WARRANTY_STATUS",
            type="choice",
            dimension="warranty_status",
            question="您的维修或保修情况属于哪一种？",
            options=[
                WorkflowOption(
                    option_id="WT_ELIGIBILITY",
                    label="咨询是否可以维修 / 保修",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="WT_APPLY",
                    label="准备申请维修 / 保修",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="WT_PROCESSING",
                    label="维修处理中",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="WT_STILL_BROKEN",
                    label="维修后仍有问题",
                    next_node="AI_RAG_SERVICE",
                ),
                WorkflowOption(
                    option_id="WT_DISPUTE",
                    label="维修结果 / 收费有异议",
                    next_node="HANDOFF_AUTHORITY",
                    handoff_trigger="AUTHORITY_BOUNDARY",
                ),
                WorkflowOption(
                    option_id="WT_OTHER",
                    label="其他",
                    next_node="OTHER_CONFIRM",
                ),
            ],
        ),

        # ================================================================
        # “其他”统一二次确认
        # ================================================================
        "OTHER_CONFIRM": WorkflowNode(
            id="OTHER_CONFIRM",
            type="confirm",
            dimension="other_confirm",
            question="当前选项中确实没有符合您的情况吗？",
            options=[
                WorkflowOption(
                    option_id="OTHER_RETURN",
                    label="返回重新选择",
                    action="RETURN_PREVIOUS",
                ),
                WorkflowOption(
                    option_id="OTHER_HANDOFF",
                    label="是的，都不符合，转人工",
                    action="HANDOFF_NO_MATCH",
                ),
            ],
        ),

        # ================================================================
        # Terminal nodes
        # ================================================================
        "AI_RAG_SERVICE": WorkflowNode(
            id="AI_RAG_SERVICE",
            type="terminal",
            action="ENTER_RAG_SERVICE",
        ),

        "HANDOFF_AUTHORITY": WorkflowNode(
            id="HANDOFF_AUTHORITY",
            type="terminal",
            action="HANDOFF",
            handoff_trigger="AUTHORITY_BOUNDARY",
        ),

        "HANDOFF_SAFETY": WorkflowNode(
            id="HANDOFF_SAFETY",
            type="terminal",
            action="HANDOFF",
            handoff_trigger="SAFETY_RISK",
        ),
    },
)

MVP_PRIORITY_POLICY = PriorityPolicy(
    priority_policy_version="mvp-v1",
    p1_min_exposure=2000,
    p2_min_exposure=500,
    p3_min_exposure=0,
    aging_interval_minutes=60,
    aging_ceiling="P1",
)

DEFAULT_SYSTEM_CONFIG = SystemConfig(
    mapping_confidence_threshold=0.80,
    rag_retrieval_threshold=0.60,
    rag_top_k=3,
    workflow=MVP_WORKFLOW,
    priority_policy=MVP_PRIORITY_POLICY,
)

# ── MiMo LLM API 配置 ────────────────────────────────────────────────────
# OpenAI 兼容格式。密钥从环境变量读取；可用环境变量覆盖服务地址和模型。
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "").strip()
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").strip()
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5").strip()
MIMO_MAX_TOKENS = 2048                         # 推理模型需要更多 token（reasoning + content）
MIMO_TEMPERATURE = 0.1                         # 低温度 = 更稳定的结构化输出

# ── AI 判断引擎配置 ───────────────────────────────────────────────────────
JUDGE_CONFIDENCE_THRESHOLD = 0.8               # 高置信度阈值：>= 此值自动转人工
JUDGE_USER_CONFIRM_THRESHOLD = 0.5             # 中置信度阈值：>= 此值提示用户确认转人工
