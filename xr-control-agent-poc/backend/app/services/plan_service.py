"""계획 생성(/plan) 및 실행(/execute, /confirmations, /feedback) 오케스트레이션."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agents.xr_control.graph import XrAgentRunner
from app.core.enums import ActionType, ConfirmationStatus, FeedbackEffect
from app.llm.protocol import LocalLLMClientProtocol
from app.memory.service import XrMemoryV2
from app.models import ActionPlanRecord, Confirmation, Execution, XrEpisodicMemory
from app.repositories.catalog_repo import ContentRepository
from app.repositories.plan_repo import ActionPlanRepository, ConfirmationRepository, ExecutionRepository
from app.repositories.user_repo import UserRepository
from app.services.mock_xr_runtime import MockXrRuntime


class PlanNotFoundError(Exception):
    pass


class ConfirmationNotFoundError(Exception):
    pass


class ExecutionNotFoundError(Exception):
    pass


class PlanService:
    """`/plan`은 LangGraph 러너에 위임하고, `/execute` 이후 흐름을 직접 관리한다."""

    def __init__(self, db: Session, *, llm_client: Optional[LocalLLMClientProtocol] = None) -> None:
        self.db = db
        self.llm_client = llm_client
        self.plan_repo = ActionPlanRepository(db)
        self.confirmation_repo = ConfirmationRepository(db)
        self.execution_repo = ExecutionRepository(db)
        self.user_repo = UserRepository(db)
        self.content_repo = ContentRepository(db)
        self.xr_runtime = MockXrRuntime(db)
        self.memory_v2 = XrMemoryV2(db)

    def _state_level_for_plan(self, plan_id: str) -> str:
        record = self.plan_repo.get_by_plan_id(plan_id)
        if record is None:
            return "UNKNOWN"
        episode = (
            self.db.query(XrEpisodicMemory)
            .filter(XrEpisodicMemory.state_report_id == record.state_report_id)
            .first()
        )
        return episode.state_level if episode else "UNKNOWN"

    # ------------------------------------------------------------------
    # /plan
    # ------------------------------------------------------------------
    def create_plan(self, raw_state_report: Dict[str, Any]) -> Dict[str, Any]:
        runner = XrAgentRunner(self.db, llm_client=self.llm_client)
        return runner.run(raw_state_report)

    # ------------------------------------------------------------------
    # /execute
    # ------------------------------------------------------------------
    def execute_plan(self, plan_id: str) -> Dict[str, Any]:
        record = self.plan_repo.get_by_plan_id(plan_id)
        if record is None:
            raise PlanNotFoundError(f"plan_id '{plan_id}'를 찾을 수 없습니다.")

        if record.executed_at is not None:
            return {
                "plan_id": plan_id,
                "already_executed": True,
                "confirmations": [
                    self.confirmation_to_response(c)
                    for c in self.confirmation_repo.list_for_plan(plan_id)
                ],
                "executions": [
                    self.execution_to_response(e) for e in self.execution_repo.list_for_plan(plan_id)
                ],
            }

        confirmations: List[Confirmation] = []
        executions: List[Execution] = []
        for idx, action_dict in enumerate(record.actions_json or []):
            if action_dict.get("requires_confirmation"):
                confirmation = self.confirmation_repo.create(
                    confirmation_id=f"CNF-{uuid4().hex[:10].upper()}",
                    plan_id=plan_id,
                    user_id=record.user_id,
                    session_id=record.session_id,
                    action_index=idx,
                    action_json=action_dict,
                    status=ConfirmationStatus.PENDING.value,
                )
                confirmations.append(confirmation)
            else:
                execution = self._apply_action(record, action_dict, confirmation_id=None)
                executions.append(execution)

        self.plan_repo.mark_executed(plan_id)

        return {
            "plan_id": plan_id,
            "already_executed": False,
            "confirmations": [self.confirmation_to_response(c) for c in confirmations],
            "executions": [self.execution_to_response(e) for e in executions],
        }

    # ------------------------------------------------------------------
    # /confirmations/{id}
    # ------------------------------------------------------------------
    def resolve_confirmation(
        self, confirmation_id: str, decision: str
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        confirmation = self.confirmation_repo.get(confirmation_id)
        if confirmation is None:
            raise ConfirmationNotFoundError(f"confirmation_id '{confirmation_id}'를 찾을 수 없습니다.")

        if confirmation.status != ConfirmationStatus.PENDING.value:
            return self.confirmation_to_response(confirmation), None

        if decision == ConfirmationStatus.ACCEPTED.value:
            record = self.plan_repo.get_by_plan_id(confirmation.plan_id)
            if record is None:
                raise PlanNotFoundError(f"plan_id '{confirmation.plan_id}'를 찾을 수 없습니다.")
            execution = self._apply_action(
                record, confirmation.action_json, confirmation_id=confirmation.confirmation_id
            )
            confirmation = self.confirmation_repo.resolve(confirmation_id, ConfirmationStatus.ACCEPTED.value)
            return self.confirmation_to_response(confirmation), self.execution_to_response(execution)

        confirmation = self.confirmation_repo.resolve(confirmation_id, ConfirmationStatus.REJECTED.value)
        self._record_rejected_action(confirmation.user_id, confirmation.action_json)
        self.memory_v2.record_outcome(
            user_id=confirmation.user_id,
            session_id=confirmation.session_id,
            state_level=self._state_level_for_plan(confirmation.plan_id),
            action=confirmation.action_json,
            effect="rejected",
            ref_id=confirmation.confirmation_id,
        )
        return self.confirmation_to_response(confirmation), None

    # ------------------------------------------------------------------
    # /feedback
    # ------------------------------------------------------------------
    def submit_feedback(
        self, execution_id: str, effect: str, comment: Optional[str] = None
    ) -> Tuple[Dict[str, Any], bool]:
        execution = self.execution_repo.get(execution_id)
        if execution is None:
            raise ExecutionNotFoundError(f"execution_id '{execution_id}'를 찾을 수 없습니다.")

        self.execution_repo.update_feedback(execution_id, effect)
        profile_updated = False
        if effect == FeedbackEffect.NEGATIVE.value:
            profile_updated = self._apply_negative_feedback(execution)
        self.memory_v2.record_outcome(
            user_id=execution.user_id,
            session_id=execution.session_id,
            state_level=self._state_level_for_plan(execution.plan_id),
            action=execution.action_json or {},
            effect=effect,
            ref_id=execution_id,
            comment=comment,
        )

        return self.execution_to_response(self.execution_repo.get(execution_id)), profile_updated

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    def _apply_action(
        self,
        record: ActionPlanRecord,
        action_dict: Dict[str, Any],
        *,
        confirmation_id: Optional[str],
    ) -> Execution:
        action_type = action_dict.get("action_type")
        status = "SUCCESS"
        result: Dict[str, Any] = {}
        try:
            if action_type == ActionType.UPDATE_XR_PARAMETER.value:
                parameter = action_dict.get("xr_parameter")
                final_value = action_dict.get("final_value")
                if not parameter or final_value is None:
                    raise ValueError("xr_parameter 또는 final_value가 없습니다.")
                xr_state = self.xr_runtime.apply_parameter(
                    record.user_id, record.session_id, parameter, float(final_value)
                )
                result = {
                    "applied_parameter": parameter,
                    "final_value": final_value,
                    "xr_state": xr_state,
                }
            elif action_type == ActionType.RECOMMEND_CONTENT.value:
                content = self.content_repo.get_by_content_id(action_dict.get("target_content_id"))
                result = {
                    "recommended_content_id": action_dict.get("target_content_id"),
                    "found": content is not None,
                }
            elif action_type == ActionType.SUGGEST_BREAK.value:
                result = {"suggested_break": True}
            elif action_type == ActionType.KEEP_CURRENT_STATE.value:
                result = {"kept_current_state": True}
            else:
                result = {"observed": True}
        except Exception as exc:  # noqa: BLE001
            status = "FAILED"
            result = {"error": str(exc)}

        return self.execution_repo.create(
            execution_id=f"EXE-{uuid4().hex[:10].upper()}",
            plan_id=record.plan_id,
            confirmation_id=confirmation_id,
            user_id=record.user_id,
            session_id=record.session_id,
            action_json=action_dict,
            status=status,
            result_json=result,
        )

    @staticmethod
    def _action_signature(action_dict: Dict[str, Any]) -> str:
        return f"{action_dict.get('action_type')}:{action_dict.get('xr_parameter') or ''}"

    def _record_rejected_action(self, user_id: str, action_dict: Dict[str, Any]) -> None:
        user = self.user_repo.get_by_user_id(user_id)
        if user is None:
            return
        profile = dict(user.profile_json or {})
        rejected = list(profile.get("rejected_actions") or [])
        signature = self._action_signature(action_dict)
        if signature not in rejected:
            rejected.append(signature)
            profile["rejected_actions"] = rejected
            self.user_repo.update_profile(user_id, profile)

    def _apply_negative_feedback(self, execution: Execution) -> bool:
        user = self.user_repo.get_by_user_id(execution.user_id)
        if user is None:
            return False
        profile = dict(user.profile_json or {})
        action = execution.action_json or {}
        updated = False

        if action.get("action_type") == ActionType.UPDATE_XR_PARAMETER.value and action.get("xr_parameter"):
            sensitivities = dict(profile.get("sensitivities") or {})
            key = action["xr_parameter"]
            sensitivities[key] = round(min(1.0, float(sensitivities.get(key, 0.0)) + 0.1), 4)
            profile["sensitivities"] = sensitivities
            updated = True
        elif action.get("action_type") == ActionType.RECOMMEND_CONTENT.value:
            rejected = list(profile.get("rejected_actions") or [])
            signature = self._action_signature(action)
            if signature not in rejected:
                rejected.append(signature)
                profile["rejected_actions"] = rejected
                updated = True

        if updated:
            self.user_repo.update_profile(execution.user_id, profile)
        return updated

    @staticmethod
    def confirmation_to_response(confirmation: Confirmation) -> Dict[str, Any]:
        return {
            "confirmation_id": confirmation.confirmation_id,
            "plan_id": confirmation.plan_id,
            "user_id": confirmation.user_id,
            "session_id": confirmation.session_id,
            "action_index": confirmation.action_index,
            "action": confirmation.action_json,
            "status": confirmation.status,
            "created_at": confirmation.created_at,
            "resolved_at": confirmation.resolved_at,
        }

    @staticmethod
    def execution_to_response(execution: Execution) -> Dict[str, Any]:
        return {
            "execution_id": execution.execution_id,
            "plan_id": execution.plan_id,
            "confirmation_id": execution.confirmation_id,
            "user_id": execution.user_id,
            "session_id": execution.session_id,
            "action": execution.action_json,
            "status": execution.status,
            "result": execution.result_json,
            "feedback_effect": execution.feedback_effect,
            "created_at": execution.created_at,
        }
