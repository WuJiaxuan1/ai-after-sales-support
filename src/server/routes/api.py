"""
api.py — FastAPI 薄路由层（v2）
==============================
业务编排统一委托给 AfterSalesService；路由只负责请求解析、基础状态校验和响应构造。
保持现有前端 API URL 不变。
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    CaseState, HandoffTrigger, AuditEventType, Actor,
    CreateCaseRequest, SelectOptionRequest, FreeTextRequest,
    ConfirmMappingRequest, GoBackRequest, RAGQueryRequest,
    HandoffRequest, AssignCaseRequest, ResolveCaseRequest,
    SendMessageRequest, RAGResolveRequest, CaseResponse, QueueItem, CaseData, WorkflowNode, HandoffJudgment,
)
from ..engine.case_manager import CaseManager
from ..engine.handoff import HandoffManager
from ..engine.service import AfterSalesService
from ..data.mock_data import MockBusinessData


def create_router(
    case_mgr: CaseManager,
    handoff_mgr: HandoffManager,
    service: AfterSalesService,
    mock_data: MockBusinessData,
) -> APIRouter:
    router = APIRouter()
    workflow = case_mgr.engine

    # ── 1. Case 生命周期 ─────────────────────────────────────────────────

    @router.post("/cases", response_model=CaseResponse)
    async def create_case(req: CreateCaseRequest):
        case = await case_mgr.create_case(req.idempotency_key, req.product_name, req.product_model)
        # MVP 演示：给每个 Case 绑定一条模拟的“系统已核验订单”，轮换覆盖 P1/P2/P3。
        mock_data.assign_demo_order(case.case_id)
        return _case_response(case, workflow.get_start_node())

    @router.get("/cases/{case_id}", response_model=CaseResponse)
    async def get_case(case_id: str):
        case = _require_case(case_mgr, case_id)
        return _case_response(case, workflow.get_node(case.current_node_id))

    # ── 2. Workflow 按钮 ─────────────────────────────────────────────────

    @router.post("/cases/{case_id}/select", response_model=CaseResponse)
    async def select_option(case_id: str, req: SelectOptionRequest):
        case = _require_case(case_mgr, case_id)
        result = workflow.select_option(case, req.node_id, req.option_id)
        if not result.success:
            return CaseResponse(success=False, case_id=case_id, error=result.error)

        case.case_version += 1
        case_mgr.audit(AuditEventType.WORKFLOW_SELECTED, case, Actor.USER, {
            "node_id": req.node_id,
            "option_id": req.option_id,
            "label": result.label_of_selected,
        })

        if result.terminal_action == "HANDOFF":
            return await _do_handoff(case, handoff_mgr, mock_data)
        return _case_response(case, result.current_node, terminal_action=result.terminal_action)

    @router.post("/cases/{case_id}/go-back", response_model=CaseResponse)
    async def go_back(case_id: str, req: GoBackRequest):
        case = _require_case(case_mgr, case_id)
        result = workflow.go_back(case, req.target_node_id)
        if not result.success:
            return CaseResponse(success=False, case_id=case_id, error=result.error)
        case.case_version += 1
        case_mgr.audit(AuditEventType.SELECTION_REVISED, case, Actor.USER, {
            "target_node_id": req.target_node_id,
        })
        return _case_response(case, result.current_node)

    # ── 3. 任意 Workflow 阶段自由文本 ───────────────────────────────────

    @router.post("/cases/{case_id}/map-text", response_model=CaseResponse)
    async def map_free_text(case_id: str, req: FreeTextRequest):
        case = _require_case(case_mgr, case_id)
        if case.state != CaseState.IN_WORKFLOW:
            return CaseResponse(
                success=False, case_id=case_id,
                error="INVALID_STATE: expected IN_WORKFLOW, got {}".format(case.state),
            )

        result = await service.handle_workflow_text(case, req.user_text)

        if result["kind"] == "handoff":
            return CaseResponse(
                success=True,
                case_id=case.case_id,
                case_version=case.case_version,
                state=CaseState.QUEUED,
                current_node=_node_to_dict(workflow.get_node(case.current_node_id)),
                issue_path=case.issue_path,
                visited_nodes=case.visited_nodes,
                confirmed_facts=case.confirmed_facts,
                handoff_trigger=result["trigger"],
                message=result["message"],
            )

        if result["kind"] == "mapping":
            mapping = result["mapping"]
            rag = result["rag"]
            return CaseResponse(
                success=True,
                case_id=case.case_id,
                case_version=case.case_version,
                state=CaseState.MAPPING_CONFIRMING,
                current_node=_node_to_dict(workflow.get_node(case.current_node_id)),
                issue_path=case.issue_path,
                visited_nodes=case.visited_nodes,
                confirmed_facts=case.confirmed_facts,
                candidate_path=mapping.candidate_path,
                assistant_answer=rag.answer if rag.knowledge_sufficient else None,
                used_sources=rag.used_sources,
                message=mapping.path_label,
            )

        rag = result.get("rag")
        return CaseResponse(
            success=True,
            case_id=case.case_id,
            case_version=case.case_version,
            state=CaseState.IN_WORKFLOW,
            current_node=_node_to_dict(workflow.get_node(case.current_node_id)),
            issue_path=case.issue_path,
            visited_nodes=case.visited_nodes,
            confirmed_facts=case.confirmed_facts,
            assistant_answer=rag.answer if rag and rag.knowledge_sufficient else None,
            used_sources=rag.used_sources if rag else [],
            message=result["message"],
        )

    @router.post("/cases/{case_id}/confirm-mapping", response_model=CaseResponse)
    async def confirm_mapping(case_id: str, req: ConfirmMappingRequest):
        case = _require_case(case_mgr, case_id)
        if case.state != CaseState.MAPPING_CONFIRMING:
            return CaseResponse(
                success=False, case_id=case_id,
                error="INVALID_STATE: expected MAPPING_CONFIRMING, got {}".format(case.state),
            )

        pending_answer = case.pending_rag_answer
        pending_sources = list(case.pending_rag_sources)
        candidate_path = list(case.pending_candidate_path)

        if not req.confirmed:
            _clear_pending(case)
            case.state = CaseState.IN_WORKFLOW
            case.case_version += 1
            case_mgr.audit(AuditEventType.MAPPING_REJECTED, case, Actor.USER, {})
            return _case_response(case, workflow.get_node(case.current_node_id))

        if not candidate_path:
            _clear_pending(case)
            case.state = CaseState.IN_WORKFLOW
            return CaseResponse(success=False, case_id=case_id, error="NO_PENDING_CANDIDATE_PATH")

        case_mgr.audit(AuditEventType.MAPPING_CONFIRMED, case, Actor.USER, {
            "candidate_path": [step.model_dump() for step in candidate_path],
        })
        result = workflow.apply_candidate_path(case, candidate_path)
        if not result.success:
            _clear_pending(case)
            case.state = CaseState.IN_WORKFLOW
            return CaseResponse(success=False, case_id=case_id, error=result.error)

        _clear_pending(case)
        case.case_version += 1

        if result.terminal_action == "HANDOFF":
            return await _do_handoff(case, handoff_mgr, mock_data)

        return _case_response(
            case,
            result.current_node,
            terminal_action=result.terminal_action,
            assistant_answer=pending_answer,
            used_sources=pending_sources,
        )

    # ── 4. RAG / AI 服务 ─────────────────────────────────────────────────

    @router.post("/cases/{case_id}/ask")
    async def ask_ai(case_id: str, req: RAGQueryRequest):
        case = _require_case(case_mgr, case_id)
        if case.state != CaseState.AI_RAG_SERVICE:
            return {"success": False, "error": "INVALID_STATE: expected AI_RAG_SERVICE, got {}".format(case.state)}

        result = await service.handle_rag_text(case, req.user_message)
        if result["kind"] == "handoff":
            return {
                "success": True,
                "answer": result["message"],
                "handoff": True,
                "packet": result["packet"].model_dump(),
                "judgment": result["judgment"],
            }

        judgment = result.get("judgment")
        return {
            "success": True,
            "answer": result["answer"],
            "handoff": False,
            "used_sources": result.get("used_sources", []),
            "suggested_path": result.get("suggested_path"),
            "mapping": result.get("mapping"),
            "judgment": judgment.model_dump() if judgment else {
                "need_human": False, "trigger": None, "reason_code": "CONTINUE",
                "confidence": 0.0, "reason": "可继续自动处理", "evidence": []
            },
        }

    @router.post("/cases/{case_id}/rag-resolve")
    async def rag_resolve(case_id: str, req: RAGResolveRequest):
        case = _require_case(case_mgr, case_id)
        if case.state != CaseState.AI_RAG_SERVICE:
            return {"success": False, "error": "INVALID_STATE: expected AI_RAG_SERVICE, got {}".format(case.state)}

        if req.resolved:
            case.state = CaseState.RESOLVED
            case.case_version += 1
            case_mgr.audit(AuditEventType.CASE_RESOLVED, case, Actor.USER, {"resolution": "self_resolved"})
            case_mgr.add_message(case_id, "system", "用户确认问题已解决。")
            return {"success": True, "state": "RESOLVED", "message": "问题已解决，感谢您的反馈！"}

        case.user_unresolved_count += 1
        case.case_version += 1
        case_mgr.add_message(case_id, "system", "用户反馈问题仍未解决。")
        case_mgr.audit(AuditEventType.AUTOMATION_NO_PROGRESS, case, Actor.USER, {
            "user_unresolved_count": case.user_unresolved_count,
        })

        if case.user_unresolved_count >= 2:
            result = await service.handoff_by_rule(
                case,
                HandoffTrigger.AUTOMATION_NO_PROGRESS,
                "用户连续确认问题仍未解决",
                reason_code="AUTOMATION_NO_PROGRESS",
                reason="AI 排查连续 {} 次未能有效解决问题".format(case.user_unresolved_count),
                evidence=["user_unresolved_count={}".format(case.user_unresolved_count)],
                layer="hard_rule",
            )
            return {
                "success": True, "state": "QUEUED", "handoff": True,
                "message": result["message"],
                "packet": result["packet"].model_dump(),
                "judgment": result["judgment"].model_dump(),
            }

        return {
            "success": True,
            "state": "AI_RAG_SERVICE",
            "handoff": False,
            "failure_count": case.user_unresolved_count,
            "message": "当前问题仍未解决，您可以继续描述；如再次确认未解决，系统将转人工。",
        }

    # ── 5. Handoff ───────────────────────────────────────────────────────

    @router.post("/cases/{case_id}/handoff")
    async def request_handoff(case_id: str, req: HandoffRequest):
        case = _require_case(case_mgr, case_id)
        result = await service.handoff_by_rule(
            case,
            HandoffTrigger.USER_REQUEST,
            "用户点击转人工客服按钮",
            reason_code="USER_REQUEST",
            reason="用户主动点击转人工客服按钮",
            evidence=["source=button"],
            layer="hard_rule",
        )
        return {
            "success": True,
            "case_id": case_id,
            "packet": result["packet"].model_dump(),
            "judgment": result["judgment"].model_dump(),
        }

    # ── 6. 人工队列 ─────────────────────────────────────────────────────

    @router.get("/queue", response_model=List[QueueItem])
    async def get_queue():
        return await handoff_mgr.get_queue()

    @router.post("/queue/assign")
    async def assign_case(req: AssignCaseRequest):
        ok = await handoff_mgr.assign_case(req.case_id, req.agent_id)
        if not ok:
            raise HTTPException(409, "CASE_NOT_QUEUED: 请从待处理队列中接单")
        return {"success": True, "case_id": req.case_id, "agent_id": req.agent_id, "state": "ASSIGNED"}

    @router.post("/cases/{case_id}/resolve")
    async def resolve_case(case_id: str, req: ResolveCaseRequest):
        case = _require_case(case_mgr, case_id)
        if case.state != CaseState.ASSIGNED:
            raise HTTPException(409, "CASE_NOT_ASSIGNED: 请先接单后再标记解决")
        if case.agent_reply_count < 1:
            raise HTTPException(409, "NO_AGENT_REPLY: 请至少回复用户一次后再标记解决")
        ok = await handoff_mgr.resolve_case(case_id, req.agent_id)
        if not ok:
            raise HTTPException(409, "CASE_RESOLVE_REJECTED")
        return {"success": True, "case_id": case_id, "state": "RESOLVED"}

    # ── 7. 转人工后的消息通信 ───────────────────────────────────────────

    @router.post("/cases/{case_id}/messages")
    async def send_message(case_id: str, req: SendMessageRequest):
        case = _require_case(case_mgr, case_id)
        if req.role not in {"user", "human_agent"}:
            raise HTTPException(400, "INVALID_MESSAGE_ROLE")
        if not req.content.strip():
            raise HTTPException(400, "EMPTY_MESSAGE")
        if req.role == "human_agent" and case.state != CaseState.ASSIGNED:
            raise HTTPException(409, "CASE_NOT_ASSIGNED: 人工客服必须先接单才能回复")
        if req.role == "user" and case.state not in {CaseState.QUEUED, CaseState.ASSIGNED}:
            raise HTTPException(409, "INVALID_STATE: 当前状态不能发送人工会话消息")

        actor = Actor.USER if req.role == "user" else Actor.HUMAN_AGENT
        display_name = req.sender_name or ("用户" if req.role == "user" else "人工客服")
        msg = case_mgr.add_message(case_id, req.role, req.content, {"sender_name": display_name})
        if req.role == "human_agent":
            case.agent_reply_count += 1
        case_mgr.audit(AuditEventType.MESSAGE_SENT, case, actor, {"message": req.content[:100], "role": req.role})
        return {
            "success": True,
            "message": {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "sender_name": display_name,
            },
        }

    @router.get("/cases/{case_id}/messages")
    async def get_messages(case_id: str, after: int = 0):
        case = _require_case(case_mgr, case_id)
        conv = case_mgr.get_conversation_by_case(case_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        msgs = []
        for i, msg in enumerate(conv.messages):
            if i >= after:
                msgs.append({
                    "index": i,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "sender_name": msg.metadata.get("sender_name", ""),
                })
        return {"messages": msgs, "total": len(conv.messages), "case_state": case.state.value}

    # ── 8. 审计 / 对话 / Handoff Packet ─────────────────────────────────

    @router.get("/cases/{case_id}/audit")
    async def get_audit_log(case_id: str):
        return [e.model_dump() for e in case_mgr.get_audit_log(case_id)]

    @router.get("/cases/{case_id}/conversation")
    async def get_conversation(case_id: str):
        _require_case(case_mgr, case_id)
        conv = case_mgr.get_conversation_by_case(case_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return conv.model_dump()

    @router.get("/cases/{case_id}/handoff-packet")
    async def get_handoff_packet(case_id: str):
        case = _require_case(case_mgr, case_id)
        if not case.handoff_packet:
            raise HTTPException(404, "Handoff packet not found")
        conv = case_mgr.get_conversation_by_case(case_id)
        return {
            "packet": case.handoff_packet.model_dump(),
            "conversation": conv.model_dump() if conv else None,
            "audit_log": [e.model_dump() for e in case_mgr.get_audit_log(case_id)],
        }

    return router


# ── Helpers ───────────────────────────────────────────────────────────────

def _require_case(case_mgr: CaseManager, case_id: str) -> CaseData:
    case = case_mgr.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case {} not found".format(case_id))
    return case


def _node_to_dict(node: WorkflowNode) -> Optional[dict]:
    if node is None:
        return None
    return {
        "node_id": node.id,
        "type": node.type,
        "dimension": node.dimension,
        "question": node.question,
        "options": [{"option_id": o.option_id, "label": o.label} for o in node.options],
    }


def _case_response(
    case: CaseData,
    node=None,
    terminal_action=None,
    handoff_trigger=None,
    assistant_answer=None,
    used_sources=None,
) -> CaseResponse:
    return CaseResponse(
        success=True,
        case_id=case.case_id,
        case_version=case.case_version,
        state=case.state,
        current_node=_node_to_dict(node),
        issue_path=case.issue_path,
        visited_nodes=case.visited_nodes,
        confirmed_facts=case.confirmed_facts,
        diagnosis=case.diagnosis,
        user_intent=case.user_intent,
        terminal_action=terminal_action,
        handoff_trigger=handoff_trigger or case.handoff_trigger,
        candidate_path=case.pending_candidate_path,
        assistant_answer=assistant_answer,
        used_sources=used_sources or [],
    )


def _clear_pending(case: CaseData):
    case.pending_mapped_option_id = None
    case.pending_mapping_reason = None
    case.pending_candidate_path = []
    case.pending_original_text = None
    case.pending_rag_answer = None
    case.pending_rag_sources = []


async def _do_handoff(case: CaseData, handoff_mgr: HandoffManager, mock_data: MockBusinessData) -> CaseResponse:
    # 保留现有模拟金额数据链路，避免覆盖队友正在修改的 priority / handoff 逻辑。
    # Case 创建时已经绑定模拟“已核验订单”，确保 Demo 可展示 P1/P2/P3。
    exposure = mock_data.get_demo_verified_exposure_amount(case.case_id)
    packet = await handoff_mgr.create_handoff(case, verified_exposure_amount=exposure)
    # 固定 Workflow 触发的 Handoff 同样生成结构化判断，保证客服端字段一致。
    trigger = case.handoff_trigger or HandoffTrigger.NO_MATCH_CONFIRMED
    reason_code = {
        HandoffTrigger.NO_MATCH_CONFIRMED: "OUT_OF_SCOPE",
        HandoffTrigger.AUTHORITY_BOUNDARY: "AUTHORITY_BOUNDARY",
        HandoffTrigger.SAFETY_RISK: "SAFETY_RISK",
        HandoffTrigger.USER_REQUEST: "USER_REQUEST",
    }.get(trigger, "OUT_OF_SCOPE")
    judgment = HandoffJudgment(
        need_human=True, trigger=trigger, reason_code=reason_code, confidence=1.0,
        reason="固定 Workflow 规则触发人工接管", layer="hard_rule",
        evidence=["terminal_action=HANDOFF"],
    )
    case.latest_handoff_judgment = judgment
    packet.handoff_judgment = judgment
    case.handoff_packet = packet
    return CaseResponse(
        success=True,
        case_id=case.case_id,
        case_version=case.case_version,
        state=CaseState.QUEUED,
        issue_path=case.issue_path,
        visited_nodes=case.visited_nodes,
        confirmed_facts=case.confirmed_facts,
        handoff_trigger=case.handoff_trigger,
        terminal_action="HANDOFF",
    )
