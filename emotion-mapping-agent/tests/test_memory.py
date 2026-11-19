"""감정 매핑 Agent 메모리 평가 (LLM 제외 · 오프라인 모드) — 책 3.1.1 3단계 + 규칙집 PR."""

from __future__ import annotations

import os

os.environ["LLM_MODE"] = "offline"
os.environ["MEMORY_DB_PATH"] = ":memory:"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from pipeline import EmotionPipeline  # noqa: E402


@pytest.fixture()
def client():
    main.pipeline = EmotionPipeline(memory_db_path=":memory:", llm_mode="offline")
    with TestClient(main.app) as c:
        yield c


def analyze(client: TestClient, text: str, user_id: str = "U1") -> dict:
    r = client.post("/api/analyze", json={"text": text, "user_id": user_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_offline_mode_runs_without_llm(client: TestClient) -> None:
    data = analyze(client, "시험에 합격해서 너무 기쁘다!")
    assert data["mode"] == "offline"
    assert data["final_emotion"] == "기쁨"
    assert data["emotion_context"]["label"] == "기쁨"
    assert 0 < data["emotion_context"]["intensity"] <= 1


# ---------------------------------------------------------------- 1단계
def test_level1_case_recall(client: TestClient) -> None:
    first = analyze(client, "친구가 약속을 또 어겨서 정말 화가 난다")
    second = analyze(client, "친구가 약속을 어겨서 화가 난다")
    similar = second["memory"]["working_memory"]["similar_cases"]
    assert similar and similar[0]["case_id"] == first["case_id"]


# ---------------------------------------------------------------- 2단계
def test_level2_correction_changes_later_analysis(client: TestClient) -> None:
    text = "기대했는데 결과가 이래서 실망이다"
    first = analyze(client, text)
    assert first["final_emotion"] == "슬픔"
    r = client.post("/api/memory/correction", json={"case_id": first["case_id"], "correct_emotion": "분노", "note": "항의 맥락"})
    assert r.status_code == 200
    again = analyze(client, "기대했는데 결과가 이래서 실망이다 진짜")
    assert again["final_emotion"] == "분노"
    assert any("메모리 근거" in rule for rule in again["mapping"]["applied_memory_rules"])


def test_level2_one_shared_word_does_not_reuse_correction(client: TestClient) -> None:
    first = analyze(client, "이번 발표 결과에 실망했다")
    client.post("/api/memory/correction", json={"case_id": first["case_id"], "correct_emotion": "분노"})
    unrelated = analyze(client, "발표가 너무 걱정돼서 잠이 안 와")
    assert unrelated["final_emotion"] == "공포"


def test_level2_memory_is_per_user(client: TestClient) -> None:
    first = analyze(client, "기대했는데 결과가 이래서 실망이다", user_id="A")
    client.post("/api/memory/correction", json={"case_id": first["case_id"], "correct_emotion": "분노"})
    other = analyze(client, "기대했는데 결과가 이래서 실망이다", user_id="B")
    assert other["final_emotion"] == "슬픔"


# ---------------------------------------------------------------- 3단계
def test_level3_consolidation_builds_procedure_and_flags_rulebook_conflict(client: TestClient) -> None:
    for t in ("실망스럽다 정말", "이번 발표 결과에 실망했다", "또 실망이야"):
        case = analyze(client, t)
        client.post("/api/memory/correction", json={"case_id": case["case_id"], "correct_emotion": "분노"})
    result = client.post("/api/memory/U1/consolidate").json()
    change = next(c for c in result["procedure_changes"] if c["key"] == "procedure.kote.안타까움/실망")
    assert change["conflicts_reference"] is True
    overview = client.get("/api/memory/U1").json()
    assert "rulebook_conflict" in {a["rule"] for a in overview["alerts"]}
    # 처음 보는 문장이라도 절차 카드로 '실망' 계열은 분노로 매핑
    unseen = analyze(client, "그 사람한테 실망했어")
    assert unseen["final_emotion"] == "분노"


def test_level3_negative_persistence_alert(client: TestClient) -> None:
    for t in ("너무 슬프다", "무서워서 잠이 안 온다", "짜증나 죽겠다", "우울하다", "화가 난다"):
        data = analyze(client, t)
    assert "negative_emotion_persistence" in {a["rule"] for a in data["memory"]["alerts"]}


# ---------------------------------------------------------------- 규칙집 PR
def test_rulebook_pr_review_approve_rollback(client: TestClient) -> None:
    v1 = client.get("/api/mapping-memory").json()
    bad = client.post("/api/rulebook/propose", json={"content": "■ 기쁨만 남김 가중치 가중치", "note": "bad"}).json()
    assert bad["status"] == "rejected" and bad["review"]["issues"]

    new_content = v1["content"] + "\n\n■ 추가 지침\n- '어이없다'가 항의와 함께 쓰이면 분노를 우선 검토한다."
    good = client.post("/api/rulebook/propose", json={"content": new_content, "note": "어이없음 지침"}).json()
    assert good["status"] == "reviewed"
    assert client.get("/api/mapping-memory").json()["version"] == v1["version"]  # 승인 전에는 미반영
    client.post(f"/api/rulebook/{good['version']}/approve")
    assert client.get("/api/mapping-memory").json()["version"] == good["version"]
    rb = client.post(f"/api/rulebook/{v1['version']}/rollback").json()
    restored = client.get("/api/mapping-memory").json()
    assert restored["version"] == rb["active_version"] and restored["content"] == v1["content"]


def test_pii_masked(client: TestClient) -> None:
    analyze(client, "010-1234-5678로 연락했는데 답이 없어서 짜증난다")
    cases = client.get("/api/memory/U1").json()["cases"]
    assert "010-1234-5678" not in cases[0]["text"] and "[PHONE]" in cases[0]["text"]
