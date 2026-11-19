"""정책 / 행동 / 콘텐츠 카탈로그 리포지토리."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import ActionCatalogEntry, Content, ResponsePolicy


class PolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> List[ResponsePolicy]:
        return (
            self.db.query(ResponsePolicy)
            .filter(ResponsePolicy.is_active.is_(True))
            .all()
        )

    def list_all(self) -> List[ResponsePolicy]:
        return self.db.query(ResponsePolicy).order_by(ResponsePolicy.id).all()

    def get_by_key(self, policy_key: str) -> Optional[ResponsePolicy]:
        return (
            self.db.query(ResponsePolicy)
            .filter(ResponsePolicy.policy_key == policy_key)
            .first()
        )

    def get_for_state_level(self, state_level: str) -> Optional[ResponsePolicy]:
        return (
            self.db.query(ResponsePolicy)
            .filter(
                ResponsePolicy.state_level == state_level,
                ResponsePolicy.is_active.is_(True),
            )
            .first()
        )

    def create(self, **kwargs) -> ResponsePolicy:
        policy = ResponsePolicy(**kwargs)
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy


class ActionCatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> List[ActionCatalogEntry]:
        return (
            self.db.query(ActionCatalogEntry)
            .filter(ActionCatalogEntry.is_active.is_(True))
            .all()
        )

    def list_all(self) -> List[ActionCatalogEntry]:
        return self.db.query(ActionCatalogEntry).order_by(ActionCatalogEntry.id).all()

    def find(
        self, action_type: str, xr_parameter: Optional[str] = None
    ) -> Optional[ActionCatalogEntry]:
        query = self.db.query(ActionCatalogEntry).filter(
            ActionCatalogEntry.action_type == action_type,
            ActionCatalogEntry.is_active.is_(True),
        )
        if xr_parameter is not None:
            query = query.filter(ActionCatalogEntry.xr_parameter == xr_parameter)
        return query.first()

    def create(self, **kwargs) -> ActionCatalogEntry:
        entry = ActionCatalogEntry(**kwargs)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry


class ContentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> List[Content]:
        return self.db.query(Content).filter(Content.is_active.is_(True)).all()

    def list_all(self) -> List[Content]:
        return self.db.query(Content).order_by(Content.id).all()

    def get_by_content_id(self, content_id: str) -> Optional[Content]:
        return self.db.query(Content).filter(Content.content_id == content_id).first()

    def create(self, **kwargs) -> Content:
        content = Content(**kwargs)
        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)
        return content
