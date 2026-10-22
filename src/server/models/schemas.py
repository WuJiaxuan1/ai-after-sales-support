"""
schemas.py — 全局数据模型定义
=================================
本文件是整个系统的数据契约层，定义了：
  1. 所有枚举类型（Case 状态、Handoff 触发器、优先级、审计事件类型等）
  2. Workflow 配置结构（节点、选项、决策树）
  3. Case 生命周期数据（CaseData、HandoffPacket）
  4. 审计与对话数据（AuditEvent、Message、Conversation）
  5. 所有 API 请求/响应模型

所有其他模块（engine、routes、ai）从这里导入模型，确保数据结构零重复定义。
Pydantic v2 BaseModel 提供自动校验、序列化和 JSON Schema 生成。
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# 枚举类型 — 系统中所有有限状态集合
# ═══════════════════════════════════════════════════════════════════════════════

class CaseState(str, Enum):
    """
    Case 全生命周期状态。
    流转路径：
      IN_WORKFLOW → MAPPING_CONFIRMING → IN_WORKFLOW（映射失败回退）
      IN_WORKFLOW → AI_RAG_SERVICE（Workflow 走完进入 AI 服务）
      任意状态 → HANDOFF_CREATED → QUEUED → ASSIGNED → RESOLVED
    """
    IN_WORKFLOW = "IN_WORKFLOW"              # 正在走固定按钮决策树
    MAPPING_CONFIRMING = "MAPPING_CONFIRMING"  # AI 映射结果等待用户确认
    AI_RAG_SERVICE = "AI_RAG_SERVICE"        # 进入 RAG 知识问答阶段
    HANDOFF_CREATED = "HANDOFF_CREATED"      # 已创建 Handoff（瞬态，立即进入 QUEUED）
    QUEUED = "QUEUED"                        # 在人工客服队列中等待
    ASSIGNED = "ASSIGNED"                    # 已分配给人工客服
    RESOLVED = "RESOLVED"                    # 已解决


class HandoffTrigger(str, Enum):
    """
    触发转人工的 6 种原因。每个触发器对应不同的可观察依据和服务端动作。
    - SAFETY_RISK: 用户确认安全问题（P0）
    - AUTHORITY_BOUNDARY: 退款复核/责任认定等 AI 无权执行的诉求
    - USER_REQUEST: 用户主动点击转人工按钮
    - NO_MATCH_CONFIRMED: 用户在"其他"二次确认中选择转人工
    - KNOWLEDGE_OR_CAPABILITY_GAP: RAG 无结果或需要系统不具备的能力
    - AUTOMATION_NO_PROGRESS: AI 连续处理无进展（用户两次点"未解决"）
    """
    SAFETY_RISK = "SAFETY_RISK"
    AUTHORITY_BOUNDARY = "AUTHORITY_BOUNDARY"
    USER_REQUEST = "USER_REQUEST"
    NO_MATCH_CONFIRMED = "NO_MATCH_CONFIRMED"
    KNOWLEDGE_OR_CAPABILITY_GAP = "KNOWLEDGE_OR_CAPABILITY_GAP"
    AUTOMATION_NO_PROGRESS = "AUTOMATION_NO_PROGRESS"


class Priority(str, Enum):
    """
    人工客服接入优先级。仅在 HANDOFF 后计算。
    P0: 安全风险（最高，只能由安全风险产生）
    P1: 高经济暴露（verified_exposure_amount >= p1_min_exposure）
    P2: 中经济暴露
    P3: 低经济暴露 / 金额缺失
    非 P0 每等待 60 分钟升一级，最高升至 P1。
    """
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Actor(str, Enum):
    """
    审计事件的操作者标识。
    user: 售后消费者
    system: 系统自动操作（Handoff 创建、优先级计算等）
    ai: AI 模型生成的内容（映射结果、RAG 回答等）
    human_agent: 人工客服
    """
    USER = "user"
    SYSTEM = "system"
    AI = "ai"
    HUMAN_AGENT = "human_agent"


class AuditEventType(str, Enum):
    """
    审计事件类型。所有事件以追加方式记录，历史事件不覆盖。
    用于复原任一 Case 的完整演变过程，支持结果追溯。
    """
    CASE_CREATED = "case_created"                          # Case 创建
    WORKFLOW_SELECTED = "workflow_selected"                 # 用户点击按钮选择
    SELECTION_REVISED = "selection_revised"                 # 用户回退并修改选择
    MAPPING_PENDING_CONFIRMATION = "mapping_pending_confirmation"  # AI 映射等待确认
    MAPPING_CONFIRMED = "mapping_confirmed"                # 用户确认 AI 映射
    MAPPING_REJECTED = "mapping_rejected"                  # 用户否认 AI 映射
    MAPPING_FAILED = "mapping_failed"                      # AI 映射失败（超时/格式错误）
    RAG_RETRIEVED = "rag_retrieved"                        # RAG 检索完成
    AI_ANSWERED = "ai_answered"                            # AI 回答生成完成
    HANDOFF_CREATED = "handoff_created"                    # 创建 Handoff
    PRIORITY_AGED = "priority_aged"                        # 优先级老化升级
    CASE_ASSIGNED = "case_assigned"                        # 人工客服接单
    CASE_RESOLVED = "case_resolved"                        # Case 标记解决
    USER_REQUEST_HANDOFF = "user_request_handoff"          # 用户主动请求转人工
    AUTOMATION_NO_PROGRESS = "automation_no_progress"      # 自动处理无进展
    AI_JUDGMENT = "ai_judgment"                            # AI 判断引擎决策事件
    MESSAGE_SENT = "message_sent"                            # 用户/人工客服发送消息


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 配置 — 决策树结构定义
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowOption(BaseModel):
    """
    决策树中的一个可选项（按钮）。
    - option_id: 稳定唯一标识（如 ISSUE_USE、SAFETY_YES），不使用中文作为主键
    - label: 前端展示的按钮文案
    - next_node: 选择后跳转的下一节点 ID
    - action: 特殊动作（如 RETURN_PREVIOUS 返回上一步、HANDOFF_NO_MATCH 转人工）
    - handoff_trigger: 如果该选项直接触发转人工，记录触发器类型
    """
    option_id: str
    label: str
    next_node: Optional[str] = None
    action: Optional[str] = None
    handoff_trigger: Optional[str] = None


class WorkflowNode(BaseModel):
    """
    决策树中的一个节点。
    - id: 节点唯一标识（如 N0、N1、N1A、OTHER_CONFIRM）
    - type: 节点类型（choice 按钮选择、confirm 确认、terminal 终态）
    - dimension: 该节点正在确认的业务维度（如 issue_category、safety_check）
    - question: 前端展示的问题文案
    - options: 该节点的所有可选项
    - action: terminal 节点的动作（ENTER_RAG_SERVICE、HANDOFF）
    - handoff_trigger: terminal HANDOFF 节点的触发器类型
    """
    id: str
    type: str
    dimension: Optional[str] = None
    question: Optional[str] = None
    options: List[WorkflowOption] = []
    action: Optional[str] = None
    handoff_trigger: Optional[str] = None


class WorkflowConfig(BaseModel):
    """
    完整的 Workflow 配置。由人工设计和维护，AI 不得修改。
    - workflow_id: Workflow 标识
    - workflow_version: 版本号（用于审计追溯）
    - start_node: 起始节点 ID
    - nodes: 所有节点的字典，key 为节点 ID
    """
    workflow_id: str
    workflow_version: str
    start_node: str
    nodes: Dict[str, WorkflowNode]


class PriorityPolicy(BaseModel):
    """
    优先级计算策略。金额区间可配置，不硬编码。
    - p1_min_exposure: P1 最低金额阈值
    - p2_min_exposure: P2 最低金额阈值
    - aging_interval_minutes: 老化升级间隔（分钟）
    - aging_ceiling: 老化升级天花板（最高升到 P1）
    """
    priority_policy_version: str
    p1_min_exposure: float = 2000
    p2_min_exposure: float = 500
    p3_min_exposure: float = 0
    aging_interval_minutes: int = 60
    aging_ceiling: str = "P1"


class SystemConfig(BaseModel):
    """
    全局系统配置。
    - mapping_confidence_threshold: AI 映射置信度阈值（低于此值视为 NO_MATCH）
    - rag_retrieval_threshold: RAG 检索分数阈值
    - rag_top_k: RAG 返回的最大片段数
    """
    mapping_confidence_threshold: float = 0.80
    rag_retrieval_threshold: float = 0.60
    rag_top_k: int = 3
    workflow: WorkflowConfig
    priority_policy: PriorityPolicy


# ═══════════════════════════════════════════════════════════════════════════════
# 受限 AI / Safety Gate 结构
# ═══════════════════════════════════════════════════════════════════════════════

class CandidatePathStep(BaseModel):
    """Longest Reliable Existing Path 中的一个已存在 Workflow 选项。"""
    node_id: str
    option_id: str
    label: str


class SafetyAssessment(BaseModel):
    """Safety Gate 的结构化结果。疑似与明确风险一旦成立都自动转人工。"""
    safety_signal: bool = False
    certainty: str = "NONE"  # NONE / SUSPECTED / CONFIRMED
    hazard_type: Optional[str] = None
    evidence: str = ""
    source: str = "none"  # rule / semantic / none
    confidence: float = 0.0


class HandoffJudgment(BaseModel):
    """
    受限 AI Handoff Judge 的结构化结果。

    AI 只负责判断是否还应继续自动化，以及给出可审计原因；
    真正的 create_handoff 仍由后端 Service / HandoffManager 执行。
    """
    need_human: bool = False
    trigger: Optional[HandoffTrigger] = None
    reason_code: str = "CONTINUE"
    confidence: float = 0.0
    reason: str = ""
    layer: str = "unknown"  # hard_rule / ai_judge / deterministic_fallback
    evidence: List[str] = []
    workflow_reachable: Optional[bool] = None
    knowledge_sufficient: Optional[bool] = None
    capability_within_bounds: Optional[bool] = None


# ═══════════════════════════════════════════════════════════════════════════════
# HandoffPacket — 转人工交接数据包
# 在 CaseData 之前定义，因为 CaseData 引用它
# ═══════════════════════════════════════════════════════════════════════════════

class HandoffPacket(BaseModel):
    """
    转人工时生成的结构化交接数据包。人工客服通过此包快速理解上下文。
    核心字段：
    - core_issue: 一句话核心问题
    - confirmed_facts: 用户已确认的事实（仅来自用户操作，非 AI 推断）
    - diagnosis: AI 疑似判断（单独标注，不混入事实）
    - user_intent: 用户明确表达的处理诉求
    - handoff_trigger: 触发转人工的原因
    - key_quotes: 用户关键原话（保留原始表述）
    - priority: 计算后的优先级
    - verified_exposure_amount: 来自系统数据的可验证经济暴露金额
    - missing_exposure_data: 金额数据是否缺失（缺失时标记并按 P3 入队）
    """
    case_id: str
    workflow_version: str
    issue_path: List[str] = []                    # 用户确认的问题分类路径
    core_issue: str = ""                          # 一句话核心问题
    confirmed_facts: List[str] = []               # 用户已确认的事实
    diagnosis: Optional[str] = None               # AI 疑似判断
    user_intent: Optional[str] = None             # 用户明确诉求
    handoff_trigger: HandoffTrigger               # 转人工触发器
    handoff_trigger_detail: str = ""              # 触发器详细说明
    ai_actions: List[str] = []                    # AI 已执行的操作
    unconfirmed_information: List[str] = []       # 尚未确认的信息
    key_quotes: List[str] = []                    # 用户关键原话
    conversation_id: str = ""                     # 对话 ID（用于关联完整聊天记录）
    retrieval_ids: List[str] = []                 # RAG 检索 ID（用于追溯知识来源）
    priority: Priority = Priority.P3              # 计算后的优先级
    priority_policy_version: str = ""             # 优先级策略版本
    priority_reason: str = ""                     # 优先级计算依据
    verified_exposure_amount: Optional[float] = None  # 可验证经济暴露金额
    claimed_amount: Optional[float] = None        # 用户自报金额（仅供参考，不参与排序）
    missing_exposure_data: bool = False           # 金额数据是否缺失
    handoff_judgment: Optional[HandoffJudgment] = None  # AI/规则为何退出自动化的结构化判断
    safety_certainty: Optional[str] = None         # NONE / SUSPECTED / CONFIRMED
    safety_hazard_type: Optional[str] = None       # Safety Gate 预设 hazard type
    safety_evidence: Optional[str] = None          # 触发安全判断的用户原始依据
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# CaseData — 售后 Case 核心数据
# ═══════════════════════════════════════════════════════════════════════════════

class CaseData(BaseModel):
    """
    售后 Case 的完整状态。系统中所有模块共享此模型。
    关键设计：
    - issue_path / confirmed_facts / diagnosis / user_intent 严格分层
      （Facts ≠ Diagnosis ≠ User Intent ≠ Action，AI 不得跨层推断）
    - pending_mapped_option_id: AI 映射暂存区（用户确认前不写入正式状态）
    - handoff_packet: 转人工后填充，包含完整交接信息
    - automation_failure_count: AI 处理失败计数（ask 调用时递增/重置）
    - user_unresolved_count: 用户点击"未解决"的次数（独立计数，不受 ask 影响）
    - case_version: 乐观并发版本号，每次状态变更递增
    """
    case_id: str
    case_version: int = 0                                    # 乐观并发版本号
    state: CaseState = CaseState.IN_WORKFLOW                 # 当前状态
    workflow_version: str = "mvp-v1"                         # 使用的 Workflow 版本
    current_node_id: str = ""                                # 当前 Workflow 节点 ID
    issue_path: List[str] = []                               # 用户确认的问题分类路径
    confirmed_facts: List[str] = []                          # 用户已确认的事实
    diagnosis: Optional[str] = None                          # AI 疑似判断
    user_intent: Optional[str] = None                        # 用户明确诉求
    conversation_id: str = ""                                # 关联的对话 ID
    pending_mapped_option_id: Optional[str] = None           # 兼容旧前端：单层映射暂存
    pending_mapping_reason: Optional[str] = None             # AI 映射原因（待用户确认）
    pending_candidate_path: List[CandidatePathStep] = []     # Longest Reliable Existing Path
    pending_original_text: Optional[str] = None               # 触发本次候选路径的用户原文
    pending_rag_answer: Optional[str] = None                  # 同次自由文本触发的 RAG 回答
    pending_rag_sources: List[str] = []                       # 对应知识来源
    safety_certainty: Optional[str] = None                    # SUSPECTED / CONFIRMED
    safety_hazard_type: Optional[str] = None                  # 预设 hazard type
    safety_evidence: Optional[str] = None                     # 安全识别依据
    latest_handoff_judgment: Optional[HandoffJudgment] = None # 最近一次自动化退出/继续判断
    assigned_agent_id: Optional[str] = None                  # 当前接单客服
    agent_reply_count: int = 0                               # 人工客服已发送有效回复数
    handoff_trigger: Optional[HandoffTrigger] = None         # 转人工触发器
    handoff_packet: Optional[HandoffPacket] = None           # 转人工交接包
    visited_nodes: List[str] = []                            # 已访问的节点（用于回退）
    automation_failure_count: int = 0                        # AI 处理失败计数
    user_unresolved_count: int = 0                           # 用户"未解决"点击次数
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# 审计与对话
# ═══════════════════════════════════════════════════════════════════════════════

class AuditEvent(BaseModel):
    """
    审计事件。所有状态变更必须生成审计事件，历史事件不覆盖。
    用于复原 Case 演变过程，回答"用户说了什么、AI 做了什么、为什么转人工"等问题。
    """
    event_id: str                    # 事件唯一 ID
    event_type: AuditEventType       # 事件类型
    case_id: str                     # 关联的 Case ID
    case_version: int                # 事件发生时的 Case 版本
    actor: Actor                     # 操作者（user/system/ai/human_agent）
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = {}        # 事件附加数据（因事件类型而异）


class Message(BaseModel):
    """
    对话消息。
    - role: 消息角色（user/assistant/system/human_agent）
    - content: 消息内容
    - metadata: 附加信息（如 sender_name 发送者显示名、used_sources RAG 来源）
    """
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class Conversation(BaseModel):
    """
    一次售后对话。包含该 Case 的所有消息（用户、AI、系统、人工客服）。
    完整对话记录是 Handoff Packet 的重要补充，人工客服必须能查看原文。
    """
    conversation_id: str
    case_id: str
    messages: List[Message] = []


# ═══════════════════════════════════════════════════════════════════════════════
# API 请求模型 — 每个端点的入参
# ═══════════════════════════════════════════════════════════════════════════════

class CreateCaseRequest(BaseModel):
    """创建新 Case 的请求。idempotency_key 用于防止重复创建。"""
    idempotency_key: str
    product_name: Optional[str] = None
    product_model: Optional[str] = None


class SelectOptionRequest(BaseModel):
    """用户点击 Workflow 按钮的请求。case_version 用于乐观并发校验。"""
    case_id: str
    case_version: int
    node_id: str                   # 当前节点 ID（服务端校验是否匹配）
    option_id: str                 # 用户选择的选项 ID（服务端校验是否合法）
    idempotency_key: str


class FreeTextRequest(BaseModel):
    """用户输入自由文本的请求。触发 AI 语义映射流程。"""
    case_id: str
    case_version: int
    user_text: str                 # 用户输入的自然语言
    idempotency_key: str


class ConfirmMappingRequest(BaseModel):
    """用户确认或否认 AI 映射结果的请求。"""
    case_id: str
    case_version: int
    confirmed: bool                # True=确认映射，False=否认映射
    idempotency_key: str


class GoBackRequest(BaseModel):
    """用户请求回退到之前某个节点。"""
    case_id: str
    case_version: int
    target_node_id: str            # 回退目标节点 ID
    idempotency_key: str


class RAGQueryRequest(BaseModel):
    """用户向 AI 提问的请求（在 AI_RAG_SERVICE 阶段）。"""
    case_id: str
    case_version: int
    user_message: str              # 用户的问题或描述
    idempotency_key: str


class HandoffRequest(BaseModel):
    """用户主动请求转人工的请求（点击转人工按钮）。"""
    case_id: str
    case_version: int
    idempotency_key: str


class AssignCaseRequest(BaseModel):
    """人工客服接单请求。"""
    case_id: str
    agent_id: str                  # 人工客服 ID
    idempotency_key: str


class ResolveCaseRequest(BaseModel):
    """人工客服标记 Case 解决的请求。"""
    case_id: str
    agent_id: str
    resolution_note: str = ""      # 处理备注
    idempotency_key: str


class SendMessageRequest(BaseModel):
    """
    发送消息请求（用户或人工客服）。
    用于转人工后的双向实时通信。
    """
    case_id: str
    role: str                      # "user" 或 "human_agent"
    content: str                   # 消息内容
    sender_name: str = ""          # 发送者显示名
    idempotency_key: str


class RAGResolveRequest(BaseModel):
    """
    用户对 AI 排查结果的反馈。
    - resolved=True: 问题已解决，Case 标记为 RESOLVED
    - resolved=False: 问题未解决，累计 2 次自动转人工
    """
    case_id: str
    case_version: int
    resolved: bool
    idempotency_key: str


# ═══════════════════════════════════════════════════════════════════════════════
# API 响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class CaseResponse(BaseModel):
    """
    Case 相关操作的通用响应。
    包含 Case 当前状态快照，前端据此更新 UI。
    """
    success: bool
    case_id: Optional[str] = None
    case_version: Optional[int] = None
    state: Optional[CaseState] = None
    current_node: Optional[Dict[str, Any]] = None
    issue_path: List[str] = []
    visited_nodes: List[str] = []
    confirmed_facts: List[str] = []
    diagnosis: Optional[str] = None
    user_intent: Optional[str] = None
    terminal_action: Optional[str] = None              # 终态动作（HANDOFF/ENTER_RAG_SERVICE）
    handoff_trigger: Optional[HandoffTrigger] = None
    candidate_path: List[CandidatePathStep] = []       # 待确认的多层候选路径
    assistant_answer: Optional[str] = None             # 同次自由文本得到的 RAG 回答（前端可选展示）
    used_sources: List[str] = []                       # RAG 来源
    error: Optional[str] = None                        # 错误信息
    message: Optional[str] = None                      # 用户可见的消息


class MappingResult(BaseModel):
    """
    Longest Reliable Existing Path 的结构化输出。
    candidate_path 只能包含人工 Workflow 中已经存在的节点/选项，且必须经后端校验。
    mapped_option_id 保留用于兼容旧代码，等于候选路径最后一个 option_id。
    """
    decision: str                                    # MATCH / NO_MATCH
    mapped_option_id: Optional[str] = None
    candidate_path: List[CandidatePathStep] = []
    confidence: float = 0.0
    reason: str = ""
    path_label: str = ""


class RAGResult(BaseModel):
    """
    RAG 检索返回的单个知识片段。
    每个片段必须可追溯到 source_id，用于审计和验证。
    """
    source_id: str               # 来源标识（如 POLICY-REFUND-001）
    source_title: str            # 来源标题
    source_version: str          # 来源版本
    chunk_id: str                # 片段标识
    content: str                 # 片段内容
    score: float                 # 检索相关度分数


class AIAnswerResponse(BaseModel):
    """
    AI 售后回答的结构化输出。
    - knowledge_sufficient: RAG 是否提供了足够知识（不足时转人工）
    - capability_within_bounds: 请求是否在 AI 能力范围内
    - is_safety_risk: 是否检测到安全风险（辅助信号，最终以用户确认为准）
    """
    answer: str
    used_sources: List[str] = []
    suggested_next_actions: List[str] = []
    knowledge_sufficient: bool = True
    capability_within_bounds: bool = True
    is_safety_risk: bool = False
    handoff_judgment: HandoffJudgment = Field(default_factory=HandoffJudgment)


class JudgmentResult(HandoffJudgment):
    """兼容旧测试/调用名称；新代码统一使用 HandoffJudgment。"""
    pass


class QueueItem(BaseModel):
    """
    人工客服队列中的单个 Case。
    按 priority 排序（P0 > P1 > P2 > P3），同级按 queued_at FIFO。
    """
    case_id: str
    priority: Priority
    queued_at: datetime
    core_issue: str = ""
    verified_exposure_amount: Optional[float] = None
    missing_exposure_data: bool = False
