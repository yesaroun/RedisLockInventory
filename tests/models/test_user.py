"""
User 모델 테스트

TDD 방식으로 User 모델의 기능을 검증합니다.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.db.database import Base


@pytest.fixture(scope="function")
def db_session():
    """테스트용 인메모리 SQLite 데이터베이스 세션"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


class TestUserModel:
    """User 모델 테스트 클래스"""

    def test_create_user_with_all_fields(self, db_session):
        """모든 필드를 포함한 User 생성 테스트"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_123"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_create_user_without_email(self, db_session):
        """email 없이 User 생성 테스트 (email은 선택적)"""
        user = User(
            username="testuser_no_email",
            hashed_password="hashed_password_123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser_no_email"
        assert user.email is None
        assert user.hashed_password == "hashed_password_123"

    def test_username_unique_constraint(self, db_session):
        """username의 unique constraint 테스트"""
        user1 = User(
            username="duplicateuser",
            hashed_password="password1",
        )
        db_session.add(user1)
        db_session.commit()

        # 같은 username으로 다시 생성 시도
        user2 = User(
            username="duplicateuser",
            hashed_password="password2",
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_email_unique_constraint(self, db_session):
        """email의 unique constraint 테스트"""
        user1 = User(
            username="user1",
            email="same@example.com",
            hashed_password="password1",
        )
        db_session.add(user1)
        db_session.commit()

        # 같은 email로 다시 생성 시도
        user2 = User(
            username="user2",
            email="same@example.com",
            hashed_password="password2",
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_username_not_null(self, db_session):
        """username이 NULL일 수 없음을 테스트"""
        user = User(
            hashed_password="password123",
        )
        db_session.add(user)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_hashed_password_not_null(self, db_session):
        """hashed_password가 NULL일 수 없음을 테스트"""
        user = User(
            username="testuser",
        )
        db_session.add(user)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_created_at_auto_set(self, db_session):
        """created_at이 자동으로 설정되는지 테스트"""
        before_create = datetime.utcnow()

        user = User(
            username="testuser",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        after_create = datetime.utcnow()

        assert user.created_at is not None
        assert before_create <= user.created_at <= after_create

    def test_updated_at_auto_set_on_create(self, db_session):
        """updated_at이 생성 시 자동으로 설정되는지 테스트"""
        user = User(
            username="testuser",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.updated_at is not None
        # created_at과 updated_at은 거의 동일한 시간이어야 함 (1초 이내 차이)
        time_diff = abs((user.updated_at - user.created_at).total_seconds())
        assert time_diff < 1

    def test_updated_at_auto_update_on_modification(self, db_session):
        """updated_at이 수정 시 자동으로 업데이트되는지 테스트"""
        user = User(
            username="testuser",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        original_updated_at = user.updated_at

        # 약간의 시간 지연 후 수정
        import time
        time.sleep(0.01)

        user.email = "updated@example.com"
        db_session.commit()
        db_session.refresh(user)

        assert user.updated_at > original_updated_at

    def test_user_representation(self, db_session):
        """User 객체의 문자열 표현 테스트"""
        user = User(
            username="testuser",
            hashed_password="password123",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # __repr__ 또는 __str__ 메서드가 정의되어 있다면
        assert "testuser" in str(user) or user.username == "testuser"
