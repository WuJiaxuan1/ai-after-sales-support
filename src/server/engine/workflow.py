"""
workflow.py — 确定性 Workflow 引擎（v2）
========================================
负责：
  1. 固定按钮推进 / 回退
  2. 输出人工预设 Workflow 的合法路径，供 AI 做受限路径理解
  3. 校验并一次性应用 Longest Reliable Existing Path

核心边界：
  - AI 可以提出路径，但不能创建节点或连接
  - 候选路径必须经过本模块逐步校验
  - 用户确认后才写入 Case 正式状态
"""
from typing import Optional, List, Dict, Any

from ..models.schemas import (
    WorkflowConfig, WorkflowNode, CaseData, CaseState,
    HandoffTrigger, WorkflowOption, CandidatePathStep,
)


class NavigationResult:
    def __init__(self, success, case, error="", current_node=None,
                 terminal_action=None, handoff_trigger=None, label_of_selected=""):
        self.success = success
        self.case = case
        self.error = error
        self.current_node = current_node
        self.terminal_action = terminal_action
        self.handoff_trigger = handoff_trigger
        self.label_of_selected = label_of_selected


class WorkflowEngine:
    def __init__(self, config: WorkflowConfig):
        self.config = config

    def get_start_node(self) -> WorkflowNode:
        return self.config.nodes[self.config.start_node]

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        return self.config.nodes.get(node_id)

    # ── 固定按钮导航 ─────────────────────────────────────────────────────

    def select_option(self, case: CaseData, node_id: str, option_id: str) -> NavigationResult:
        node = self._require_current_node(case, node_id)
        if node is None:
            return NavigationResult(
                False, case,
                error="NODE_MISMATCH: expected {}, got {}".format(case.current_node_id, node_id),
            )

        option = self._find_option(node, option_id)
        if option is None:
            return NavigationResult(False, case, error="INVALID_OPTION: {} not in node {}".format(option_id, node_id))

        if option.action == "RETURN_PREVIOUS":
            return self._handle_return(case)

        if option.action == "HANDOFF_NO_MATCH":
            case.state = CaseState.HANDOFF_CREATED
            case.handoff_trigger = HandoffTrigger.NO_MATCH_CONFIRMED
            return NavigationResult(
                True, case,
                terminal_action="HANDOFF",
                handoff_trigger=HandoffTrigger.NO_MATCH_CONFIRMED,
                label_of_selected=option.label,
            )

        self._record_selection(case, node, option)

        next_node = self.config.nodes.get(case.current_node_id)
        if next_node is None:
            return NavigationResult(False, case, error="WORKFLOW_CONFIGURATION_ERROR: node {} not found".format(case.current_node_id))

        if next_node.type == "terminal":
            result = self._handle_terminal(case, next_node)
            result.label_of_selected = option.label
            return result

        return NavigationResult(True, case, current_node=next_node, label_of_selected=option.label)

    def apply_mapping_option(self, case: CaseData, option_id: str) -> NavigationResult:
        """兼容旧单层映射。"""
        return self.select_option(case, case.current_node_id, option_id)

    # ── Longest Reliable Existing Path ──────────────────────────────────

    def enumerate_routes(self, max_depth: int = 8) -> List[List[CandidatePathStep]]:
        """枚举从根节点出发的合法人工 Workflow 路径，供受限 AI 选择。"""
        routes: List[List[CandidatePathStep]] = []

        def dfs(node_id: str, path: List[CandidatePathStep], seen: set):
            if len(path) >= max_depth or node_id in seen:
                if path:
                    routes.append(list(path))
                return

            node = self.config.nodes.get(node_id)
            if node is None:
                return
            if node.type == "terminal":
                routes.append(list(path))
                return

            for option in node.options:
                # “返回重新选择 / 都不符合转人工”属于动作，不作为语义路径候选。
                if option.action:
                    continue
                step = CandidatePathStep(node_id=node.id, option_id=option.option_id, label=option.label)
                next_path = path + [step]
                if not option.next_node:
                    routes.append(next_path)
                    continue
                next_node = self.config.nodes.get(option.next_node)
                if next_node is None or next_node.type == "terminal":
                    routes.append(next_path)
                else:
                    dfs(option.next_node, next_path, seen | {node_id})

        dfs(self.config.start_node, [], set())
        return routes

    def validate_candidate_path(self, path: List[CandidatePathStep]) -> bool:
        """候选路径必须是从根节点开始的一段合法前缀。"""
        if not path:
            return False
        expected_node_id = self.config.start_node
        for step in path:
            if step.node_id != expected_node_id:
                return False
            node = self.config.nodes.get(expected_node_id)
            if node is None or node.type == "terminal":
                return False
            option = self._find_option(node, step.option_id)
            if option is None or option.action:
                return False
            if option.label != step.label:
                return False
            if not option.next_node:
                return False
            expected_node_id = option.next_node
        return True

    def apply_candidate_path(self, case: CaseData, path: List[CandidatePathStep]) -> NavigationResult:
        """
        用户确认 AI 候选路径后一次应用整条路径。
        为支持“自由文本纠正之前误点的按钮”，从根节点重放候选路径；
        任何一步非法都整体拒绝，AI 无法越过 Workflow。
        """
        if not self.validate_candidate_path(path):
            return NavigationResult(False, case, error="INVALID_CANDIDATE_PATH")

        # 候选路径已经由用户整体确认，因此可以安全替换旧的下游分类。
        self._reset_workflow_state(case)

        last_label = ""
        for step in path:
            node = self.config.nodes.get(case.current_node_id)
            if node is None or node.id != step.node_id:
                return NavigationResult(False, case, error="CANDIDATE_PATH_NODE_MISMATCH")
            option = self._find_option(node, step.option_id)
            if option is None or option.label != step.label or option.action:
                return NavigationResult(False, case, error="CANDIDATE_PATH_OPTION_MISMATCH")

            last_label = option.label
            self._record_selection(case, node, option)
            next_node = self.config.nodes.get(case.current_node_id)
            if next_node is None:
                return NavigationResult(False, case, error="WORKFLOW_CONFIGURATION_ERROR")

            if next_node.type == "terminal":
                # 候选路径到达终态，必须恰好在最后一步。
                if step is not path[-1]:
                    return NavigationResult(False, case, error="CANDIDATE_PATH_AFTER_TERMINAL")
                result = self._handle_terminal(case, next_node)
                result.label_of_selected = last_label
                return result

        # 路径只可靠到中间节点：停在该节点继续按钮/自由文本。
        case.state = CaseState.IN_WORKFLOW
        node = self.config.nodes.get(case.current_node_id)
        return NavigationResult(True, case, current_node=node, label_of_selected=last_label)

    # ── 回退 ─────────────────────────────────────────────────────────────

    def go_back(self, case: CaseData, target_node_id: str) -> NavigationResult:
        if target_node_id not in case.visited_nodes and target_node_id != self.config.start_node:
            return NavigationResult(False, case, error="INVALID_BACK_TARGET: {} not in visited path".format(target_node_id))

        target_idx = None
        for i, nid in enumerate(case.visited_nodes):
            if nid == target_node_id:
                target_idx = i
                break

        if target_idx is not None:
            case.visited_nodes = case.visited_nodes[:target_idx]
            case.issue_path = case.issue_path[:target_idx]
            # 分类路径不是“客观事实”，只保留对应的人工确认记录数量。
            case.confirmed_facts = case.confirmed_facts[:target_idx]

        self._clear_pending(case)
        case.automation_failure_count = 0
        case.current_node_id = target_node_id
        case.state = CaseState.IN_WORKFLOW
        target_node = self.config.nodes.get(target_node_id)
        return NavigationResult(True, case, current_node=target_node)

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _record_selection(self, case: CaseData, node: WorkflowNode, option: WorkflowOption):
        case.issue_path.append(option.label)
        case.confirmed_facts.append("用户确认分类：{}".format(option.label))
        if node.dimension == "user_intent":
            case.user_intent = option.label
        case.visited_nodes.append(node.id)
        case.current_node_id = option.next_node or ""

    def _reset_workflow_state(self, case: CaseData):
        case.state = CaseState.IN_WORKFLOW
        case.current_node_id = self.config.start_node
        case.issue_path = []
        case.confirmed_facts = []
        case.user_intent = None
        case.visited_nodes = []
        case.handoff_trigger = None

    @staticmethod
    def _clear_pending(case: CaseData):
        case.pending_mapped_option_id = None
        case.pending_mapping_reason = None
        case.pending_candidate_path = []
        case.pending_original_text = None
        case.pending_rag_answer = None
        case.pending_rag_sources = []

    def _require_current_node(self, case: CaseData, node_id: str) -> Optional[WorkflowNode]:
        if node_id != case.current_node_id:
            return None
        return self.config.nodes.get(node_id)

    @staticmethod
    def _find_option(node: WorkflowNode, option_id: str) -> Optional[WorkflowOption]:
        for opt in node.options:
            if opt.option_id == option_id:
                return opt
        return None

    def _handle_terminal(self, case: CaseData, node: WorkflowNode) -> NavigationResult:
        if node.action == "HANDOFF":
            case.state = CaseState.HANDOFF_CREATED
            trigger = HandoffTrigger(node.handoff_trigger) if node.handoff_trigger else HandoffTrigger.AUTHORITY_BOUNDARY
            case.handoff_trigger = trigger
            return NavigationResult(True, case, terminal_action="HANDOFF", handoff_trigger=trigger)
        case.state = CaseState.AI_RAG_SERVICE
        return NavigationResult(True, case, terminal_action="ENTER_RAG_SERVICE")

    def _handle_return(self, case: CaseData) -> NavigationResult:
        if not case.visited_nodes:
            node = self.config.nodes.get(case.current_node_id)
            return NavigationResult(True, case, current_node=node)
        return self.go_back(case, case.visited_nodes[-1])
