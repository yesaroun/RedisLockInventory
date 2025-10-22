"""
User 모델

사용자 계정 정보를 저장하는 SQLAlchemy 모델입니다.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.db.database import Base


class User(Base):
    """
    사용자 모델

    Attributes:
        id: 사용자 고유 ID (Primary Key)
        username: 사용자명 (Unique, Not Null)
        email: 이메일 주소 (Unique, Nullable)
        hashed_password: 해싱된 비밀번호 (Not Null)
        created_at: 생성 일시 (자동 설정)
        updated_at: 수정 일시 (자동 업데이트)
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        """User 객체의 문자열 표현"""
        return f"<User(id={self.id}, username='{self.username}')>"

    def __str__(self) -> str:
        """User 객체의 문자열 표현 (사용자 친화적)"""
        return f"User: {self.username}"
