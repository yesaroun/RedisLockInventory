"""
인증 서비스

사용자 등록, 로그인, 토큰 기반 사용자 조회 기능을 제공합니다.
"""

import jwt
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password, verify_password, verify_access_token
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    UserNotFoundException,
)
from app.models.user import User


class AuthService:
    """인증 관련 비즈니스 로직을 처리하는 서비스 클래스"""

    @staticmethod
    def register_user(username: str, password: str, db: Session) -> User:
        """
        새 사용자를 등록합니다.

        Args:
            username: 사용자명
            password: 평문 비밀번호
            db: 데이터베이스 세션

        Returns:
            User: 생성된 사용자 객체

        Raises:
            UserAlreadyExistsException: 이미 존재하는 사용자명인 경우

        Example:
            >>> user = AuthService.register_user("john", "secret123", db)
            >>> user.username
            'john'
        """
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise UserAlreadyExistsException(username)

        hashed_password = hash_password(password)
        new_user = User(username=username, hashed_password=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return new_user

    @staticmethod
    def authenticate_user(username: str, password: str, db: Session) -> User | None:
        """
        사용자 인증을 수행합니다.

        Args:
            username: 사용자명
            password: 평문 비밀번호
            db: 데이터베이스 세션

        Returns:
            User | None: 인증 성공 시 User 객체, 실패 시 None

        Example:
            >>> user = AuthService.authenticate_user("john", "secret123", db)
            >>> user.username if user else None
            'john'
        """
        user: User | None = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def get_current_user(token: str, db: Session, settings: Settings) -> User:
        """
        JWT 토큰에서 현재 사용자를 조회합니다.

        Args:
            token: JWT 액세스 토큰
            db: 데이터베이스 세션
            settings: 애플리케이션 설정

        Returns:
            User: 사용자 객체

        Raises:
            InvalidCredentialsException: 토큰이 유효하지 않거나 만료된 경우
            UserNotFoundException: 토큰은 유효하지만 사용자가 없는 경우

        Example:
            >>> token = create_access_token({"sub": "john"}, settings)
            >>> user = AuthService.get_current_user(token, db, settings)
            >>> user.username
            'john'
        """
        try:
            # 토큰 검증
            payload = verify_access_token(token, settings)
        except jwt.ExpiredSignatureError:
            # 만료된 토큰
            raise InvalidCredentialsException("Token has expired")
        except jwt.InvalidTokenError:
            # 유효하지 않은 토큰 (잘못된 서명, 형식 등)
            raise InvalidCredentialsException("Invalid token")

        # 페이로드에서 username 추출 (sub 클레임)
        username = payload.get("sub")
        if not username:
            raise InvalidCredentialsException("Token payload missing 'sub' claim")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise UserNotFoundException(username)

        return user
