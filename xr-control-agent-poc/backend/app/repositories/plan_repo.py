"""ActionPlan / Confirmation / Execution 리포지토리."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import ActionPlanRecord, Confirmation, Execution


class ActionPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_plan_id(self, plan_id: str) -> Optional[ActionPlanRecord]:
        return (
            self.db.query(ActionPlanRecord)
            .filter(ActionPlanRecord.plan_id == plan_id)
            .first()
        )

    def get_by_state_report_id(self, state_report_id: str) -> Optional[ActionPlanRecord]:
        return (
            self.db.query(ActionPlanRecord)
            .filter(ActionPlanRecord.state_report_id == state_report_id)
            .first()
        )

    def save(self, record: ActionPlanRecord) -> ActionPlanRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_executed(self, plan_id: str) -> Optional[ActionPlanRecord]:
        record = self.get_by_plan_id(plan_id)
        if record is None:
            return None
        record.executed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record


class ConfirmationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, confirmation_id: str) -> Optional[Confirmation]:
        return (
            self.db.query(Confirmation)
            .filter(Confirmation.confirmation_id == confirmation_id)
            .first()
        )

    def list_for_plan(self, plan_id: str) -> List[Confirmation]:
        return (
            self.db.query(Confirmation)
            .filter(Confirmation.plan_id == plan_id)
            .order_by(Confirmation.action_index)
            .all()
        )

    def create(self, **kwargs) -> Confirmation:
        row = Confirmation(**kwargs)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def resolve(self, confirmation_id: str, status: str) -> Optional[Confirmation]:
        row = self.get(confirmation_id)
        if row is None:
            return None
        row.status = status
        row.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row


class ExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, execution_id: str) -> Optional[Execution]:
        return (
            self.db.query(Execution).filter(Execution.execution_id == execution_id).first()
        )

    def list_for_plan(self, plan_id: str) -> List[Execution]:
        return (
            self.db.query(Execution)
            .filter(Execution.plan_id == plan_id)
            .order_by(Execution.id)
            .all()
        )

    def create(self, **kwargs) -> Execution:
        row = Execution(**kwargs)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_feedback(self, execution_id: str, effect: str) -> Optional[Execution]:
        row = self.get(execution_id)
        if row is None:
            return None
        row.feedback_effect = effect
        self.db.commit()
        self.db.refresh(row)
        return row
