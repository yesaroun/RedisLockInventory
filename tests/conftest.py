"""
pytest 픽스처 정의
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import Settings
from app.db.redis_client import get_redis_client
from app.db.database import Base
from app.main import app


@pytest.fixture(scope="session")
def settings():
    """테스트용 설정 객체 픽스처"""
    return Settings(
        redis_host="localhost",
        redis_port=6379,
        redis_db=1,  # 테스트용 DB 프로덕션과 분리
        redis_password="",
        jwt_secret_key="test-secret-key-for-testing",
        jwt_algorithm="HS256",
        jwt_expiration_minutes=30,
        lock_timeout_seconds=10,
        lock_retry_attempts=3,
        lock_retry_delay_ms=100,
    )


@pytest.fixture(scope="function")
def redis_client(settings):
    """
    테스트용 Redis 클라이언트 픽스처

    각 테스트 함수마다 새로운 Redis 연결을 생성하고,
    테스트 종료 후 데이터를 정리합니다.
    """
    client = get_redis_client(settings)

    # 테스트 시작 전 DB 비우기 (테스트 DB만 비움)
    client.flushdb()

    yield client

    # 테스트 종료 후 정리
    client.flushdb()
    client.close()


@pytest.fixture(scope="module")
def test_app():
    """FastAPI TestClient 픽스처"""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def test_db() -> Session:
    """
    테스트용 in-memory SQLite 데이터베이스 세션 픽스처

    각 테스트 함수마다 새로운 데이터베이스를 생성하고,
    테스트 종료 후 자동으로 롤백하여 격리를 보장합니다.
    """
    # In-memory SQLite 데이터베이스 엔진 생성
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)

    # 테스트용 세션 생성
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        # 테스트 종료 후 세션 닫기
        db.close()
        # 모든 테이블 삭제
        Base.metadata.drop_all(bind=engine)
