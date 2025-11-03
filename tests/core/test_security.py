"""
비밀번호 해싱 및 JWT 토큰 관련 테스트
"""

from datetime import datetime, timedelta, timezone
import pytest
import jwt

from app.core.security import hash_password, verify_password, create_access_token, verify_access_token
from app.core.config import Settings


class TestPasswordHashing:
    """비밀번호 해싱 테스트 클래스"""

    def test_hash_password(self):
        """비밀번호가 해싱되는지 테스트"""
        password = "test_password_123"
        hashed = hash_password(password)

        # 해시된 값이 원본과 다른지 확인
        assert hashed != password
        # 해시된 값이 존재하는지 확인
        assert hashed is not None
        assert len(hashed) > 0
        # bcrypt 해시는 $2b$로 시작
        assert hashed.startswith("$2b$")

    def test_verify_password_success(self):
        """올바른 비밀번호 검증 성공 테스트"""
        password = "correct_password"
        hashed = hash_password(password)

        # 같은 비밀번호는 검증 성공
        assert verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """잘못된 비밀번호 검증 실패 테스트"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        # 다른 비밀번호는 검증 실패
        assert verify_password(wrong_password, hashed) is False

    def test_hash_password_different_hashes(self):
        """같은 비밀번호도 매번 다른 해시값 생성 테스트"""
        password = "same_password"
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)

        # 같은 비밀번호라도 salt가 다르므로 해시값이 다름
        assert hashed1 != hashed2

        # 하지만 둘 다 검증은 성공해야 함
        assert verify_password(password, hashed1) is True
        assert verify_password(password, hashed2) is True

    def test_verify_password_empty_string(self):
        """빈 문자열 비밀번호 테스트"""
        password = ""
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("not_empty", hashed) is False


class TestJWTToken:
    """JWT 토큰 생성 및 검증 테스트 클래스"""

    @pytest.fixture
    def test_settings(self):
        """테스트용 설정 픽스처"""
        return Settings(
            redis_host="localhost",
            redis_port=6380,
            redis_db=0,
            redis_password="",
            jwt_secret_key="test_secret_key_for_testing",
            jwt_algorithm="HS256",
            jwt_expiration_minutes=30,
        )

    def test_create_access_token(self, test_settings):
        """JWT 토큰 생성 테스트"""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(data, test_settings)

        # 토큰이 생성되는지 확인
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        # JWT 형식인지 확인 (헤더.페이로드.서명)
        parts = token.split(".")
        assert len(parts) == 3

    def test_verify_access_token_success(self, test_settings):
        """유효한 JWT 토큰 검증 성공 테스트"""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(data, test_settings)

        # 토큰 검증
        payload = verify_access_token(token, test_settings)

        # 페이로드 데이터 확인
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == 1
        # exp, iat 등의 클레임도 포함되어야 함
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_access_token_expired(self, test_settings):
        """만료된 JWT 토큰 검증 실패 테스트"""
        # 만료 시간을 음수로 설정하여 즉시 만료되는 토큰 생성
        data = {"sub": "testuser"}

        # 만료된 토큰 직접 생성
        now = datetime.now(timezone.utc)
        payload = {
            **data,
            "exp": now - timedelta(minutes=1),  # 1분 전에 만료
            "iat": now - timedelta(minutes=31),
        }
        expired_token = jwt.encode(
            payload,
            test_settings.jwt_secret_key,
            algorithm=test_settings.jwt_algorithm
        )

        # 만료된 토큰 검증 시 예외 발생
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_access_token(expired_token, test_settings)

    def test_verify_access_token_invalid_signature(self, test_settings):
        """잘못된 서명의 JWT 토큰 검증 실패 테스트"""
        data = {"sub": "testuser"}
        token = create_access_token(data, test_settings)

        # 토큰의 마지막 문자를 변경하여 서명을 손상
        invalid_token = token[:-10] + "corrupted!"

        # 잘못된 서명 검증 시 예외 발생
        with pytest.raises(jwt.InvalidTokenError):
            verify_access_token(invalid_token, test_settings)

    def test_verify_access_token_invalid_format(self, test_settings):
        """잘못된 형식의 JWT 토큰 검증 실패 테스트"""
        invalid_token = "this.is.not.a.valid.jwt.token"

        # 잘못된 형식 검증 시 예외 발생
        with pytest.raises(jwt.InvalidTokenError):
            verify_access_token(invalid_token, test_settings)

    def test_verify_access_token_wrong_secret(self, test_settings):
        """다른 시크릿 키로 생성된 토큰 검증 실패 테스트"""
        data = {"sub": "testuser"}

        # 다른 시크릿 키로 토큰 생성
        wrong_token = jwt.encode(
            {**data, "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            "wrong_secret_key",
            algorithm=test_settings.jwt_algorithm
        )

        # 다른 시크릿으로 생성된 토큰 검증 시 예외 발생
        with pytest.raises(jwt.InvalidTokenError):
            verify_access_token(wrong_token, test_settings)
