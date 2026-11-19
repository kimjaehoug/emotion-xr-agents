"""LLM 없이 동작하는 규칙 기반 분류·매핑 (LLM_MODE=offline 또는 LLM 장애 시 fallback).

LLM과 같은 JSON 형태를 만들어 ClassifierAgent/MapperAgent의 `_validate`를 그대로 재사용한다.
정확도는 LLM보다 낮으며, 메모리(검증된 사례·절차 카드)가 있으면 그 근거를 우선한다.
"""

from __future__ import annotations

import re
from typing import Any

# (단서, KOTE 44 라벨, 18대 라벨)
LEXICON: list[tuple[str, str, str]] = [
    ("기쁘", "기쁨", "기쁨"), ("기뻐", "기쁨", "기쁨"), ("행복", "행복", "기쁨"), ("신나", "즐거움/신남", "기쁨"),
    ("즐거", "즐거움/신남", "기쁨"), ("좋아", "기쁨", "기쁨"), ("뿌듯", "뿌듯함", "기쁨"), ("감동", "감동/감탄", "기쁨"),
    ("고맙", "고마움", "감사"), ("감사", "고마움", "감사"), ("설레", "기대감", "기대"), ("기대된", "기대감", "기대"),
    ("사랑", "아껴주는", "사랑"),
    ("슬프", "슬픔", "슬픔"), ("슬퍼", "슬픔", "슬픔"), ("우울", "슬픔", "슬픔"), ("외롭", "서러움", "외로움"),
    ("서럽", "서러움", "슬픔"), ("절망", "절망", "슬픔"), ("허무", "안타까움/실망", "실망"), ("실망", "안타까움/실망", "실망"),
    ("힘들", "힘듦/지침", "슬픔"), ("지쳤", "힘듦/지침", "슬픔"), ("미안", "죄책감", "죄책감"), ("부끄", "부끄러움", "수치"),
    ("화나", "화남/분노", "분노"), ("화가", "화남/분노", "분노"), ("열받", "화남/분노", "분노"), ("빡치", "화남/분노", "분노"),
    ("짜증", "짜증", "짜증"), ("불공평", "불평/불만", "분노"), ("왜 나한테", "불평/불만", "분노"), ("억울", "불평/불만", "분노"),
    ("지긋지긋", "지긋지긋", "짜증"), ("귀찮", "귀찮음", "짜증"),
    ("무섭", "공포/무서움", "공포"), ("무서", "공포/무서움", "공포"), ("두렵", "공포/무서움", "공포"), ("불안", "불안/걱정", "불안"),
    ("걱정", "불안/걱정", "불안"), ("떨려", "불안/걱정", "불안"), ("부담", "부담/안_내킴", "불안"), ("의심", "의심/불신", "불안"),
    ("놀랐", "놀람", "놀람"), ("깜짝", "놀람", "놀람"), ("어이없", "어이없음", "놀람"), ("당황", "당황/난처", "놀람"),
    ("신기", "신기함/관심", "호기심"), ("궁금", "신기함/관심", "호기심"),
    ("역겹", "역겨움/징그러움", "혐오"), ("징그", "역겨움/징그러움", "혐오"), ("구역질", "역겨움/징그러움", "혐오"),
    ("혐오", "증오/혐오", "혐오"), ("한심", "한심함", "혐오"),
    ("편안", "편안/쾌적", "안도"), ("다행", "안심/신뢰", "안도"), ("안심", "안심/신뢰", "안도"),
]
INTENSIFIERS = ("너무", "정말", "진짜", "완전", "엄청", "매우", "미치겠")
NEGATION = re.compile(r"(안\s*$|못\s*$)")
VALENCE = {"기쁨": "긍정", "슬픔": "부정", "분노": "부정", "공포": "부정", "혐오": "부정", "놀람": "혼합", "중립": "중립"}
AROUSAL = {"분노": "높음", "공포": "높음", "놀람": "높음", "기쁨": "중간", "혐오": "중간", "슬픔": "낮음", "중립": "낮음"}
# 매핑 메모리 4절 '실망' 애매 케이스: 항의·배신 단서가 있으면 분노
PROTEST_CUES = ("왜 나한테", "억울", "배신", "어떻게 이럴", "따지")


def _matches(text: str) -> list[dict[str, Any]]:
    found = []
    for cue, kote, eighteen in LEXICON:
        for m in re.finditer(re.escape(cue), text):
            if NEGATION.search(text[max(0, m.start() - 2) : m.start()]):
                continue
            boost = sum(1 for w in INTENSIFIERS if w in text[max(0, m.start() - 6) : m.start()])
            found.append({"cue": cue, "kote": kote, "eighteen": eighteen, "pos": m.start(), "score": 1 + boost})
    return found


def emotional_intensity(text: str) -> float:
    found = _matches(text)
    if not found:
        return 0.1
    boosts = sum(f["score"] - 1 for f in found)
    return round(min(1.0, 0.4 + 0.15 * len(found) + 0.15 * boosts + 0.05 * text.count("!")), 2)


def offline_classify(text: str) -> dict[str, Any]:
    found = _matches(text)
    if not found:
        return {
            "key_phrases": [],
            "valence": "중립",
            "arousal": "낮음",
            "process": [
                {"title": "감정 단서 탐색", "finding": "사전에 있는 감정 어휘가 없음"},
                {"title": "사실 서술 판단", "finding": "명시적 정서 없이 사실을 서술"},
                {"title": "라벨 결정", "finding": "KOTE '없음' / 18대 '중립'"},
            ],
            "kote_44": {"primary": "없음", "secondary": [], "confidence": 0.5, "why": "감정 어휘 없음"},
            "eighteen": {"primary": "중립", "secondary": [], "confidence": 0.5, "why": "감정 어휘 없음"},
            "alternatives": [],
        }
    # 점수 합 → 같으면 뒤쪽(문장 끝 쪽 주관 정서) 우선
    agg: dict[str, dict[str, Any]] = {}
    for f in found:
        a = agg.setdefault(f["kote"], {"score": 0, "pos": 0, "eighteen": f["eighteen"], "cues": []})
        a["score"] += f["score"]
        a["pos"] = max(a["pos"], f["pos"])
        a["cues"].append(f["cue"])
    ranked = sorted(agg.items(), key=lambda kv: (kv[1]["score"], kv[1]["pos"]), reverse=True)
    (kote, top), rest = ranked[0], ranked[1:]
    confidence = round(min(0.9, 0.5 + 0.1 * top["score"]), 2)
    eighteen = top["eighteen"]
    seven_hint = {"기쁨": "기쁨", "감사": "기쁨", "기대": "기쁨", "사랑": "기쁨", "안도": "중립", "호기심": "놀람",
                  "실망": "슬픔", "수치": "슬픔", "죄책감": "슬픔", "외로움": "슬픔", "짜증": "분노", "불안": "공포"}.get(eighteen, eighteen)
    return {
        "key_phrases": sorted({c for _, a in ranked for c in a["cues"]}),
        "valence": VALENCE.get(seven_hint, "혼합"),
        "arousal": AROUSAL.get(seven_hint, "중간"),
        "process": [
            {"title": "감정 단서 추출", "finding": ", ".join(top["cues"])},
            {"title": "단서 점수 비교", "finding": f"'{kote}' {top['score']}점" + (f", '{rest[0][0]}' {rest[0][1]['score']}점" if rest else "")},
            {"title": "라벨 결정", "finding": f"KOTE '{kote}' / 18대 '{eighteen}'"},
        ],
        "kote_44": {"primary": kote, "secondary": [rest[0][0]] if rest else [], "confidence": confidence, "why": f"단서 {top['cues']}"},
        "eighteen": {"primary": eighteen, "secondary": [rest[0][1]["eighteen"]] if rest and rest[0][1]["eighteen"] != eighteen else [], "confidence": confidence, "why": f"단서 {top['cues']}"},
        "alternatives": [{"label": k, "why": f"단서 {a['cues']} 점수 낮음"} for k, a in rest[:2]],
    }


def offline_map(
    text: str,
    classification: dict[str, Any],
    reference_mapping: dict[str, str],
    *,
    memory_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """참고 변환표 + 매핑 메모리의 애매 케이스 규칙 + (있으면) 메모리 근거로 7대 감정을 정한다."""
    kote = classification.get("kote_44", {}).get("primary", "없음")
    eighteen = classification.get("eighteen", {}).get("primary", "중립")
    from_kote = reference_mapping.get(kote, "중립")
    from_eighteen = reference_mapping.get(eighteen, from_kote)
    rules = ["주 감정을 보조 감정보다 우선 (규칙 2-2)", "세부 감정 → 7가지 변환표 적용 (규칙 3절)"]
    final = from_kote
    reasons = [f"KOTE '{kote}'→{from_kote}", f"18대 '{eighteen}'→{from_eighteen}"]
    if from_kote == from_eighteen:
        rules.append("두 분류 결과가 같으면 그대로 채택 (규칙 2-3)")

    if kote == "안타까움/실망" and any(c in text for c in PROTEST_CUES):
        final = "분노"
        rules.append("'실망'에 억울함·항의·배신감이 강하면 분노 (규칙 4절)")
        reasons.append("항의/배신 단서 존재")

    confidence = 0.7 if from_kote == from_eighteen else 0.55
    if memory_override:
        final = memory_override["emotion"]
        rules.append(f"메모리 근거 우선: {memory_override['source']}")
        reasons.insert(0, memory_override["reason"])
        confidence = max(confidence, float(memory_override.get("confidence", 0.75)))

    rejected = [{"emotion": e, "why": "참고 매핑 후보였으나 최종과 다름"} for e in {from_kote, from_eighteen} if e != final]
    return {
        "final_emotion": final,
        "confidence": confidence,
        "summary": f"{kote}/{eighteen} → {final} (오프라인 규칙)",
        "applied_rules": rules,
        "process": [
            {"title": "분류 결과 확인", "finding": f"KOTE {kote}, 18대 {eighteen}"},
            {"title": "변환표·애매 규칙 적용", "finding": "; ".join(rules[-2:])},
            {"title": "최종 선택", "finding": f"{final} 선택"},
        ],
        "mapping_details": [
            {"source_taxonomy": "kote_44", "source_label": kote, "mapped_to": from_kote, "role": "primary", "why": "참고 변환표"},
            {"source_taxonomy": "eighteen", "source_label": eighteen, "mapped_to": from_eighteen, "role": "primary", "why": "참고 변환표"},
        ],
        "key_reasons": reasons,
        "rejected": rejected[:2],
        "rule_checks": [{"rule": r, "status": "준수", "evidence": "오프라인 규칙 엔진"} for r in rules[:3]],
    }
