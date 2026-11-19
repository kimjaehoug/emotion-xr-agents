"""Baseline 통계 유틸 (중앙값 + 절사평균, 극단값 제외)."""

from typing import List, Sequence, Tuple

import numpy as np


def _trim_values(values: Sequence[float], trim_ratio: float) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("값이 비어 있습니다.")
    if arr.size < 3 or trim_ratio <= 0:
        return np.sort(arr)
    k = int(np.floor(arr.size * trim_ratio))
    if k * 2 >= arr.size:
        k = max(0, (arr.size - 1) // 2)
    sorted_arr = np.sort(arr)
    if k == 0:
        return sorted_arr
    return sorted_arr[k : arr.size - k]


def robust_center(values: Sequence[float], trim_ratio: float = 0.1) -> float:
    """중앙값과 절사평균의 평균을 center로 사용."""
    trimmed = _trim_values(values, trim_ratio)
    median = float(np.median(trimmed))
    trimmed_mean = float(np.mean(trimmed))
    return float((median + trimmed_mean) / 2.0)


def robust_bounds(
    values: Sequence[float],
    trim_ratio: float = 0.1,
    iqr_multiplier: float = 1.5,
) -> Tuple[float, float, float]:
    """center, lower, upper 반환. IQR 기반 범위 + 절사."""
    trimmed = _trim_values(values, trim_ratio)
    center = robust_center(values, trim_ratio)
    q1 = float(np.percentile(trimmed, 25))
    q3 = float(np.percentile(trimmed, 75))
    iqr = max(q3 - q1, 0.05)
    lower = max(0.0, center - iqr_multiplier * iqr)
    upper = min(1.0, center + iqr_multiplier * iqr)
    # 최소 폭 보장
    if upper - lower < 0.1:
        lower = max(0.0, center - 0.05)
        upper = min(1.0, center + 0.05)
    return center, lower, upper


def is_extreme_value(value: float, values: Sequence[float], z_threshold: float = 2.5) -> bool:
    """극단값 여부 (MAD 기반)."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size < 3:
        return False
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    if mad < 1e-6:
        return abs(value - median) > 0.2
    modified_z = 0.6745 * (value - median) / mad
    return abs(modified_z) > z_threshold


def reliability_score(sample_count: int, min_samples: int = 3) -> float:
    """샘플 수 기반 신뢰도 (0~1)."""
    if sample_count <= 0:
        return 0.0
    return float(min(1.0, 0.5 + 0.5 * (sample_count / max(min_samples * 2, 1))))
