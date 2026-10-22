"""v2.3 售后 AI 判断回归测试。

这些测试直接走当前 FastAPI 应用或当前生产核心规则，不调用外部模型。
因此它们用于稳定验证：Safety / Handoff 的业务动作由后端执行，而不是
由 AI 文本声称执行。真实模型行为另在手工端到端回归中记录。
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from server.engine.safety import SafetyGate
from server.main import app
from server.models.schemas import CandidatePathStep, CaseState, HandoffTrigger


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_case(client: TestClient) -> dict:
    response = client.post(
        "/api/cases",
        json={
            "idempotency_key": "test-create-{}".format(uuid4()),
            "product_name": "自动化测试商品",
        },
    )
    assert response.status_code == 200
    return response.json()


def map_text(client: TestClient, case: dict, text: str) -> dict:
    response = client.post(
        "/api/cases/{}/map-text".format(case["case_id"]),
        json={
            "case_id": case["case_id"],
            "case_version": case["case_version"],
            "user_text": text,
            "idempotency_key": "test-map-{}".format(uuid4()),
        },
    )
    assert response.status_code == 200
    return response.json()


def handoff_packet(client: TestClient, case_id: str) -> dict:
    response = client.get("/api/cases/{}/handoff-packet".format(case_id))
    assert response.status_code == 200
    return response.json()["packet"]


def test_confirmed_safety_risk_creates_p0_handoff(client: TestClient):
    """V06：明确爆炸风险必须真实创建 P0 工单。"""
    case = create_case(client)
    result = map_text(client, case, "我的充电宝爆了")
    packet = handoff_packet(client, case["case_id"])

    assert result["state"] == CaseState.QUEUED.value
    assert result["handoff_trigger"] == HandoffTrigger.SAFETY_RISK.value
    assert packet["priority"] == "P0"
    assert packet["safety_hazard_type"] == "EXPLOSION_PRESSURE"
    assert packet["key_quotes"] == ["我的充电宝爆了"]


def test_suspected_safety_risk_creates_p0_handoff(client: TestClient):
    """V09：疑似发热风险同样必须进入 P0 队列。"""
    case = create_case(client)
    result = map_text(client, case, "我的充电宝有点热")
    packet = handoff_packet(client, case["case_id"])

    assert result["state"] == CaseState.QUEUED.value
    assert result["handoff_trigger"] == HandoffTrigger.SAFETY_RISK.value
    assert packet["priority"] == "P0"
    assert packet["safety_certainty"] == "SUSPECTED"
    assert packet["safety_hazard_type"] == "THERMAL_FIRE"


def test_negated_safety_phrase_does_not_trigger_safety_gate():
    """V13：否定语境不能仅因“冒烟”二字触发 P0。"""
    assessment = SafetyGate().check_rules("没有冒烟，只是开不了机")

    assert assessment.safety_signal is False
    assert assessment.certainty == "NONE"


def test_explicit_human_request_creates_real_queue_case(client: TestClient):
    """V14：明确找人工必须创建队列 Case，而非只返回提示文字。"""
    case = create_case(client)
    result = map_text(client, case, "找真人")

    queue = client.get("/api/queue")
    assert queue.status_code == 200
    assert result["state"] == CaseState.QUEUED.value
    assert result["handoff_trigger"] == HandoffTrigger.USER_REQUEST.value
    assert case["case_id"] in [item["case_id"] for item in queue.json()]


def test_authority_boundary_creates_handoff(client: TestClient):
    """退款执行诉求属于权限边界，必须由人工接管。"""
    case = create_case(client)
    result = map_text(client, case, "你给我仅退款吧")

    assert result["state"] == CaseState.QUEUED.value
    assert result["handoff_trigger"] == HandoffTrigger.AUTHORITY_BOUNDARY.value


def test_symptom_does_not_infer_refund_intent(client: TestClient):
    """V16：仅描述鼠标故障时，核心服务不得创建退款意图。"""
    created = create_case(client)
    case = app.state.case_mgr.get_case(created["case_id"])

    judgment = app.state.service._hard_gate(case, "鼠标左键坏了，我只是想先看看怎么处理")

    assert judgment is None
    assert case.user_intent is None
    assert case.state == CaseState.IN_WORKFLOW


def test_workflow_accepts_only_existing_candidate_path(client: TestClient):
    """V03 的安全边界：AI 候选路径只能引用人工定义的连续节点。"""
    engine = app.state.case_mgr.engine
    valid = [
        CandidatePathStep(node_id="N0", option_id="ISSUE_PRODUCT", label="商品本身问题"),
        CandidatePathStep(node_id="PRODUCT_CATEGORY", option_id="PRODUCT_APPAREL", label="服饰 / 鞋包"),
        CandidatePathStep(node_id="PRODUCT_APPAREL_TYPE", option_id="PA_SIZE", label="尺码 / 版型问题"),
    ]
    forged = [
        CandidatePathStep(node_id="N0", option_id="ISSUE_PRODUCT", label="商品本身问题"),
        CandidatePathStep(node_id="PRODUCT_CATEGORY", option_id="FAKE_OPTION", label="虚构分类"),
    ]

    assert engine.validate_candidate_path(valid) is True
    assert engine.validate_candidate_path(forged) is False
