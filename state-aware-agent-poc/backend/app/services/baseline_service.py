"""Baseline 생성 / 조회 서비스."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.constants import GROUP_DEFAULT_BASELINE, METRIC_NAMES
from app.models import Baseline, BaselineObservation
from app.repositories.baseline_repo import BaselineRepository
from app.schemas import BaselineObservationCreate, BaselineResponse, MetricBounds
from app.services.stats import is_extreme_value, reliability_score, robust_bounds


class BaselineService:
    def __init__(self, db: Session, settings: Optional[Settings] = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.repo = BaselineRepository(db)

    def add_observation(
        self, user_id: str, payload: BaselineObservationCreate
    ) -> BaselineObservation:
        obs = BaselineObservation(
            user_id=user_id,
            session_id=payload.session_id,
            cognitive_load=payload.cognitive_load,
            attention=payload.attention,
            fatigue=payload.fatigue,
            confidence=payload.confidence,
            completeness=payload.completeness,
            is_normal_confirmed=payload.is_normal_confirmed,
        )
        return self.repo.add_observation(obs)

    def build_baseline(self, user_id: str) -> Baseline:
        observations = self.repo.list_observations(
            user_id,
            normal_only=True,
            quality_min=0.8,
        )
        if len(observations) < self.settings.min_baseline_samples:
            raise ValueError(
                f"Baseline 생성에는 정상 확인 샘플이 최소 "
                f"{self.settings.min_baseline_samples}개 필요합니다. "
                f"현재: {len(observations)}개"
            )

        metric_values: Dict[str, List[float]] = {m: [] for m in METRIC_NAMES}
        for obs in observations:
            for m in METRIC_NAMES:
                metric_values[m].append(getattr(obs, m))

        # 극단값 제외 후 재계산
        filtered: Dict[str, List[float]] = {}
        for m, vals in metric_values.items():
            kept = [v for v in vals if not is_extreme_value(v, vals)]
            filtered[m] = kept if len(kept) >= self.settings.min_baseline_samples else vals

        bounds: Dict[str, tuple[float, float, float]] = {}
        for m in METRIC_NAMES:
            bounds[m] = robust_bounds(
                filtered[m], trim_ratio=self.settings.baseline_trim_ratio
            )

        sample_count = len(observations)
        rel = reliability_score(sample_count, self.settings.min_baseline_samples)

        # 기존 Baseline과 과도한 드리프트면 보류 플래그는 호출측에서 처리 가능
        existing = self.repo.get_active_baseline(user_id)
        if existing is not None:
            drifts = []
            for m in METRIC_NAMES:
                old = getattr(existing, f"{m}_center")
                new = bounds[m][0]
                drifts.append(abs(new - old))
            max_drift = max(drifts) if drifts else 0.0
            if max_drift > self.settings.baseline_update_max_drift:
                raise ValueError(
                    f"기존 Baseline과 편차({max_drift:.3f})가 허용치"
                    f"({self.settings.baseline_update_max_drift})를 초과하여 "
                    "자동 갱신을 보류합니다. 수동 검토가 필요합니다."
                )

        version = self.repo.next_version(user_id)
        self.repo.deactivate_all(user_id)
        baseline = Baseline(
            user_id=user_id,
            version=version,
            cognitive_load_center=bounds["cognitive_load"][0],
            cognitive_load_lower=bounds["cognitive_load"][1],
            cognitive_load_upper=bounds["cognitive_load"][2],
            attention_center=bounds["attention"][0],
            attention_lower=bounds["attention"][1],
            attention_upper=bounds["attention"][2],
            fatigue_center=bounds["fatigue"][0],
            fatigue_lower=bounds["fatigue"][1],
            fatigue_upper=bounds["fatigue"][2],
            sample_count=sample_count,
            reliability=rel,
            is_active=True,
        )
        return self.repo.save_baseline(baseline)

    def get_active(self, user_id: str) -> Optional[Baseline]:
        return self.repo.get_active_baseline(user_id)

    def to_response(self, baseline: Baseline) -> BaselineResponse:
        return BaselineResponse(
            user_id=baseline.user_id,
            version=baseline.version,
            cognitive_load=MetricBounds(
                center=baseline.cognitive_load_center,
                lower=baseline.cognitive_load_lower,
                upper=baseline.cognitive_load_upper,
            ),
            attention=MetricBounds(
                center=baseline.attention_center,
                lower=baseline.attention_lower,
                upper=baseline.attention_upper,
            ),
            fatigue=MetricBounds(
                center=baseline.fatigue_center,
                lower=baseline.fatigue_lower,
                upper=baseline.fatigue_upper,
            ),
            sample_count=baseline.sample_count,
            reliability=baseline.reliability,
            is_active=baseline.is_active,
            created_at=baseline.created_at,
            updated_at=baseline.updated_at,
        )

    def baseline_dict_for_agent(
        self, user_id: str
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """Agent용 Baseline dict와 source 반환."""
        active = self.get_active(user_id)
        if active is not None:
            return (
                {
                    "version": active.version,
                    "reliability": active.reliability,
                    "sample_count": active.sample_count,
                    "cognitive_load": {
                        "center": active.cognitive_load_center,
                        "lower": active.cognitive_load_lower,
                        "upper": active.cognitive_load_upper,
                    },
                    "attention": {
                        "center": active.attention_center,
                        "lower": active.attention_lower,
                        "upper": active.attention_upper,
                    },
                    "fatigue": {
                        "center": active.fatigue_center,
                        "lower": active.fatigue_lower,
                        "upper": active.fatigue_upper,
                    },
                },
                "personal",
            )

        if self.settings.use_group_default_baseline:
            return dict(GROUP_DEFAULT_BASELINE), "group_default"
        return None, "none"

    def observation_count(self, user_id: str) -> int:
        return len(self.repo.list_observations(user_id, normal_only=True))
