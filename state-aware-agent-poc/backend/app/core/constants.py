"""공통 상수."""

from typing import Final, Literal, Tuple

METRIC_NAMES: Final[Tuple[str, ...]] = (
    "cognitive_load",
    "attention",
    "fatigue",
)

StateLevel = Literal["NORMAL", "WATCH", "ACTION_REQUIRED", "UNKNOWN"]
GapStatus = Literal[
    "above_baseline",
    "below_baseline",
    "within_range",
    "unknown",
]
TrendDirection = Literal[
    "increasing",
    "decreasing",
    "stable",
    "insufficient_data",
]
BaselineSource = Literal["personal", "group_default", "none"]

# 그룹 기본 Baseline (개인 Baseline 없을 때 선택적 사용)
GROUP_DEFAULT_BASELINE: Final[dict] = {
    "version": "group_v1",
    "reliability": 0.5,
    "sample_count": 0,
    "cognitive_load": {"center": 0.45, "lower": 0.25, "upper": 0.65},
    "attention": {"center": 0.70, "lower": 0.50, "upper": 0.90},
    "fatigue": {"center": 0.35, "lower": 0.15, "upper": 0.55},
}
