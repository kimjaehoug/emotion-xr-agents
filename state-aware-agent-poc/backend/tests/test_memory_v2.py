"""Memory v2 평가 — 책 3.1.1의 3단계 프레임워크.

1단계 기본 회상 / 2단계 다중 세션 검색·갱신 / 3단계 능동적 서비스
+ ADD-only 이력 보존, 압축, 비식별화.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.memory.core import importance_score, resolve_current, sanitize_text
from tests.test_state_agent import _add_normal_samples, _create_user, client  # noqa: F401


def _setup(client: TestClient, user_id: str) -> None:
    _create_user(client, user_id)
    _add_normal_samples(client, user_id, 3)
    assert client.post(f"/api/v1/users/{user_id}/baseline/build").status_code == 200


def _analyze(client: TestClient, user_id: str, session_id: str, *, cl: float, att: float, fat: float,
             visual: float = 0.3, content_type: str = "education", content_id: str = "C1",
             emotion: dict | None = None) -> dict:
    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": "2026-10-27T10:00:00+09:00",
        "cognitive_metrics": {"cognitive_load": cl, "attention": att, "fatigue": fat},
        "context": {"content_id": content_id, "content_type": content_type, "visual_complexity": visual},
        "data_quality": {"cognitive_confidence": 0.9, "completeness": 0.95},
    }
    if emotion:
        payload["emotion_context"] = emotion
    resp = client.post("/api/v1/state/analyze", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _current(client: TestClient, user_id: str) -> dict:
    data = client.get(f"/api/v1/users/{user_id}/memory").json()
    return {c["key"]: c for c in data["current_cards"]}


# ---------------------------------------------------------------- 1단계
def test_level1_basic_recall_trait_card(client: TestClient) -> None:
    _setup(client, "M1")
    for i in range(3):
        _analyze(client, "M1", f"S{i}", cl=0.47, att=0.71, fat=0.75)
    cards = _current(client, "M1")
    card = cards["trait.fatigue.deviation"]
    assert card["value"] == {"direction": "above_baseline"}
    assert set(card["evidence"]) == {"S0", "S1", "S2"}
    assert "피로도" in card["backstory"]


# ---------------------------------------------------------------- 2단계
def test_level2_multi_session_update_keeps_history(client: TestClient) -> None:
    _setup(client, "M2")
    for i in range(3):
        _analyze(client, "M2", f"A{i}", cl=0.47, att=0.71, fat=0.75)
    first_id = _current(client, "M2")["trait.fatigue.deviation"]["card_id"]
    # 이후 세션에서 피로가 정상으로 돌아오면 카드는 '삭제'가 아니라 유효기간이 닫힌다.
    for i in range(3):
        _analyze(client, "M2", f"B{i}", cl=0.47, att=0.71, fat=0.33)
    overview = client.get("/api/v1/users/M2/memory").json()
    assert "trait.fatigue.deviation" not in {c["key"] for c in overview["current_cards"]}
    history_ids = {c["card_id"] for c in overview["card_history"]}
    assert first_id in history_ids
    events = client.get("/api/v1/users/M2/memory/events?limit=500").json()
    assert any(e["event_type"] == "card_expired" for e in events)


def test_level2_similar_episode_retrieval(client: TestClient) -> None:
    _setup(client, "M3")
    _analyze(client, "M3", "HIGH1", cl=0.85, att=0.71, fat=0.33)
    _analyze(client, "M3", "NORM1", cl=0.46, att=0.71, fat=0.33)
    report = _analyze(client, "M3", "HIGH2", cl=0.86, att=0.71, fat=0.33)
    similar = report["memory_context"]["working_memory"]["similar_episodes"]
    assert similar[0]["session_id"] == "HIGH1"


# ---------------------------------------------------------------- 3단계
def test_level3_proactive_known_trigger(client: TestClient) -> None:
    """과거 세션에서 학습한 '고시각복잡도 → 부하' 조건을 정상 지표 세션에서도 선제 경고."""
    _setup(client, "M4")
    _analyze(client, "M4", "V1", cl=0.85, att=0.71, fat=0.33, visual=0.8)
    _analyze(client, "M4", "V2", cl=0.86, att=0.71, fat=0.33, visual=0.75)
    _analyze(client, "M4", "L1", cl=0.46, att=0.71, fat=0.33, visual=0.2)
    assert "trigger.visual_complexity" in _current(client, "M4")
    report = _analyze(client, "M4", "V3", cl=0.46, att=0.71, fat=0.33, visual=0.8)
    assert report["state_level"] == "NORMAL"
    rules = {a["rule"] for a in report["memory_context"]["proactive_alerts"]}
    assert "known_trigger_active" in rules


def test_level3_emotion_metric_mismatch(client: TestClient) -> None:
    _setup(client, "M5")
    report = _analyze(client, "M5", "E1", cl=0.46, att=0.71, fat=0.33,
                      emotion={"label": "슬픔", "intensity": 0.8, "confidence": 0.9})
    assert report["emotion_context"]["label"] == "슬픔"
    rules = {a["rule"] for a in report["memory_context"]["proactive_alerts"]}
    assert "emotion_metric_mismatch" in rules


# ---------------------------------------------------------------- 관리
def test_consolidation_archives_without_deleting(client: TestClient) -> None:
    _setup(client, "M6")
    for i in range(4):
        _analyze(client, "M6", f"N{i}", cl=0.46, att=0.71, fat=0.33)
    result = client.post("/api/v1/users/M6/memory/consolidate?min_age_days=0&threshold=0.9").json()
    assert result["archived_sessions"]
    assert result["cluster_cards"][0]["episodes"] == len(result["archived_sessions"])
    # 원본 일화는 남아 있다
    assert len(client.get("/api/v1/users/M6/episodes").json()) == 4


def test_pii_is_sanitized_in_raw_events(client: TestClient) -> None:
    _setup(client, "M7")
    _analyze(client, "M7", "P1", cl=0.46, att=0.71, fat=0.33, content_id="call 010-1234-5678")
    events = client.get("/api/v1/users/M7/memory/events").json()
    payload = next(e for e in events if e["event_type"] == "state_analyzed")["payload"]
    assert "010-1234-5678" not in str(payload)
    assert "[PHONE]" in str(payload)


def test_core_helpers() -> None:
    assert sanitize_text("메일 a@b.com")[0] == "메일 [EMAIL]"
    hot = importance_score(created_at=None, access_count=5, emotional_intensity=1.0, duplicate_count=0)
    cold = importance_score(created_at=None, access_count=0, emotional_intensity=0.0, duplicate_count=3)
    assert hot["score"] > cold["score"]
    cards = [
        {"card_id": "a", "key": "k", "valid_from": "2026-01-01T00:00:00+00:00", "valid_to": "2026-02-01T00:00:00+00:00"},
        {"card_id": "b", "key": "k", "valid_from": "2026-02-01T00:00:00+00:00", "valid_to": None},
    ]
    assert resolve_current(cards)["k"]["card_id"] == "b"
