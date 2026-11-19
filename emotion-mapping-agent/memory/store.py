"""감정 매핑 Agent 메모리 저장소 (SQLite, 표준 라이브러리).

계층:
- events      원시 증거 (append-only, PII 마스킹)
- cases       일화 메모리 (분석 사례). 교정 시 corrected_to만 주석으로 추가
- cards       의미/절차 카드 (ADD-only, valid_to로 이력 보존)
- rulebook    매핑 규칙집 버전 (PR 방식: proposed → reviewed → active / rejected)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from memory.core import sanitize_obj, sanitize_text, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, event_type TEXT NOT NULL,
    payload TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, text TEXT NOT NULL, key_phrases TEXT NOT NULL,
    kote TEXT, eighteen TEXT, final TEXT NOT NULL, confidence REAL, intensity REAL, mode TEXT,
    corrected_to TEXT, correction_note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, memory_type TEXT NOT NULL, key TEXT NOT NULL,
    value TEXT, backstory TEXT NOT NULL, evidence TEXT NOT NULL, confidence REAL NOT NULL,
    source TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT, superseded_by TEXT
);
CREATE TABLE IF NOT EXISTS rulebook (
    version INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, status TEXT NOT NULL,
    note TEXT, review TEXT, parent_version INTEGER, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_cases_user ON cases(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_events_user ON events(user_id, created_at);
"""


def _now() -> str:
    return utcnow().isoformat()


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, args)
            rows = cur.fetchall()
            self._conn.commit()
            return rows

    # ---------------------------------------------------------------- events
    def append_event(self, user_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = f"EV-{uuid4().hex[:12].upper()}"
        self._exec(
            "INSERT INTO events VALUES (?,?,?,?,?)",
            (event_id, user_id, event_type, json.dumps(sanitize_obj(payload), ensure_ascii=False), _now()),
        )
        return event_id

    def list_events(self, user_id: str, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events WHERE user_id=?" + (" AND event_type=?" if event_type else "") + " ORDER BY rowid DESC LIMIT ?"
        args = (user_id, event_type, limit) if event_type else (user_id, limit)
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in self._exec(sql, args)]

    def access_counts(self, user_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ev in self.list_events(user_id, limit=5000, event_type="memory_accessed"):
            for ref in ev["payload"].get("refs", []):
                counts[ref] = counts.get(ref, 0) + 1
        return counts

    # ---------------------------------------------------------------- cases
    def add_case(self, user_id: str, *, text: str, key_phrases: list[str], kote: str, eighteen: str,
                 final: str, confidence: float, intensity: float, mode: str) -> str:
        case_id = f"CASE-{uuid4().hex[:10].upper()}"
        clean, _ = sanitize_text(text)
        self._exec(
            "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (case_id, user_id, clean, json.dumps(key_phrases, ensure_ascii=False), kote, eighteen, final,
             confidence, intensity, mode, None, None, _now()),
        )
        return case_id

    def annotate_correction(self, case_id: str, corrected_to: str, note: str | None) -> None:
        self._exec("UPDATE cases SET corrected_to=?, correction_note=? WHERE case_id=?",
                   (corrected_to, sanitize_text(note or "")[0] or None, case_id))

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        rows = self._exec("SELECT * FROM cases WHERE case_id=?", (case_id,))
        return self._case(rows[0]) if rows else None

    def list_cases(self, user_id: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._exec("SELECT * FROM cases WHERE user_id=? ORDER BY rowid DESC LIMIT ?", (user_id, limit))
        return [self._case(r) for r in rows]

    @staticmethod
    def _case(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["key_phrases"] = json.loads(d["key_phrases"])
        d["label"] = d["corrected_to"] or d["final"]
        d["verified"] = d["corrected_to"] is not None
        return d

    # ---------------------------------------------------------------- cards
    def add_card(self, user_id: str, *, memory_type: str, key: str, value: Any, backstory: str,
                 evidence: list[str], confidence: float, source: str) -> str:
        card_id = f"MC-{uuid4().hex[:10].upper()}"
        self._exec(
            "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (card_id, user_id, memory_type, key, json.dumps(value, ensure_ascii=False), backstory,
             json.dumps(evidence, ensure_ascii=False), round(confidence, 4), source, _now(), None, None),
        )
        return card_id

    def close_card(self, card_id: str, superseded_by: str | None = None) -> None:
        self._exec("UPDATE cards SET valid_to=?, superseded_by=? WHERE card_id=? AND valid_to IS NULL",
                   (_now(), superseded_by, card_id))

    def list_cards(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._exec("SELECT * FROM cards WHERE user_id=? ORDER BY rowid", (user_id,))
        out = []
        for r in rows:
            d = dict(r)
            d["value"] = json.loads(d["value"]) if d["value"] else None
            d["evidence"] = json.loads(d["evidence"])
            out.append(d)
        return out

    # ---------------------------------------------------------------- rulebook
    def rulebook_versions(self) -> list[dict[str, Any]]:
        return [dict(r) | {"review": json.loads(r["review"]) if r["review"] else None}
                for r in self._exec("SELECT * FROM rulebook ORDER BY version DESC")]

    def get_rulebook(self, version: int) -> dict[str, Any] | None:
        rows = self._exec("SELECT * FROM rulebook WHERE version=?", (version,))
        if not rows:
            return None
        r = rows[0]
        return dict(r) | {"review": json.loads(r["review"]) if r["review"] else None}

    def active_rulebook(self) -> dict[str, Any] | None:
        rows = self._exec("SELECT * FROM rulebook WHERE status='active' ORDER BY version DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    def add_rulebook(self, content: str, *, status: str, note: str, review: dict | None, parent: int | None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO rulebook (content,status,note,review,parent_version,created_at,decided_at) VALUES (?,?,?,?,?,?,?)",
                (content, status, note, json.dumps(review, ensure_ascii=False) if review else None, parent, _now(),
                 _now() if status == "active" else None),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def set_rulebook_status(self, version: int, status: str) -> None:
        self._exec("UPDATE rulebook SET status=?, decided_at=? WHERE version=?", (status, _now(), version))
