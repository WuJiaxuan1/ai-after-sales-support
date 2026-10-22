"""
case_manager.py — Case 生命周期管理器
=======================================
系统中所有 Case 状态的单一数据源（Single Source of Truth）。
负责：
  1. Case 的创建、查询、版本化变更
  2. 对话消息的管理
  3. 审计日志的追加记录
  4. 幂等键缓存（防止重复提交）

线程安全：通过 asyncio.Lock 保护所有写操作。
生产环境应替换为数据库 + 乐观并发控制。
"""
import asyncio
import uuid
from typing import Optional, Dict, List, Callable
from datetime import datetime

from ..models.schemas import (
    CaseData, CaseState, Conversation, Message,
    AuditEvent, AuditEventType, Actor,
)
from ..config.defaults import DEFAULT_SYSTEM_CONFIG
from .workflow import WorkflowEngine


class CaseManager:
    """
    Case 管理器。内存存储，适用于 MVP 原型。
    所有状态变更通过 mutate() 方法执行，自动处理版本递增和幂等。
    """

    def __init__(self):
        self._cases = {}                # type: Dict[str, CaseData]     所有 Case
        self._conversations = {}        # type: Dict[str, Conversation] 所有对话
        self._audit_log = []            # type: List[AuditEvent]        审计日志（只追加）
        self._idempotency_cache = {}    # type: Dict[str, CaseData]     幂等键缓存
        self._lock = asyncio.Lock()     # 写操作锁
        self._engine = WorkflowEngine(DEFAULT_SYSTEM_CONFIG.workflow)

    @property
    def engine(self) -> WorkflowEngine:
        """获取 Workflow 引擎实例。"""
        return self._engine

    # ── Case CRUD ─────────────────────────────────────────────────────────

    async def create_case(self, idempotency_key: str, product_name: str = None, product_model: str = None) -> CaseData:
        """
        创建新 Case。
        1. 检查幂等键（防止重复创建）
        2. 生成唯一 Case ID 和对话 ID
        3. 初始化 Case 状态（从 Workflow 起始节点开始）
        4. 记录审计事件
        """
        cached = self._check_idempotency(idempotency_key)
        if cached:
            return cached  # 幂等：返回已创建的 Case

        async with self._lock:
            case_id = "CASE-{}".format(uuid.uuid4().hex[:8].upper())
            conv_id = "CONV-{}".format(uuid.uuid4().hex[:8].upper())
            start_node = self._engine.get_start_node()

            case = CaseData(
                case_id=case_id,
                case_version=1,
                state=CaseState.IN_WORKFLOW,
                workflow_version=DEFAULT_SYSTEM_CONFIG.workflow.workflow_version,
                current_node_id=start_node.id,
                conversation_id=conv_id,
                visited_nodes=[],
            )
            self._cases[case_id] = case
            self._conversations[conv_id] = Conversation(
                conversation_id=conv_id, case_id=case_id, messages=[],
            )
            self._append_audit(AuditEventType.CASE_CREATED, case, Actor.SYSTEM,
                               {"product_name": product_name, "product_model": product_model})
            self._cache_idempotency(idempotency_key, case)
            return case

    def get_case(self, case_id: str) -> Optional[CaseData]:
        """根据 Case ID 查询 Case。"""
        return self._cases.get(case_id)

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """根据对话 ID 查询对话。"""
        return self._conversations.get(conversation_id)

    def get_conversation_by_case(self, case_id: str) -> Optional[Conversation]:
        """根据 Case ID 查询关联的对话。"""
        case = self._cases.get(case_id)
        if case:
            return self._conversations.get(case.conversation_id)
        return None

    def list_cases(self) -> List[CaseData]:
        """列出所有 Case。"""
        return list(self._cases.values())

    # ── 版本化变更 ────────────────────────────────────────────────────────

    async def mutate(self, case_id: str, expected_version: int, idempotency_key: str, mutation: Callable):
        """
        执行版本化的 Case 变更。
        1. 检查幂等键（防止重复操作）
        2. 校验 Case 存在性和版本号（防止过期操作覆盖最新状态）
        3. 执行变更函数
        4. 递增版本号
        返回 (case, error_string)。error 为空表示成功。
        """
        cached = self._check_idempotency(idempotency_key)
        if cached:
            if isinstance(cached, CaseData):
                return cached, ""
            return self._cases.get(case_id), ""

        async with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None, "CASE_NOT_FOUND: {}".format(case_id)
            if case.case_version != expected_version:
                return case, "VERSION_MISMATCH: expected {}, got {}".format(expected_version, case.case_version)
            mutation(case)
            case.case_version += 1
            self._cache_idempotency(idempotency_key, case)
            return case, ""

    # ── 对话消息 ──────────────────────────────────────────────────────────

    def add_message(self, case_id: str, role: str, content: str, metadata: dict = None) -> Message:
        """
        向 Case 的对话中添加一条消息。
        role: "user" / "assistant" / "system" / "human_agent"
        metadata: 附加信息（如 sender_name、used_sources）
        """
        case = self._cases.get(case_id)
        conv = self._conversations.get(case.conversation_id) if case else None
        if conv is None:
            raise ValueError("No conversation for case {}".format(case_id))
        msg = Message(role=role, content=content, metadata=metadata or {})
        conv.messages.append(msg)
        return msg

    # ── 审计日志 ──────────────────────────────────────────────────────────

    def audit(self, event_type: AuditEventType, case: CaseData, actor: Actor, data: dict = None):
        """记录审计事件。历史事件不覆盖，支持复原 Case 完整演变。"""
        self._append_audit(event_type, case, actor, data)

    def get_audit_log(self, case_id: str) -> List[AuditEvent]:
        """获取指定 Case 的所有审计事件。"""
        return [e for e in self._audit_log if e.case_id == case_id]

    def _append_audit(self, event_type: AuditEventType, case: CaseData, actor: Actor, data: dict = None):
        """内部方法：创建并追加审计事件。"""
        evt = AuditEvent(
            event_id="EVT-{}".format(uuid.uuid4().hex[:8].upper()),
            event_type=event_type,
            case_id=case.case_id,
            case_version=case.case_version,
            actor=actor,
            data=data or {},
        )
        self._audit_log.append(evt)

    # ── 幂等缓存 ─────────────────────────────────────────────────────────

    def _check_idempotency(self, key: str) -> Optional[CaseData]:
        """检查幂等键是否已存在。存在则返回缓存的 Case，避免重复操作。"""
        return self._idempotency_cache.get(key)

    def _cache_idempotency(self, key: str, case: CaseData):
        """缓存幂等键对应的 Case 对象。"""
        self._idempotency_cache[key] = case
