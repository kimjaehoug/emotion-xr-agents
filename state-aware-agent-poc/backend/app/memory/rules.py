"""User as Code (3.1.4): 타입이 있는 메모리 상태 + 결정적 규칙 함수 → 능동적 경고.

LLM의 '암산'에 맡기던 집계·충돌 발견·제약 집행을 검증 가능한 함수로 옮긴다.
경고는 의료 진단이 아니며, 후속 Agent(XR)가 참고할 관찰 신호다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

NEGATIVE_EMOTIONS = {"슬픔", "분노", "공포", "혐오"}
# 지표별로 '나빠지는' 추세 방향
WORSENING_TREND = {"cognitive_load": "increasing", "fatigue": "increasing", "attention": "decreasing"}
VISUAL_TRIGGER_THRESHOLD = 0.6
METRIC_KO = {"cognitive_load": "인지 부하", "attention": "집중도", "fatigue": "피로도"}
LEVEL_KO = {"NORMAL": "정상", "WATCH": "주의", "ACTION_REQUIRED": "조치 필요", "UNKNOWN": "판단 보류"}


def metric_ko(metric: str) -> str:
    return METRIC_KO.get(metric, metric)


@dataclass
class MemoryState:
    """규칙이 읽는 타입 있는 상태 스냅샷."""

    report: Dict[str, Any]
    baseline: Optional[Dict[str, Any]]
    current_cards: Dict[str, Dict[str, Any]]
    episodes: List[Dict[str, Any]] = field(default_factory=list)
    emotion_context: Optional[Dict[str, Any]] = None


Alert = Dict[str, Any]


def _alert(rule: str, severity: str, message: str, evidence: List[str]) -> Alert:
    return {"rule": rule, "severity": severity, "message": message, "evidence": evidence}


def check_persistent_deviation(s: MemoryState) -> List[Alert]:
    alerts: List[Alert] = []
    for metric, gap in (s.report.get("cognitive_gap") or {}).items():
        count = int(gap.get("persistence_count") or 0)
        if count >= 3:
            alerts.append(
                _alert(
                    "persistent_deviation",
                    "high",
                    f"{metric_ko(metric)} 수치가 {count}회 연속 기준선 범위를 벗어났습니다. 담당자 확인을 권장합니다.",
                    [f"cognitive_gap.{metric}.persistence_count={count}"],
                )
            )
    return alerts


def check_early_drift(s: MemoryState) -> List[Alert]:
    """임계 전 예측형 경고: 정상 범위지만 나빠지는 추세가 이어지는 지표."""
    alerts: List[Alert] = []
    for metric, gap in (s.report.get("cognitive_gap") or {}).items():
        if gap.get("status") != "within_range":
            continue
        if gap.get("trend") == WORSENING_TREND.get(metric):
            alerts.append(
                _alert(
                    "early_drift",
                    "low",
                    f"{metric_ko(metric)} 수치가 기준선 범위 내이나 악화 추세입니다. 다음 세션을 관찰해 주세요.",
                    [f"cognitive_gap.{metric}.trend={gap.get('trend')}"],
                )
            )
    return alerts


def check_baseline_reliability(s: MemoryState) -> List[Alert]:
    baseline = s.baseline or {}
    reliability = baseline.get("reliability")
    if reliability is not None and float(reliability) < 0.6:
        return [
            _alert(
                "baseline_low_reliability",
                "medium",
                f"개인 기준선 신뢰도({float(reliability):.2f})가 낮습니다. 정상 상태 측정을 추가해 기준선을 다시 생성해 주세요.",
                [f"baseline.version={baseline.get('version')}"],
            )
        ]
    return []


def check_known_trigger(s: MemoryState) -> List[Alert]:
    """복합 사고: 과거 세션에서 학습한 '부하 유발 조건' 카드와 현재 콘텐츠 맥락을 교차 대조."""
    alerts: List[Alert] = []
    ctx = s.report.get("context_summary") or {}
    visual = ctx.get("visual_complexity")
    card = s.current_cards.get("trigger.visual_complexity")
    if card and visual is not None and float(visual) >= VISUAL_TRIGGER_THRESHOLD:
        alerts.append(
            _alert(
                "known_trigger_active",
                "medium",
                f"이 사용자는 시각 복잡도 {VISUAL_TRIGGER_THRESHOLD} 이상에서 인지 부하가 상승한 이력이 있습니다"
                f"(현재 {float(visual):.2f}). 선제적 부하 완화를 권장합니다.",
                [card["card_id"], *card.get("evidence", [])[:3]],
            )
        )
    content_type = ctx.get("content_type")
    ct_card = s.current_cards.get(f"trigger.content_type.{content_type}") if content_type else None
    if ct_card:
        alerts.append(
            _alert(
                "known_trigger_active",
                "medium",
                f"'{content_type}' 콘텐츠에서 주의·조치 필요 상태가 반복되었습니다.",
                [ct_card["card_id"], *ct_card.get("evidence", [])[:3]],
            )
        )
    return alerts


def check_emotion_metric_mismatch(s: MemoryState) -> List[Alert]:
    emo = s.emotion_context or {}
    label = emo.get("label")
    intensity = float(emo.get("intensity") or 0.0)
    if label in NEGATIVE_EMOTIONS and intensity >= 0.6 and s.report.get("state_level") == "NORMAL":
        return [
            _alert(
                "emotion_metric_mismatch",
                "medium",
                f"감정 분석 결과는 부정 감정 '{label}'(강도 {intensity:.2f}), 인지 지표는 정상입니다. 추가 관찰을 권장합니다.",
                [f"emotion_context.label={label}"],
            )
        ]
    return []


RULES: List[Callable[[MemoryState], List[Alert]]] = [
    check_persistent_deviation,
    check_early_drift,
    check_baseline_reliability,
    check_known_trigger,
    check_emotion_metric_mismatch,
]


def evaluate_rules(state: MemoryState) -> List[Alert]:
    alerts: List[Alert] = []
    for rule in RULES:
        alerts.extend(rule(state))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(alerts, key=lambda a: order.get(a["severity"], 3))
