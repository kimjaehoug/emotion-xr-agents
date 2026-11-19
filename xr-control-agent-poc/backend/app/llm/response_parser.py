"""LLM 원시 출력에서 JSON을 추출하는 유틸."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think_tags(text: str) -> str:
    """Qwen `<think>...</think>` 추론 흔적 제거."""
    cleaned = _THINK_TAG_RE.sub("", text)
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1]
    return cleaned.strip()


def extract_json_block(text: str) -> str:
    """코드펜스(```json ... ```) 안의 내용을 우선 추출한다. 없으면 원문 반환."""
    cleaned = strip_think_tags(text)
    matches = _CODE_FENCE_RE.findall(cleaned)
    if matches:
        return matches[-1].strip()

    # 코드펜스가 없으면 첫 '{' 부터 마지막 '}' 까지를 시도한다.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned.strip()


def parse_json_response(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(파싱된 dict, 오류 메시지) 튜플 반환. 성공 시 오류는 None."""
    candidate = extract_json_block(text)
    data, err = _loads_json(candidate)
    if data is None:
        # trailing comma 등 흔한 문법 오류 보정 후 재시도
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        repaired = repaired.replace("'", '"')
        data, err2 = _loads_json(repaired)
        if data is None:
            return None, err or err2

    if not isinstance(data, dict):
        return None, "JSON 최상위 요소가 객체가 아닙니다."
    return normalize_plan_dict(data), None


def _loads_json(text: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"JSON 파싱 실패: {exc}"


_GOAL_ALIASES = {
    "REDUCE_COGNITIVE_LOAD": "REDUCE_COGNITIVE_BURDEN",
    "REDUCE_LOAD": "REDUCE_COGNITIVE_BURDEN",
    "COGNITIVE_BURDEN": "REDUCE_COGNITIVE_BURDEN",
    "ATTENTION_RECOVERY": "SUPPORT_ATTENTION_RECOVERY",
    "REDUCE_FATIGUE": "REDUCE_ACCUMULATED_FATIGUE",
    "FATIGUE": "REDUCE_ACCUMULATED_FATIGUE",
    "OBSERVE": "CONTINUE_OBSERVATION",
    "OBSERVATION": "CONTINUE_OBSERVATION",
    "KEEP": "MAINTAIN_CURRENT_STATE",
    "MAINTAIN": "MAINTAIN_CURRENT_STATE",
}

_ROUTE_ALIASES = {
    "XR": "XR_OPTIMIZATION",
    "CONTENT": "CONTENT_RECOMMENDATION",
    "RECOMMEND": "CONTENT_RECOMMENDATION",
    "BREAK": "BREAK_SUGGESTION",
    "REST": "BREAK_SUGGESTION",
    "NONE": "NO_ACTION",
    "KEEP": "NO_ACTION",
}

_ACTION_ALIASES = {
    "UPDATE_XR": "UPDATE_XR_PARAMETER",
    "UPDATE_PARAMETER": "UPDATE_XR_PARAMETER",
    "CHANGE_XR": "UPDATE_XR_PARAMETER",
    "RECOMMEND": "RECOMMEND_CONTENT",
    "BREAK": "SUGGEST_BREAK",
    "REST": "SUGGEST_BREAK",
    "KEEP": "KEEP_CURRENT_STATE",
}


def normalize_plan_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM이 흔히 틀리는 enum 별칭을 허용값으로 보정한다."""
    out = dict(data)
    goal = str(out.get("goal") or "").strip().upper()
    if goal in _GOAL_ALIASES:
        out["goal"] = _GOAL_ALIASES[goal]
    elif goal:
        out["goal"] = goal

    route = str(out.get("route") or "").strip().upper()
    if route in _ROUTE_ALIASES:
        out["route"] = _ROUTE_ALIASES[route]
    elif route:
        out["route"] = route

    actions = out.get("actions")
    if isinstance(actions, list):
        normalized_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            a = dict(action)
            at = str(a.get("action_type") or "").strip().upper()
            if at in _ACTION_ALIASES:
                a["action_type"] = _ACTION_ALIASES[at]
            elif at:
                a["action_type"] = at
            # selected_policy_code 등 여분 필드 제거는 pydantic이 무시
            normalized_actions.append(a)
        out["actions"] = normalized_actions
    return out
