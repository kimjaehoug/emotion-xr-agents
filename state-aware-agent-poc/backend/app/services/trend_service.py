"""단기/누적 추세 및 지속성 분석."""

from typing import Any, Dict, List, Optional

from app.core.constants import METRIC_NAMES


def _trend_from_series(values: List[float], epsilon: float = 0.03) -> str:
    if len(values) < 2:
        return "insufficient_data"
    # 최근 값 기준 단순 기울기
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_delta = sum(deltas) / len(deltas)
    if avg_delta > epsilon:
        return "increasing"
    if avg_delta < -epsilon:
        return "decreasing"
    return "stable"


def _persistence_count(
    recent_statuses: List[str],
    current_status: str,
) -> int:
    """같은 방향(이탈)이 연속으로 나타난 횟수."""
    if current_status in ("within_range", "unknown"):
        return 0
    count = 1
    for status in reversed(recent_statuses):
        if status == current_status:
            count += 1
        else:
            break
    return count


def analyze_trends(
    gaps: Dict[str, Dict[str, Any]],
    recent_episodes: List[Dict[str, Any]],
    *,
    window: int = 5,
    persistence_threshold: int = 2,
) -> Dict[str, Dict[str, Any]]:
    """gap에 trend / persistence_count / persistent 를 보강."""
    # episodes: newest first 가정
    recent = recent_episodes[:window]

    for metric in METRIC_NAMES:
        series: List[float] = []
        statuses: List[str] = []
        # 오래된 순으로 재정렬하여 추세 계산
        for ep in reversed(recent):
            gap = (ep.get("gap_json") or ep.get("cognitive_gap") or {}).get(metric)
            if not gap:
                report = ep.get("state_report_json") or ep.get("state_report") or {}
                cg = report.get("cognitive_gap") or {}
                gap = cg.get(metric)
            if gap:
                val = gap.get("current_value", gap.get("current"))
                if val is not None:
                    series.append(float(val))
                st = gap.get("status")
                if st:
                    statuses.append(st)

        # 현재 값 추가
        current = gaps[metric]["current_value"]
        series.append(float(current))
        current_status = gaps[metric]["status"]

        trend = _trend_from_series(series)
        # 직전 세션 대비
        session_delta: Optional[float] = None
        if len(series) >= 2:
            session_delta = round(series[-1] - series[-2], 4)

        pcount = _persistence_count(statuses, current_status)
        gaps[metric]["trend"] = trend
        gaps[metric]["persistence_count"] = pcount
        gaps[metric]["persistent"] = pcount >= persistence_threshold
        gaps[metric]["session_delta"] = session_delta

    # 복수 지표 동시 변화
    out_of_range = [
        m for m in METRIC_NAMES if gaps[m].get("in_normal_range") is False
    ]
    multi_metric_shift = len(out_of_range) >= 2

    return {
        "gaps": gaps,
        "multi_metric_shift": multi_metric_shift,
        "out_of_range_metrics": out_of_range,
        "recent_window_size": len(recent),
    }
