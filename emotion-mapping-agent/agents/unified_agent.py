"""분류 + 7대 매핑을 1회 LLM 호출로 처리."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_client import LLMClient

BASE_DIR = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = BASE_DIR / "taxonomies" / "emotions.json"
MEMORY_PATH = BASE_DIR / "taxonomies" / "mapping_memory.txt"


def load_default_mapping_memory() -> str:
    return MEMORY_PATH.read_text(encoding="utf-8").strip()


class UnifiedEmotionAgent:
    """문장 → KOTE44/18대 분류 → 7대 매핑 (단일 LLM 호출)."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.kote_labels: list[str] = data["kote_44"]["labels"]
        self.eighteen_labels: list[str] = data["eighteen"]["labels"]
        self.seven_labels: list[str] = data["seven_basic"]["labels"]
        self.reference_mapping: dict[str, str] = data["reference_mapping_to_seven"]
        self.default_memory = load_default_mapping_memory()

    def analyze(
        self,
        text: str,
        mapping_memory: str | None = None,
    ) -> dict[str, Any]:
        memory = (mapping_memory or self.default_memory).strip()
        # 프롬프트 폭주 방지: 너무 긴 메모리는 앞부분 우선
        memory_for_prompt = memory if len(memory) <= 2500 else memory[:2500] + "\n...(생략)"

        system_prompt = f"""한국어 감정 분석기. 문장을 분류하고 7대 감정으로 매핑한다.
반드시 JSON만 출력. 설명 문단/마크다운 금지. 각 문자열은 짧게(한 줄).

7대: {json.dumps(self.seven_labels, ensure_ascii=False)}
KOTE라벨 중 선택: {json.dumps(self.kote_labels, ensure_ascii=False)}
18대라벨 중 선택: {json.dumps(self.eighteen_labels, ensure_ascii=False)}

출력스키마:
{{
  "key_phrases": ["단서1","단서2"],
  "valence": "긍정|부정|혼합|중립",
  "arousal": "높음|중간|낮음",
  "process": ["1) ...","2) ...","3) ...","4) ..."],
  "kote_44": {{"primary":"...","secondary":[],"confidence":0.0,"why":"..."}},
  "eighteen": {{"primary":"...","secondary":[],"confidence":0.0,"why":"..."}},
  "applied_rules": ["적용규칙1","규칙2"],
  "mapping_details": [
    {{"source_taxonomy":"kote_44","source_label":"...","mapped_to":"...","role":"primary","why":"..."}}
  ],
  "final_emotion":"7대중하나",
  "confidence":0.0,
  "summary":"한줄요약",
  "key_reasons":["근거1","근거2"],
  "rejected":[{{"emotion":"...","why":"..."}}]
}}"""

        user_prompt = f"""문장: {text}

[매핑기준]
{memory_for_prompt}

요구:
- process 3~5개, 각 1문장
- secondary 0~1개
- rejected는 유력 대안 1~2개만
- 장문 금지, JSON만"""

        raw = self.llm.chat_json(system_prompt, user_prompt, temperature=0.1)
        return self._shape(text, memory, raw)

    def _shape(self, text: str, memory: str, raw: dict[str, Any]) -> dict[str, Any]:
        kote = self._validate_tax(raw.get("kote_44", {}), self.kote_labels, "없음")
        eighteen = self._validate_tax(raw.get("eighteen", {}), self.eighteen_labels, "중립")

        process_raw = raw.get("process", [])
        if not isinstance(process_raw, list):
            process_raw = []
        analysis_process = []
        for i, item in enumerate(process_raw[:6], start=1):
            if isinstance(item, dict):
                analysis_process.append({
                    "step": i,
                    "title": str(item.get("title") or item.get("phase") or f"단계 {i}"),
                    "description": str(item.get("description") or item.get("actions") or ""),
                    "finding": str(item.get("finding") or item.get("conclusion") or ""),
                })
            else:
                analysis_process.append({
                    "step": i,
                    "title": f"단계 {i}",
                    "description": str(item),
                    "finding": "",
                })

        final = str(raw.get("final_emotion", "중립"))
        if final not in self.seven_labels:
            # 참고 테이블로 보정
            hint = self.reference_mapping.get(kote["primary"]) or self.reference_mapping.get(eighteen["primary"])
            final = hint if hint in self.seven_labels else "중립"

        details_in = raw.get("mapping_details", [])
        if not isinstance(details_in, list):
            details_in = []
        mapping_details = []
        for item in details_in:
            if not isinstance(item, dict):
                continue
            mapped_to = item.get("mapped_to", "")
            if mapped_to not in self.seven_labels:
                mapped_to = self.reference_mapping.get(str(item.get("source_label", "")), mapped_to)
            mapping_details.append({
                "source_taxonomy": item.get("source_taxonomy", ""),
                "source_label": item.get("source_label", ""),
                "mapped_to": mapped_to if mapped_to in self.seven_labels else final,
                "role": item.get("role", "primary"),
                "reference_hint": self.reference_mapping.get(str(item.get("source_label", "")), ""),
                "rationale": item.get("why") or item.get("rationale") or "",
            })

        # 매핑 디테일이 없으면 참고 테이블로 채움
        if not mapping_details:
            for tax, block in (("kote_44", kote), ("eighteen", eighteen)):
                label = block["primary"]
                mapping_details.append({
                    "source_taxonomy": tax,
                    "source_label": label,
                    "mapped_to": self.reference_mapping.get(label, final),
                    "role": "primary",
                    "reference_hint": self.reference_mapping.get(label, ""),
                    "rationale": block.get("reasoning", ""),
                })

        applied_rules = raw.get("applied_rules") or raw.get("applied_memory_rules") or []
        if not isinstance(applied_rules, list):
            applied_rules = [str(applied_rules)]

        key_reasons = raw.get("key_reasons", [])
        if not isinstance(key_reasons, list):
            key_reasons = [str(key_reasons)] if key_reasons else []

        rejected = raw.get("rejected") or []
        if not isinstance(rejected, list):
            rejected = []
        rejected_alts = []
        for r in rejected:
            if isinstance(r, dict):
                rejected_alts.append({
                    "emotion": r.get("emotion", ""),
                    "why_rejected": r.get("why") or r.get("why_rejected") or "",
                })

        # 후보 검토는 최종+기각만 간단히 구성 (장문 생성 유도 안 함)
        candidate_review = [{
            "emotion": final,
            "fit_level": "높음",
            "supporting_evidence": key_reasons[:3] or [str(raw.get("summary", ""))],
            "opposing_evidence": [],
            "verdict": "채택",
        }]
        for r in rejected_alts[:3]:
            candidate_review.append({
                "emotion": r["emotion"],
                "fit_level": "낮음",
                "supporting_evidence": [],
                "opposing_evidence": [r["why_rejected"]],
                "verdict": "기각",
            })

        mapping_process = []
        for i, item in enumerate(process_raw[:6], start=1):
            text_item = item if not isinstance(item, dict) else (
                item.get("conclusion") or item.get("description") or item.get("phase") or str(item)
            )
            mapping_process.append({
                "phase": f"단계 {i}",
                "actions": [str(text_item)],
                "observations": [],
                "conclusion": str(text_item),
            })

        classification = {
            "text_analysis": {
                "key_phrases": raw.get("key_phrases", []),
                "speaker_intent": str(raw.get("summary", "")),
                "valence": raw.get("valence", ""),
                "arousal": raw.get("arousal", ""),
            },
            "analysis_process": analysis_process,
            "kote_44": kote,
            "eighteen": eighteen,
        }

        mapping = {
            "final_emotion": final,
            "confidence": float(raw.get("confidence", 0.7)),
            "summary": str(raw.get("summary", "")),
            "applied_memory_rules": [str(x) for x in applied_rules],
            "process": mapping_process,
            "candidate_review": candidate_review,
            "mapping_details": mapping_details,
            "final_decision": {
                "chosen_emotion": final,
                "key_reasons": [str(x) for x in key_reasons],
                "rejected_alternatives": rejected_alts,
                "confidence_basis": str(raw.get("summary", "")),
            },
            "mapping_memory_used": memory,
        }

        return {
            "text": text,
            "classification": classification,
            "mapping": mapping,
        }

    def _validate_tax(
        self,
        block: Any,
        labels: list[str],
        fallback: str,
    ) -> dict[str, Any]:
        if not isinstance(block, dict):
            block = {}
        primary = block.get("primary", fallback)
        if primary not in labels:
            primary = self._closest(str(primary), labels) or fallback
        secondary = [
            s for s in block.get("secondary", [])
            if s in labels and s != primary
        ][:1]
        return {
            "primary": primary,
            "secondary": secondary,
            "confidence": float(block.get("confidence", 0.6)),
            "reasoning": str(block.get("why") or block.get("reasoning") or ""),
            "label_considerations": [],
        }

    @staticmethod
    def _closest(label: str, labels: list[str]) -> str | None:
        for candidate in labels:
            if label in candidate or candidate in label:
                return candidate
        return None
