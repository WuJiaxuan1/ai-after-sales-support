"""
service.py — 售后流程编排中心（v2.1）
====================================
后端唯一业务编排层。

自由文本统一顺序：
  1. Global Hard Gate：明确人工请求 / 明确权限边界
  2. Safety Gate 第一层确定性规则
  3. Safety 第二层语义 + Longest Reliable Existing Path + RAG Answer/Handoff Judge 并发
  4. Safety 命中优先中断
  5. 普通 Handoff Judge 判断 AI 是否还能可靠继续处理
  6. 若继续，则返回候选路径 / RAG；若退出自动化，则后端真实创建 Handoff

AI Judgment ≠ Business Action：AI 只输出结构化 judgment，真正 create_handoff 由本 Service 调 HandoffManager。
"""
import asyncio
from typing import Dict, Any, List, Optional

from ..models.schemas import (
    CaseData, CaseState, HandoffTrigger, AuditEventType, Actor,
    SafetyAssessment, HandoffJudgment,
)
from .case_manager import CaseManager
from .handoff import HandoffManager
from .safety import SafetyGate
from ..ai.adapter import AIAdapter
from ..data.mock_data import MockBusinessData


class AfterSalesService:
    def __init__(self, case_mgr: CaseManager, handoff_mgr: HandoffManager, ai_adapter: AIAdapter, safety_gate: SafetyGate, mock_data: Optional[MockBusinessData] = None):
        self.case_mgr = case_mgr
        self.handoff_mgr = handoff_mgr
        self.ai = ai_adapter
        self.safety = safety_gate
        self.mock_data = mock_data
        self.workflow = case_mgr.engine
        self._routes = self.workflow.enumerate_routes()

    # ── Workflow 阶段自由文本 ───────────────────────────────────────────

    async def handle_workflow_text(self, case: CaseData, user_text: str) -> Dict[str, Any]:
        self.case_mgr.add_message(case.case_id, "user", user_text)

        hard = self._hard_gate(case, user_text)
        if hard:
            return await self._handoff(case, hard, user_text)

        safety_rule = self.safety.check_rules(user_text)
        if safety_rule.safety_signal:
            return await self._safety_handoff(case, user_text, safety_rule)

        history = self._history(case)
        safety_task = self.ai.classify_safety_semantic(user_text)
        path_task = self.ai.infer_longest_reliable_path(case, user_text, self._routes)
        rag_task = self.ai.answer_with_rag(case, user_text, history)
        safety_semantic, mapping, rag_answer = await asyncio.gather(safety_task, path_task, rag_task)

        if safety_semantic.safety_signal:
            return await self._safety_handoff(case, user_text, safety_semantic)

        judgment = rag_answer.handoff_judgment
        judgment.workflow_reachable = bool(
            mapping.decision == "MATCH"
            and mapping.candidate_path
            and self.workflow.validate_candidate_path(mapping.candidate_path)
        )
        case.latest_handoff_judgment = judgment
        self._audit_judgment(case, judgment, user_text, rag_answer.used_sources)

        if judgment.need_human:
            return await self._handoff(
                case,
                judgment,
                user_text,
                retrieval_ids=list(rag_answer.used_sources),
            )

        # AI 可继续：候选路径必须经后端校验 + 用户确认后才能写正式状态。
        if judgment.workflow_reachable:
            case.state = CaseState.MAPPING_CONFIRMING
            case.pending_candidate_path = list(mapping.candidate_path)
            case.pending_mapped_option_id = mapping.candidate_path[-1].option_id
            case.pending_mapping_reason = mapping.reason
            case.pending_original_text = user_text
            case.pending_rag_answer = rag_answer.answer if rag_answer.knowledge_sufficient else None
            case.pending_rag_sources = list(rag_answer.used_sources)
            case.case_version += 1

            self.case_mgr.audit(AuditEventType.MAPPING_PENDING_CONFIRMATION, case, Actor.AI, {
                "user_text": user_text,
                "mapping": mapping.model_dump(),
                "rag_sources": rag_answer.used_sources,
                "handoff_judgment": judgment.model_dump(),
            })
            return {
                "kind": "mapping",
                "mapping": mapping,
                "rag": rag_answer,
                "judgment": judgment,
                "message": mapping.path_label,
            }

        # 路径无法可靠定位，但 RAG 足以回答：可以继续知识服务，不强行分类。
        if rag_answer.knowledge_sufficient and rag_answer.capability_within_bounds:
            self.case_mgr.add_message(
                case.case_id,
                "assistant",
                rag_answer.answer,
                {"used_sources": rag_answer.used_sources},
            )
            return {
                "kind": "rag_only",
                "mapping": mapping,
                "rag": rag_answer,
                "judgment": judgment,
                "message": rag_answer.answer,
            }

        # 理论上知识/能力不足已由 Handoff Judge 拦截；保留兜底避免静默失败。
        fallback = HandoffJudgment(
            need_human=True,
            trigger=HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
            reason_code="OUT_OF_SCOPE",
            confidence=1.0,
            reason="无法形成可靠 Workflow 路径，且当前自动化能力不足以继续处理",
            layer="deterministic_fallback",
            evidence=["workflow_reachable=false", "RAG/capability insufficient"],
            workflow_reachable=False,
            knowledge_sufficient=rag_answer.knowledge_sufficient,
            capability_within_bounds=rag_answer.capability_within_bounds,
        )
        return await self._handoff(case, fallback, user_text, retrieval_ids=list(rag_answer.used_sources))

    # ── 已进入 AI_RAG_SERVICE 后的自由文本 ─────────────────────────────

    async def handle_rag_text(self, case: CaseData, user_text: str) -> Dict[str, Any]:
        self.case_mgr.add_message(case.case_id, "user", user_text)

        hard = self._hard_gate(case, user_text)
        if hard:
            return await self._handoff(case, hard, user_text)

        safety_rule = self.safety.check_rules(user_text)
        if safety_rule.safety_signal:
            return await self._safety_handoff(case, user_text, safety_rule)

        history = self._history(case)
        safety_task = self.ai.classify_safety_semantic(user_text)
        rag_task = self.ai.answer_with_rag(case, user_text, history)
        path_task = self.ai.infer_longest_reliable_path(case, user_text, self._routes)
        safety_semantic, rag_answer, mapping = await asyncio.gather(safety_task, rag_task, path_task)

        if safety_semantic.safety_signal:
            return await self._safety_handoff(case, user_text, safety_semantic)

        judgment = rag_answer.handoff_judgment
        judgment.workflow_reachable = bool(
            mapping.decision == "MATCH"
            and mapping.candidate_path
            and self.workflow.validate_candidate_path(mapping.candidate_path)
        )
        case.latest_handoff_judgment = judgment
        self._audit_judgment(case, judgment, user_text, rag_answer.used_sources)

        if judgment.need_human:
            return await self._handoff(
                case,
                judgment,
                user_text,
                retrieval_ids=list(rag_answer.used_sources),
            )

        case.automation_failure_count = 0
        self.case_mgr.add_message(
            case.case_id,
            "assistant",
            rag_answer.answer,
            {"used_sources": rag_answer.used_sources},
        )

        suggested_path = mapping.path_label if (
            judgment.workflow_reachable
            and [s.label for s in mapping.candidate_path] != case.issue_path
        ) else None

        return {
            "kind": "answer",
            "answer": rag_answer.answer,
            "used_sources": rag_answer.used_sources,
            "suggested_path": suggested_path,
            "mapping": mapping.model_dump(),
            "judgment": judgment,
        }

    # ── Public Handoff helpers：按钮 / no-progress 等仍统一产生结构化 Judgment ──

    async def handoff_by_rule(
        self,
        case: CaseData,
        trigger: HandoffTrigger,
        user_text: str,
        *,
        reason_code: str,
        reason: str,
        evidence: Optional[List[str]] = None,
        layer: str = "hard_rule",
    ) -> Dict[str, Any]:
        judgment = HandoffJudgment(
            need_human=True,
            trigger=trigger,
            reason_code=reason_code,
            confidence=1.0,
            reason=reason,
            layer=layer,
            evidence=evidence or [user_text],
        )
        case.latest_handoff_judgment = judgment
        self._audit_judgment(case, judgment, user_text, [])
        return await self._handoff(case, judgment, user_text)

    # ── Hard Gates ───────────────────────────────────────────────────────

    def _hard_gate(self, case: CaseData, user_text: str) -> Optional[HandoffJudgment]:
        if self.safety.explicit_human_request(user_text):
            return HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.USER_REQUEST,
                reason_code="USER_REQUEST",
                confidence=1.0,
                reason="用户通过自由文本明确请求人工客服",
                layer="hard_rule",
                evidence=[user_text],
            )

        # 真实订单/支付/物流内部状态查询属于已知系统能力边界，不依赖模型是否恰好判断出来。
        # 这一判断优先于“退款”关键词的权限判断，确保“查退款到哪张卡”归为 CAPABILITY_GAP。
        if self._requires_connected_business_data(user_text):
            return HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
                reason_code="CAPABILITY_GAP",
                confidence=1.0,
                reason="用户请求查询真实订单、支付或物流内部数据，当前 MVP 未接入对应业务系统",
                layer="hard_rule",
                evidence=[user_text, "当前系统未接入真实订单/支付/物流查询能力"],
                capability_within_bounds=False,
            )

        # 明确要求执行退款/赔付/改判等真实业务动作：属于人工权限边界。
        if self.safety.authority_boundary(user_text) or self._explicit_business_action(user_text):
            return HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.AUTHORITY_BOUNDARY,
                reason_code="AUTHORITY_BOUNDARY",
                confidence=1.0,
                reason="用户请求执行退款、复核、赔偿、责任认定或其他人工权限动作",
                layer="hard_rule",
                evidence=[user_text],
                capability_within_bounds=False,
            )
        return None

    @staticmethod
    def _explicit_business_action(user_text: str) -> bool:
        text = (user_text or "").replace(" ", "")
        action_targets = ["仅退款", "退款", "退钱", "赔钱", "赔偿", "赔付", "取消订单", "改退款", "修改订单"]
        imperatives = ["你给我", "给我", "帮我", "请给我", "直接给我", "马上给我", "现在给我", "替我", "帮忙"]
        if any(i in text for i in imperatives) and any(t in text for t in action_targets):
            return True
        return any(p in text for p in ["要求改判", "要求重新审核", "重新审核退款", "重新审核我的退款"])

    @staticmethod
    def _requires_connected_business_data(user_text: str) -> bool:
        text = (user_text or "").replace(" ", "")
        query_markers = ["帮我查", "给我查", "查一下", "查询一下", "帮忙查", "查查", "看一下", "帮我看"]
        data_targets = [
            "哪张银行卡", "哪张卡", "到账银行卡", "到账账户", "退款去向", "退款到哪",
            "真实退款状态", "退款现在到哪", "订单内部状态", "真实订单状态",
            "物流内部状态", "当前物流位置", "支付账户", "付款账户"
        ]
        if any(t in text for t in data_targets) and any(q in text for q in query_markers):
            return True
        # “这笔退款最终退到哪张银行卡”即使省略“查”也明显需要真实账户数据。
        if "这笔退款" in text and any(t in text for t in ["哪张银行卡", "哪张卡", "退到哪", "打到哪"]):
            return True
        return False

    # ── Safety Handoff ───────────────────────────────────────────────────

    async def _safety_handoff(self, case: CaseData, user_text: str, assessment: SafetyAssessment) -> Dict[str, Any]:
        case.safety_certainty = assessment.certainty
        case.safety_hazard_type = assessment.hazard_type
        case.safety_evidence = assessment.evidence

        judgment = HandoffJudgment(
            need_human=True,
            trigger=HandoffTrigger.SAFETY_RISK,
            reason_code="SAFETY_RISK",
            confidence=max(assessment.confidence, 0.95),
            reason="Safety Gate 识别到{}安全风险：{}".format(assessment.certainty, assessment.hazard_type),
            layer="hard_rule" if assessment.source == "rule" else "ai_judge",
            evidence=[assessment.evidence or user_text],
        )
        case.latest_handoff_judgment = judgment
        self._audit_judgment(case, judgment, user_text, [])
        return await self._handoff(case, judgment, user_text, safety=assessment)

    # ── 真正的 Handoff Business Action ──────────────────────────────────

    async def _handoff(
        self,
        case: CaseData,
        judgment: HandoffJudgment,
        user_text: str,
        *,
        safety: Optional[SafetyAssessment] = None,
        retrieval_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        trigger = judgment.trigger or HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP
        case.state = CaseState.HANDOFF_CREATED
        case.handoff_trigger = trigger
        case.latest_handoff_judgment = judgment
        case.case_version += 1

        if trigger == HandoffTrigger.USER_REQUEST:
            self.case_mgr.audit(AuditEventType.USER_REQUEST_HANDOFF, case, Actor.USER, {
                "source": "free_text_or_button",
                "message": user_text[:200],
                "handoff_judgment": judgment.model_dump(),
            })

        unconfirmed = []
        if safety and safety.certainty == "SUSPECTED":
            unconfirmed.append("疑似安全风险：{}（{}）".format(safety.hazard_type, safety.evidence))

        # 对明确业务诉求保留用户原文，人工客服可直接看到。Safety 不写成 user_intent。
        if trigger in {
            HandoffTrigger.USER_REQUEST, HandoffTrigger.AUTHORITY_BOUNDARY,
            HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP, HandoffTrigger.AUTOMATION_NO_PROGRESS,
        } and not case.user_intent:
            case.user_intent = user_text

        # MVP Demo：每个 Case 绑定一条模拟“已核验订单”，用于展示 P1/P2/P3。
        # 用户在聊天中自报的金额仍然不会参与优先级。Safety 始终由 PriorityCalculator 覆盖为 P0。
        verified_exposure = (
            self.mock_data.get_demo_verified_exposure_amount(case.case_id)
            if self.mock_data else None
        )

        packet = await self.handoff_mgr.create_handoff(
            case,
            verified_exposure_amount=verified_exposure,
            ai_actions=["AI 转人工判断：{}".format(judgment.reason)],
            unconfirmed_information=unconfirmed,
            key_quotes=[user_text],
            retrieval_ids=retrieval_ids or [],
        )

        # 不修改 handoff.py，也能把结构化 Handoff Judge 与 Safety 字段写进现有 Packet。
        packet.handoff_judgment = judgment
        packet.safety_certainty = safety.certainty if safety else case.safety_certainty
        packet.safety_hazard_type = safety.hazard_type if safety else case.safety_hazard_type
        packet.safety_evidence = safety.evidence if safety else case.safety_evidence
        case.handoff_packet = packet

        if trigger == HandoffTrigger.SAFETY_RISK:
            message = (
                "检测到可能涉及商品安全风险，已自动为您创建人工服务工单并进入最高优先级队列。"
                "请停止继续使用或测试该商品，避免继续接触可能存在风险的部位，并等待人工客服处理。"
            )
        elif trigger == HandoffTrigger.AUTHORITY_BOUNDARY:
            message = "该问题涉及人工处理权限，已自动为您转接人工客服。"
        elif trigger == HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP:
            message = "当前问题已超出智能客服可可靠处理范围，已自动为您转接人工客服。"
        elif trigger == HandoffTrigger.AUTOMATION_NO_PROGRESS:
            message = "自动排查未能有效解决当前问题，已自动为您转接人工客服。"
        else:
            message = "已收到您的人工服务请求，正在为您转接人工客服。"

        self.case_mgr.add_message(case.case_id, "system", message)
        return {
            "kind": "handoff",
            "message": message,
            "packet": packet,
            "trigger": trigger,
            "judgment": judgment,
        }

    def _audit_judgment(self, case: CaseData, judgment: HandoffJudgment, user_text: str, sources: List[str]):
        self.case_mgr.audit(AuditEventType.AI_JUDGMENT, case, Actor.AI if judgment.layer == "ai_judge" else Actor.SYSTEM, {
            "user_text": user_text[:240],
            "handoff_judgment": judgment.model_dump(),
            "used_sources": list(sources or []),
        })

    def _history(self, case: CaseData) -> List[dict]:
        conv = self.case_mgr.get_conversation_by_case(case.case_id)
        if not conv:
            return []
        return [{"role": msg.role, "content": msg.content} for msg in conv.messages]
