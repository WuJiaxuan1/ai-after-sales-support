"""
handoff.py — 转人工管理器
===========================
负责：
  1. 创建 Handoff Packet（结构化交接数据包）
  2. 计算优先级并入队
  3. 管理人工客服队列（老化、排序、接单、解决）

所有转人工 Case 统一经过此模块，确保 Handoff Packet 完整性和优先级一致性。
"""
import asyncio
import uuid
from typing import Optional, List
from datetime import datetime

from ..models.schemas import (
    CaseData, CaseState, HandoffTrigger, HandoffPacket,
    Priority, QueueItem, AuditEventType, Actor,
)
from ..config.defaults import DEFAULT_SYSTEM_CONFIG
from .priority import PriorityCalculator
from .case_manager import CaseManager


class HandoffManager:
    """转人工管理器。管理 Handoff 创建、队列操作和优先级计算。"""

    def __init__(self, case_mgr: CaseManager):
        self._case_mgr = case_mgr
        self._priority_calc = PriorityCalculator(DEFAULT_SYSTEM_CONFIG.priority_policy)
        self._queue = []       # type: List[QueueItem]   人工客服队列
        self._lock = asyncio.Lock()

    async def create_handoff(
        self, case: CaseData, *,
        verified_exposure_amount: Optional[float] = None,
        claimed_amount: Optional[float] = None,
        ai_actions: Optional[List[str]] = None,
        unconfirmed_information: Optional[List[str]] = None,
        key_quotes: Optional[List[str]] = None,
        retrieval_ids: Optional[List[str]] = None,
    ) -> HandoffPacket:
        """
        创建 Handoff Packet 并将 Case 入队。
        流程：
          1. 确定触发器类型
          2. 计算优先级（安全风险→P0，否则按金额映射）
          3. 构建 Handoff Packet
          4. 入队并记录审计事件
        """
        trigger = case.handoff_trigger or HandoffTrigger.USER_REQUEST
        is_safety = trigger == HandoffTrigger.SAFETY_RISK

        # 计算优先级
        priority, reason, missing = self._priority_calc.calculate(
            is_safety_risk=is_safety,
            verified_exposure_amount=verified_exposure_amount,
        )

        core_issue = self._derive_core_issue(case, key_quotes)

        # 构建 Handoff Packet
        packet = HandoffPacket(
            case_id=case.case_id,
            workflow_version=case.workflow_version,
            issue_path=list(case.issue_path),
            core_issue=core_issue,
            confirmed_facts=list(case.confirmed_facts),
            diagnosis=case.diagnosis,
            user_intent=case.user_intent,
            handoff_trigger=trigger,
            handoff_trigger_detail=self._trigger_detail(trigger),
            ai_actions=ai_actions or [],
            unconfirmed_information=unconfirmed_information or [],
            key_quotes=key_quotes or [],
            conversation_id=case.conversation_id,
            retrieval_ids=retrieval_ids or [],
            priority=priority,
            priority_policy_version=DEFAULT_SYSTEM_CONFIG.priority_policy.priority_policy_version,
            priority_reason=reason,
            verified_exposure_amount=verified_exposure_amount,
            claimed_amount=claimed_amount,
            missing_exposure_data=missing,
        )

        case.handoff_packet = packet
        case.state = CaseState.QUEUED

        # 入队
        async with self._lock:
            self._queue.append(QueueItem(
                case_id=case.case_id,
                priority=priority,
                queued_at=datetime.utcnow(),
                core_issue=core_issue,
                verified_exposure_amount=verified_exposure_amount,
                missing_exposure_data=missing,
            ))

        # 记录审计事件
        self._case_mgr.audit(AuditEventType.HANDOFF_CREATED, case, Actor.SYSTEM, {
            "handoff_trigger": trigger.value,
            "priority": priority.value,
            "priority_reason": reason,
        })
        return packet

    async def get_queue(self) -> List[QueueItem]:
        """获取人工客服队列（已老化 + 已排序）。P0 > P1 > P2 > P3，同级 FIFO。"""
        async with self._lock:
            self._apply_aging()
            return sorted(self._queue, key=lambda q: (
                {"P0": 0, "P1": 1, "P2": 2, "P3": 3}[q.priority.value],
                q.queued_at,
            ))

    async def assign_case(self, case_id: str, agent_id: str) -> bool:
        """人工客服接单。从队列中移除 Case，标记为 ASSIGNED。"""
        async with self._lock:
            self._apply_aging()
            item = None
            for q in self._queue:
                if q.case_id == case_id:
                    item = q
                    break
            if item is None:
                return False
            self._queue.remove(item)

        case = self._case_mgr.get_case(case_id)
        if case:
            case.state = CaseState.ASSIGNED
            case.assigned_agent_id = agent_id
            case.agent_reply_count = 0
            self._case_mgr.audit(AuditEventType.CASE_ASSIGNED, case, Actor.HUMAN_AGENT, {"agent_id": agent_id})
        return True

    async def resolve_case(self, case_id: str, agent_id: str) -> bool:
        """人工客服标记 Case 解决。"""
        case = self._case_mgr.get_case(case_id)
        if case is None:
            return False
        if case.state != CaseState.ASSIGNED:
            return False
        if case.assigned_agent_id and case.assigned_agent_id != agent_id:
            return False
        if case.agent_reply_count < 1:
            return False
        case.state = CaseState.RESOLVED
        self._case_mgr.audit(AuditEventType.CASE_RESOLVED, case, Actor.HUMAN_AGENT, {"agent_id": agent_id})
        return True

    def _apply_aging(self):
        """对队列中所有 Case 应用优先级老化升级。"""
        now = datetime.utcnow()
        for item in self._queue:
            new_pri, aged = self._priority_calc.age_priority(item.priority, item.queued_at, now)
            if aged:
                item.priority = new_pri

    def _derive_core_issue(self, case: CaseData, key_quotes: Optional[List[str]] = None) -> str:
        """从 Case 状态中提取核心问题描述，优先保留用户真实诉求/原话。"""
        if case.user_intent:
            return case.user_intent[:160]
        if case.issue_path:
            return " > ".join(case.issue_path)
        if key_quotes:
            return str(key_quotes[-1])[:160]
        return "用户请求人工服务"

    @staticmethod
    def _trigger_detail(trigger: HandoffTrigger) -> str:
        """获取触发器的详细说明。"""
        details = {
            HandoffTrigger.SAFETY_RISK: "检测到疑似或明确的商品安全风险，系统自动转人工",
            HandoffTrigger.AUTHORITY_BOUNDARY: "用户诉求涉及退款复核、赔付、责任认定或审批等人工权限",
            HandoffTrigger.USER_REQUEST: "用户明确请求人工客服",
            HandoffTrigger.NO_MATCH_CONFIRMED: "用户确认现有选项均不符合，需要人工处理",
            HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP: "当前智能客服的知识或系统能力不足以可靠继续处理",
            HandoffTrigger.AUTOMATION_NO_PROGRESS: "AI 排查多次未取得有效进展，系统自动转人工",
        }
        return details.get(trigger, "")
