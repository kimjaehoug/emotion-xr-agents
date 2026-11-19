"""응답 정책(response_policies) 검증.

Qwen(또는 Fallback)이 산출한 route가 현재 state_level에서 허용되는지,
분석 신뢰도가 정책 최소 기준을 만족하는지 확인한다.
"""

from __future__ import annotations

from typing import Any, Dict, List


def validate_policy(
    *,
    state_level: str,
    confidence: float,
    route: str,
    policies: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    matching = [p for p in policies if p.get("state_level") == state_level]
    if not matching:
        # 정책이 정의되지 않은 상태수준은 보수적으로 통과시키되 상위 로직에서 경고 처리 가능.
        return errors

    policy = matching[0]
    min_confidence = float(policy.get("min_confidence", 0.0))
    if confidence < min_confidence:
        errors.append(
            f"분석 신뢰도({confidence:.2f})가 정책 '{policy.get('policy_key')}' "
            f"최소 기준({min_confidence:.2f})보다 낮습니다."
        )

    allowed_routes = policy.get("allowed_routes") or []
    if allowed_routes and route not in allowed_routes:
        errors.append(
            f"라우트 '{route}'는 상태수준 '{state_level}' 정책에서 허용되지 않습니다 "
            f"(허용: {allowed_routes})."
        )
    return errors
