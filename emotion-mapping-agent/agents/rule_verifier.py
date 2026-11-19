"""매핑 기준 준수 여부를 규칙 기반으로 검증."""

from __future__ import annotations

import json
from typing import Any


class RuleVerifier:
    """LLM 출력과 참고 매핑 테이블을 대조해 규칙 준수를 채점."""

    def __init__(self, seven_labels: list[str], reference_mapping: dict[str, str]) -> None:
        self.seven_labels = seven_labels
        self.reference_mapping = reference_mapping

    def verify(
        self,
        text: str,
        classification: dict[str, Any],
        mapping: dict[str, Any],
        mapping_memory: str,
    ) -> dict[str, Any]:
        checks: list[dict[str, str]] = []
        final = mapping.get("final_emotion", "")
        kote = classification.get("kote_44", {})
        eighteen = classification.get("eighteen", {})

        checks.append(self._check_seven_range(final))
        checks.append(self._check_reference("KOTE 44", kote.get("primary", ""), final))
        checks.append(self._check_reference("18대", eighteen.get("primary", ""), final))
        checks.append(self._check_emotion_agreement(kote, eighteen, final))
        checks.append(self._check_primary_priority(kote, eighteen, mapping))
        checks.append(self._check_no_weight_word(mapping))
        checks.append(self._check_applied_rules_present(mapping))
        checks.append(self._check_exception_explained(kote, eighteen, final, mapping))

        # LLM이 보고한 규칙 점검이 있으면 합산
        for item in mapping.get("rule_checks") or []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or item.get("followed") or "")
            if status in ("true", "True", True):
                status = "준수"
            elif status in ("false", "False", False):
                status = "위반"
            if status not in ("준수", "위반", "예외", "해당없음"):
                status = "예외" if status else "해당없음"
            checks.append({
                "rule": str(item.get("rule") or item.get("name") or "메모리 규칙"),
                "status": status,
                "evidence": str(item.get("evidence") or item.get("note") or item.get("why") or ""),
                "source": "llm",
            })

        scored = [c for c in checks if c["status"] in ("준수", "위반")]
        passed = sum(1 for c in scored if c["status"] == "준수")
        total = len(scored) or 1
        score = round(100 * passed / total)
        if score >= 80:
            grade = "양호"
        elif score >= 60:
            grade = "보통"
        else:
            grade = "미흡"

        return {
            "score": score,
            "grade": grade,
            "summary": f"검증 {len(checks)}항목 중 준수 {passed}/{total} · {grade} ({score}%)",
            "checks": checks,
        }

    def _check_seven_range(self, final: str) -> dict[str, str]:
        ok = final in self.seven_labels
        return {
            "rule": "최종 감정은 7대 라벨 안에서만 선택",
            "status": "준수" if ok else "위반",
            "evidence": f"최종={final}" if ok else f"최종={final} (허용: {', '.join(self.seven_labels)})",
            "source": "system",
        }

    def _check_reference(self, source_name: str, primary: str, final: str) -> dict[str, str]:
        expected = self.reference_mapping.get(primary or "")
        if not primary or not expected:
            return {
                "rule": f"{source_name} 주감정 참고 매핑 대조",
                "status": "해당없음",
                "evidence": f"주감정={primary or '(없음)'}",
                "source": "system",
            }
        if expected == final:
            status, evidence = "준수", f"{primary} → {expected} 와 최종 {final} 일치"
        else:
            status, evidence = "예외", f"참고는 {primary} → {expected} 이나 최종은 {final} (문맥 예외인지 확인)"
        return {
            "rule": f"{source_name} 주감정 '{primary}'의 참고 매핑은 '{expected}'",
            "status": status,
            "evidence": evidence,
            "source": "system",
        }

    def _check_emotion_agreement(
        self,
        kote: dict[str, Any],
        eighteen: dict[str, Any],
        final: str,
    ) -> dict[str, str]:
        k_exp = self.reference_mapping.get(kote.get("primary", ""))
        e_exp = self.reference_mapping.get(eighteen.get("primary", ""))
        if not k_exp or not e_exp:
            return {
                "rule": "두 감정 참고매핑이 같으면 그 방향을 채택",
                "status": "해당없음",
                "evidence": "한쪽 참고매핑이 없음",
                "source": "system",
            }
        if k_exp != e_exp:
            return {
                "rule": "두 감정 참고매핑이 같으면 그 방향을 채택",
                "status": "해당없음",
                "evidence": f"KOTE→{k_exp}, 18대→{e_exp} 로 서로 다름 (충돌 규칙 적용 대상)",
                "source": "system",
            }
        ok = final == k_exp
        return {
            "rule": "두 감정 참고매핑이 같으면 그 방향을 강하게 채택",
            "status": "준수" if ok else "위반",
            "evidence": f"둘 다 {k_exp}인데 최종은 {final}" if not ok else f"둘 다 {k_exp}, 최종도 {final}",
            "source": "system",
        }

    def _check_primary_priority(
        self,
        kote: dict[str, Any],
        eighteen: dict[str, Any],
        mapping: dict[str, Any],
    ) -> dict[str, str]:
        details = mapping.get("mapping_details") or []
        primary_mapped = [
            d.get("mapped_to")
            for d in details
            if isinstance(d, dict) and d.get("role") == "primary"
        ]
        if not primary_mapped:
            return {
                "rule": "primary 감정을 secondary보다 우선",
                "status": "해당없음",
                "evidence": "mapping_details에 primary 역할이 없음",
                "source": "system",
            }
        final = mapping.get("final_emotion")
        ok = final in primary_mapped
        return {
            "rule": "primary 감정을 secondary보다 우선",
            "status": "준수" if ok else "예외",
            "evidence": f"primary 매핑={primary_mapped}, 최종={final}",
            "source": "system",
        }

    def _check_no_weight_word(self, mapping: dict[str, Any]) -> dict[str, str]:
        blob = json.dumps(mapping, ensure_ascii=False)
        hit = "가중치" in blob
        return {
            "rule": "'가중치'라는 표현을 사용하지 않는다",
            "status": "위반" if hit else "준수",
            "evidence": "출력에 '가중치' 포함" if hit else "해당 표현 없음",
            "source": "system",
        }

    def _check_applied_rules_present(self, mapping: dict[str, Any]) -> dict[str, str]:
        rules = mapping.get("applied_memory_rules") or []
        ok = bool(rules)
        return {
            "rule": "적용한 메모리 규칙을 명시",
            "status": "준수" if ok else "위반",
            "evidence": f"{len(rules)}개 규칙 기록" if ok else "적용 규칙이 비어 있음",
            "source": "system",
        }

    def _check_exception_explained(
        self,
        kote: dict[str, Any],
        eighteen: dict[str, Any],
        final: str,
        mapping: dict[str, Any],
    ) -> dict[str, str]:
        expecteds = [
            self.reference_mapping.get(kote.get("primary", "")),
            self.reference_mapping.get(eighteen.get("primary", "")),
        ]
        expecteds = [e for e in expecteds if e]
        if not expecteds or final in expecteds:
            return {
                "rule": "참고 매핑과 다르면 예외 이유를 남긴다",
                "status": "해당없음",
                "evidence": "참고 매핑과 최종이 일치하거나 대조 대상 없음",
                "source": "system",
            }
        reasons = mapping.get("final_decision", {}).get("key_reasons") or []
        summary = mapping.get("summary") or ""
        ok = bool(reasons) or bool(summary)
        return {
            "rule": "참고 매핑과 다르면 예외 이유를 남긴다",
            "status": "준수" if ok else "위반",
            "evidence": "근거/요약이 있음" if ok else "예외인데 근거가 없음",
            "source": "system",
        }
