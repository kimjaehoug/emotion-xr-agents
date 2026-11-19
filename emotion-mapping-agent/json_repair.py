"""LLM JSON 응답 보정."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_llm_json(text: str) -> dict[str, Any]:
    candidates = _extract_candidates(text)
    errors: list[str] = []
    for raw in candidates:
        for variant in _variants(raw):
            try:
                parsed = json.loads(variant)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    return parsed[0]
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
    hint = errors[-1] if errors else "unknown"
    raise ValueError(f"JSON 파싱 실패 ({hint}): {text[:240]}")


def _extract_candidates(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    out = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        out.append(text[start : end + 1])
    return out


def _variants(raw: str) -> list[str]:
    cleaned = raw.strip()
    cleaned = cleaned.replace("\ufeff", "")
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    # 트레일링 콤마
    no_trail = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    # 잘린 JSON 닫기
    closed = _close_truncated(no_trail)
    closed2 = _close_truncated(cleaned)
    variants = [cleaned, no_trail, closed, closed2]
    # 중복 제거, 빈 값 제외
    seen: set[str] = set()
    uniq: list[str] = []
    for item in variants:
        if item and item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _close_truncated(text: str) -> str:
    """토큰 제한으로 잘린 JSON의 괄호를 닫아 복구 시도."""
    in_str = False
    escape = False
    quote = ""
    stack: list[str] = []
    last_ok = 0
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
            last_ok = i
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
                last_ok = i

    if in_str:
        text += quote
    # 마지막 불완전 키/값 잘라내기
    trimmed = text.rstrip()
    if trimmed.endswith(","):
        trimmed = trimmed[:-1]
    elif trimmed.endswith(":"):
        trimmed += '""'
    trimmed += "".join(reversed(stack))
    return trimmed
