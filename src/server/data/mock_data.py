"""
mock_data.py — 模拟业务数据
==============================
提供 MVP 原型所需的模拟业务数据，包括：
  - 订单记录（商品名称、价格、购买日期、保修期）
  - 退款记录（退款金额、状态、拒绝原因）
  - 维修记录（维修状态、诊断、预估费用）

关键方法：
  - get_verified_exposure_amount(): 从系统数据中读取可验证经济暴露金额
    （用于优先级计算，不得由 AI 估算或使用用户自述金额）

生产环境应替换为真实的订单/支付系统接口。
"""
from typing import Optional


class OrderRecord:
    """订单记录。product_price 为可验证经济暴露金额的基础。"""
    def __init__(self, order_id, product_name, product_model, product_price,
                 purchase_date, warranty_end_date, customer_id):
        self.order_id = order_id              # 订单 ID
        self.product_name = product_name      # 商品名称
        self.product_model = product_model    # 商品型号
        self.product_price = product_price    # 商品价格（元）
        self.purchase_date = purchase_date    # 购买日期
        self.warranty_end_date = warranty_end_date  # 保修截止日期
        self.customer_id = customer_id        # 客户 ID


class RefundRecord:
    """退款记录。status 为 rejected 时退款金额计入经济暴露。"""
    def __init__(self, refund_id, order_id, refund_amount, status,
                 reject_reason="", created_at=""):
        self.refund_id = refund_id            # 退款 ID
        self.order_id = order_id              # 关联订单 ID
        self.refund_amount = refund_amount    # 退款金额
        self.status = status                  # 状态：pending/approved/rejected/completed
        self.reject_reason = reject_reason    # 拒绝原因
        self.created_at = created_at          # 创建时间


class RepairRecord:
    """维修记录。estimated_cost > 0 时计入经济暴露。"""
    def __init__(self, repair_id, order_id, status, diagnosis="", estimated_cost=0.0):
        self.repair_id = repair_id            # 维修 ID
        self.order_id = order_id              # 关联订单 ID
        self.status = status                  # 状态：pending/in_progress/completed/disputed
        self.diagnosis = diagnosis            # 诊断结果
        self.estimated_cost = estimated_cost  # 预估维修费用


class MockBusinessData:
    """
    模拟业务数据存储。预加载示例数据供 MVP 使用。
    提供查询接口，支持按订单 ID 或商品名称查找。
    """

    def __init__(self):
        self._orders = {}       # type: dict   订单数据
        self._refunds = {}      # type: dict   退款数据
        self._repairs = {}      # type: dict   维修数据
        # Demo 专用：为每个新 Case 绑定一条“系统已核验”的模拟订单，
        # 仅用于展示 P1/P2/P3 分级，不读取用户在聊天中自报的金额。
        self._demo_case_orders = {}
        self._demo_order_cycle = ["ORD-003", "ORD-001", "ORD-004"]  # P1 / P2 / P3
        self._demo_assign_index = 0
        self._load_sample_data()


    def assign_demo_order(self, case_id: str) -> str:
        """为 Case 绑定一条模拟的已核验订单。幂等；用于 MVP 展示 P1/P2/P3。"""
        if case_id in self._demo_case_orders:
            return self._demo_case_orders[case_id]
        order_id = self._demo_order_cycle[self._demo_assign_index % len(self._demo_order_cycle)]
        self._demo_assign_index += 1
        self._demo_case_orders[case_id] = order_id
        return order_id

    def get_demo_order_id(self, case_id: str) -> Optional[str]:
        return self._demo_case_orders.get(case_id)

    def get_demo_verified_exposure_amount(self, case_id: str) -> Optional[float]:
        """返回该 Case 绑定的模拟“已核验经济暴露”。用户自述金额绝不参与。"""
        order_id = self._demo_case_orders.get(case_id)
        if not order_id:
            return None
        return self.get_verified_exposure_amount(order_id)

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """根据订单 ID 查询订单。"""
        return self._orders.get(order_id)

    def get_order_by_product(self, product_name: str) -> Optional[OrderRecord]:
        """根据商品名称模糊查询订单。"""
        for order in self._orders.values():
            if product_name and product_name in order.product_name:
                return order
        return None

    def get_refund(self, order_id: str) -> Optional[RefundRecord]:
        """根据订单 ID 查询退款记录。"""
        return self._refunds.get(order_id)

    def get_repair(self, order_id: str) -> Optional[RepairRecord]:
        """根据订单 ID 查询维修记录。"""
        return self._repairs.get(order_id)

    def get_verified_exposure_amount(self, order_id: str) -> Optional[float]:
        """
        计算可验证经济暴露金额。
        取商品价格、退款金额、维修费用中的最大值。
        退款状态为 pending 或 rejected 时金额计入暴露。
        返回 None 表示无法计算（订单不存在）。
        """
        order = self._orders.get(order_id)
        if not order:
            return None

        refund = self._refunds.get(order_id)
        repair = self._repairs.get(order_id)

        amount = order.product_price
        if refund and refund.status in ("pending", "rejected"):
            amount = max(amount, refund.refund_amount)
        if repair and repair.estimated_cost > 0:
            amount = max(amount, repair.estimated_cost)

        return amount

    def _load_sample_data(self):
        """加载示例数据。涵盖不同价格区间和业务状态。"""
        orders = [
            OrderRecord("ORD-001", "小米无线鼠标", "XM-MS-001", 899.0, "2025-12-01", "2026-12-01", "CUST-001"),
            OrderRecord("ORD-002", "小米蓝牙耳机", "XM-BT-002", 1299.0, "2025-11-15", "2026-11-15", "CUST-002"),
            OrderRecord("ORD-003", "小米智能手表", "XM-SW-003", 2499.0, "2025-10-01", "2026-10-01", "CUST-003"),
            OrderRecord("ORD-004", "小米充电宝", "XM-PB-004", 199.0, "2025-09-20", "2026-09-20", "CUST-004"),
            OrderRecord("ORD-005", "小米机械键盘", "XM-KB-005", 599.0, "2026-01-10", "2027-01-10", "CUST-005"),
        ]
        for o in orders:
            self._orders[o.order_id] = o

        refunds = [
            RefundRecord("REF-001", "ORD-001", 899.0, "rejected", "商品已使用超过7天", "2026-01-05"),
            RefundRecord("REF-002", "ORD-003", 2499.0, "pending", "", "2026-02-01"),
        ]
        for r in refunds:
            self._refunds[r.order_id] = r

        repairs = [
            RepairRecord("RPR-001", "ORD-002", "in_progress", "左耳单元故障", 0.0),
        ]
        for r in repairs:
            self._repairs[r.order_id] = r
