"""
priority.py — 优先级计算器
============================
纯规则引擎，零 AI 参与。
负责：
  1. 根据安全风险和可验证经济暴露金额计算 P0-P3
  2. 非 P0 Case 的老化升级（每 60 分钟升一级，最高 P1）

关键约束：
  - P0 只能由安全风险产生，不因投诉、强烈情绪或金额大小产生
  - verified_exposure_amount 必须来自系统数据（订单/退款/维修），非用户自述
  - 用户自报金额只保存为 claimed_amount，不参与排序
  - 金额缺失时标记 MISSING_EXPOSURE_DATA，按 P3 入队等待人工核验
"""
from typing import Optional, Tuple
from datetime import datetime

from ..models.schemas import Priority, PriorityPolicy


class PriorityCalculator:
    """优先级计算器。配置驱动，阈值可调整。"""

    def __init__(self, policy: PriorityPolicy):
        self.policy = policy

    def calculate(self, is_safety_risk: bool, verified_exposure_amount: Optional[float]) -> Tuple[Priority, str, bool]:
        """
        计算优先级。
        返回 (priority, reason, missing_exposure_data)。
        计算顺序固定：安全风险 → 金额区间映射 → 缺失处理。
        """
        # Step 1: 安全风险 → P0（最高优先级，不受金额影响）
        if is_safety_risk:
            return Priority.P0, "安全风险触发，按最高优先级处理", False

        # Step 2: 金额缺失 → P3 + 标记缺失（不得由 AI 估算）
        if verified_exposure_amount is None:
            return Priority.P3, "缺少已核验经济暴露金额，暂按 P3 入队等待人工核验", True

        amount = verified_exposure_amount

        # Step 3: 按金额区间映射（阈值可配置）
        if amount >= self.policy.p1_min_exposure:
            return Priority.P1, "已核验经济暴露金额 {} 元达到 P1 阈值 {} 元".format(amount, self.policy.p1_min_exposure), False
        if amount >= self.policy.p2_min_exposure:
            return Priority.P2, "已核验经济暴露金额 {} 元达到 P2 阈值 {} 元".format(amount, self.policy.p2_min_exposure), False

        return Priority.P3, "已核验经济暴露金额 {} 元低于 P2 阈值 {} 元".format(amount, self.policy.p2_min_exposure), False

    def age_priority(self, current: Priority, queued_at: datetime, now: datetime = None) -> Tuple[Priority, bool]:
        """
        优先级老化升级。
        P0 不参与老化。非 P0 每等待 aging_interval_minutes 分钟升一级。
        最高升至 aging_ceiling（默认 P1）。
        返回 (new_priority, was_aged)。
        """
        if current == Priority.P0:
            return Priority.P0, False

        now = now or datetime.utcnow()
        elapsed = (now - queued_at).total_seconds() / 60.0  # 已等待分钟数
        steps = int(elapsed // self.policy.aging_interval_minutes)
        if steps <= 0:
            return current, False

        order = [Priority.P3, Priority.P2, Priority.P1]
        idx = order.index(current)
        new_idx = min(idx + steps, order.index(Priority(self.policy.aging_ceiling)))
        new_priority = order[new_idx]
        return new_priority, new_priority != current
