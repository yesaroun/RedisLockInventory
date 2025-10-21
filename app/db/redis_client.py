"""
Redis 클라이언트 연결 관리
"""

from redis import Redis

from app.core.config import Settings


def get_redis_client(settings: Settings) -> Redis:
    """
    Redis 클라이언트 생성

    Args:
        settings: 애플리케이션 설정 객체

    Returns:
        Redis 클라이언트 인스턴스
    """
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password if settings.redis_password else None,
        decode_responses=True,
    )
