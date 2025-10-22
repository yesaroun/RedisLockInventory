"""
인증 관련 API 엔드포인트

회원 가입, 로그인, 사용자 정보 조회 기능을 제공합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.services.auth_service import AuthService
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
)
from app.core.exceptions import UserAlreadyExistsException
from app.models.user import User


router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    새 사용자를 등록합니다.

    Args:
        user_data: 사용자 등록 정보 (username, password)
        db: 데이터베이스 세션

    Returns:
        UserResponse: 생성된 사용자 정보

    Raises:
        HTTPException 409: 이미 존재하는 사용자명

    Example:
        Request:
        ```json
        {
            "username": "john_doe",
            "password": "securePass123"
        }
        ```

        Response (201):
        ```json
        {
            "id": 1,
            "username": "john_doe",
            "email": null,
            "created_at": "2025-01-22T10:30:00Z"
        }
        ```
    """
    try:
        user = AuthService.register_user(
            username=user_data.username,
            password=user_data.password,
            db=db,
        )
        return user

    except UserAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    사용자 로그인 및 JWT 토큰 발급

    Args:
        credentials: 로그인 정보 (username, password)
        db: 데이터베이스 세션
        settings: 애플리케이션 설정

    Returns:
        TokenResponse: JWT 액세스 토큰

    Raises:
        HTTPException 401: 잘못된 인증 정보

    Example:
        Request:
        ```json
        {
            "username": "john_doe",
            "password": "securePass123"
        }
        ```

        Response (200):
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
    """
    user = AuthService.authenticate_user(
        username=credentials.username,
        password=credentials.password,
        db=db,
    )

    # 인증 실패
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT 토큰 생성
    token_data = {"sub": user.username, "user_id": user.id}
    access_token = create_access_token(token_data, settings)

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    현재 인증된 사용자의 정보를 조회합니다.

    Args:
        current_user: 인증된 사용자 (자동 주입)

    Returns:
        UserResponse: 사용자 정보

    Raises:
        HTTPException 401: 인증되지 않은 요청

    Example:
        Request:
        ```
        GET /api/auth/me
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        ```

        Response (200):
        ```json
        {
            "id": 1,
            "username": "john_doe",
            "email": null,
            "created_at": "2025-01-22T10:30:00Z"
        }
        ```
    """
    return current_user
