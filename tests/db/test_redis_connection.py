"""
Redis 연결 테스트
"""

from redis import Redis

from app.db.redis_client import create_redis_client


def test_redis_ping(redis_client):
    """Redis 연결 확인 (PING 테스트)"""
    response = redis_client.ping()
    assert response is True


def test_create_redis_client(settings):
    """create_redis_client 함수가 Redis 클라이언트를 반환하는지 테스트"""
    client = create_redis_client(settings)

    assert client is not None
    assert isinstance(client, Redis)

    # 연결 확인
    assert client.ping() is True

    # 정리
    client.close()
