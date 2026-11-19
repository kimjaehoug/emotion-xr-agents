"""XR Memory v2 평가 — 책 3.1.1 3단계 프레임워크 (절차 메모리 중심)."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from tests.test_xr_agent import (  # noqa: F401
    LLM_CHAT_URL,
    VALID_WATCH_PLAN,
    _openai_chat_response,
    _seed,
    _state_report,
    client,
)


def _plan(client: TestClient, *, llm_ok: bool = False, **report) -> dict:
    with respx.mock:
        if llm_ok:
            respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(VALID_WATCH_PLAN))
        else:
            respx.post(LLM_CHAT_URL).mock(side_effect=httpx.ConnectError("LLM 제외"))
        resp = client.post("/api/v1/xr-agent/plan", json=_state_report(**report))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _run_and_feedback(client: TestClient, session_id: str, effect: str) -> dict:
    plan = _plan(client, state_level="WATCH", analysis_confidence=0.75, session_id=session_id)
    executions = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]}).json()["executions"]
    eid = executions[0]["execution_id"]
    assert client.post("/api/v1/xr-agent/feedback", json={"execution_id": eid, "effect": effect}).status_code == 200
    return plan


def _cards(client: TestClient, user_id: str = "U100") -> dict:
    data = client.get(f"/api/v1/xr-agent/users/{user_id}/memory").json()
    return {c["key"]: c for c in data["current_cards"]}


# ---------------------------------------------------------------- 1단계
def test_level1_feedback_becomes_procedure_card(client: TestClient) -> None:
    _seed(client)
    _run_and_feedback(client, "S-P1", "positive")
    card = _cards(client)["procedure.WATCH.UPDATE_XR_PARAMETER:visual_complexity"]
    assert card["memory_type"] == "procedural"
    assert card["value"]["positive"] == 1 and card["value"]["effectiveness"] == 1.0


# ---------------------------------------------------------------- 2단계
def test_level2_repeated_negative_learns_avoidance_and_changes_plan(client: TestClient) -> None:
    _seed(client)
    _run_and_feedback(client, "S-N1", "negative")
    _run_and_feedback(client, "S-N2", "negative")
    assert "preference.avoid.UPDATE_XR_PARAMETER:visual_complexity" in _cards(client)

    # Fallback(LLM 제외)은 회피 학습된 visual_complexity 대신 다른 파라미터를 고른다.
    plan = _plan(client, state_level="WATCH", analysis_confidence=0.75, session_id="S-N3")
    assert plan["actions"][0]["xr_parameter"] != "visual_complexity"
    assert plan["memory_context"]["avoid_signatures"] == ["UPDATE_XR_PARAMETER:visual_complexity"]

    # LLM이 같은 행동을 다시 제안해도 가드가 자동 실행을 막고 확인으로 전환한다.
    plan = _plan(client, llm_ok=True, state_level="WATCH", analysis_confidence=0.75, session_id="S-N4")
    assert plan["actions"][0]["requires_confirmation"] is True
    assert any("부정 반응 이력" in w for w in plan["warnings"])


def test_level2_history_preserved_on_update(client: TestClient) -> None:
    _seed(client)
    _run_and_feedback(client, "S-H1", "negative")
    _run_and_feedback(client, "S-H2", "positive")
    data = client.get("/api/v1/xr-agent/users/U100/memory").json()
    history = [c for c in data["card_history"] if c["key"].startswith("procedure.WATCH")]
    assert history and history[0]["superseded_by"]
    current = {c["key"]: c for c in data["current_cards"]}
    assert current["procedure.WATCH.UPDATE_XR_PARAMETER:visual_complexity"]["value"]["n"] == 2


def test_level2_effective_procedure_is_preferred(client: TestClient) -> None:
    _seed(client)
    # audio_stimulation 조정이 효과적이었다는 피드백을 LLM 계획으로 축적
    audio_plan = {**VALID_WATCH_PLAN, "actions": [{**VALID_WATCH_PLAN["actions"][0], "xr_parameter": "audio_stimulation"}]}
    for sid in ("S-A1", "S-A2"):
        with respx.mock:
            respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(audio_plan))
            plan = client.post("/api/v1/xr-agent/plan", json=_state_report(state_level="WATCH", analysis_confidence=0.75, session_id=sid)).json()
        eid = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]}).json()["executions"][0]["execution_id"]
        client.post("/api/v1/xr-agent/feedback", json={"execution_id": eid, "effect": "positive"})
    plan = _plan(client, state_level="WATCH", analysis_confidence=0.75, session_id="S-A3")
    assert plan["actions"][0]["xr_parameter"] == "audio_stimulation"
    assert "조절 효과 이력" in plan["actions"][0]["rationale"]


# ---------------------------------------------------------------- 3단계
def test_level3_upstream_high_alert_requires_confirmation(client: TestClient) -> None:
    _seed(client)
    upstream = {"proactive_alerts": [{"rule": "persistent_deviation", "severity": "high", "message": "x", "evidence": []}]}
    plan = _plan(client, llm_ok=True, state_level="WATCH", analysis_confidence=0.75,
                 session_id="S-U1", memory_context=upstream)
    assert plan["actions"][0]["requires_confirmation"] is True
    assert "upstream_high_alert" in {a["rule"] for a in plan["memory_context"]["proactive_alerts"]}


def test_level3_repeated_action_required_escalates(client: TestClient) -> None:
    _seed(client)
    for i in range(3):
        plan = _plan(client, state_level="ACTION_REQUIRED", analysis_confidence=0.9,
                     requires_response=True, session_id=f"S-E{i}")
    assert "repeated_action_required" in {a["rule"] for a in plan["memory_context"]["proactive_alerts"]}


def test_rejected_confirmation_counts_as_negative(client: TestClient) -> None:
    _seed(client)
    plan = _plan(client, state_level="ACTION_REQUIRED", analysis_confidence=0.9, requires_response=True, session_id="S-R1")
    confirmations = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]}).json()["confirmations"]
    cid = confirmations[0]["confirmation_id"]
    assert client.post(f"/api/v1/xr-agent/confirmations/{cid}", json={"decision": "REJECTED"}).status_code == 200
    card = _cards(client)["procedure.ACTION_REQUIRED.SUGGEST_BREAK:"]
    assert card["value"]["rejected"] == 1
