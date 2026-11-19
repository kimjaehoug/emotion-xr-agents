"""Cognitive Gap 계산."""

from typing import Any, Dict, List, Optional

from app.core.constants import METRIC_NAMES


def compute_metric_gap(
    metric: str,
    current: float,
    baseline_metric: Optional[Dict[str, float]],
) -> Dict[str, Any]:
    if baseline_metric is None:
        return {
            "current_value": current,
            "baseline_center": None,
            "absolute_deviation": None,
            "relative_deviation": None,
            "lower_bound": None,
            "upper_bound": None,
            "in_normal_range": None,
            "status": "unknown",
            "trend": "insufficient_data",
            "persistence_count": 0,
        }

    center = float(baseline_metric["center"])
    lower = float(baseline_metric["lower"])
    upper = float(baseline_metric["upper"])
    abs_dev = current - center
    rel_dev = abs_dev / center if abs(center) > 1e-9 else abs_dev

    if current < lower:
        status = "below_baseline"
        in_range = False
    elif current > upper:
        status = "above_baseline"
        in_range = False
    else:
        status = "within_range"
        in_range = True

    return {
        "current_value": current,
        "baseline_center": center,
        "absolute_deviation": round(abs_dev, 4),
        "relative_deviation": round(rel_dev, 4),
        "lower_bound": lower,
        "upper_bound": upper,
        "in_normal_range": in_range,
        "status": status,
        "trend": "insufficient_data",
        "persistence_count": 0,
    }


def compute_cognitive_gaps(
    metrics: Dict[str, float],
    baseline: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    gaps: Dict[str, Dict[str, Any]] = {}
    for name in METRIC_NAMES:
        bm = baseline.get(name) if baseline else None
        gaps[name] = compute_metric_gap(name, float(metrics[name]), bm)
    return gaps
