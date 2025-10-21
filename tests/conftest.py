"""
pytest 픽스처 정의
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.redis_client import get_redis_client
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
