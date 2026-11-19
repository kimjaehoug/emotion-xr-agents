"""XR Control Agent Memory v2 서비스.

핵심은 절차 메모리(3.1.5): "이 사용자에게 이 상태에서 어떤 행동이 효과가 있었나".
- 피드백/확인 거절은 원시 이벤트로 append (프로필 덮어쓰기만으로는 이력이 사라짐)
- 이벤트 로그에서 행동별 효과 통계를 재구성 → procedure 카드 (User-as-Code: 로그 + 체크포인트)
- 효과가 반복적으로 나빴던 행동 → semantic 'avoid' 카드
- 계획 생성 시 작업 메모리로 활성화하여 Planner(LLM 프롬프트/Fallback)와 가드에 반영
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.enums import ActionType
from app.memory.core import PROCEDURAL, SEMANTIC, card_view, plan_card_write, resolve_current
from app.memory.store import MemoryCardStore, MemoryEventStore

EFFECT_SCORE = {"positive": 1, "neutral": 0, "negative": -1, "rejected": -1}
AVOID_MIN_TRIALS = 2
AVOID_MAX_EFFECTIVENESS = -0.5
ESCALATION_WINDOW = 3

LEVEL_KO = {"NORMAL": "정상", "WATCH": "주의", "ACTION_REQUIRED": "조치 필요", "UNKNOWN": "판단 보류"}
PARAM_KO = {
    "visual_complexity": "시각 복잡도",
    "audio_stimulation": "청각 자극",
    "interaction_density": "상호작용 빈도",
    "information_density": "정보량",
    "motion_intensity": "움직임 강도",
}
ACTION_KO = {
    "SUGGEST_BREAK": "휴식 제안",
    "RECOMMEND_CONTENT": "콘텐츠 추천",
    "OBSERVE": "지켜보기",
    "KEEP_CURRENT_STATE": "현재 상태 유지",
}


def signature_ko(sig: str) -> str:
    """'UPDATE_XR_PARAMETER:visual_complexity' → '시각 복잡도 조절'."""
    action, _, param = sig.partition(":")
    if action == ActionType.UPDATE_XR_PARAMETER.value:
        return f"{PARAM_KO.get(param, param)} 조절"
    return ACTION_KO.get(action, action)


def action_signature(action: Dict[str, Any]) -> str:
    return f"{action.get('action_type')}:{action.get('xr_parameter') or ''}"


class XrMemoryV2:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.events = MemoryEventStore(db)
        self.cards = MemoryCardStore(db)

    def current_cards(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        return resolve_current(self.cards.to_dict(c) for c in self.cards.list(user_id))

    # ------------------------------------------------------------------
    # 원시 증거
    # ------------------------------------------------------------------
    def record_plan(self, state_report: Dict[str, Any], action_plan: Dict[str, Any]) -> None:
        upstream = (state_report.get("memory_context") or {}).get("proactive_alerts") or []
        self.events.append(
            action_plan["user_id"],
            "plan_created",
            {
                "plan_id": action_plan["plan_id"],
                "state_report_id": action_plan["state_report_id"],
                "state_level": state_report.get("state_level"),
                "goal": str(action_plan.get("goal")),
                "route": str(action_plan.get("route")),
                "planner_source": str(action_plan.get("planner_source")),
                "signatures": [action_signature(a) for a in action_plan.get("actions") or []],
                "upstream_alert_rules": [a.get("rule") for a in upstream],
            },
            session_id=action_plan["session_id"],
        )

    def record_outcome(
        self,
        *,
        user_id: str,
        session_id: str,
        state_level: str,
        action: Dict[str, Any],
        effect: str,
        ref_id: str,
        comment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """피드백(positive/neutral/negative) 또는 확인 거절(rejected)을 기록하고 절차 지식을 갱신한다."""
        self.events.append(
            user_id,
            "action_outcome",
            {
                "ref_id": ref_id,
                "state_level": state_level,
                "signature": action_signature(action),
                "effect": effect,
                "comment": comment,
            },
            session_id=session_id,
            commit=False,
        )
        self.db.commit()
        return self.update_procedures(user_id)

    # ------------------------------------------------------------------
    # 지식 갱신: 로그 → 절차/의미 카드
    # ------------------------------------------------------------------
    def _write(self, user_id: str, current: Dict[str, Dict[str, Any]], **kw: Any) -> Tuple[str, Optional[str]]:
        existing = current.get(kw["key"])
        decision = plan_card_write(existing, kw["value"])
        if decision == "REINFORCE":
            return decision, existing["card_id"]
        card = self.cards.add(user_id=user_id, commit=False, **kw)
        if decision == "SUPERSEDE":
            old = next(c for c in self.cards.list(user_id) if c.card_id == existing["card_id"])
            self.cards.close(old, superseded_by=card.card_id, commit=False)
        self.events.append(
            user_id,
            "card_added" if decision == "ADD" else "card_superseded",
            {"card_id": card.card_id, "key": kw["key"], "value": kw["value"]},
            commit=False,
        )
        return decision, card.card_id

    def update_procedures(self, user_id: str) -> List[Dict[str, Any]]:
        stats: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"positive": 0, "neutral": 0, "negative": 0, "rejected": 0, "refs": []}
        )
        for ev in reversed(self.events.list(user_id, event_type="action_outcome", limit=5000)):
            p = ev.payload_json or {}
            s = stats[(p.get("state_level") or "UNKNOWN", p.get("signature") or "")]
            s[p.get("effect", "neutral")] = s.get(p.get("effect", "neutral"), 0) + 1
            s["refs"].append(p.get("ref_id"))

        current = self.current_cards(user_id)
        changes: List[Dict[str, Any]] = []
        for (level, sig), s in stats.items():
            n = s["positive"] + s["neutral"] + s["negative"] + s["rejected"]
            score = sum(EFFECT_SCORE[k] * s[k] for k in EFFECT_SCORE)
            effectiveness = round(score / n, 3) if n else 0.0
            value = {k: s[k] for k in EFFECT_SCORE} | {"n": n, "effectiveness": effectiveness}
            decision, cid = self._write(
                user_id, current,
                memory_type=PROCEDURAL,
                key=f"procedure.{level}.{sig}",
                value=value,
                backstory=(
                    f"'{LEVEL_KO.get(level, level)}' 상태에서 '{signature_ko(sig)}' {n}회 실행: 긍정 {s['positive']}, 중립 {s['neutral']}, "
                    f"부정 {s['negative']}, 거절 {s['rejected']} (효과 점수 {effectiveness:+.2f}, 범위 -1~+1)."
                ),
                evidence=[r for r in s["refs"] if r][-10:],
                confidence=min(1.0, n / 5),
                source="feedback_log",
            )
            changes.append({"key": f"procedure.{level}.{sig}", "decision": decision, "card_id": cid})

            avoid_key = f"preference.avoid.{sig}"
            if n >= AVOID_MIN_TRIALS and effectiveness <= AVOID_MAX_EFFECTIVENESS:
                decision, cid = self._write(
                    user_id, current,
                    memory_type=SEMANTIC,
                    key=avoid_key,
                    value={"signature": sig, "since_level": level},
                    backstory=f"'{signature_ko(sig)}'에 부정·거절 반응 누적({n}회, 효과 점수 {effectiveness:+.2f}) → 회피 대상으로 학습.",
                    evidence=[r for r in s["refs"] if r][-10:],
                    confidence=min(1.0, n / 4),
                    source="feedback_log",
                )
                changes.append({"key": avoid_key, "decision": decision, "card_id": cid})
            elif avoid_key in current and effectiveness > 0:
                row = next(c for c in self.cards.list(user_id) if c.card_id == current[avoid_key]["card_id"])
                self.cards.close(row, commit=False)
                self.events.append(user_id, "card_expired", {"card_id": row.card_id, "key": avoid_key}, commit=False)
                changes.append({"key": avoid_key, "decision": "EXPIRE", "card_id": row.card_id})
        self.db.commit()
        return changes

    # ------------------------------------------------------------------
    # 작업 메모리
    # ------------------------------------------------------------------
    def build_working_memory(
        self, state_report: Dict[str, Any], recent_episodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        user_id = state_report["user_id"]
        level = state_report.get("state_level", "UNKNOWN")
        current = self.current_cards(user_id)

        procedures = sorted(
            (c for k, c in current.items() if k.startswith(f"procedure.{level}.")),
            key=lambda c: (c["value"] or {}).get("effectiveness", 0),
            reverse=True,
        )
        avoid = [c["value"]["signature"] for k, c in current.items() if k.startswith("preference.avoid.")]

        upstream = (state_report.get("memory_context") or {}).get("proactive_alerts") or []
        alerts: List[Dict[str, Any]] = []
        recent_levels = [level] + [e.get("state_level") for e in recent_episodes[: ESCALATION_WINDOW - 1]]
        escalate = len(recent_levels) >= ESCALATION_WINDOW and all(l == "ACTION_REQUIRED" for l in recent_levels)
        if escalate:
            alerts.append({
                "rule": "repeated_action_required",
                "severity": "high",
                "message": f"최근 {ESCALATION_WINDOW}세션 연속 '조치 필요' 판정입니다. 자동 조절 대신 사용자 확인을 요청합니다.",
                "evidence": [e.get("state_report_id") for e in recent_episodes[: ESCALATION_WINDOW - 1]],
            })
        if any(a.get("severity") == "high" for a in upstream):
            escalate = True
            alerts.append({
                "rule": "upstream_high_alert",
                "severity": "high",
                "message": "상태 인지 에이전트로부터 높은 단계 알림을 받았습니다. 자동 조절 대신 사용자 확인을 요청합니다.",
                "evidence": [a.get("rule") for a in upstream if a.get("severity") == "high"],
            })
        if avoid:
            alerts.append({
                "rule": "learned_avoidance",
                "severity": "medium",
                "message": f"회피 대상 조절: {', '.join(signature_ko(s) for s in avoid)}",
                "evidence": [current[f'preference.avoid.{s}']["card_id"] for s in avoid],
            })

        refs = [c["card_id"] for c in procedures] + [current[f"preference.avoid.{s}"]["card_id"] for s in avoid]
        if refs:
            self.events.append(user_id, "memory_accessed", {"refs": refs, "for": state_report.get("state_report_id")})

        return {
            "procedures": [card_view(c) for c in procedures[:5]],
            "avoid_signatures": avoid,
            "escalate_confirmation": escalate,
            "proactive_alerts": alerts,
            "upstream_alerts": upstream,
        }

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------
    def overview(self, user_id: str) -> Dict[str, Any]:
        all_cards = [self.cards.to_dict(c) for c in self.cards.list(user_id)]
        current = resolve_current(all_cards)
        return {
            "user_id": user_id,
            "layers": {
                "raw_events": len(self.events.list(user_id, limit=100000)),
                "current_cards": len(current),
                "card_history": len(all_cards),
            },
            "current_cards": [card_view(c) for c in current.values()],
            "card_history": [card_view(c) | {"superseded_by": c.get("superseded_by")} for c in all_cards if c["valid_to"]],
        }


def apply_memory_guards(actions: List[Dict[str, Any]], memory: Dict[str, Any]) -> List[str]:
    """Planner 출력(LLM/Fallback 공통)에 메모리 기반 안전 가드를 적용한다."""
    warnings: List[str] = []
    avoid = set(memory.get("avoid_signatures") or [])
    for action in actions:
        if action.get("action_type") not in (ActionType.UPDATE_XR_PARAMETER.value, ActionType.RECOMMEND_CONTENT.value):
            continue
        sig = action_signature(action)
        if sig in avoid and not action.get("requires_confirmation"):
            action["requires_confirmation"] = True
            warnings.append(f"'{signature_ko(sig)}'은(는) 부정 반응 이력이 있는 회피 대상이므로 사용자 확인 후 실행합니다.")
        if memory.get("escalate_confirmation") and not action.get("requires_confirmation"):
            action["requires_confirmation"] = True
            warnings.append(f"선제 알림에 따라 '{signature_ko(sig)}' 자동 조절을 보류하고 사용자 확인을 요청합니다.")
    return warnings
