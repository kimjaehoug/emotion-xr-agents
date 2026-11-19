"""상태 인지 Agent Memory v2 서비스.

흐름 (책 3.1 / 3.3.3):
  분석 1회 → 원시 이벤트 append → 규칙 기반 추출(선택성·추상화·구조화)로 카드 ADD/SUPERSEDE
  → 작업 메모리 활성화(관련 카드 + 유사 일화) → User-as-Code 규칙으로 능동 경고
  주기적: 중요도 점수 → 군집 요약 카드 → 저중요 일화 보조 저장소로 이동(삭제 아님)
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.constants import METRIC_NAMES
from app.memory.core import (
    EPISODIC,
    SEMANTIC,
    card_view,
    hybrid_rank,
    importance_score,
    parse_time,
    plan_card_write,
    resolve_current,
    utcnow,
)
from app.memory.rules import (
    LEVEL_KO,
    NEGATIVE_EMOTIONS,
    VISUAL_TRIGGER_THRESHOLD,
    MemoryState,
    evaluate_rules,
    metric_ko,
)
from app.memory.store import EpisodeArchiveStore, MemoryCardStore, MemoryEventStore
from app.repositories.memory_repo import EpisodeRepository

EXTRACTION_WINDOW = 5
TRAIT_MIN_COUNT = 3
LEVEL_SEVERITY = {"ACTION_REQUIRED": 1.0, "WATCH": 0.6, "UNKNOWN": 0.2, "NORMAL": 0.1}
OUT_STATUSES = ("above_baseline", "below_baseline")


def _episode_view(ep: Dict[str, Any]) -> Dict[str, Any]:
    report = ep.get("state_report_json") or ep.get("state_report") or {}
    gaps = report.get("cognitive_gap") or ep.get("gap_json") or {}
    return {
        "session_id": ep.get("session_id"),
        "state_level": ep.get("state_level") or report.get("state_level"),
        "gaps": gaps,
        "context": report.get("context_summary") or {},
        "emotion": report.get("emotion_context") or {},
        "created_at": ep.get("created_at") or report.get("timestamp"),
    }


def _signature(view: Dict[str, Any]) -> str:
    statuses = [f"{m}:{(view['gaps'].get(m) or {}).get('status', 'unknown')}" for m in METRIC_NAMES]
    return f"{view['state_level']}|" + ",".join(statuses)


def _gap_vector(gaps: Dict[str, Any]) -> List[float]:
    return [float((gaps.get(m) or {}).get("relative_deviation") or 0.0) for m in METRIC_NAMES]


class StateMemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.events = MemoryEventStore(db)
        self.cards = MemoryCardStore(db)
        self.archive = EpisodeArchiveStore(db)
        self.episode_repo = EpisodeRepository(db)

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------
    def current_cards(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        return resolve_current(self.cards.to_dict(c) for c in self.cards.list(user_id))

    def _episodes(self, user_id: str, limit: int = 50, include_archived: bool = False) -> List[Dict[str, Any]]:
        rows = self.episode_repo.list_recent(user_id, limit=limit)
        archived = {} if include_archived else self.archive.archived_sessions(user_id)
        return [
            _episode_view(
                {
                    "session_id": e.session_id,
                    "state_level": e.state_level,
                    "gap_json": e.gap_json,
                    "state_report_json": e.state_report_json,
                    "created_at": e.created_at,
                }
            )
            for e in rows
            if e.session_id not in archived
        ]

    # ------------------------------------------------------------------
    # 1) 원시 증거 기록
    # ------------------------------------------------------------------
    def record_analysis(self, raw_input: Dict[str, Any], report: Dict[str, Any]) -> None:
        self.events.append(
            report["user_id"],
            "state_analyzed",
            {
                "input": raw_input,
                "state_report_id": report.get("state_report_id"),
                "state_level": report.get("state_level"),
                "statuses": {m: (g or {}).get("status") for m, g in (report.get("cognitive_gap") or {}).items()},
            },
            session_id=report.get("session_id"),
        )

    # ------------------------------------------------------------------
    # 2) 지식 추출 → 카드 ADD-only 갱신
    # ------------------------------------------------------------------
    def _write_card(
        self,
        user_id: str,
        current: Dict[str, Dict[str, Any]],
        *,
        key: str,
        value: Any,
        backstory: str,
        evidence: List[str],
        confidence: float,
        memory_type: str = SEMANTIC,
        source: str = "rule_extractor",
    ) -> Tuple[str, Optional[str]]:
        existing = current.get(key)
        decision = plan_card_write(existing, value)
        if decision == "REINFORCE":
            self.events.append(user_id, "card_reinforced", {"card_id": existing["card_id"], "key": key, "evidence": evidence}, commit=False)
            return decision, existing["card_id"]
        card = self.cards.add(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value=value,
            backstory=backstory,
            evidence=evidence,
            confidence=confidence,
            source=source,
            commit=False,
        )
        if decision == "SUPERSEDE":
            old = next(c for c in self.cards.list(user_id) if c.card_id == existing["card_id"])
            self.cards.close(old, superseded_by=card.card_id, commit=False)
        self.events.append(
            user_id,
            "card_added" if decision == "ADD" else "card_superseded",
            {"card_id": card.card_id, "key": key, "value": value, "replaces": existing["card_id"] if existing else None},
            commit=False,
        )
        return decision, card.card_id

    def _expire_card(self, user_id: str, current: Dict[str, Dict[str, Any]], key: str, reason: str) -> Optional[str]:
        existing = current.get(key)
        if existing is None:
            return None
        row = next(c for c in self.cards.list(user_id) if c.card_id == existing["card_id"])
        self.cards.close(row, commit=False)
        self.events.append(user_id, "card_expired", {"card_id": row.card_id, "key": key, "reason": reason}, commit=False)
        return row.card_id

    def update_knowledge(self, user_id: str) -> List[Dict[str, Any]]:
        """최근 일화에서 안정적 특성을 추출한다. 단기 세부는 버리고(선택성) 지속 성향으로 일반화(추상화)."""
        episodes = self._episodes(user_id, limit=20)
        window = episodes[:EXTRACTION_WINDOW]
        current = self.current_cards(user_id)
        changes: List[Dict[str, Any]] = []

        def log(key: str, decision: str, card_id: Optional[str]) -> None:
            changes.append({"key": key, "decision": decision, "card_id": card_id})

        # (a) 지표별 이탈 성향
        for metric in METRIC_NAMES:
            key = f"trait.{metric}.deviation"
            by_dir: Dict[str, List[str]] = defaultdict(list)
            for ep in window:
                status = (ep["gaps"].get(metric) or {}).get("status")
                if status in OUT_STATUSES:
                    by_dir[status].append(ep["session_id"])
            direction, sessions = max(by_dir.items(), key=lambda kv: len(kv[1]), default=(None, []))
            if direction and len(sessions) >= TRAIT_MIN_COUNT:
                ratio = len(sessions) / len(window)
                decision, cid = self._write_card(
                    user_id,
                    current,
                    key=key,
                    value={"direction": direction},
                    backstory=f"최근 {len(window)}세션 중 {len(sessions)}회 {metric_ko(metric)} 수치가 기준선보다 {'높음' if direction == 'above_baseline' else '낮음'}.",
                    evidence=sessions,
                    confidence=ratio,
                )
                log(key, decision, cid)
            elif key in current:
                log(key, "EXPIRE", self._expire_card(user_id, current, key, "최근 창에서 반복 이탈이 더 이상 관찰되지 않음"))

        # (b) 반복 ACTION_REQUIRED
        key = "trait.state.recurring_action_required"
        ar = [ep["session_id"] for ep in window if ep["state_level"] == "ACTION_REQUIRED"]
        if len(ar) >= 2:
            decision, cid = self._write_card(
                user_id, current, key=key, value=True,
                backstory=f"최근 {len(window)}세션 중 {len(ar)}회 '조치 필요' 판정.",
                evidence=ar, confidence=len(ar) / len(window),
            )
            log(key, decision, cid)
        elif key in current:
            log(key, "EXPIRE", self._expire_card(user_id, current, key, "ACTION_REQUIRED 반복이 해소됨"))

        # (c) 부하 유발 조건 (콘텐츠 맥락 × 상태) — 다중 세션 연결
        high = [ep for ep in episodes if (ep["context"].get("visual_complexity") or 0) >= VISUAL_TRIGGER_THRESHOLD]
        low = [ep for ep in episodes if ep["context"].get("visual_complexity") is not None and ep not in high]
        def abnormal_ratio(group: List[Dict[str, Any]]) -> float:
            return sum(ep["state_level"] in ("WATCH", "ACTION_REQUIRED") for ep in group) / len(group) if group else 0.0
        if len(high) >= 2 and abnormal_ratio(high) >= 0.67 and abnormal_ratio(high) > abnormal_ratio(low):
            key = "trigger.visual_complexity"
            decision, cid = self._write_card(
                user_id, current, key=key, value={"threshold": VISUAL_TRIGGER_THRESHOLD},
                backstory=(
                    f"시각 복잡도 {VISUAL_TRIGGER_THRESHOLD} 이상 세션 {len(high)}개 중 {abnormal_ratio(high):.0%}가 주의·조치 필요"
                    f" (그 외 세션 {abnormal_ratio(low):.0%})."
                ),
                evidence=[ep["session_id"] for ep in high], confidence=abnormal_ratio(high),
            )
            log(key, decision, cid)

        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for ep in episodes:
            if ep["context"].get("content_type"):
                by_type[ep["context"]["content_type"]].append(ep)
        for ctype, group in by_type.items():
            if len(group) >= 2 and abnormal_ratio(group) >= 0.67:
                key = f"trigger.content_type.{ctype}"
                decision, cid = self._write_card(
                    user_id, current, key=key, value={"content_type": ctype},
                    backstory=f"'{ctype}' 콘텐츠 세션 {len(group)}개 중 {abnormal_ratio(group):.0%}가 주의·조치 필요.",
                    evidence=[ep["session_id"] for ep in group], confidence=abnormal_ratio(group),
                )
                log(key, decision, cid)

        # (d) 지배 정서 (감정 매핑 Agent의 emotion_context 연계)
        labels = [ep["emotion"].get("label") for ep in window if (ep["emotion"].get("intensity") or 0) >= 0.5]
        if labels:
            top = max(set(labels), key=labels.count)
            if labels.count(top) >= TRAIT_MIN_COUNT:
                key = "trait.emotion.dominant"
                decision, cid = self._write_card(
                    user_id, current, key=key, value={"label": top, "negative": top in NEGATIVE_EMOTIONS},
                    backstory=f"최근 {len(window)}세션 중 {labels.count(top)}회 '{top}' 감정이 강하게 나타남.",
                    evidence=[ep["session_id"] for ep in window if ep["emotion"].get("label") == top],
                    confidence=labels.count(top) / len(window),
                )
                log(key, decision, cid)

        self.db.commit()
        return changes

    # ------------------------------------------------------------------
    # 3) 작업 메모리 활성화 + 능동 경고
    # ------------------------------------------------------------------
    def _importance_map(self, user_id: str, episodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        access = self.events.access_counts(user_id)
        sig_counts: Dict[str, int] = defaultdict(int)
        for ep in episodes:
            sig_counts[_signature(ep)] += 1
        result = {}
        for ep in episodes:
            intensity = max(
                LEVEL_SEVERITY.get(ep["state_level"] or "", 0.2),
                float(ep["emotion"].get("intensity") or 0.0),
            )
            result[ep["session_id"]] = importance_score(
                created_at=parse_time(ep["created_at"]),
                access_count=access.get(ep["session_id"], 0),
                emotional_intensity=intensity,
                duplicate_count=sig_counts[_signature(ep)] - 1,
            )
        return result

    def build_working_memory(
        self,
        report: Dict[str, Any],
        *,
        baseline: Optional[Dict[str, Any]],
        top_k: int = 3,
    ) -> Dict[str, Any]:
        user_id = report["user_id"]
        current = self.current_cards(user_id)
        episodes = [ep for ep in self._episodes(user_id) if ep["session_id"] != report.get("session_id")]
        importance = self._importance_map(user_id, episodes)

        q_vec = _gap_vector(report.get("cognitive_gap") or {})
        q_entities = {m for m, g in (report.get("cognitive_gap") or {}).items() if (g or {}).get("status") in OUT_STATUSES}

        def similarity(ep: Dict[str, Any]) -> float:
            return 1.0 / (1.0 + math.dist(q_vec, _gap_vector(ep["gaps"])) * 4)

        ranked = hybrid_rank(
            episodes,
            similarity_of=similarity,
            importance_of=lambda ep: importance[ep["session_id"]]["score"],
            entities_of=lambda ep: {m for m, g in ep["gaps"].items() if (g or {}).get("status") in OUT_STATUSES},
            query_entities=q_entities,
            top_k=top_k,
        )
        similar = [
            {
                "session_id": r["item"]["session_id"],
                "state_level": r["item"]["state_level"],
                "score": r["score"],
                "signals": r["signals"],
            }
            for r in ranked
        ]

        # 관련 카드만 활성화: 현재 이탈 지표·현재 맥락과 관련 있는 카드 + 상태/정서 특성
        ctx = report.get("context_summary") or {}
        activated = []
        for key, card in current.items():
            if key.startswith("trait.state") or key.startswith("trait.emotion"):
                activated.append(card)
            elif key.startswith("trait.") and key.split(".")[1] in q_entities:
                activated.append(card)
            elif key == "trigger.visual_complexity" and (ctx.get("visual_complexity") or 0) >= VISUAL_TRIGGER_THRESHOLD:
                activated.append(card)
            elif key == f"trigger.content_type.{ctx.get('content_type')}":
                activated.append(card)

        alerts = evaluate_rules(
            MemoryState(
                report=report,
                baseline=baseline,
                current_cards=current,
                episodes=episodes,
                emotion_context=report.get("emotion_context"),
            )
        )

        refs = [s["session_id"] for s in similar] + [c["card_id"] for c in activated]
        if refs:
            self.events.append(user_id, "memory_accessed", {"refs": refs, "for_session": report.get("session_id")})

        return {
            "working_memory": {
                "activated_cards": [card_view(c) for c in activated],
                "similar_episodes": similar,
            },
            "proactive_alerts": alerts,
            "long_term_card_count": len(current),
        }

    # ------------------------------------------------------------------
    # 4) 주기적 압축·정리 (3.1.7)
    # ------------------------------------------------------------------
    def consolidate(self, user_id: str, *, min_age_days: float = 14.0, threshold: float = 0.35) -> Dict[str, Any]:
        episodes = self._episodes(user_id, limit=500)
        importance = self._importance_map(user_id, episodes)
        current = self.current_cards(user_id)

        candidates = [
            ep for ep in episodes
            if importance[ep["session_id"]]["age_days"] >= min_age_days
            and importance[ep["session_id"]]["score"] < threshold
        ]
        clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for ep in candidates:
            clusters[_signature(ep)].append(ep)

        archived: List[str] = []
        cluster_cards: List[Dict[str, Any]] = []
        for sig, group in clusters.items():
            times = sorted(str(parse_time(ep["created_at"])) for ep in group)
            prev = current.get(f"cluster.{sig}")
            prev_count = (prev or {}).get("value", {}).get("count", 0) if prev else 0
            decision, cid = self._write_card(
                user_id, current, key=f"cluster.{sig}", memory_type=EPISODIC,
                value={"count": prev_count + len(group), "state_level": group[0]["state_level"]},
                backstory=f"{LEVEL_KO.get(group[0]['state_level'] or '', '')} 상태의 유사 이력 {len(group)}건 요약 ({times[0][:10]} ~ {times[-1][:10]}). 원본은 별도 보관.",
                evidence=[ep["session_id"] for ep in group],
                confidence=1.0,
                source="consolidation",
            )
            cluster_cards.append({"signature": sig, "card_id": cid, "decision": decision, "episodes": len(group)})
            for ep in group:
                self.archive.archive(
                    user_id=user_id, session_id=ep["session_id"], cluster_card_id=cid,
                    importance=importance[ep["session_id"]],
                )
                archived.append(ep["session_id"])

        self.events.append(
            user_id, "consolidated",
            {"archived": archived, "clusters": cluster_cards, "threshold": threshold, "min_age_days": min_age_days},
            commit=False,
        )
        self.db.commit()
        return {
            "user_id": user_id,
            "scored": [{"session_id": sid, **imp} for sid, imp in importance.items()],
            "archived_sessions": archived,
            "cluster_cards": cluster_cards,
            "ran_at": utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # API 뷰
    # ------------------------------------------------------------------
    def overview(self, user_id: str) -> Dict[str, Any]:
        all_cards = [self.cards.to_dict(c) for c in self.cards.list(user_id)]
        current = resolve_current(all_cards)
        episodes = self._episodes(user_id, limit=500, include_archived=True)
        archived = self.archive.archived_sessions(user_id)
        importance = self._importance_map(user_id, episodes)
        return {
            "user_id": user_id,
            "layers": {
                "raw_events": len(self.events.list(user_id, limit=100000)),
                "episodic": len(episodes),
                "archived_episodes": len(archived),
                "current_cards": len(current),
                "card_history": len(all_cards),
            },
            "current_cards": [card_view(c) for c in current.values()],
            "card_history": [card_view(c) | {"superseded_by": c.get("superseded_by")} for c in all_cards if c["valid_to"]],
            "episode_importance": [
                {"session_id": sid, "archived": sid in archived, **imp} for sid, imp in importance.items()
            ],
        }
