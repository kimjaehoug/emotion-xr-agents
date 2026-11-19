"""Ollama Qwen3.5 9B 연동 — 선택적 서술 관찰 생성.

16GB RAM 환경에서 KV 캐시 여유를 위해 num_ctx=4096을 사용한다.
LLM 실패 시에도 결정적 파이프라인은 정상 동작한다.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

STATE_LEVEL_KO = {
    "NORMAL": "정상",
    "WATCH": "주의",
    "ACTION_REQUIRED": "조치 필요",
    "UNKNOWN": "미확인",
}

METRIC_KO = {
    "cognitive_load": "인지 부하",
    "attention": "주의 집중",
    "fatigue": "피로",
}

STATUS_KO = {
    "above_baseline": "기준 초과",
    "below_baseline": "기준 미만",
    "within_range": "정상 범위",
    "unknown": "미확인",
}

TREND_KO = {
    "increasing": "상승",
    "decreasing": "하락",
    "stable": "안정",
    "insufficient_data": "데이터 부족",
}


class OllamaLLMService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.ollama_enabled

    def generate_narrative(
        self,
        *,
        state_level: str,
        cognitive_gap: Dict[str, Any],
        warnings: list[str],
        context_summary: Optional[Dict[str, Any]] = None,
        baseline_source: Optional[str] = None,
        analysis_confidence: Optional[float] = None,
        contributing_factors: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        prompt = self._build_prompt(
            state_level=state_level,
            cognitive_gap=cognitive_gap,
            warnings=warnings,
            context_summary=context_summary or {},
            baseline_source=baseline_source or "none",
            analysis_confidence=analysis_confidence,
            contributing_factors=contributing_factors or [],
        )
        try:
            with httpx.Client(timeout=self.settings.ollama_timeout_sec) as client:
                payload: Dict[str, Any] = {
                    "model": self.settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": self.settings.ollama_num_ctx,
                        "temperature": 0.35,
                        "num_predict": 420,
                    },
                }
                resp = client.post(
                    f"{self.settings.ollama_base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("response") or "").strip()
                for marker in ("</think>", "</thinking>"):
                    if marker in text:
                        text = text.split(marker)[-1].strip()
                if text.startswith("<think>"):
                    text = ""
                return text[:1600] if text else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama 호출 실패, 서술 관찰을 생략합니다: %s", exc)
            return None

    def _compact_gap(self, cognitive_gap: Dict[str, Any]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {}
        for key, gap in cognitive_gap.items():
            if not isinstance(gap, dict):
                continue
            compact[METRIC_KO.get(key, key)] = {
                "현재값": gap.get("current"),
                "기준값": gap.get("baseline"),
                "편차": gap.get("deviation"),
                "상태": STATUS_KO.get(str(gap.get("status")), gap.get("status")),
                "추세": TREND_KO.get(str(gap.get("trend")), gap.get("trend")),
                "지속여부": bool(gap.get("persistent")),
                "정상범위내": gap.get("in_normal_range"),
            }
        return compact

    def _build_prompt(
        self,
        *,
        state_level: str,
        cognitive_gap: Dict[str, Any],
        warnings: list[str],
        context_summary: Dict[str, Any],
        baseline_source: str,
        analysis_confidence: Optional[float],
        contributing_factors: List[str],
    ) -> str:
        level_ko = STATE_LEVEL_KO.get(state_level, state_level)
        gap_ko = self._compact_gap(cognitive_gap)
        payload = {
            "상태수준": level_ko,
            "상태수준_코드": state_level,
            "기준선출처": baseline_source,
            "분석신뢰도": analysis_confidence,
            "지표비교": gap_ko,
            "콘텐츠조건": context_summary,
            "경고": warnings,
            "가능기여요인_후보": contributing_factors,
        }
        lines = [
            "/no_think",
            "당신은 연구용 상태 인지 시스템의 관찰 보고서 작성기입니다.",
            "의료 진단, 치료 권고, 확정적 인과관계 표현을 사용하지 마세요.",
            "생각 과정은 출력하지 말고, 한국어 본문만 작성하세요.",
            "",
            "아래 구조로 4~6문장 분량의 서술 관찰을 작성하세요.",
            "1) 종합 상태: 상태 수준과 분석 신뢰도를 한 문장으로 설명",
            "2) 지표별 변화: 인지 부하·주의 집중·피로를 기준선·추세·지속성과 함께 구체적으로 서술",
            "3) 맥락 관찰: 콘텐츠 난이도·시각 복잡도·경과 시간 등과 함께 관찰된 점을 '함께 관찰됨' 수준으로만 언급",
            "4) 후속 관찰 포인트: 다음에 더 지켜보면 좋은 점을 한 문장으로 제안 (명령/처방 금지)",
            "",
            "입력 데이터(JSON):",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "",
            "서술 관찰:",
        ]
        return "\n".join(lines)

    def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.settings.ollama_base_url}/api/tags")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False
