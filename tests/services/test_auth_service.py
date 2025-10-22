"""
인증 서비스 테스트
"""

from datetime import datetime, timedelta, timezone
import pytest
import jwt

from app.services.auth_service import AuthService
from app.core.config import Settings
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    UserNotFoundException,
)
from app.models.user import User


class TestRegisterUser:
    """회원 가입 테스트 클래스"""

    def test_register_user_success(self, test_db, settings):
        """회원 가입 성공 테스트"""
        username = "testuser1"
        password = "testpassword123"

        user = AuthService.register_user(username, password, test_db)

        # User 객체가 반환되는지 확인
        assert user is not None
        assert isinstance(user, User)
        assert user.id is not None
        assert user.username == username

        # 비밀번호가 해싱되어 저장되는지 확인
        assert user.hashed_password != password
        assert user.hashed_password.startswith("$2b$")

        # 해싱된 비밀번호로 검증 가능한지 확인
        assert verify_password(password, user.hashed_password) is True

        # created_at이 설정되었는지 확인
        assert user.created_at is not None

    def test_register_user_duplicate_username(self, test_db, settings):
        """중복 사용자 등록 실패 테스트"""
        username = "duplicate_user"
        password = "password123"

        # 첫 번째 사용자 등록 성공
        AuthService.register_user(username, password, test_db)

        # 동일한 username으로 재등록 시도 → 예외 발생
        with pytest.raises(UserAlreadyExistsException) as exc_info:
            AuthService.register_user(username, password, test_db)

        # 예외 메시지 확인
        assert username in str(exc_info.value)


class TestAuthenticateUser:
    """로그인 인증 테스트 클래스"""

    def test_authenticate_user_success(self, test_db, settings):
        """로그인 성공 테스트"""
        username = "loginuser"
        password = "securepass456"

        # 사용자 등록
        registered_user = AuthService.register_user(username, password, test_db)

        # 인증 시도
        authenticated_user = AuthService.authenticate_user(username, password, test_db)

        # User 객체가 반환되는지 확인
        assert authenticated_user is not None
        assert isinstance(authenticated_user, User)
        assert authenticated_user.id == registered_user.id
        assert authenticated_user.username == username

    def test_authenticate_user_wrong_password(self, test_db, settings):
        """잘못된 비밀번호로 로그인 실패 테스트"""
        username = "wrongpassuser"
        correct_password = "correct123"
        wrong_password = "wrong456"

        # 사용자 등록
        AuthService.register_user(username, correct_password, test_db)

        # 잘못된 비밀번호로 인증 시도
        result = AuthService.authenticate_user(username, wrong_password, test_db)

        # None이 반환되는지 확인
        assert result is None

    def test_authenticate_user_nonexistent(self, test_db, settings):
        """존재하지 않는 사용자 로그인 실패 테스트"""
        username = "nonexistent_user"
        password = "anypassword"

        # 등록되지 않은 사용자로 인증 시도
        result = AuthService.authenticate_user(username, password, test_db)

        # None이 반환되는지 확인
        assert result is None


class TestGetCurrentUser:
    """토큰으로 사용자 조회 테스트 클래스"""

    def test_get_current_user_success(self, test_db, settings):
        """유효한 토큰으로 사용자 조회 성공 테스트"""
        username = "tokenuser"
        password = "tokenpass789"

        # 사용자 등록
        registered_user = AuthService.register_user(username, password, test_db)

        # JWT 토큰 생성
        token_data = {"sub": username, "user_id": registered_user.id}
        token = create_access_token(token_data, settings)

        # 토큰으로 사용자 조회
        current_user = AuthService.get_current_user(token, test_db, settings)

        # User 객체가 반환되는지 확인
        assert current_user is not None
        assert isinstance(current_user, User)
        assert current_user.id == registered_user.id
        assert current_user.username == username

    def test_get_current_user_invalid_token(self, test_db, settings):
        """잘못된 토큰으로 조회 실패 테스트"""
        invalid_token = "invalid.token.string"

        # 잘못된 토큰으로 조회 시도 → 예외 발생
        with pytest.raises(InvalidCredentialsException) as exc_info:
            AuthService.get_current_user(invalid_token, test_db, settings)

        # 예외 메시지 확인
        assert (
            "invalid" in str(exc_info.value).lower()
            or "credentials" in str(exc_info.value).lower()
        )

    def test_get_current_user_expired_token(self, test_db, settings):
        """만료된 토큰으로 조회 실패 테스트"""
        username = "expireduser"
        password = "expiredpass"

        # 사용자 등록
        AuthService.register_user(username, password, test_db)

        # 만료된 토큰 생성 (1분 전에 만료)
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": username,
            "exp": now - timedelta(minutes=1),
            "iat": now - timedelta(minutes=31),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        # 만료된 토큰으로 조회 시도 → 예외 발생
        with pytest.raises(InvalidCredentialsException) as exc_info:
            AuthService.get_current_user(expired_token, test_db, settings)

        # 예외 메시지 확인
        assert (
            "expired" in str(exc_info.value).lower()
            or "credentials" in str(exc_info.value).lower()
        )

    def test_get_current_user_nonexistent(self, test_db, settings):
        """토큰은 유효하지만 사용자가 없는 경우 테스트"""
        username = "ghost_user"

        # 사용자를 등록하지 않고 토큰만 생성
        token_data = {"sub": username}
        token = create_access_token(token_data, settings)

        # 토큰으로 조회 시도 → 예외 발생
        with pytest.raises(UserNotFoundException) as exc_info:
            AuthService.get_current_user(token, test_db, settings)

        # 예외 메시지에 사용자명이 포함되는지 확인
        assert username in str(exc_info.value)
