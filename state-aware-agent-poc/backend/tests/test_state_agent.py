"""통합 테스트 — 상태 인지 Agent PoC."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 DB를 메모리로 강제
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["OLLAMA_ENABLED"] = "false"
os.environ["USE_GROUP_DEFAULT_BASELINE"] = "false"
os.environ["MIN_BASELINE_SAMPLES"] = "3"

from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import create_app
from app.schemas import UserProfile

get_settings.cache_clear()


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


def _create_user(client: TestClient, user_id: str = "U100") -> None:
    resp = client.post(
        "/api/v1/users",
        json={
            "user_id": user_id,
            "profile": UserProfile().model_dump(),
        },
    )
    assert resp.status_code == 201


def _add_normal_samples(client: TestClient, user_id: str, n: int = 3) -> None:
    samples = [
        (0.45, 0.72, 0.32),
        (0.48, 0.70, 0.35),
        (0.42, 0.74, 0.30),
        (0.50, 0.68, 0.38),
        (0.46, 0.71, 0.33),
    ]
    for i in range(n):
        cl, att, fat = samples[i]
        r = client.post(
            f"/api/v1/users/{user_id}/baseline-observations",
            json={
                "session_id": f"OBS-{i+1}",
                "cognitive_load": cl,
                "attention": att,
                "fatigue": fat,
                "confidence": 0.9,
                "completeness": 0.95,
                "is_normal_confirmed": True,
            },
        )
        assert r.status_code == 201


def _analyze(
    client: TestClient,
    *,
    user_id: str,
    session_id: str,
    cl: float,
    att: float,
    fat: float,
    confidence: float = 0.9,
    completeness: float = 0.95,
) -> dict:
    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": "2026-07-21T10:00:00+09:00",
        "cognitive_metrics": {
            "cognitive_load": cl,
            "attention": att,
            "fatigue": fat,
        },
        "context": {
            "content_id": "C102",
            "content_type": "education",
            "difficulty": 0.8,
            "visual_complexity": 0.75,
            "audio_stimulation": 0.6,
            "elapsed_time_min": 25,
        },
        "data_quality": {
            "cognitive_confidence": confidence,
            "completeness": completeness,
        },
    }
    resp = client.post("/api/v1/state/analyze", json=payload)
    return resp


def test_no_baseline_returns_unknown(client: TestClient) -> None:
    _create_user(client, "U_NO_BL")
    resp = _analyze(client, user_id="U_NO_BL", session_id="S1", cl=0.5, att=0.7, fat=0.3)
    assert resp.status_code == 200
    data = resp.json()
    assert data["state_level"] == "UNKNOWN"
    assert data["baseline"]["source"] == "none"


def test_normal_range_input(client: TestClient) -> None:
    _create_user(client, "U_NORM")
    _add_normal_samples(client, "U_NORM", 3)
    br = client.post("/api/v1/users/U_NORM/baseline/build")
    assert br.status_code == 200
    resp = _analyze(client, user_id="U_NORM", session_id="S_N1", cl=0.46, att=0.71, fat=0.33)
    assert resp.status_code == 200
    assert resp.json()["state_level"] == "NORMAL"


def test_single_metric_watch(client: TestClient) -> None:
    _create_user(client, "U_WATCH")
    _add_normal_samples(client, "U_WATCH", 3)
    assert client.post("/api/v1/users/U_WATCH/baseline/build").status_code == 200
    # cognitive_load만 크게 이탈, 나머지 정상 근처
    resp = _analyze(client, user_id="U_WATCH", session_id="S_W1", cl=0.85, att=0.71, fat=0.33)
    assert resp.status_code == 200
    assert resp.json()["state_level"] == "WATCH"


def test_multi_metric_persistent_action_required(client: TestClient) -> None:
    _create_user(client, "U_ACT")
    _add_normal_samples(client, "U_ACT", 3)
    assert client.post("/api/v1/users/U_ACT/baseline/build").status_code == 200

    # 연속 이탈로 persistence 쌓기
    for i, (cl, att, fat) in enumerate(
        [
            (0.85, 0.40, 0.80),
            (0.88, 0.38, 0.82),
            (0.90, 0.35, 0.85),
        ],
        start=1,
    ):
        resp = _analyze(
            client,
            user_id="U_ACT",
            session_id=f"S_A{i}",
            cl=cl,
            att=att,
            fat=fat,
        )
        assert resp.status_code == 200

    data = resp.json()
    assert data["state_level"] == "ACTION_REQUIRED"
    assert data["requires_response"] is True


def test_low_confidence_unknown_or_warning(client: TestClient) -> None:
    _create_user(client, "U_LOW")
    _add_normal_samples(client, "U_LOW", 3)
    assert client.post("/api/v1/users/U_LOW/baseline/build").status_code == 200
    resp = _analyze(
        client,
        user_id="U_LOW",
        session_id="S_L1",
        cl=0.46,
        att=0.71,
        fat=0.33,
        confidence=0.3,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state_level"] == "UNKNOWN"
    assert len(data["warnings"]) > 0


def test_invalid_range_returns_422(client: TestClient) -> None:
    _create_user(client, "U_422")
    payload = {
        "user_id": "U_422",
        "session_id": "S1",
        "timestamp": "2026-07-21T10:00:00+09:00",
        "cognitive_metrics": {
            "cognitive_load": 1.5,
            "attention": 0.5,
            "fatigue": 0.5,
        },
        "data_quality": {"cognitive_confidence": 0.9, "completeness": 0.9},
    }
    resp = client.post("/api/v1/state/analyze", json=payload)
    assert resp.status_code == 422


def test_baseline_min_samples(client: TestClient) -> None:
    _create_user(client, "U_MIN")
    _add_normal_samples(client, "U_MIN", 2)
    resp = client.post("/api/v1/users/U_MIN/baseline/build")
    assert resp.status_code == 400
    assert "최소" in resp.json()["detail"]


def test_abnormal_session_excluded_from_baseline(client: TestClient) -> None:
    _create_user(client, "U_EXCL")
    _add_normal_samples(client, "U_EXCL", 3)
    # 비정상 세션 추가
    r = client.post(
        "/api/v1/users/U_EXCL/baseline-observations",
        json={
            "session_id": "OBS-BAD",
            "cognitive_load": 0.95,
            "attention": 0.2,
            "fatigue": 0.9,
            "confidence": 0.9,
            "completeness": 0.9,
            "is_normal_confirmed": False,
        },
    )
    assert r.status_code == 201
    br = client.post("/api/v1/users/U_EXCL/baseline/build")
    assert br.status_code == 200
    # sample_count는 정상 확인 3개만
    assert br.json()["sample_count"] == 3


def test_episodic_and_summary_memory(client: TestClient) -> None:
    _create_user(client, "U_MEM")
    _add_normal_samples(client, "U_MEM", 3)
    assert client.post("/api/v1/users/U_MEM/baseline/build").status_code == 200
    resp = _analyze(client, user_id="U_MEM", session_id="S_MEM1", cl=0.46, att=0.71, fat=0.33)
    assert resp.status_code == 200

    eps = client.get("/api/v1/users/U_MEM/episodes")
    assert eps.status_code == 200
    assert len(eps.json()) >= 1
    assert eps.json()[0]["session_id"] == "S_MEM1"

    summary = client.get("/api/v1/users/U_MEM/summary")
    assert summary.status_code == 200
    assert summary.json()["recent_episode_count"] >= 1
    assert "long_term_state_summary" in summary.json()["summary"]


def test_memory_persists_across_sessions(client: TestClient, tmp_path: Path) -> None:
    """동일 엔진 세션을 재사용해 Memory 유지 확인."""
    _create_user(client, "U_PERS")
    _add_normal_samples(client, "U_PERS", 3)
    assert client.post("/api/v1/users/U_PERS/baseline/build").status_code == 200
    _analyze(client, user_id="U_PERS", session_id="S_P1", cl=0.46, att=0.71, fat=0.33)

    # 재조회
    bl = client.get("/api/v1/users/U_PERS/baseline")
    assert bl.status_code == 200
    eps = client.get("/api/v1/users/U_PERS/episodes")
    assert len(eps.json()) >= 1


def test_mock_seed(client: TestClient) -> None:
    resp = client.post("/api/v1/mock/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert "U001" in data["users_created"] or client.get("/api/v1/users/U001").status_code == 200
