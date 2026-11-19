"""상태 분석 서비스 파사드."""

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.agents.graph import StateAgentRunner


class AnalyzeService:
    def __init__(self, db: Session) -> None:
        self.runner = StateAgentRunner(db)

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.runner.run(payload)
