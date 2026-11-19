"""에이전트 메모리 공통 코어 (표준 라이브러리만 사용).

세 Agent(감정 매핑 / 상태 인지 / XR 제어)가 같은 파일을 복제해 사용한다.
설계 근거는 「AI 에이전트를 깊이 이해하기」 3장 사용자 메모리 시스템:

- 3.1.3 고급 JSON 카드: key/value + backstory + evidence + 시간 메타데이터
- 3.1.6 Mem0 v3: ADD-only 쓰기, 충돌은 검색 시점에 시간·관련도로 해소
- 3.1.7 중요도 점수: 접근 빈도 · 시간 감쇠 · 감정 강도 · 고유성
- 3.1.8 비식별화: 저장 전 PII 마스킹 (로컬 정규식, 외부 전송 없음)
- 3.2.4 혼합 검색: 어휘(BM25) + 최신성 + 중요도 + 엔터티 일치
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MEMORY_CORE_VERSION = "1.0.0"

SEMANTIC = "semantic"
PROCEDURAL = "procedural"
EPISODIC = "episodic"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite는 tz 정보를 잃으므로 naive 값은 UTC로 간주한다."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_time(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return as_aware(value)
    try:
        return as_aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


# ----------------------------------------------------------------------
# 3.1.8 비식별화
# ----------------------------------------------------------------------
# 한국어는 조사가 숫자에 바로 붙으므로("5678로") \b 대신 숫자/ASCII 경계를 쓴다.
_D0, _D1 = r"(?<![0-9])", r"(?![0-9])"
_PII_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("RRN", re.compile(_D0 + r"\d{6}[-\s]?[1-4]\d{6}" + _D1)),
    ("CARD", re.compile(_D0 + r"\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}" + _D1)),
    ("PHONE", re.compile(_D0 + r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}" + _D1)),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    ("ACCOUNT", re.compile(_D0 + r"\d{3,6}-\d{2,6}-\d{2,8}" + _D1)),
]


def sanitize_text(text: str) -> Tuple[str, List[str]]:
    """PII를 [TYPE]으로 치환하고 발견한 유형 목록을 반환한다."""
    found: List[str] = []
    clean = text
    for label, pattern in _PII_PATTERNS:
        clean, n = pattern.subn(f"[{label}]", clean)
        if n:
            found.extend([label] * n)
    return clean, found


def sanitize_obj(obj: Any) -> Any:
    """dict/list 안의 모든 문자열을 재귀적으로 비식별화한다."""
    if isinstance(obj, str):
        return sanitize_text(obj)[0]
    if isinstance(obj, dict):
        return {k: sanitize_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_obj(v) for v in obj]
    return obj


# ----------------------------------------------------------------------
# 3.1.7 중요도 점수
# ----------------------------------------------------------------------
IMPORTANCE_WEIGHTS = {"frequency": 0.25, "recency": 0.25, "emotion": 0.25, "uniqueness": 0.25}


def importance_score(
    *,
    created_at: Optional[datetime],
    access_count: int = 0,
    emotional_intensity: float = 0.0,
    duplicate_count: int = 0,
    now: Optional[datetime] = None,
    half_life_days: float = 30.0,
) -> Dict[str, float]:
    """네 요소를 0~1로 정규화해 가중합한다. 구성 요소도 함께 반환해 설명 가능하게 한다."""
    now = now or utcnow()
    created = as_aware(created_at) or now
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    parts = {
        "frequency": 1.0 - math.exp(-max(0, access_count) / 3.0),
        "recency": 0.5 ** (age_days / half_life_days),
        "emotion": max(0.0, min(1.0, float(emotional_intensity))),
        "uniqueness": 1.0 / (1.0 + max(0, duplicate_count)),
    }
    score = sum(IMPORTANCE_WEIGHTS[k] * v for k, v in parts.items())
    return {**{k: round(v, 4) for k, v in parts.items()}, "score": round(score, 4), "age_days": round(age_days, 2)}


# ----------------------------------------------------------------------
# 3.2 혼합 검색 (한국어용 문자 bigram BM25)
# ----------------------------------------------------------------------
def char_ngrams(text: str, n: int = 2) -> List[str]:
    compact = re.sub(r"\s+", " ", text.strip().lower())
    tokens: List[str] = []
    for word in compact.split(" "):
        if not word:
            continue
        if len(word) < n:
            tokens.append(word)
            continue
        tokens.extend(word[i : i + n] for i in range(len(word) - n + 1))
    return tokens


def bm25_scores(query: str, docs: Sequence[str], k1: float = 1.5, b: float = 0.75) -> List[float]:
    if not docs:
        return []
    doc_tokens = [char_ngrams(d) for d in docs]
    avg_len = sum(len(t) for t in doc_tokens) / len(doc_tokens) or 1.0
    df: Counter[str] = Counter()
    for toks in doc_tokens:
        df.update(set(toks))
    n_docs = len(docs)
    q_tokens = set(char_ngrams(query))
    scores: List[float] = []
    for toks in doc_tokens:
        tf = Counter(toks)
        s = 0.0
        for t in q_tokens:
            if t not in tf:
                continue
            idf = math.log(1 + (n_docs - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(toks) / avg_len))
        scores.append(s)
    return scores


def _normalize(values: Sequence[float]) -> List[float]:
    hi = max(values) if values else 0.0
    return [v / hi if hi > 0 else 0.0 for v in values]


def hybrid_rank(
    items: Sequence[Dict[str, Any]],
    *,
    query: str = "",
    text_of=lambda item: str(item.get("text") or ""),
    time_of=lambda item: item.get("created_at"),
    importance_of=lambda item: float(item.get("importance") or 0.0),
    entities_of=lambda item: set(item.get("entities") or []),
    query_entities: Iterable[str] = (),
    similarity_of=None,
    weights: Optional[Dict[str, float]] = None,
    half_life_days: float = 30.0,
    top_k: int = 5,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """의미(어휘)·최신성·중요도·엔터티 신호를 융합해 상위 k개를 반환한다."""
    if not items:
        return []
    w = {"lexical": 0.4, "recency": 0.2, "importance": 0.2, "entity": 0.2, **(weights or {})}
    now = now or utcnow()
    if similarity_of is not None:
        # 수치 벡터처럼 어휘가 아닌 유사도를 쓰는 Agent는 lexical 신호를 대체한다.
        lexical = [max(0.0, min(1.0, float(similarity_of(i)))) for i in items]
    elif query:
        lexical = _normalize(bm25_scores(query, [text_of(i) for i in items]))
    else:
        lexical = [0.0] * len(items)
    q_ents = set(query_entities)
    ranked: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        created = parse_time(time_of(item)) or now
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
        recency = 0.5 ** (age_days / half_life_days)
        ents = entities_of(item)
        entity = len(ents & q_ents) / len(q_ents) if q_ents else 0.0
        signals = {
            "lexical": round(lexical[idx], 4),
            "recency": round(recency, 4),
            "importance": round(importance_of(item), 4),
            "entity": round(entity, 4),
        }
        score = sum(w[k] * v for k, v in signals.items())
        ranked.append({"item": item, "score": round(score, 4), "signals": signals})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:top_k]


# ----------------------------------------------------------------------
# 3.1.6 Mem0 v3: ADD-only + 검색 시점 충돌 해소
# ----------------------------------------------------------------------
def is_valid_at(card: Dict[str, Any], at: Optional[datetime] = None) -> bool:
    at = at or utcnow()
    start = parse_time(card.get("valid_from"))
    end = parse_time(card.get("valid_to"))
    if start and start > at:
        return False
    return end is None or end > at


def resolve_current(cards: Iterable[Dict[str, Any]], at: Optional[datetime] = None) -> Dict[str, Dict[str, Any]]:
    """key별로 시점 at에 유효한 카드 중 가장 최근 것을 고른다. 이력은 지우지 않는다."""
    current: Dict[str, Dict[str, Any]] = {}
    for card in cards:
        if not is_valid_at(card, at):
            continue
        key = card["key"]
        prev = current.get(key)
        if prev is None or (parse_time(card.get("valid_from")) or utcnow()) >= (
            parse_time(prev.get("valid_from")) or utcnow()
        ):
            current[key] = card
    return current


def plan_card_write(
    existing_current: Optional[Dict[str, Any]],
    new_value: Any,
) -> str:
    """새 관측에 대한 쓰기 결정. 이전 카드는 지우지 않고 유효기간만 닫는다.

    반환: "ADD"(새 키) | "SUPERSEDE"(값 변경 → 새 카드 + 이전 카드 valid_to) | "REINFORCE"(동일 값, 이벤트만 기록)
    """
    if existing_current is None:
        return "ADD"
    if existing_current.get("value") == new_value:
        return "REINFORCE"
    return "SUPERSEDE"


def card_view(card: Dict[str, Any]) -> Dict[str, Any]:
    """API/LLM 컨텍스트용 간결한 카드 표현."""
    return {
        "card_id": card.get("card_id"),
        "memory_type": card.get("memory_type"),
        "key": card.get("key"),
        "value": card.get("value"),
        "backstory": card.get("backstory"),
        "confidence": card.get("confidence"),
        "evidence": card.get("evidence") or [],
        "valid_from": str(card.get("valid_from")) if card.get("valid_from") else None,
        "valid_to": str(card.get("valid_to")) if card.get("valid_to") else None,
    }
