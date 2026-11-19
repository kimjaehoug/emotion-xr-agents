"""사용자 / Profile Memory 리포지토리."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.user_id == user_id).first()

    def list_all(self) -> List[User]:
        return self.db.query(User).order_by(User.user_id).all()

    def create(self, user_id: str, profile: Dict[str, Any]) -> User:
        existing = self.get_by_user_id(user_id)
        if existing:
            raise ValueError(f"사용자 '{user_id}'가 이미 존재합니다.")
        user = User(user_id=user_id, profile_json=profile)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create(self, user_id: str, default_profile: Dict[str, Any]) -> User:
        user = self.get_by_user_id(user_id)
        if user is not None:
            return user
        return self.create(user_id, default_profile)

    def update_profile(self, user_id: str, profile: Dict[str, Any]) -> User:
        user = self.get_by_user_id(user_id)
        if user is None:
            return self.create(user_id, profile)
        user.profile_json = profile
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user
