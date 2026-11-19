"""감정 매핑 Agent 메모리 서비스.

- 작업 메모리: 유사 사례(BM25 + 최신성 + 중요도 + 단서 일치) + 절차 카드 + 활성 규칙집
- 교정 피드백: 원시 이벤트 → 사례에 정답 주석 → 검증된 사례가 이후 분석의 근거
- 압축(3.1.7): 교정 사례를 KOTE 라벨별로 묶어 절차 카드로 추상화
- 규칙집 PR(3.3.3): Proposer(사람/압축 결과) → Reviewer(결정적 검사) → 명시적 승인 시에만 활성화
- User-as-Code: 부정 정서 지속 / 규칙집과 충돌하는 교정 누적을 능동 경고
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from pathlib import Path
from typing import Any

from memory.core import (
    EPISODIC,
    PROCEDURAL,
    card_view,
    char_ngrams,
    hybrid_rank,
    importance_score,
    parse_time,
    plan_card_write,
    resolve_current,
)
from memory.store import MemoryStore

SEVEN = ["기쁨", "슬픔", "분노", "공포", "놀람", "혐오", "중립"]
NEGATIVE = {"슬픔", "분노", "공포", "혐오"}
# 검색 점수는 최고점을 1로 맞춘 상대값이라, 정답 재사용 여부는 문자 bigram 겹침(절대값)으로 판단한다.
VERIFIED_MATCH_MIN = 0.5
PROCEDURE_MIN_SUPPORT = 2
PROCEDURE_MIN_RATIO = 0.67
NEGATIVE_STREAK = 4
NEGATIVE_WINDOW = 5
MAX_DELETION_RATIO = 0.3


def _ro(word: str) -> str:
    """'분노' → "'분노'로", '슬픔' → "'슬픔'으로" (받침에 따라 조사 선택)."""
    code = ord(word[-1]) - 0xAC00 if word else -1
    if 0 <= code < 11172:
        jong = code % 28
        return f"'{word}'" + ("로" if jong in (0, 8) else "으로")
    return f"'{word}'(으)로"


class EmotionMemory:
    def __init__(self, store: MemoryStore, seed_rulebook_path: Path, reference_mapping: dict[str, str]) -> None:
        self.store = store
        self.reference_mapping = reference_mapping
        if self.store.active_rulebook() is None:
            content = seed_rulebook_path.read_text(encoding="utf-8").strip()
            self.store.add_rulebook(content, status="active", note="초기 감정 매핑 규칙 (mapping_memory.txt)", review=None, parent=None)

    # ------------------------------------------------------------------ 규칙집
    def active_rulebook(self) -> dict[str, Any]:
        return self.store.active_rulebook()  # type: ignore[return-value]

    def review_rulebook(self, old: str, new: str) -> dict[str, Any]:
        """Reviewer: 증거·형식에 근거한 결정적 검사. 통과해도 병합은 사람의 승인으로만."""
        issues: list[str] = []
        for label in SEVEN:
            if f"■ {label}" not in new:
                issues.append(f"7대 감정 '{label}' 정의 섹션이 없습니다.")
        for section in ("매핑 우선순위", "변환표", "결정 절차"):
            if section not in new:
                issues.append(f"필수 섹션 '{section}'이(가) 없습니다.")
        if new.count("가중치") > old.count("가중치"):
            issues.append("금지 표현 '가중치'가 새로 추가되었습니다.")
        old_lines, new_lines = old.splitlines(), new.splitlines()
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=0))
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        if old_lines and removed / len(old_lines) > MAX_DELETION_RATIO:
            issues.append(f"삭제 범위가 과도합니다 ({removed}/{len(old_lines)}줄).")
        if added == 0 and removed == 0:
            issues.append("변경 사항이 없습니다.")
        return {"approved": not issues, "issues": issues, "added": added, "removed": removed, "diff": diff[:80]}

    def propose_rulebook(self, content: str, note: str, user_id: str = "default") -> dict[str, Any]:
        active = self.active_rulebook()
        review = self.review_rulebook(active["content"], content.strip())
        status = "reviewed" if review["approved"] else "rejected"
        version = self.store.add_rulebook(content.strip(), status=status, note=note, review=review, parent=active["version"])
        self.store.append_event(user_id, "rulebook_proposed", {"version": version, "status": status, "issues": review["issues"]})
        return {"version": version, "status": status, "review": review}

    def approve_rulebook(self, version: int, user_id: str = "default") -> dict[str, Any]:
        rb = self.store.get_rulebook(version)
        if rb is None or rb["status"] != "reviewed":
            raise ValueError("리뷰를 통과한(reviewed) 버전만 승인할 수 있습니다.")
        prev = self.active_rulebook()
        self.store.set_rulebook_status(prev["version"], "superseded")
        self.store.set_rulebook_status(version, "active")
        self.store.append_event(user_id, "rulebook_merged", {"version": version, "replaces": prev["version"]})
        return {"active_version": version, "replaced": prev["version"]}

    def rollback_rulebook(self, version: int, user_id: str = "default") -> dict[str, Any]:
        """과거 버전 내용을 새 버전으로 복원 (이력은 그대로 남는다)."""
        target = self.store.get_rulebook(version)
        if target is None:
            raise ValueError(f"버전 {version}이 없습니다.")
        prev = self.active_rulebook()
        self.store.set_rulebook_status(prev["version"], "superseded")
        new_version = self.store.add_rulebook(target["content"], status="active", note=f"v{version}로 롤백",
                                              review=None, parent=prev["version"])
        self.store.append_event(user_id, "rulebook_rollback", {"to": version, "new_version": new_version})
        return {"active_version": new_version, "restored_from": version}

    # ------------------------------------------------------------------ 작업 메모리
    def current_cards(self, user_id: str) -> dict[str, dict[str, Any]]:
        return resolve_current(self.store.list_cards(user_id))

    def _importance(self, user_id: str, cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        access = self.store.access_counts(user_id)
        dup = defaultdict(int)
        for c in cases:
            dup[(c["kote"], c["label"])] += 1
        return {
            c["case_id"]: importance_score(
                created_at=parse_time(c["created_at"]),
                access_count=access.get(c["case_id"], 0) + (3 if c["verified"] else 0),
                emotional_intensity=c.get("intensity") or 0.0,
                duplicate_count=dup[(c["kote"], c["label"])] - 1,
            )
            for c in cases
        }

    def recall(self, user_id: str, text: str, key_phrases: list[str] | None = None, top_k: int = 3) -> dict[str, Any]:
        cases = self.store.list_cases(user_id)
        imp = self._importance(user_id, cases)
        ranked = hybrid_rank(
            cases,
            query=text,
            importance_of=lambda c: imp[c["case_id"]]["score"],
            entities_of=lambda c: set(c["key_phrases"]),
            query_entities=key_phrases or [],
            weights={"lexical": 0.55, "recency": 0.1, "importance": 0.15, "entity": 0.2},
            top_k=top_k,
        )
        similar = [
            {
                "case_id": r["item"]["case_id"],
                "text": r["item"]["text"],
                "label": r["item"]["label"],
                "first_label": r["item"]["final"],
                "note": r["item"].get("correction_note"),
                "verified": r["item"]["verified"],
                "kote": r["item"]["kote"],
                "score": r["score"],
                "signals": r["signals"],
            }
            for r in ranked
            if r["signals"]["lexical"] > 0 or r["signals"]["entity"] > 0
        ]
        procedures = [card_view(c) for k, c in self.current_cards(user_id).items() if k.startswith("procedure.")]
        refs = [s["case_id"] for s in similar] + [p["card_id"] for p in procedures]
        if refs:
            self.store.append_event(user_id, "memory_accessed", {"refs": refs})
        return {"similar_cases": similar, "procedures": procedures}

    @staticmethod
    def hints_for_prompt(working: dict[str, Any]) -> str:
        lines = []
        for s in working.get("similar_cases", []):
            tag = "검증됨" if s["verified"] else "과거 분석"
            lines.append(f"- ({tag}) \"{s['text'][:60]}\" → {s['label']}")
        for p in working.get("procedures", []):
            v = p.get("value") or {}
            lines.append(f"- (절차) KOTE '{v.get('kote')}'는 교정 {v.get('support')}/{v.get('n')}회 '{v.get('preferred')}'")
        return "\n".join(lines)

    def override_for(self, text: str, classification: dict[str, Any], working: dict[str, Any]) -> dict[str, Any] | None:
        """오프라인 매퍼용: 검증된 매우 유사한 사례 > 절차 카드 순으로 근거를 제공."""
        query = set(char_ngrams(text))
        for s in working.get("similar_cases", []):
            past = set(char_ngrams(s["text"]))
            overlap = len(query & past) / len(query | past) if query | past else 0.0
            if s["verified"] and overlap >= VERIFIED_MATCH_MIN:
                return {"emotion": s["label"], "source": f"사용자 보정 사례 {s['case_id']}",
                        "reason": f"유사 문장 \"{s['text'][:30]}\"을 사용자가 {_ro(s['label'])} 보정한 이력", "confidence": 0.8}
        kote = classification.get("kote_44", {}).get("primary")
        for p in working.get("procedures", []):
            v = p.get("value") or {}
            if v.get("kote") == kote:
                return {"emotion": v["preferred"], "source": f"보정 경향 메모리 {p['card_id']}",
                        "reason": f"분류 결과가 '{kote}'인 문장을 이 사용자가 {_ro(v['preferred'])} 보정한 경향({v['support']}/{v['n']})",
                        "confidence": p.get("confidence") or 0.7}
        return None

    # ------------------------------------------------------------------ 기록·교정
    def record(self, user_id: str, text: str, result: dict[str, Any], *, mode: str, intensity: float) -> str:
        cls = result["classification"]
        case_id = self.store.add_case(
            user_id, text=text, key_phrases=cls.get("text_analysis", {}).get("key_phrases", []),
            kote=cls.get("kote_44", {}).get("primary", ""), eighteen=cls.get("eighteen", {}).get("primary", ""),
            final=result["final_emotion"], confidence=float(result["mapping"].get("confidence", 0.5)),
            intensity=intensity, mode=mode,
        )
        self.store.append_event(user_id, "emotion_analyzed", {
            "case_id": case_id, "text": text, "final": result["final_emotion"], "mode": mode,
            "rulebook_version": result.get("rulebook_version"),
        })
        return case_id

    def correct(self, case_id: str, correct_emotion: str, note: str | None = None) -> dict[str, Any]:
        if correct_emotion not in SEVEN:
            raise ValueError(f"7대 감정 중 하나여야 합니다: {SEVEN}")
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"사례 {case_id}가 없습니다.")
        event_id = self.store.append_event(case["user_id"], "correction", {
            "case_id": case_id, "from": case["final"], "to": correct_emotion, "note": note,
        })
        self.store.annotate_correction(case_id, correct_emotion, note)
        return {"case_id": case_id, "from": case["final"], "to": correct_emotion, "event_id": event_id}

    # ------------------------------------------------------------------ 압축·추상화
    def consolidate(self, user_id: str) -> dict[str, Any]:
        cases = self.store.list_cases(user_id)
        current = self.current_cards(user_id)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in cases:
            if c["verified"]:
                groups[c["kote"]].append(c)
        changes = []
        for kote, group in groups.items():
            counts: dict[str, int] = defaultdict(int)
            for c in group:
                counts[c["label"]] += 1
            preferred, support = max(counts.items(), key=lambda kv: kv[1])
            ratio = support / len(group)
            key = f"procedure.kote.{kote}"
            if support >= PROCEDURE_MIN_SUPPORT and ratio >= PROCEDURE_MIN_RATIO:
                value = {"kote": kote, "preferred": preferred, "support": support, "n": len(group)}
                existing = current.get(key)
                decision = plan_card_write(existing, value)
                if decision != "REINFORCE":
                    cid = self.store.add_card(
                        user_id, memory_type=PROCEDURAL, key=key, value=value,
                        backstory=f"분류 결과가 '{kote}'인 문장 {len(group)}건 중 {support}건을 사용자가 {_ro(preferred)} 보정·확정.",
                        evidence=[c["case_id"] for c in group][:10], confidence=ratio, source="consolidation",
                    )
                    if existing:
                        self.store.close_card(existing["card_id"], superseded_by=cid)
                    changes.append({"key": key, "decision": decision, "card_id": cid,
                                    "conflicts_reference": self.reference_mapping.get(kote) != preferred})
        imp = self._importance(user_id, cases)
        low = [cid for cid, s in imp.items() if s["score"] < 0.3]
        if low:
            cluster_key = "cluster.low_importance"
            existing = current.get(cluster_key)
            value = {"count": len(low)}
            if plan_card_write(existing, value) != "REINFORCE":
                cid = self.store.add_card(
                    user_id, memory_type=EPISODIC, key=cluster_key, value=value,
                    backstory=f"중요도 낮은 사례 {len(low)}건 — 유사 사례 검색 시 후순위 (원본 보관).",
                    evidence=low[:10], confidence=1.0, source="consolidation",
                )
                if existing:
                    self.store.close_card(existing["card_id"], superseded_by=cid)
        self.store.append_event(user_id, "consolidated", {"changes": changes, "low_importance": len(low)})
        return {"procedure_changes": changes, "low_importance_cases": low,
                "importance": [{"case_id": k, **v} for k, v in imp.items()]}

    # ------------------------------------------------------------------ 능동 경고 (User as Code)
    def alerts(self, user_id: str) -> list[dict[str, Any]]:
        out = []
        recent = self.store.list_cases(user_id, limit=NEGATIVE_WINDOW)
        neg = [c for c in recent if c["label"] in NEGATIVE]
        if len(recent) >= NEGATIVE_WINDOW and len(neg) >= NEGATIVE_STREAK:
            out.append({
                "rule": "negative_emotion_persistence", "severity": "medium",
                "message": f"최근 {len(recent)}건 중 {len(neg)}건이 부정 감정입니다. 상태 인지 에이전트에 관찰 강화를 요청합니다.",
                "evidence": [c["case_id"] for c in neg],
            })
        for key, card in self.current_cards(user_id).items():
            v = card.get("value") or {}
            if key.startswith("procedure.kote.") and self.reference_mapping.get(v.get("kote")) != v.get("preferred"):
                out.append({
                    "rule": "rulebook_conflict", "severity": "low",
                    "message": f"감정 매핑 규칙은 '{v.get('kote')}' → '{self.reference_mapping.get(v.get('kote'))}', "
                               f"사용자 보정 결과는 '{v.get('preferred')}'({v.get('support')}/{v.get('n')}). 매핑 규칙 수정을 검토해 주세요.",
                    "evidence": [card["card_id"]],
                })
        return out

    def overview(self, user_id: str) -> dict[str, Any]:
        cards = self.store.list_cards(user_id)
        current = resolve_current(cards)
        cases = self.store.list_cases(user_id, limit=50)
        return {
            "user_id": user_id,
            "layers": {
                "raw_events": len(self.store.list_events(user_id, limit=100000)),
                "cases": len(self.store.list_cases(user_id, limit=100000)),
                "verified_cases": sum(1 for c in self.store.list_cases(user_id, limit=100000) if c["verified"]),
                "current_cards": len(current),
                "rulebook_versions": len(self.store.rulebook_versions()),
            },
            "active_rulebook_version": self.active_rulebook()["version"],
            "cases": cases,
            "current_cards": [card_view(c) for c in current.values()],
            "card_history": [card_view(c) | {"superseded_by": c.get("superseded_by")} for c in cards if c["valid_to"]],
            "alerts": self.alerts(user_id),
        }
