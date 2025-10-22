"""
보안 관련 유틸리티 함수

비밀번호 해싱 및 JWT 토큰 생성/검증 기능을 제공합니다.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import bcrypt
import jwt

from app.core.config import Settings


def hash_password(password: str) -> str:
    """
    비밀번호를 bcrypt로 해싱합니다.

    Args:
        password: 해싱할 평문 비밀번호

    Returns:
        str: bcrypt로 해싱된 비밀번호 (salt 포함)

    Example:
        >>> hashed = hash_password("my_password")
        >>> hashed.startswith("$2b$")
        True
    """
    password_bytes = password.encode("utf-8")

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해시된 비밀번호를 비교하여 검증합니다.

    Args:
        plain_password: 검증할 평문 비밀번호
        hashed_password: 저장된 해시된 비밀번호

    Returns:
        bool: 비밀번호가 일치하면 True, 그렇지 않으면 False

    Example:
        >>> hashed = hash_password("my_password")
        >>> verify_password("my_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    password_bytes = plain_password.encode("utf-8")

    hashed_bytes = hashed_password.encode("utf-8")

    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: Dict[str, Any], settings: Settings) -> str:
    """
    JWT 액세스 토큰을 생성합니다.

    Args:
        data: 토큰에 포함할 페이로드 데이터 (예: {"sub": "username", "user_id": 1})
        settings: 애플리케이션 설정 (JWT 시크릿 키, 알고리즘, 만료 시간 포함)

    Returns:
        str: 생성된 JWT 토큰 문자열

    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> token = create_access_token({"sub": "testuser", "user_id": 1}, settings)
        >>> isinstance(token, str)
        True
    """
    # 페이로드 복사본 생성 (원본 데이터 보존)
    payload = data.copy()

    now = datetime.now(timezone.utc)
    payload.update(
        {"iat": now, "exp": now + timedelta(minutes=settings.jwt_expiration_minutes)}
    )
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    return token


def verify_access_token(token: str, settings: Settings) -> Dict[str, Any]:
    """
    JWT 액세스 토큰을 검증하고 페이로드를 반환합니다.

    Args:
        token: 검증할 JWT 토큰 문자열
        settings: 애플리케이션 설정 (JWT 시크릿 키, 알고리즘 포함)

    Returns:
        Dict[str, Any]: 토큰의 페이로드 데이터

    Raises:
        jwt.ExpiredSignatureError: 토큰이 만료된 경우
        jwt.InvalidTokenError: 토큰이 유효하지 않은 경우 (잘못된 서명, 형식 등)

    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> token = create_access_token({"sub": "testuser"}, settings)
        >>> payload = verify_access_token(token, settings)
        >>> payload["sub"]
        'testuser'
    """
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )

    return payload
