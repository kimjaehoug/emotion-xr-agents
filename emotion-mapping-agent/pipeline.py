"""감정 분류 → 7대 매핑 파이프라인 (LLM 2회 호출, 또는 오프라인 규칙) + 에이전트 메모리."""

from __future__ import annotations

import time
from typing import Any

from agents.classifier_agent import ClassifierAgent
from agents.mapper_agent import MEMORY_PATH, MapperAgent
from agents.offline_agent import emotional_intensity, offline_classify, offline_map
from agents.rule_verifier import RuleVerifier
from config import LLM_MODE, MEMORY_DB_PATH
from llm_client import LLMClient
from memory.service import EmotionMemory
from memory.store import MemoryStore


class EmotionPipeline:
    def __init__(self, memory_db_path: str | None = None, llm_mode: str | None = None) -> None:
        self.llm_mode = (llm_mode or LLM_MODE).lower()
        self.llm = LLMClient()
        self.classifier = ClassifierAgent(self.llm)
        self.mapper = MapperAgent(self.llm)
        self.verifier = RuleVerifier(
            seven_labels=self.mapper.seven_labels,
            reference_mapping=self.mapper.reference_mapping,
        )
        self.memory = EmotionMemory(
            MemoryStore(memory_db_path or MEMORY_DB_PATH),
            seed_rulebook_path=MEMORY_PATH,
            reference_mapping=self.mapper.reference_mapping,
        )

    def _classify(self, text: str, mode: str) -> tuple[dict[str, Any], str, str | None]:
        if mode != "offline":
            try:
                return self.classifier.classify(text), "llm", None
            except Exception as exc:  # noqa: BLE001 - LLM 장애는 오프라인 규칙으로 대체
                fallback_reason = f"LLM 분류 실패 → 오프라인 규칙: {exc}"
                taxonomies = self.classifier.taxonomies
                return self.classifier._validate(
                    offline_classify(text), taxonomies["kote_44"]["labels"], taxonomies["eighteen"]["labels"]
                ), "offline", fallback_reason
        taxonomies = self.classifier.taxonomies
        return self.classifier._validate(
            offline_classify(text), taxonomies["kote_44"]["labels"], taxonomies["eighteen"]["labels"]
        ), "offline", None

    def _map(
        self, text: str, classification: dict[str, Any], memory: str, working: dict[str, Any], mode: str
    ) -> dict[str, Any]:
        if mode == "llm":
            try:
                return self.mapper.map_to_seven(
                    text, classification, mapping_memory=memory,
                    memory_hints=self.memory.hints_for_prompt(working),
                )
            except Exception:  # noqa: BLE001
                pass
        mapped = self.mapper._validate(offline_map(
            text, classification, self.mapper.reference_mapping,
            memory_override=self.memory.override_for(text, classification, working),
        ))
        mapped["mapping_memory_used"] = memory
        return mapped

    def run(
        self,
        text: str,
        mapping_memory: str | None = None,
        user_id: str = "default",
    ) -> dict[str, Any]:
        started = time.time()
        steps: list[dict[str, Any]] = []
        rulebook = self.memory.active_rulebook()
        memory = (mapping_memory or rulebook["content"]).strip()
        mode_requested = "offline" if self.llm_mode == "offline" else "llm"

        steps.append({"step": 1, "name": "문장 입력", "status": "completed", "output": {"text": text}})

        steps.append({
            "step": 2,
            "name": "감정 매핑 규칙 불러오기",
            "status": "completed",
            "agent": "MapperAgent",
            "output": {
                "source": "user" if mapping_memory else f"감정 매핑 규칙 v{rulebook['version']}",
                "memory_preview": memory[:200] + ("..." if len(memory) > 200 else ""),
                "memory_full": memory,
            },
        })

        classification, mode, fallback_reason = self._classify(text, mode_requested)
        steps.append({
            "step": 3,
            "name": "세부 감정 분류 (KOTE 44 · 18 감정)",
            "status": "completed",
            "agent": "ClassifierAgent" if mode == "llm" else "OfflineRuleClassifier",
            "output": classification,
        })

        working = self.memory.recall(user_id, text, classification.get("text_analysis", {}).get("key_phrases"))
        steps.append({
            "step": 4,
            "name": "유사 사례 검색 (분석 참조 메모리)",
            "status": "completed",
            "agent": "EmotionMemory",
            "output": working,
        })

        mapping = self._map(text, classification, memory, working, mode)
        steps.append({
            "step": 5,
            "name": "7대 기본 감정 매핑",
            "status": "completed",
            "agent": "MapperAgent" if mode == "llm" else "OfflineRuleMapper",
            "output": mapping,
        })

        verification = self.verifier.verify(text, classification, mapping, memory)
        steps.append({
            "step": 6,
            "name": "매핑 규칙 준수 검증",
            "status": "completed",
            "agent": "RuleVerifier",
            "output": verification,
        })

        intensity = emotional_intensity(text)
        result: dict[str, Any] = {
            "input": text,
            "mapping_memory": memory,
            "classification": classification,
            "mapping": mapping,
            "verification": verification,
            "final_emotion": mapping["final_emotion"],
            "rulebook_version": rulebook["version"],
        }
        case_id = self.memory.record(user_id, text, result, mode=mode, intensity=intensity)
        alerts = self.memory.alerts(user_id)
        steps.append({
            "step": 7,
            "name": "메모리 저장 · 선제 알림",
            "status": "completed",
            "agent": "EmotionMemory",
            "output": {"case_id": case_id, "alerts": alerts},
        })

        result.update({
            "steps": steps,
            "elapsed_ms": int((time.time() - started) * 1000),
            "mode": mode,
            "fallback_reason": fallback_reason,
            "case_id": case_id,
            "memory": {"working_memory": working, "alerts": alerts},
            # 상태 인지 Agent 입력의 emotion_context로 그대로 전달 가능
            "emotion_context": {
                "label": mapping["final_emotion"],
                "intensity": intensity,
                "confidence": round(float(mapping.get("confidence", 0.5)), 2),
            },
        })
        return result
