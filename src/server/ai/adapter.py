"""
adapter.py — 受限 AI 适配器（v2.1）
===================================
AI 只承担四类受限能力：
  1. Longest Reliable Existing Path：在人工 Workflow 的合法路径中提出最长可靠候选路径
  2. Safety Semantic Classifier：在预设 hazard type 中识别没有被确定性规则捕获的安全语义
  3. RAG Answer：基于检索结果组织用户可读回答
  4. Handoff Judge：在普通售后处理中结构化判断 AI 是否仍能可靠继续处理

重要边界：
- Handoff Judge 只输出结构化判断，不真正创建工单。
- 真正的 create_handoff 只能由后端 Service / HandoffManager 执行。
- 为避免把 7~8 秒模型延迟叠加成两次调用，RAG Answer 与 Handoff Judge 共用一次模型请求，
  但在数据结构上仍严格分离 answer 与 handoff_judgment。
"""
import json
import logging
import re
import uuid
from typing import List, Dict, Optional, Any

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from ..models.schemas import (
    MappingResult, CandidatePathStep, AIAnswerResponse, SafetyAssessment,
    HandoffJudgment, HandoffTrigger,
    AuditEventType, Actor, CaseData,
)
from ..config.defaults import (
    DEFAULT_SYSTEM_CONFIG,
    MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_MAX_TOKENS, MIMO_TEMPERATURE,
)
from ..engine.case_manager import CaseManager
from ..engine.rag import RAGEngine

logger = logging.getLogger(__name__)


class AIAdapter:
    HAZARD_TYPES = [
        "THERMAL_FIRE",
        "ELECTRICAL",
        "EXPLOSION_PRESSURE",
        "CHEMICAL_TOXIC",
        "FOOD_INGESTION",
        "ALLERGIC_IRRITATION",
        "MECHANICAL_INJURY",
        "CHILD_CHOKING_ENTRAPMENT",
        "BIOLOGICAL_CONTAMINATION",
        "OTHER_SAFETY",
    ]

    HANDOFF_REASON_CODES = {
        "CONTINUE",
        "KNOWLEDGE_GAP",
        "CAPABILITY_GAP",
        "AUTHORITY_BOUNDARY",
        "AUTOMATION_NO_PROGRESS",
        "OUT_OF_SCOPE",
    }

    def __init__(self, case_mgr: CaseManager, rag_engine: RAGEngine, safety_rag: RAGEngine):
        self._case_mgr = case_mgr
        self._rag = rag_engine
        self._safety_rag = safety_rag
        self._threshold = DEFAULT_SYSTEM_CONFIG.mapping_confidence_threshold

    # ── Longest Reliable Existing Path ───────────────────────────────────

    async def infer_longest_reliable_path(
        self,
        case: CaseData,
        user_text: str,
        routes: List[List[CandidatePathStep]],
    ) -> MappingResult:
        """AI 只能从给定合法路径中选一个可靠前缀，服务端还会再次校验。"""
        prompt = self._build_path_prompt(case, user_text, routes)
        try:
            raw = await self._call_llm(prompt)
            parsed = self._extract_json(raw)
            result = self._parse_path_output(parsed, routes)
            if result.decision == "MATCH" and result.confidence >= self._threshold:
                return result
        except Exception as exc:
            logger.warning("Path inference failed: %s", exc)
            self._case_mgr.audit(
                AuditEventType.MAPPING_FAILED, case, Actor.AI,
                {"error": str(exc), "user_text": user_text},
            )

        return self._deterministic_path_fallback(user_text, routes)

    def _parse_path_output(self, data: Dict[str, Any], routes: List[List[CandidatePathStep]]) -> MappingResult:
        if not isinstance(data, dict) or str(data.get("decision", "")).upper() != "MATCH":
            return MappingResult(
                decision="NO_MATCH",
                confidence=float(data.get("confidence", 0) or 0),
                reason=str(data.get("reason", "")),
            )

        raw_ids = data.get("candidate_path") or data.get("option_ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return MappingResult(decision="NO_MATCH", confidence=0.0, reason="候选路径为空")
        option_ids = [str(x) for x in raw_ids]

        matched_steps: Optional[List[CandidatePathStep]] = None
        for route in routes:
            route_ids = [s.option_id for s in route]
            if route_ids[:len(option_ids)] == option_ids:
                matched_steps = route[:len(option_ids)]
                break
        if not matched_steps:
            return MappingResult(decision="NO_MATCH", confidence=0.0, reason="AI 返回了不存在的 Workflow 路径")

        confidence = float(data.get("confidence", 0) or 0)
        label = " → ".join(step.label for step in matched_steps)
        return MappingResult(
            decision="MATCH",
            mapped_option_id=matched_steps[-1].option_id,
            candidate_path=matched_steps,
            confidence=confidence,
            reason=str(data.get("reason", "")),
            path_label=label,
        )

    # ── Safety Semantic Classifier ───────────────────────────────────────

    async def classify_safety_semantic(self, user_text: str) -> SafetyAssessment:
        """第二层 Safety Gate。只输出预设 hazard type；不执行 Handoff。"""
        safety_docs = self._safety_rag.retrieve(user_text, top_k=3, threshold=0.01)
        context = "\n\n".join(
            "[{}] {}".format(r.source_id, r.content[:900]) for r in safety_docs
        ) or "无额外安全知识片段"

        prompt = (
            "你是全品类售后 Safety Gate 的受限语义分类器。\n"
            "目标是识别已经发生或尚未发生但具有合理安全隐患的商品问题。\n"
            "不要因为没有出现‘危险’二字就判断安全。异常发热、结构将倾倒、明显刺激、危险异物等都可能是疑似安全信号。\n"
            "同时注意否定和引用语境，例如‘没有冒烟，只是开不了机’不应因为‘冒烟’二字判为安全风险。\n"
            "允许的 hazard_type 仅为：{}。\n"
            "certainty 仅允许 NONE / SUSPECTED / CONFIRMED。\n"
            "只返回 JSON，不要解释：\n"
            '{{"safety_signal":true,"certainty":"SUSPECTED","hazard_type":"THERMAL_FIRE","evidence":"用户原文中的依据","confidence":0.90}}\n\n'
            "安全知识：\n{}\n\n用户文本：{}"
        ).format(", ".join(self.HAZARD_TYPES), context, user_text)

        try:
            raw = await self._call_llm(prompt)
            data = self._extract_json(raw)
            signal = bool(data.get("safety_signal", False))
            certainty = str(data.get("certainty", "NONE")).upper()
            hazard = data.get("hazard_type")
            confidence = float(data.get("confidence", 0) or 0)
            if not signal or certainty not in {"SUSPECTED", "CONFIRMED"}:
                return SafetyAssessment()
            if hazard not in self.HAZARD_TYPES:
                return SafetyAssessment()
            if confidence < 0.78:
                return SafetyAssessment()
            return SafetyAssessment(
                safety_signal=True,
                certainty=certainty,
                hazard_type=hazard,
                evidence=str(data.get("evidence", user_text))[:300],
                source="semantic",
                confidence=confidence,
            )
        except Exception as exc:
            logger.warning("Safety semantic classification failed: %s", exc)
            return SafetyAssessment()

    # ── RAG Answer + Handoff Judge ───────────────────────────────────────

    async def answer_with_rag(self, case: CaseData, user_message: str, conversation_history: List[dict]) -> AIAnswerResponse:
        """
        普通 RAG 回答与 Handoff Judge 共用一次 LLM 调用以控制延迟。
        返回值仍然将 answer 与 handoff_judgment 严格分开。
        """
        query = self._build_rag_query(case, user_message)
        rag_results = self._rag.retrieve(
            query,
            top_k=DEFAULT_SYSTEM_CONFIG.rag_top_k,
            threshold=0.01,
        )
        retrieval_id = "RET-{}".format(uuid.uuid4().hex[:8].upper())
        # 明确“查看/了解规则、政策、条件、流程”等属于知识咨询。
        # 只要普通 RAG 已检索到知识，就不应因历史对话中的“退货/退款”等词被 Handoff Judge 误判为无进展。
        knowledge_query = self._is_knowledge_query(user_message)

        self._case_mgr.audit(AuditEventType.RAG_RETRIEVED, case, Actor.AI, {
            "retrieval_id": retrieval_id,
            "query": query,
            "results": [{"source_id": r.source_id, "score": r.score} for r in rag_results],
        })

        if not rag_results:
            judgment = HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
                reason_code="KNOWLEDGE_GAP",
                confidence=1.0,
                reason="知识库未检索到足以支持当前问题的依据",
                layer="deterministic_fallback",
                evidence=["RAG returned 0 relevant chunks"],
                knowledge_sufficient=False,
                capability_within_bounds=True,
            )
            return AIAnswerResponse(
                answer="暂未检索到足以支持当前问题的知识依据。",
                knowledge_sufficient=False,
                capability_within_bounds=True,
                handoff_judgment=judgment,
            )

        prompt = self._build_answer_and_judge_prompt(
            case, user_message, rag_results, conversation_history
        )
        try:
            raw = await self._call_llm(prompt)
            data = self._extract_json(raw)
            answer = str(data.get("answer", "")).strip()
            if not answer:
                answer = self._fallback_answer(rag_results, user_message)

            knowledge_sufficient = bool(data.get("knowledge_sufficient", True))
            capability_within_bounds = bool(data.get("capability_within_bounds", True))
            judgment = self._parse_handoff_judgment(
                data.get("handoff_judgment") or {},
                knowledge_sufficient=knowledge_sufficient,
                capability_within_bounds=capability_within_bounds,
            )
        except Exception as exc:
            logger.warning("RAG answer / handoff judgment failed: %s", exc)
            answer = self._fallback_answer(rag_results, user_message)
            knowledge_sufficient = True
            capability_within_bounds = True
            judgment = HandoffJudgment(
                need_human=False,
                trigger=None,
                reason_code="CONTINUE",
                confidence=0.55,
                reason="模型判断不可用，当前存在可检索知识，采用保守继续策略",
                layer="deterministic_fallback",
                evidence=["RAG has relevant chunks", "LLM judge unavailable"],
                knowledge_sufficient=True,
                capability_within_bounds=True,
            )

        # 面向消费者的回答不暴露“知识库/检索片段/内部分类”等系统语言。
        answer = self._sanitize_customer_answer(answer, user_message, rag_results)

        # 知识咨询保护：规则、政策、条件、流程等查询只要已经检索到普通售后知识，
        # 就继续知识服务，不因历史上下文或重复提问被误判为 AUTOMATION_NO_PROGRESS。
        # 明确人工请求、安全风险、真实业务数据查询和权限动作已由 Service 的 Hard/Safety Gate 优先处理。
        if knowledge_query and rag_results:
            knowledge_sufficient = True
            capability_within_bounds = True
            judgment = HandoffJudgment(
                need_human=False,
                trigger=None,
                reason_code="CONTINUE",
                confidence=1.0,
                reason="用户当前是在咨询售后规则/政策/条件/流程，已有知识可回答，继续智能客服服务",
                layer="knowledge_query_guard",
                evidence=[user_message, "RAG returned relevant chunks"],
                knowledge_sufficient=True,
                capability_within_bounds=True,
            )

        # 服务端兜底：模型不能在知识不足或能力越界时强行继续。
        if not knowledge_sufficient:
            judgment = HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
                reason_code="KNOWLEDGE_GAP",
                confidence=max(judgment.confidence, 0.95),
                reason=judgment.reason or "知识依据不足，无法继续可靠回答",
                layer=judgment.layer or "deterministic_fallback",
                evidence=judgment.evidence or ["knowledge_sufficient=false"],
                knowledge_sufficient=False,
                capability_within_bounds=capability_within_bounds,
            )
        elif not capability_within_bounds:
            judgment = HandoffJudgment(
                need_human=True,
                trigger=HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
                reason_code="CAPABILITY_GAP",
                confidence=max(judgment.confidence, 0.95),
                reason=judgment.reason or "请求超出当前智能客服系统能力范围",
                layer=judgment.layer or "deterministic_fallback",
                evidence=judgment.evidence or ["capability_within_bounds=false"],
                knowledge_sufficient=knowledge_sufficient,
                capability_within_bounds=False,
            )

        self._case_mgr.audit(AuditEventType.AI_ANSWERED, case, Actor.AI, {
            "answer": answer[:300],
            "used_sources": [r.source_id for r in rag_results],
            "handoff_judgment": judgment.model_dump(),
        })
        return AIAnswerResponse(
            answer=answer,
            used_sources=[r.source_id for r in rag_results],
            knowledge_sufficient=knowledge_sufficient,
            capability_within_bounds=capability_within_bounds,
            is_safety_risk=False,
            handoff_judgment=judgment,
        )

    def _parse_handoff_judgment(
        self,
        data: Dict[str, Any],
        *,
        knowledge_sufficient: bool,
        capability_within_bounds: bool,
    ) -> HandoffJudgment:
        if not isinstance(data, dict):
            data = {}
        reason_code = str(data.get("reason_code", "CONTINUE")).upper()
        if reason_code not in self.HANDOFF_REASON_CODES:
            reason_code = "CONTINUE"

        confidence = float(data.get("confidence", 0) or 0)
        need_human = bool(data.get("need_human", False))
        evidence = data.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        evidence = [str(x)[:240] for x in evidence[:6]]

        trigger = self._reason_code_to_trigger(reason_code) if need_human else None
        # AI 判断必须达到较高置信度才允许触发普通自动转人工。
        # 知识不足/能力越界由上层确定性兜底，不依赖该阈值。
        if need_human and confidence < 0.80:
            need_human = False
            trigger = None
            reason_code = "CONTINUE"

        return HandoffJudgment(
            need_human=need_human,
            trigger=trigger,
            reason_code=reason_code,
            confidence=confidence,
            reason=str(data.get("reason", ""))[:400],
            layer="ai_judge",
            evidence=evidence,
            knowledge_sufficient=knowledge_sufficient,
            capability_within_bounds=capability_within_bounds,
        )

    @staticmethod
    def _reason_code_to_trigger(reason_code: str) -> Optional[HandoffTrigger]:
        mapping = {
            "KNOWLEDGE_GAP": HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
            "CAPABILITY_GAP": HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
            "OUT_OF_SCOPE": HandoffTrigger.KNOWLEDGE_OR_CAPABILITY_GAP,
            "AUTHORITY_BOUNDARY": HandoffTrigger.AUTHORITY_BOUNDARY,
            "AUTOMATION_NO_PROGRESS": HandoffTrigger.AUTOMATION_NO_PROGRESS,
        }
        return mapping.get(reason_code)

    # ── Prompt / Parse ───────────────────────────────────────────────────

    def _build_path_prompt(self, case: CaseData, user_text: str, routes: List[List[CandidatePathStep]]) -> str:
        lines = []
        for route in routes:
            lines.append(" | ".join("{}={}".format(step.option_id, step.label) for step in route))
        route_text = "\n".join(lines)
        confirmed = " → ".join(case.issue_path) if case.issue_path else "无"
        return (
            "你是售后 Workflow 的受限语义映射器。\n"
            "从下面人工预设的合法路径中，选择用户文本能够可靠支持的‘最长可靠既有路径’。\n"
            "允许修正用户之前误点的分类，因此输出从根节点开始的完整候选路径前缀。\n"
            "不能创建新节点、新选项、新连接；不能为了更深层级而猜测。\n"
            "如果只能确定第一层，就只输出第一层；如果可以确定三层，就输出三层。\n"
            "例如‘我衣服买大了’应利用‘衣服’和‘买大了’的信息尽可能定位到服饰尺码问题。\n"
            "只返回 JSON：\n"
            '{{"decision":"MATCH","candidate_path":["OPTION_ID1","OPTION_ID2"],"confidence":0.95,"reason":"简短理由"}}\n'
            "无法可靠映射时：\n"
            '{{"decision":"NO_MATCH","candidate_path":[],"confidence":0.0,"reason":"信息不足"}}\n\n'
            "用户此前已确认路径：{}\n"
            "合法路径：\n{}\n\n"
            "用户文本：{}"
        ).format(confirmed, route_text, user_text)

    @staticmethod
    def _build_rag_query(case: CaseData, user_message: str) -> str:
        parts = list(case.issue_path[-3:])
        if case.user_intent:
            parts.append(case.user_intent)
        parts.append(user_message)
        return " ".join(p for p in parts if p)

    @staticmethod
    def _build_answer_and_judge_prompt(case: CaseData, user_msg: str, rag_results, history: List[dict]) -> str:
        knowledge = "\n\n".join(
            "[{} | {}]\n{}".format(r.source_id, r.source_title, r.content) for r in rag_results
        )
        recent = history[-8:] if history else []
        history_text = "\n".join("{}: {}".format(x.get("role"), x.get("content")) for x in recent)
        return (
            "你是售后知识助手，同时承担受限 Handoff Judge。\n"
            "你只能依据提供的 Workflow 上下文、知识库和对话判断当前智能客服是否还能可靠继续处理。\n"
            "你没有权限真正创建工单、转人工、退款、赔付、修改订单或做责任认定。\n"
            "真正的业务动作由后端执行，因此禁止在 answer 中声称‘已转人工’‘已创建工单’。\n\n"
            "Handoff Judge 允许的 reason_code 只有：\n"
            "CONTINUE：知识和能力足够，可继续自动处理；\n"
            "KNOWLEDGE_GAP：知识库依据不足；\n"
            "CAPABILITY_GAP：需要真实订单、资金、物流内部状态等系统未接入能力；\n"
            "AUTHORITY_BOUNDARY：需要退款复核、赔偿、责任认定、审批等人工权限；\n"
            "AUTOMATION_NO_PROGRESS：结合历史对话，自动排查已经反复没有有效推进；\n"
            "OUT_OF_SCOPE：问题无法在当前售后系统中得到可靠处理。\n\n"
            "不要因为用户情绪不好就自动转人工；判断重点是知识、能力、权限和处理进展。\n"
            "如果用户是在询问规则、政策、条件、流程、时效或一般处理方法，且知识库已有依据，必须判为 CONTINUE。\n"
            "只有需要查询真实订单/资金/物流内部状态、执行退款复核/赔付等权限动作，或自动排查确实反复无进展时，才考虑转人工。\n"
            "如果仍能提出可靠且低风险的下一步，则 CONTINUE。\n\n"
            "answer 是直接展示给消费者的客服回复，必须遵守：\n"
            "1. 使用自然、简洁、礼貌的中文，直接回答用户当前问题；\n"
            "2. 禁止出现‘根据当前知识库’‘根据检索结果’‘参考以下信息’‘知识片段’‘可帮助用户区分’等内部系统表述；\n"
            "3. 不要解释内部分类逻辑、reason_code、Workflow 或 AI 权限边界；\n"
            "4. 用户只是在查看规则/政策/条件/流程时，直接说明对应规则，不要求提供订单号，也不要擅自转人工；\n"
            "5. 不得声称已经执行退款、退货、赔付、改判或创建工单。\n"
            "只返回 JSON，不要输出 JSON 之外的文字：\n"
            "{{\n"
            '  "answer":"面向用户的简洁回答",\n'
            '  "knowledge_sufficient":true,\n'
            '  "capability_within_bounds":true,\n'
            '  "handoff_judgment":{{\n'
            '    "need_human":false,\n'
            '    "reason_code":"CONTINUE",\n'
            '    "confidence":0.92,\n'
            '    "reason":"一句话说明为什么继续或退出自动化",\n'
            '    "evidence":["证据1","证据2"]\n'
            "  }}\n"
            "}}\n\n"
            "当前已确认路径：{}\n"
            "自动排查失败计数：{}\n"
            "用户未解决反馈计数：{}\n"
            "最近对话：\n{}\n\n"
            "知识库：\n{}\n\n"
            "用户最新描述：{}"
        ).format(
            " → ".join(case.issue_path) or "尚未确认",
            case.automation_failure_count,
            case.user_unresolved_count,
            history_text or "无",
            knowledge,
            user_msg,
        )

    @staticmethod
    def _is_knowledge_query(user_message: str) -> bool:
        """识别纯知识咨询。真实数据查询/业务执行由 Service Hard Gate 优先拦截。"""
        text = (user_message or "").replace(" ", "")
        if not text:
            return False

        direct_patterns = [
            "规则", "政策", "条件", "流程", "规定", "说明", "要求",
            "怎么退", "如何退", "怎么退款", "如何退款", "怎么退货", "如何退货",
            "多久到账", "多久能到", "什么时候到账", "需要什么材料", "需要哪些材料",
            "能不能退", "可以退吗", "支持退货吗", "支持退款吗",
        ]
        consult_markers = ["我要看", "我想看", "看看", "查看", "了解", "咨询", "想知道", "告诉我", "介绍一下"]
        service_topics = ["退货", "退款", "换货", "维修", "保修", "物流", "配送", "售后", "尺码", "退换货"]

        if any(p in text for p in direct_patterns):
            return True
        return any(c in text for c in consult_markers) and any(t in text for t in service_topics)

    @classmethod
    def _sanitize_customer_answer(cls, answer: str, user_message: str, rag_results) -> str:
        """避免把知识片段/内部控制语言原样展示给消费者。"""
        text = (answer or "").strip()
        internal_markers = [
            "根据当前知识库", "根据检索结果", "可参考以下信息", "知识片段",
            "可帮助用户区分", "source_id", "source_title", "chunk_id",
            "AI 可以", "AI 不可以", "AUTHORITY_BOUNDARY", "CAPABILITY_GAP",
            "KNOWLEDGE_GAP", "AUTOMATION_NO_PROGRESS", "Workflow",
        ]
        if not text or any(marker in text for marker in internal_markers):
            return cls._fallback_answer(rag_results, user_message)
        return text

    @staticmethod
    def _fallback_answer(rag_results, user_message: str = "") -> str:
        """LLM/JSON 不可用时的消费者友好降级回答，不暴露知识库内部文本。"""
        query = (user_message or "").replace(" ", "")

        # 这些模板直接来自当前售后政策知识，避免模型故障时把内部知识片段原样吐给用户。
        if "退货" in query or "退换货" in query:
            return (
                "退货通常需要在适用的售后期限内提出，商品保持完好、未损坏且不影响二次销售，"
                "并且不属于不支持无理由退货的特殊品类。符合条件后，可以在售后入口提交退货申请。"
            )
        if "退款" in query or "退钱" in query:
            return (
                "退款一般会按原支付路径返回，具体到账时间会受到支付渠道处理周期影响。"
                "如果只是了解退款规则，我可以继续为您说明；涉及具体订单资金状态时需要人工查询。"
            )
        if any(k in query for k in ["衣服", "外套", "裤子", "鞋", "鞋子", "包", "尺码", "版型", "大了", "小了"]):
            return (
                "如果是尺码偏大、偏小或版型不合适，可以先核对商品页面的尺码说明和实际尺寸。"
                "如果您希望退换货，我也可以继续说明对应的退换货条件和流程。"
            )

        # 通用降级：只保留知识片段中的用户可读事实，移除内部控制性语言。
        first = rag_results[0]
        lines = []
        skip_prefixes = ("AI 可以", "AI 不可以", "需要真实复核时进入", "可帮助用户区分")
        for raw_line in (first.content or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(skip_prefixes):
                continue
            if any(code in line for code in ["AUTHORITY_BOUNDARY", "CAPABILITY_GAP", "KNOWLEDGE_GAP"]):
                continue
            line = re.sub(r'^[\-•]+\s*', '', line)
            lines.append(line)
        text = "；".join(lines)
        text = re.sub(r'\s+', ' ', text).strip("； ")
        if len(text) > 320:
            text = text[:320].rstrip("，。； ") + "。"
        return text or "我可以继续为您说明相关售后规则和处理方式。"

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.S)
            if match:
                return json.loads(match.group(0))
            raise

    # ── MiMo ─────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        if not HAS_HTTPX or not MIMO_API_KEY:
            raise RuntimeError("MiMo API unavailable")
        url = "{}/chat/completions".format(MIMO_BASE_URL.rstrip('/'))
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": "Bearer {}".format(MIMO_API_KEY), "Content-Type": "application/json"},
                json={
                    "model": MIMO_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": MIMO_MAX_TOKENS,
                    "temperature": MIMO_TEMPERATURE,
                },
            )
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if not content:
                content = (message.get("reasoning_content") or "").strip()
            if not content:
                raise ValueError("MiMo returned empty response")
            return content

    # ── 与 Workflow label 绑定的降级规则 ───────────────────────────────

    def _deterministic_path_fallback(self, text: str, routes: List[List[CandidatePathStep]]) -> MappingResult:
        normalized = (text or "").lower()
        targets: List[str] = []

        if any(k in normalized for k in ["退款", "退货", "退钱"]):
            targets.append("退货 / 退款问题")
            # 用户在询问退款/退货流程，且没有表达已申请、被拒、到账异常等状态时，
            # 可可靠定位到“还没有申请退货 / 退款”。
            if any(k in normalized for k in ["退款流程", "退货流程", "怎么退款", "如何退款", "怎么退货", "如何退货", "申请退款", "申请退货"]):
                targets.append("还没有申请退货 / 退款")
        elif any(k in normalized for k in ["物流", "快递", "配送", "未发货", "签收"]):
            targets.append("物流 / 配送问题")
        elif any(k in normalized for k in ["描述不符", "与描述不符", "页面写", "型号不符"]):
            targets.append("商品与描述不符")
        elif any(k in normalized for k in ["缺件", "少件", "错件", "数量不对", "发错"]):
            targets.append("缺件 / 错件 / 数量问题")
        elif any(k in normalized for k in ["维修", "保修"]):
            targets.append("维修 / 保修问题")
        elif any(k in normalized for k in ["怎么用", "如何使用", "安装方法", "操作方法", "怎么安装"]):
            targets.append("使用 / 操作咨询")
        elif any(k in normalized for k in ["衣服", "外套", "裤子", "鞋", "鞋子", "包", "鼠标", "耳机", "键盘", "充电器", "手机", "电器", "家具", "柜子", "椅子", "面霜", "化妆品", "食品", "零食", "坏", "异常", "问题", "大了", "小了", "没声音", "没有声音", "无声"]):
            targets.append("商品本身问题")

        if any(k in normalized for k in ["衣服", "外套", "裤子", "裙", "鞋", "鞋子", "包", "服装"]):
            targets.append("服饰 / 鞋包")
        elif any(k in normalized for k in ["鼠标", "键盘", "耳机", "充电器", "充电宝", "手机", "电脑", "电器", "插座"]):
            targets.append("数码 / 家电")
        elif any(k in normalized for k in ["家具", "柜子", "椅子", "桌子", "床", "收纳", "家居"]):
            targets.append("家居 / 生活用品")
        elif any(k in normalized for k in ["面霜", "精华", "口红", "化妆品", "护肤", "洗发", "个护"]):
            targets.append("美妆 / 个护")
        elif any(k in normalized for k in ["食品", "零食", "饮料", "吃", "食物"]):
            targets.append("食品 / 消耗品")

        if any(k in normalized for k in ["大了", "小了", "尺码", "版型", "不合身"]):
            targets.append("尺码 / 版型问题")
        elif ((any(k in normalized for k in ["一边", "单边", "单耳", "左耳", "右耳"]) and any(k in normalized for k in ["没声音", "没有声音", "无声", "不出声"]))
              or any(k in normalized for k in ["左键", "右键", "按键", "部分功能", "有一个功能", "只有一个"])):
            targets.append("部分功能异常")
        elif any(k in normalized for k in ["没声音", "没有声音", "无声", "不出声", "开不了", "无法工作", "完全没反应", "不能用"]):
            targets.append("完全无法工作")
        elif any(k in normalized for k in ["充不进去", "充电异常", "供电异常"]):
            targets.append("供电 / 充电异常")
        elif any(k in normalized for k in ["结构松", "松动", "结构坏", "部件坏"]):
            targets.append("结构松动 / 损坏")
        elif any(k in normalized for k in ["面料", "材质"]):
            targets.append("面料 / 材质问题")

        if not targets:
            return MappingResult(decision="NO_MATCH", confidence=0.0, reason="降级规则无法可靠定位")

        best: Optional[List[CandidatePathStep]] = None
        for route in routes:
            labels = [s.label for s in route]
            prefix = []
            for target in targets:
                if len(prefix) < len(labels) and labels[len(prefix)] == target:
                    prefix.append(route[len(prefix)])
                else:
                    break
            if prefix and (best is None or len(prefix) > len(best)):
                best = prefix

        if not best:
            for route in routes:
                if route and route[0].label == targets[0]:
                    best = [route[0]]
                    break

        if not best:
            return MappingResult(decision="NO_MATCH", confidence=0.0, reason="没有合法路径与降级规则一致")

        return MappingResult(
            decision="MATCH",
            mapped_option_id=best[-1].option_id,
            candidate_path=best,
            confidence=0.90,
            reason="基于人工 Workflow label 的确定性降级匹配",
            path_label=" → ".join(step.label for step in best),
        )
