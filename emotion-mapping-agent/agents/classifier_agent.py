"""다중 감정 분류 에이전트."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_client import LLMClient

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "taxonomies" / "emotions.json"


class ClassifierAgent:
    """입력 문장을 44대(KOTE), 18대 감정으로 분류."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
            self.taxonomies = json.load(f)

    def classify(self, text: str) -> dict[str, Any]:
        kote_labels = self.taxonomies["kote_44"]["labels"]
        eighteen_labels = self.taxonomies["eighteen"]["labels"]

        system_prompt = f"""한국어 감정 분류기. JSON만 출력. 문장은 짧게.

KOTE 라벨: {json.dumps(kote_labels, ensure_ascii=False)}
18대 라벨: {json.dumps(eighteen_labels, ensure_ascii=False)}

출력:
{{
  "key_phrases": ["단서1","단서2"],
  "valence": "긍정|부정|혼합|중립",
  "arousal": "높음|중간|낮음",
  "process": [
    {{"title":"무엇을 봤는지","finding":"그래서 알게 된 것"}}
  ],
  "kote_44": {{"primary":"...","secondary":[],"confidence":0.0,"why":"한줄 근거"}},
  "eighteen": {{"primary":"...","secondary":[],"confidence":0.0,"why":"한줄 근거"}},
  "alternatives": [{{"label":"탈락후보","why":"한줄"}}]
}}"""

        user_prompt = f"""문장: {text}

규칙: primary는 라벨 목록에서만. secondary 0~1개. process는 3개 객체(title+finding 둘 다 채움). alternatives 1~2개. 장문 금지."""

        result = self.llm.chat_json(system_prompt, user_prompt, temperature=0.1)
        return self._validate(result, kote_labels, eighteen_labels)

    def _validate(
        self,
        result: dict[str, Any],
        kote_labels: list[str],
        eighteen_labels: list[str],
    ) -> dict[str, Any]:
        process_raw = result.get("process", [])
        if not isinstance(process_raw, list):
            process_raw = []
        analysis_process = []
        for i, item in enumerate(process_raw[:5], start=1):
            analysis_process.append(_normalize_process_item(i, item))

        alternatives = result.get("alternatives", [])
        if not isinstance(alternatives, list):
            alternatives = []

        validated: dict[str, Any] = {
            "text_analysis": {
                "key_phrases": result.get("key_phrases", []) if isinstance(result.get("key_phrases"), list) else [],
                "speaker_intent": "",
                "valence": str(result.get("valence", "")),
                "arousal": str(result.get("arousal", "")),
            },
            "analysis_process": analysis_process,
        }

        for key, labels in [("kote_44", kote_labels), ("eighteen", eighteen_labels)]:
            block = result.get(key, {})
            if not isinstance(block, dict):
                block = {}
            primary = block.get("primary", "없음" if key == "kote_44" else "중립")
            if primary not in labels:
                primary = self._closest(str(primary), labels)
            secondary = [
                s for s in block.get("secondary", [])
                if s in labels and s != primary
            ][:1]
            considerations = [
                {"label": a.get("label", ""), "why": a.get("why", "")}
                for a in alternatives
                if isinstance(a, dict)
            ][:2]

            validated[key] = {
                "primary": primary,
                "secondary": secondary,
                "confidence": float(block.get("confidence", 0.5)),
                "reasoning": str(block.get("why") or block.get("reasoning") or ""),
                "label_considerations": considerations,
            }
        return validated

    @staticmethod
    def _closest(label: str, labels: list[str]) -> str:
        for candidate in labels:
            if label in candidate or candidate in label:
                return candidate
        return labels[-1]


def _normalize_process_item(i: int, item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("phase") or "").strip()
        finding = str(
            item.get("finding")
            or item.get("conclusion")
            or item.get("description")
            or ""
        ).strip()
        if not title and finding:
            title, finding = finding, ""
        return {
            "step": i,
            "title": title or f"{i}번째 관찰",
            "description": "",
            "finding": finding,
        }
    text = str(item).strip()
    text = _strip_num_prefix(text)
    return {
        "step": i,
        "title": text or f"{i}번째 관찰",
        "description": "",
        "finding": "",
    }


def _strip_num_prefix(text: str) -> str:
    import re

    return re.sub(r"^\s*(?:step\s*)?\d+\s*[.)、:：\-)]\s*", "", text, flags=re.I).strip()
