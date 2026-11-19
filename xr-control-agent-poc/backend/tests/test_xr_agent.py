"""XR Control AI Agent PoC 통합 테스트.

로컬 LLM 호출은 `respx`로 `http://llm.test/v1/chat/completions`를 가로채
실제 네트워크를 사용하지 않는다(OLLAMA_ENABLED 스타일: 실제 LLM 비활성화).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 전용 로컬 LLM 엔드포인트 — 실제 Ollama/llama.cpp에 접근하지 않는다.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LOCAL_LLM_BASE_URL"] = "http://llm.test/v1"
os.environ["LOCAL_LLM_MAX_RETRIES"] = "0"
os.environ["LLM_REPAIR_MAX_ATTEMPTS"] = "1"

from app.core.config import get_settings  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()

LLM_CHAT_URL = "http://llm.test/v1/chat/completions"


@pytest.fixture()
def client(tmp_path: Path):
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _seed(client: TestClient) -> None:
    resp = client.post("/api/v1/mock/seed")
    assert resp.status_code == 200


def _state_report(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "state_report_id": f"SR-{uuid4().hex[:10].upper()}",
        "user_id": "U100",
        "session_id": "S100",
        "timestamp": "2026-07-21T10:00:00+09:00",
        "state_level": "NORMAL",
        "analysis_confidence": 0.9,
        "requires_response": False,
        "additional_observation_required": False,
        "context_summary": {"content_id": "C001", "content_type": "education"},
    }
    base.update(overrides)
    return base


def _openai_chat_response(content: Dict[str, Any] | str) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": text}}],
        },
    )


VALID_WATCH_PLAN = {
    "goal": "REDUCE_COGNITIVE_BURDEN",
    "route": "XR_OPTIMIZATION",
    "actions": [
        {
            "action_type": "UPDATE_XR_PARAMETER",
            "xr_parameter": "visual_complexity",
            "delta": -0.15,
            "requires_confirmation": False,
            "rationale": "주의 상태로 시각 복잡도를 낮춥니다.",
            "confidence": 0.8,
        }
    ],
    "confidence": 0.8,
    "narrative": "테스트 내레이션",
}

INVALID_ROUTE_PLAN = {
    "goal": "SUPPORT_ATTENTION_RECOVERY",
    "route": "BREAK_SUGGESTION",  # policy_watch에서 허용하지 않는 라우트
    "actions": [
        {
            "action_type": "SUGGEST_BREAK",
            "requires_confirmation": True,
            "rationale": "정책상 허용되지 않는 라우트 테스트",
            "confidence": 0.7,
        }
    ],
    "confidence": 0.7,
    "narrative": None,
}


def test_qwen_success_and_planner_source_saved(client: TestClient) -> None:
    _seed(client)
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(VALID_WATCH_PLAN))
        resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(state_level="WATCH", analysis_confidence=0.75),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["planner_source"] == "qwen3.5_9b"
    assert data["route"] == "XR_OPTIMIZATION"
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_type"] == "UPDATE_XR_PARAMETER"

    # planner_source가 xr_episodic_memories에도 저장되었는지 확인
    episodes = client.get("/api/v1/xr-agent/users/U100/xr-episodes")
    assert episodes.status_code == 200
    ep_list = episodes.json()
    assert len(ep_list) >= 1
    assert ep_list[0]["planner_source"] == "qwen3.5_9b"


def test_llm_connection_fail_falls_back(client: TestClient) -> None:
    _seed(client)
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(side_effect=httpx.ConnectError("연결 실패"))
        resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(state_level="WATCH", analysis_confidence=0.75),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["planner_source"] == "rule_based_fallback"
    assert any("연결 실패" in w for w in data["warnings"])


def test_invalid_policy_route_is_blocked_and_falls_back(client: TestClient) -> None:
    _seed(client)
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(INVALID_ROUTE_PLAN))
        resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(state_level="WATCH", analysis_confidence=0.75),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["planner_source"] == "rule_based_fallback"
    assert any("검증 실패" in w or "허용되지 않습니다" in w for w in data["warnings"])


def test_unknown_state_returns_observation_without_llm(client: TestClient) -> None:
    # respx.mock을 활성화하지 않아, 실제 LLM 호출이 발생하면 네트워크 오류로 테스트가 실패한다.
    resp = client.post(
        "/api/v1/xr-agent/plan",
        json=_state_report(state_level="UNKNOWN", analysis_confidence=0.2),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "OBSERVATION"
    assert data["goal"] == "CONTINUE_OBSERVATION"
    assert data["planner_source"] == "rule_based_fallback"


def test_low_confidence_returns_observation_without_llm(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/xr-agent/plan",
        json=_state_report(state_level="WATCH", analysis_confidence=0.30),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "OBSERVATION"
    assert data["planner_source"] == "rule_based_fallback"


def test_normal_no_response_keeps_state_without_llm(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/xr-agent/plan",
        json=_state_report(state_level="NORMAL", analysis_confidence=0.9, requires_response=False),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "NO_ACTION"
    assert data["actions"][0]["action_type"] == "KEEP_CURRENT_STATE"


def test_xr_action_applies_to_mock_state(client: TestClient) -> None:
    _seed(client)
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(VALID_WATCH_PLAN))
        plan_resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(
                state_level="WATCH", analysis_confidence=0.75, session_id="S-XR-1"
            ),
        )
    assert plan_resp.status_code == 200
    plan = plan_resp.json()
    action = plan["actions"][0]
    # delta(-0.15)는 max_parameter_delta(0.20) 이내이므로 그대로 적용되고 final_value=0.5-0.15=0.35
    assert action["delta"] == pytest.approx(-0.15)
    assert action["final_value"] == pytest.approx(0.35)

    exec_resp = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]})
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert len(exec_data["executions"]) == 1
    execution = exec_data["executions"][0]
    assert execution["status"] == "SUCCESS"
    assert execution["result"]["applied_parameter"] == "visual_complexity"
    assert execution["result"]["xr_state"]["visual_complexity"] == pytest.approx(0.35)

    # 재실행 시 이미 실행된 계획으로 처리되어야 한다.
    exec_resp_2 = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]})
    assert exec_resp_2.status_code == 200
    assert exec_resp_2.json()["already_executed"] is True


def test_duplicate_state_report_id_returns_previous_result(client: TestClient) -> None:
    report = _state_report(state_level="NORMAL", analysis_confidence=0.9)
    first = client.post("/api/v1/xr-agent/plan", json=report)
    assert first.status_code == 200
    first_plan_id = first.json()["plan_id"]

    second = client.post("/api/v1/xr-agent/plan", json=report)
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["plan_id"] == first_plan_id
    assert second_data["idempotent_replay"] is True


def test_delta_clamped_to_max_parameter_delta(client: TestClient) -> None:
    _seed(client)
    oversized_plan = {
        "goal": "REDUCE_COGNITIVE_BURDEN",
        "route": "XR_OPTIMIZATION",
        "actions": [
            {
                "action_type": "UPDATE_XR_PARAMETER",
                "xr_parameter": "visual_complexity",
                "delta": -0.9,
                "requires_confirmation": False,
                "rationale": "과도한 delta 요청",
                "confidence": 0.8,
            }
        ],
        "confidence": 0.8,
        "narrative": None,
    }
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(oversized_plan))
        resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(state_level="WATCH", analysis_confidence=0.75),
        )
    assert resp.status_code == 200
    data = resp.json()
    action = data["actions"][0]
    assert action["delta"] == pytest.approx(-0.20)
    assert action["final_value"] == pytest.approx(0.30)


def test_mock_seed_creates_demo_user(client: TestClient) -> None:
    resp = client.post("/api/v1/mock/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert "U001" in data["users_created"] or client.get("/api/v1/users/U001").status_code == 200


def test_feedback_updates_execution_and_profile(client: TestClient) -> None:
    _seed(client)
    with respx.mock:
        respx.post(LLM_CHAT_URL).mock(return_value=_openai_chat_response(VALID_WATCH_PLAN))
        plan_resp = client.post(
            "/api/v1/xr-agent/plan",
            json=_state_report(state_level="WATCH", analysis_confidence=0.75, session_id="S-FB-1"),
        )
    plan = plan_resp.json()
    exec_resp = client.post("/api/v1/xr-agent/execute", json={"plan_id": plan["plan_id"]})
    execution_id = exec_resp.json()["executions"][0]["execution_id"]

    fb_resp = client.post(
        "/api/v1/xr-agent/feedback",
        json={"execution_id": execution_id, "effect": "negative"},
    )
    assert fb_resp.status_code == 200
    fb_data = fb_resp.json()
    assert fb_data["profile_updated"] is True

    user = client.get("/api/v1/users/U100").json()
    assert user["profile"]["sensitivities"].get("visual_complexity", 0) > 0
