"""세부 감정 → 7대 기본감정 매핑 에이전트."""

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


class MapperAgent:
    """분류된 감정을 7대 기본감정으로 매핑."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.seven_labels: list[str] = data["seven_basic"]["labels"]
        self.reference_mapping: dict[str, str] = data["reference_mapping_to_seven"]
        self.default_memory = load_default_mapping_memory()

    def map_to_seven(
        self,
        text: str,
        classification: dict[str, Any],
        mapping_memory: str | None = None,
        memory_hints: str = "",
    ) -> dict[str, Any]:
        kote = classification.get("kote_44", {})
        eighteen = classification.get("eighteen", {})
        memory = (mapping_memory or self.default_memory).strip()
        memory_for_prompt = memory if len(memory) <= 2500 else memory[:2500] + "\n...(생략)"

        reference_rows = []
        seen = set()
        for label in [
            kote.get("primary", ""),
            *kote.get("secondary", []),
            eighteen.get("primary", ""),
            *eighteen.get("secondary", []),
        ]:
            if label and label not in seen and label in self.reference_mapping:
                seen.add(label)
                reference_rows.append({
                    "source_label": label,
                    "reference_mapped_to": self.reference_mapping[label],
                })

        system_prompt = f"""감정 매핑기. 세부감정을 7대로 변환. JSON만. 문장 짧게.

7대: {json.dumps(self.seven_labels, ensure_ascii=False)}

출력:
{{
  "final_emotion":"7대중하나",
  "confidence":0.0,
  "summary":"한줄요약",
  "applied_rules":["적용규칙1","규칙2"],
  "process":[{{"title":"무엇을 했는지","finding":"결과"}}],
  "mapping_details":[
    {{"source_taxonomy":"kote_44","source_label":"...","mapped_to":"...","role":"primary","why":"한줄"}}
  ],
  "key_reasons":["근거1","근거2"],
  "rejected":[{{"emotion":"...","why":"한줄"}}],
  "rule_checks":[
    {{"rule":"메모리 규칙 요약","status":"준수|위반|예외","evidence":"한줄"}}
  ]
}}"""

        user_prompt = f"""[매핑기준]
{memory_for_prompt}

[원문] {text}

[KOTE] primary={kote.get('primary')} secondary={kote.get('secondary')} conf={kote.get('confidence')} why={kote.get('reasoning')}
[18대] primary={eighteen.get('primary')} secondary={eighteen.get('secondary')} conf={eighteen.get('confidence')} why={eighteen.get('reasoning')}
[참고테이블] {json.dumps(reference_rows, ensure_ascii=False)}
[사례메모리] (유사 과거 사례·교정 이력. 검증됨 사례는 강한 근거)
{memory_hints or "없음"}

규칙: process 3개(title+finding 둘 다 필수). key_reasons 2개 이상(비우지 말 것). rejected 1~2개(why 필수). rule_checks 2~4개. mapping_details primary 포함. 장문 금지. JSON만."""

        result = self.llm.chat_json(system_prompt, user_prompt, temperature=0.1)
        validated = self._validate(result)
        validated["mapping_memory_used"] = memory
        return validated

    def _validate(self, result: dict[str, Any]) -> dict[str, Any]:
        final = str(result.get("final_emotion", "중립"))
        if final not in self.seven_labels:
            final = self.reference_mapping.get(final, "중립")
            if final not in self.seven_labels:
                final = "중립"

        process_raw = result.get("process", [])
        if not isinstance(process_raw, list):
            process_raw = []
        process = []
        for i, item in enumerate(process_raw[:5], start=1):
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("phase") or "").strip()
                finding = str(item.get("finding") or item.get("conclusion") or item.get("description") or "").strip()
                if not title:
                    title = finding or f"{i}번째 판단"
                    finding = finding if title != finding else ""
            else:
                title = str(item).strip()
                finding = ""
            process.append({
                "phase": title,
                "actions": [],
                "observations": [],
                "conclusion": finding,
            })

        details_in = result.get("mapping_details", [])
        if not isinstance(details_in, list):
            details_in = []
        cleaned_details = []
        for item in details_in:
            if not isinstance(item, dict):
                continue
            mapped_to = item.get("mapped_to", "")
            if mapped_to not in self.seven_labels:
                mapped_to = self.reference_mapping.get(str(item.get("source_label", "")), final)
            cleaned_details.append({
                "source_taxonomy": item.get("source_taxonomy", ""),
                "source_label": item.get("source_label", ""),
                "mapped_to": mapped_to if mapped_to in self.seven_labels else final,
                "role": item.get("role", "primary"),
                "reference_hint": self.reference_mapping.get(str(item.get("source_label", "")), ""),
                "rationale": str(item.get("why") or item.get("rationale") or ""),
            })

        applied_rules = result.get("applied_rules") or result.get("applied_memory_rules") or []
        if not isinstance(applied_rules, list):
            applied_rules = [str(applied_rules)] if applied_rules else []

        key_reasons = result.get("key_reasons", [])
        if not isinstance(key_reasons, list):
            key_reasons = [str(key_reasons)] if key_reasons else []
        key_reasons = [str(x).strip() for x in key_reasons if str(x).strip()]

        summary = str(result.get("summary", "")).strip()
        # LLM이 근거를 비워 보내면 다른 필드에서 채움
        if not key_reasons:
            for d in cleaned_details:
                if d.get("rationale"):
                    key_reasons.append(
                        f"{d.get('source_label')}→{d.get('mapped_to')}: {d['rationale']}"
                    )
            for rule in applied_rules:
                if rule:
                    key_reasons.append(f"적용 규칙: {rule}")
            for p in process:
                if p.get("conclusion"):
                    key_reasons.append(f"{p.get('phase')}: {p['conclusion']}")
            if summary:
                key_reasons.append(summary)
        key_reasons = key_reasons[:5]

        rejected = result.get("rejected", [])
        if not isinstance(rejected, list):
            rejected = []
        rejected_alts = []
        for r in rejected[:3]:
            if isinstance(r, dict):
                why = str(r.get("why") or r.get("why_rejected") or "").strip()
                emo = str(r.get("emotion", "")).strip()
                if emo:
                    rejected_alts.append({
                        "emotion": emo,
                        "why_rejected": why or "최종 감정과 덜 맞음",
                    })

        # 탈락 후보가 없으면 참고매핑 기반 대안을 하나 보강
        if not rejected_alts and cleaned_details:
            for d in cleaned_details:
                hint = d.get("reference_hint") or ""
                if hint and hint != final and hint in self.seven_labels:
                    rejected_alts.append({
                        "emotion": hint,
                        "why_rejected": f"참고 매핑상 '{d.get('source_label')}'→{hint} 가능하나 최종은 {final}",
                    })
                    break

        support = key_reasons[:3] or ([summary] if summary else ["원문·분류 결과를 종합해 채택"])
        candidate_review = [{
            "emotion": final,
            "fit_level": "높음",
            "supporting_evidence": support,
            "opposing_evidence": [
                r["why_rejected"] for r in rejected_alts if r.get("why_rejected")
            ][:2] or ["유력한 반대 근거 없음"],
            "verdict": "채택",
        }]
        for r in rejected_alts:
            candidate_review.append({
                "emotion": r["emotion"],
                "fit_level": "낮음",
                "supporting_evidence": [f"대안 후보로 검토됨"],
                "opposing_evidence": [r["why_rejected"]],
                "verdict": "기각",
            })

        rule_checks = result.get("rule_checks", [])
        if not isinstance(rule_checks, list):
            rule_checks = []

        # process finding이 비면 title만이라도 보이게 유지, 없으면 합성
        if not process:
            process = [
                {"phase": "분류 결과 확인", "actions": [], "observations": [], "conclusion": summary or "분류 결과 반영"},
                {"phase": "매핑 기준 적용", "actions": [], "observations": [], "conclusion": "; ".join(applied_rules[:2]) or "메모리 규칙 적용"},
                {"phase": "최종 선택", "actions": [], "observations": [], "conclusion": f"{final} 선택"},
            ]
        else:
            for p in process:
                if not p.get("conclusion") and p.get("phase"):
                    p["conclusion"] = "해당 단계 수행"

        return {
            "final_emotion": final,
            "confidence": float(result.get("confidence", 0.5)),
            "summary": summary,
            "applied_memory_rules": [str(r) for r in applied_rules],
            "process": process,
            "candidate_review": candidate_review,
            "mapping_details": cleaned_details,
            "rule_checks": rule_checks,
            "final_decision": {
                "chosen_emotion": final,
                "key_reasons": key_reasons or support,
                "rejected_alternatives": rejected_alts,
                "confidence_basis": summary or (key_reasons[0] if key_reasons else ""),
            },
        }
