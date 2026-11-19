"""Qwen 계획 생성 프롬프트 빌더."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.core.config import get_settings

SYSTEM_PROMPT = """당신은 XR 세션 제어 계획 Agent다.
규칙:
1. JSON 객체 하나만 출력. 설명/마크다운/코드펜스/<think> 금지.
2. goal, route, action_type은 허용 enum만 사용.
3. UPDATE_XR_PARAMETER의 delta는 -0.2~0.2.
4. 의료 진단/치료 표현 금지.
5. rationale은 짧은 한국어.
6. memory_hints.avoid_actions의 행동은 피하고, effective_procedures를 우선 고려.

올바른 출력 예시:
{"goal":"REDUCE_COGNITIVE_BURDEN","route":"XR_OPTIMIZATION","actions":[{"action_type":"UPDATE_XR_PARAMETER","xr_parameter":"visual_complexity","target_content_id":null,"delta":-0.15,"requires_confirmation":false,"rationale":"시각 복잡도 완화","confidence":0.8}],"confidence":0.8,"narrative":"시각 자극을 낮춥니다."}
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def _compact_report(state_report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "state_report_id": state_report.get("state_report_id"),
        "state_level": state_report.get("state_level"),
        "analysis_confidence": state_report.get("analysis_confidence"),
        "requires_response": state_report.get("requires_response"),
        "additional_observation_required": state_report.get("additional_observation_required"),
        "cognitive_gap": state_report.get("cognitive_gap"),
        "context_summary": state_report.get("context_summary"),
        "possible_contributing_factors": state_report.get("possible_contributing_factors"),
        "warnings": state_report.get("warnings"),
        "narrative_observation": state_report.get("narrative_observation"),
    }


def _compact_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    """작업 메모리를 토큰 절약형으로 요약 (효과 좋은 절차 우선, 회피 행동, 경고)."""
    return {
        "effective_procedures": [
            {"key": p.get("key"), "effectiveness": (p.get("value") or {}).get("effectiveness"), "n": (p.get("value") or {}).get("n")}
            for p in (memory.get("procedures") or [])[:3]
        ],
        "avoid_actions": memory.get("avoid_signatures") or [],
        "alerts": [a.get("message") for a in (memory.get("proactive_alerts") or [])][:3],
    }


def build_user_prompt(context: Dict[str, Any]) -> str:
    settings = get_settings()
    # 스키마 전체를 넣으면 토큰이 커져 로컬 9B가 느려지므로 최소 예시만 전달
    compact_schema = {
        "goal": "REDUCE_COGNITIVE_BURDEN|SUPPORT_ATTENTION_RECOVERY|REDUCE_ACCUMULATED_FATIGUE|REDUCE_CONTENT_STIMULATION|MAINTAIN_CURRENT_STATE|CONTINUE_OBSERVATION",
        "route": "NO_ACTION|OBSERVATION|CONTENT_RECOMMENDATION|XR_OPTIMIZATION|BREAK_SUGGESTION",
        "actions": [
            {
                "action_type": "UPDATE_XR_PARAMETER|RECOMMEND_CONTENT|SUGGEST_BREAK|OBSERVE|KEEP_CURRENT_STATE",
                "xr_parameter": "visual_complexity|audio_stimulation|interaction_density|null",
                "target_content_id": "string|null",
                "delta": "number|null (-0.2~0.2)",
                "requires_confirmation": "boolean",
                "rationale": "string",
                "confidence": "0~1",
            }
        ],
        "confidence": "0~1",
        "narrative": "string",
    }
    contents = (context.get("contents") or [])[: settings.content_candidate_limit]
    payload = {
        "state_report": _compact_report(context.get("state_report") or {}),
        "user_profile": context.get("profile") or {},
        "allowed_policies": context.get("policies") or [],
        "allowed_actions": context.get("actions") or [],
        "recommendable_contents": contents,
        "current_xr_parameters": context.get("xr_state") or {},
        "constraints": {"max_parameter_delta": settings.xr_max_parameter_delta},
        "memory_hints": _compact_memory(context.get("memory") or {}),
        "output_shape": compact_schema,
    }
    lines = [
        "/no_think",
        "아래 입력을 보고 output_shape에 맞는 JSON 객체 하나만 출력하세요.",
        "설명·마크다운·코드펜스 금지.",
        "",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        "",
        "JSON:",
    ]
    return "\n".join(lines)


def build_repair_prompt(*, user_prompt: str, raw_output: str, errors: list[str]) -> str:
    lines = [
        user_prompt,
        "",
        "--- 이전 응답이 검증에 실패했습니다 ---",
        "이전 응답:",
        raw_output[:2000],
        "",
        "검증 오류:",
        "\n".join(f"- {e}" for e in errors),
        "",
        "위 오류를 모두 해결하여 output_json_schema를 만족하는 JSON 객체만 다시 출력하세요.",
    ]
    return "\n".join(lines)
