"""
Redis 클라이언트 연결 관리
"""

from typing import Generator

from fastapi import Depends
from redis import Redis

from app.core.config import Settings, get_settings


def create_redis_client(settings: Settings) -> Redis:
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


def get_redis_client(
    settings: Settings = Depends(get_settings),
) -> Generator[Redis, None, None]:
    """
    FastAPI 의존성 주입용 Redis 클라이언트 생성 함수

    Args:
        settings: 애플리케이션 설정 (의존성 주입)

    Yields:
        Redis 클라이언트 인스턴스
    """
    client = create_redis_client(settings)
    try:
        yield client
    finally:
        # Redis 클라이언트는 connection pool을 사용하므로 명시적 close 필요 없음
        # 필요시 client.close() 호출 가능
        pass


def create_redis_nodes(settings: Settings) -> list[Redis]:
    """
    Redlock을 위한 다중 Redis 클라이언트 생성

    Args:
        settings: 애플리케이션 설정 객체

    Returns:
        Redis 클라이언트 인스턴스 리스트
    """
    if not settings.redis_nodes:
        # 노드 설정이 없으면 단일 Redis 클라이언트 반환
        return [create_redis_client(settings)]

    redis_clients = []
    for node in settings.redis_node_list:
        client = Redis(
            host=node["host"],
            port=node["port"],
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            decode_responses=True,
        )
        redis_clients.append(client)

    return redis_clients


def get_redis_nodes(
    settings: Settings = Depends(get_settings),
) -> Generator[list[Redis], None, None]:
    """
    FastAPI 의존성 주입용 다중 Redis 클라이언트 생성 함수

    Args:
        settings: 애플리케이션 설정 (의존성 주입)

    Yields:
        Redis 클라이언트 인스턴스 리스트
    """
    clients = create_redis_nodes(settings)
    try:
        yield clients
    finally:
        # Redis 클라이언트는 connection pool을 사용하므로 명시적 close 필요 없음
        pass
