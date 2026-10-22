"""
safety.py — 全品类 Safety Gate（v2）
====================================
两层识别：
  1. 确定性高置信规则（本文件）
  2. 受限语义分类器（AIAdapter.classify_safety_semantic）

业务规则：一旦 Safety Gate 输出 SUSPECTED 或 CONFIRMED 风险，后端直接自动 Handoff。
不要求用户再次点击确认。
"""
import re
from typing import List, Tuple

from ..models.schemas import SafetyAssessment


class SafetyGate:
    """跨数码、服饰、家居、美妆、食品等全品类的确定性安全预检。"""

    # tuple: (hazard_type, confirmed_terms, suspected_terms)
    _RULES: List[Tuple[str, List[str], List[str]]] = [
        (
            "THERMAL_FIRE",
            ["冒烟", "起火", "着火", "烧起来", "烧焦", "焦糊", "熔化", "火花", "烧塑料味"],
            ["特别烫", "很烫", "烫手", "越来越烫", "异常发热", "发热严重", "温度很高", "有焦味", "焦糊味", "异味"],
        ),
        (
            "ELECTRICAL",
            ["漏电", "触电", "电到了", "被电", "电击", "麻手", "冒电火花", "电线露铜", "导线裸露"],
            ["有电流感", "有麻感", "噼啪声", "电气异味", "插座发热", "插头发热"],
        ),
        (
            "EXPLOSION_PRESSURE",
            ["爆炸", "爆了", "炸了", "爆裂", "鼓包", "膨胀", "电池漏液", "电池液流出", "炸开"],
            ["要爆了", "快爆了", "快要爆了", "疑似鼓包", "有点鼓", "外壳被顶起", "压力异常", "变形膨胀"],
        ),
        (
            "CHEMICAL_TOXIC",
            ["腐蚀", "化学灼伤", "灼烧", "刺激性液体", "化学品漏了", "清洁剂漏了", "不明液体泄漏"],
            ["刺激性气味", "呛人", "刺鼻", "闻着不对", "接触后刺痛", "接触后烧灼", "漏液"],
        ),
        (
            "FOOD_INGESTION",
            ["食品发霉", "食物发霉", "变质", "腐败", "玻璃碎片", "食品里有玻璃", "食品里有金属", "吃出异物", "疑似污染"],
            ["味道不对", "有馊味", "酸臭", "包装鼓起来", "食品异味", "吃了不舒服", "吃完不舒服"],
        ),
        (
            "ALLERGIC_IRRITATION",
            ["红肿", "起疹子", "皮疹", "肿起来", "严重刺痛", "明显灼烧", "过敏了"],
            ["刺痛", "烧灼感", "脸很烧", "皮肤发烫", "发痒", "疑似过敏", "刺激很强"],
        ),
        (
            "MECHANICAL_INJURY",
            ["断裂", "裂开", "倒了", "倾倒", "坍塌", "割伤", "夹伤", "尖锐金属外露", "玻璃外露"],
            ["要倒", "快倒", "一碰就倒", "晃得厉害", "承重松动", "腿松了", "支架松了", "尖锐", "割手", "夹手", "可能掉下来"],
        ),
        (
            "CHILD_CHOKING_ENTRAPMENT",
            ["误吞", "吞下去了", "窒息", "勒住脖子", "卡住头", "卡住手", "卡住脚"],
            ["小零件容易掉", "小零件脱落", "容易误吞", "勒颈风险", "缠绕", "可能卡住"],
        ),
        (
            "BIOLOGICAL_CONTAMINATION",
            ["霉菌", "长霉", "虫卵", "有虫子", "严重污染", "生物污染"],
            ["疑似发霉", "有霉点", "虫害", "包装内有虫", "卫生异常", "明显脏污"],
        ),
    ]

    _NEGATION_PREFIXES = ["没有", "没", "并没有", "并未", "不是", "无", "从未", "未出现", "没有出现"]
    _REFERENCE_PREFIXES = ["说明书说", "说明里说", "客服说", "页面写", "比如", "例如", "如果"]

    def check_rules(self, text: str) -> SafetyAssessment:
        normalized = self._normalize(text)
        if not normalized:
            return SafetyAssessment()

        # “有点热/发热”本身过于宽泛，但当主语明确是可能产生异常热风险的商品时，
        # 应按疑似安全风险处理，避免“充电宝有点热”漏判；“天气有点热”不会命中。
        if self._vague_thermal_product_risk(normalized):
            return SafetyAssessment(
                safety_signal=True, certainty="SUSPECTED", hazard_type="THERMAL_FIRE",
                evidence="商品出现异常温升/有点热", source="rule", confidence=0.90,
            )

        best = None
        for hazard_type, confirmed_terms, suspected_terms in self._RULES:
            for term in confirmed_terms:
                if self._term_is_asserted(normalized, term):
                    candidate = SafetyAssessment(
                        safety_signal=True,
                        certainty="CONFIRMED",
                        hazard_type=hazard_type,
                        evidence=term,
                        source="rule",
                        confidence=1.0,
                    )
                    return candidate
            for term in suspected_terms:
                if self._term_is_asserted(normalized, term):
                    candidate = SafetyAssessment(
                        safety_signal=True,
                        certainty="SUSPECTED",
                        hazard_type=hazard_type,
                        evidence=term,
                        source="rule",
                        confidence=0.92,
                    )
                    if best is None:
                        best = candidate
        return best or SafetyAssessment()

    @staticmethod
    def explicit_human_request(text: str) -> bool:
        """只捕获明确要求人工，不因叙述中普通出现“客服”而误触发。"""
        normalized = (text or "").lower().strip()
        phrases = [
            "转人工", "人工客服", "找人工", "找客服", "找个客服", "找个人工", "找真人",
            "真人客服", "转客服", "联系人工", "人工处理", "人工服务", "给我转人工",
            "帮我找客服", "找个人处理", "transfer to human", "speak to agent", "talk to human",
        ]
        if any(p in normalized for p in phrases):
            # 明显的叙述引用不算新的人工请求。
            narrative = ["昨天客服", "之前客服", "客服告诉我", "客服说", "客服页面", "人工客服说"]
            if any(p in normalized for p in narrative) and not any(
                p in normalized for p in ["转人工", "找人工", "找客服", "找真人", "联系人工", "给我转人工"]
            ):
                return False
            return True
        return False

    @staticmethod
    def authority_boundary(text: str) -> bool:
        normalized = (text or "").lower()
        phrases = [
            "退款复核", "重新审核退款", "重新审核", "责任认定", "赔付", "赔偿",
            "要求改判", "不认可判定", "refund review", "compensation", "liability",
        ]
        return any(p in normalized for p in phrases)

    @staticmethod
    def _vague_thermal_product_risk(text: str) -> bool:
        vague = any(term in text for term in ["有点热", "有些热", "发热", "变热", "温热异常"])
        if not vague:
            return False
        product_context = [
            "充电宝", "电池", "充电器", "插头", "插座", "电线", "电源", "手机", "电脑",
            "耳机", "键盘", "鼠标", "吹风机", "电热毯", "热水壶", "电器", "设备", "机器",
            "商品", "产品", "灯", "风扇", "路由器", "适配器"
        ]
        return any(term in text for term in product_context)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", "", (text or "").lower())

    def _term_is_asserted(self, text: str, term: str) -> bool:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx < 0:
                return False
            prefix = text[max(0, idx - 8):idx]
            if not any(neg in prefix for neg in self._NEGATION_PREFIXES):
                # “如果冒烟应该怎么办”更像咨询，不把它当成正在发生的事故；
                # 第二层语义分类器仍可结合完整语境判断。
                if not any(ref in prefix for ref in self._REFERENCE_PREFIXES):
                    return True
            start = idx + len(term)
