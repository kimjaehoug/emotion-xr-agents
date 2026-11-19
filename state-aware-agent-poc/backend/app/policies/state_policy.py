"""상태 수준 분류 정책 (config 기반)."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.core.constants import METRIC_NAMES


@dataclass
class ClassificationResult:
    state_level: str
    requires_response: bool
    additional_observation_required: bool
    analysis_confidence: float
    warnings: List[str]
    reasons: List[str]


class StatePolicy:
    """절대 진단 임계값이 아닌 Baseline 편차·지속성·품질 결합 정책."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def classify(
        self,
        *,
        gaps: Dict[str, Dict[str, Any]],
        baseline_source: str,
        confidence: float,
        completeness: float,
        multi_metric_shift: bool,
        has_input_error: bool = False,
    ) -> ClassificationResult:
        warnings: List[str] = []
        reasons: List[str] = []

        if has_input_error:
            return ClassificationResult(
                state_level="UNKNOWN",
                requires_response=False,
                additional_observation_required=True,
                analysis_confidence=0.0,
                warnings=["입력 검증 실패"],
                reasons=["invalid_input"],
            )

        if baseline_source == "none":
            return ClassificationResult(
                state_level="UNKNOWN",
                requires_response=False,
                additional_observation_required=True,
                analysis_confidence=min(confidence, completeness) * 0.5,
                warnings=["개인 Baseline이 없어 상태를 판단할 수 없습니다."],
                reasons=["no_baseline"],
            )

        if confidence < self.settings.min_confidence:
            warnings.append(
                f"cognitive_confidence({confidence:.2f})가 최소 기준"
                f"({self.settings.min_confidence}) 미만입니다."
            )
            return ClassificationResult(
                state_level="UNKNOWN",
                requires_response=False,
                additional_observation_required=True,
                analysis_confidence=confidence * completeness,
                warnings=warnings,
                reasons=["low_confidence"],
            )

        if completeness < self.settings.min_completeness:
            warnings.append(
                f"completeness({completeness:.2f})가 최소 기준"
                f"({self.settings.min_completeness}) 미만입니다."
            )
            return ClassificationResult(
                state_level="UNKNOWN",
                requires_response=False,
                additional_observation_required=True,
                analysis_confidence=confidence * completeness,
                warnings=warnings,
                reasons=["low_completeness"],
            )

        if confidence < 0.8:
            warnings.append("데이터 신뢰도가 다소 낮아 해석에 주의가 필요합니다.")
        if completeness < 0.8:
            warnings.append("데이터 완전성이 다소 낮아 해석에 주의가 필요합니다.")
        if baseline_source == "group_default":
            warnings.append("그룹 기본 Baseline을 사용했습니다. 개인 Baseline이 아닙니다.")

        out_metrics: List[Tuple[str, float, bool]] = []
        for m in METRIC_NAMES:
            g = gaps[m]
            if g.get("in_normal_range") is False:
                abs_dev = abs(float(g.get("absolute_deviation") or 0.0))
                persistent = bool(g.get("persistent"))
                out_metrics.append((m, abs_dev, persistent))

        analysis_conf = round(
            float(confidence)
            * float(completeness)
            * (0.9 if baseline_source == "personal" else 0.6),
            3,
        )

        if not out_metrics:
            reasons.append("all_within_range")
            return ClassificationResult(
                state_level="NORMAL",
                requires_response=False,
                additional_observation_required=False,
                analysis_confidence=analysis_conf,
                warnings=warnings,
                reasons=reasons,
            )

        large = [
            m
            for m, d, p in out_metrics
            if d >= self.settings.action_deviation_threshold
        ]
        medium = [
            m
            for m, d, p in out_metrics
            if d >= self.settings.watch_deviation_threshold
        ]
        persistent_large = [
            m
            for m, d, p in out_metrics
            if p and d >= self.settings.watch_deviation_threshold
        ]

        # ACTION_REQUIRED: 복수 지표 큰 이탈 OR 지속적 이탈 + 충분한 신뢰도
        if (
            (len(large) >= 2 or (multi_metric_shift and len(large) >= 1))
            and confidence >= 0.8
            and completeness >= 0.8
        ) or (
            len(persistent_large) >= 2
            and confidence >= 0.8
            and completeness >= 0.8
        ):
            reasons.append("multi_metric_large_or_persistent_deviation")
            return ClassificationResult(
                state_level="ACTION_REQUIRED",
                requires_response=True,
                additional_observation_required=False,
                analysis_confidence=analysis_conf,
                warnings=warnings,
                reasons=reasons,
            )

        # 단일 지표라도 큰 편차가 지속되면 ACTION_REQUIRED
        if (
            len(persistent_large) >= 1
            and any(d >= self.settings.action_deviation_threshold for _, d, p in out_metrics if p)
            and confidence >= 0.8
        ):
            reasons.append("persistent_large_single_metric")
            return ClassificationResult(
                state_level="ACTION_REQUIRED",
                requires_response=True,
                additional_observation_required=False,
                analysis_confidence=analysis_conf,
                warnings=warnings,
                reasons=reasons,
            )

        if medium or out_metrics:
            reasons.append("out_of_range_or_moderate_deviation")
            return ClassificationResult(
                state_level="WATCH",
                requires_response=False,
                additional_observation_required=True,
                analysis_confidence=analysis_conf,
                warnings=warnings,
                reasons=reasons,
            )

        return ClassificationResult(
            state_level="NORMAL",
            requires_response=False,
            additional_observation_required=False,
            analysis_confidence=analysis_conf,
            warnings=warnings,
            reasons=reasons,
        )


def suggest_contributing_factors(
    gaps: Dict[str, Dict[str, Any]],
    context: Optional[Dict[str, Any]],
) -> List[str]:
    """확정적 인과가 아닌 관찰 기반 후보 요인."""
    factors: List[str] = []
    ctx = context or {}
    if gaps.get("fatigue", {}).get("status") == "above_baseline":
        elapsed = ctx.get("elapsed_time_min")
        if elapsed is not None and float(elapsed) >= 20:
            factors.append(
                "세션 경과 시간이 길어 피로 지표 상승과 함께 관찰됨(인과 미확정)."
            )
    if gaps.get("cognitive_load", {}).get("status") == "above_baseline":
        diff = ctx.get("difficulty")
        if diff is not None and float(diff) >= 0.7:
            factors.append(
                "콘텐츠 난이도가 높은 조건에서 인지 부하 상승이 함께 관찰됨(인과 미확정)."
            )
    if gaps.get("attention", {}).get("status") == "below_baseline":
        vis = ctx.get("visual_complexity")
        if vis is not None and float(vis) >= 0.7:
            factors.append(
                "시각 복잡도가 높은 조건에서 주의 지표 하락이 함께 관찰됨(인과 미확정)."
            )
    return factors
