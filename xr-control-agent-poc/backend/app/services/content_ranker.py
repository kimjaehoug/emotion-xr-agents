"""추천 콘텐츠 랭킹 서비스."""

from __future__ import annotations

from typing import Any, Dict, List


def rank_contents(
    *,
    contents: List[Dict[str, Any]],
    profile: Dict[str, Any],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """사용자 감각 민감도/금지 카테고리를 고려해 자극이 낮은 콘텐츠를 우선한다."""
    forbidden = set(profile.get("forbidden_categories") or [])
    sensitivities: Dict[str, float] = profile.get("sensitivities") or {}

    candidates = [c for c in contents if c.get("category") not in forbidden]

    def score(content: Dict[str, Any]) -> float:
        visual_penalty = float(content.get("visual_complexity", 0.5)) * (
            1.0 + float(sensitivities.get("visual_complexity", sensitivities.get("visual", 0.0)))
        )
        audio_penalty = float(content.get("audio_stimulation", 0.5)) * (
            1.0 + float(sensitivities.get("audio_stimulation", sensitivities.get("audio", 0.0)))
        )
        interaction_penalty = float(content.get("interaction_density", 0.5))
        difficulty_penalty = float(content.get("difficulty", 0.5))
        return visual_penalty + audio_penalty + interaction_penalty + difficulty_penalty

    ranked = sorted(candidates, key=score)
    return ranked[:top_k]
