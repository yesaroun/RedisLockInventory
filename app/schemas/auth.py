"""
인증 관련 Pydantic 스키마

API 요청/응답 모델을 정의합니다.
"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    """
    회원 가입 요청 스키마

    Example:
        {
            "username": "john_doe",
            "password": "securePass123"
        }
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="사용자명 (3-50자)",
        examples=["john_doe"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="비밀번호 (6자 이상)",
        examples=["securePass123"],
    )


class UserLoginRequest(BaseModel):
    """
    로그인 요청 스키마

    Example:
        {
            "username": "john_doe",
            "password": "securePass123"
        }
    """

    username: str = Field(..., description="사용자명", examples=["john_doe"])
    password: str = Field(..., description="비밀번호", examples=["securePass123"])


class TokenResponse(BaseModel):
    """
    JWT 토큰 응답 스키마

    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
    """

    access_token: str = Field(..., description="JWT 액세스 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")


class UserResponse(BaseModel):
    """
    사용자 정보 응답 스키마

    Example:
        {
            "id": 1,
            "username": "john_doe",
            "email": "john@example.com",
            "created_at": "2025-01-22T10:30:00Z"
        }
    """

    model_config = ConfigDict(from_attributes=True)  # Pydantic v2에서 ORM 모델 변환 허용

    id: int = Field(..., description="사용자 ID")
    username: str = Field(..., description="사용자명")
    email: str | None = Field(None, description="이메일 주소 (선택)")
    created_at: datetime = Field(..., description="가입 일시")
