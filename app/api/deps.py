"""
FastAPI 의존성 주입 함수들

데이터베이스 세션, 설정, 인증 등의 의존성을 제공합니다.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.exceptions import InvalidCredentialsException, UserNotFoundException


# OAuth2 토큰 스키마 설정
# tokenUrl은 토큰을 얻기 위한 엔드포인트 경로
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    JWT 토큰으로 현재 인증된 사용자를 조회하는 의존성 함수

    Args:
        token: Bearer 토큰 (자동으로 Authorization 헤더에서 추출)
        db: 데이터베이스 세션
        settings: 애플리케이션 설정

    Returns:
        User: 인증된 사용자 객체

    Raises:
        HTTPException: 인증 실패 시 401 Unauthorized

    Example:
        @app.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user": current_user.username}
    """
    try:
        user = AuthService.get_current_user(token, db, settings)
        return user

    except InvalidCredentialsException as e:
        # 토큰이 유효하지 않거나 만료된 경우
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    except UserNotFoundException as e:
        # 토큰은 유효하지만 사용자가 없는 경우
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
