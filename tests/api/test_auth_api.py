"""
인증 API 엔드포인트 통합 테스트
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db
# conftest.py의 test_db 픽스처를 사용합니다


@pytest.fixture(scope="function")
def test_client(test_db):
    """각 테스트마다 테스트 데이터베이스와 클라이언트를 제공하는 픽스처"""
    # conftest.py의 test_db 픽스처를 의존성으로 주입
    def override_get_db():
        try:
            yield test_db
        except:
            test_db.rollback()
            raise

    # 데이터베이스 의존성 오버라이드
    app.dependency_overrides[get_db] = override_get_db

    # TestClient 생성
    with TestClient(app) as client:
        yield client

    # 정리
    app.dependency_overrides.clear()


class TestRegisterAPI:
    """회원 가입 API 테스트 클래스"""

    def test_register_success(self, test_client):
        """회원 가입 성공 테스트 (201 Created)"""
        response = test_client.post(
            "/api/auth/register",
            json={"username": "newuser", "password": "password123"},
        )

        # 상태 코드 확인
        assert response.status_code == 201

        # 응답 데이터 확인
        data = response.json()
        assert "id" in data
        assert data["username"] == "newuser"
        assert "created_at" in data
        # 비밀번호는 응답에 포함되지 않아야 함
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_username(self, test_client):
        """중복 사용자명 등록 실패 테스트 (409 Conflict)"""
        username = "duplicateuser"
        password = "password123"

        # 첫 번째 등록 성공
        response1 = test_client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        assert response1.status_code == 201

        # 동일한 사용자명으로 재등록 시도
        response2 = test_client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )

        # 409 Conflict 응답 확인
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()

    def test_register_invalid_username_too_short(self, test_client):
        """사용자명이 너무 짧은 경우 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "password123"},  # 2자 (최소 3자 필요)
        )

        # 422 Unprocessable Entity
        assert response.status_code == 422

    def test_register_invalid_password_too_short(self, test_client):
        """비밀번호가 너무 짧은 경우 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/auth/register",
            json={"username": "validuser", "password": "12345"},  # 5자 (최소 6자 필요)
        )

        # 422 Unprocessable Entity
        assert response.status_code == 422


class TestLoginAPI:
    """로그인 API 테스트 클래스"""

    def test_login_success(self, test_client):
        """로그인 성공 테스트 (200 OK, 토큰 반환)"""
        username = "loginuser"
        password = "loginpass123"

        # 먼저 회원 가입
        test_client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )

        # 로그인 시도
        response = test_client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

        # 상태 코드 확인
        assert response.status_code == 200

        # 토큰 응답 확인
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

        # JWT 형식 확인 (헤더.페이로드.서명)
        token_parts = data["access_token"].split(".")
        assert len(token_parts) == 3

    def test_login_wrong_password(self, test_client):
        """잘못된 비밀번호 로그인 실패 테스트 (401 Unauthorized)"""
        username = "wrongpassuser"
        correct_password = "correctpass123"
        wrong_password = "wrongpass456"

        # 회원 가입
        test_client.post(
            "/api/auth/register",
            json={"username": username, "password": correct_password},
        )

        # 잘못된 비밀번호로 로그인 시도
        response = test_client.post(
            "/api/auth/login",
            json={"username": username, "password": wrong_password},
        )

        # 401 Unauthorized
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, test_client):
        """존재하지 않는 사용자 로그인 실패 테스트 (401 Unauthorized)"""
        response = test_client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "anypassword"},
        )

        # 401 Unauthorized
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


class TestGetMeAPI:
    """현재 사용자 조회 API 테스트 클래스"""

    def test_get_me_success(self, test_client):
        """인증된 사용자 정보 조회 성공 테스트 (200 OK)"""
        username = "meuser"
        password = "mepass123"

        # 회원 가입
        register_response = test_client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        user_id = register_response.json()["id"]

        # 로그인하여 토큰 획득
        login_response = test_client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        token = login_response.json()["access_token"]

        # 인증 헤더와 함께 /me 요청
        response = test_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        # 상태 코드 확인
        assert response.status_code == 200

        # 사용자 정보 확인
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == username
        assert "created_at" in data

    def test_get_me_without_token(self, test_client):
        """토큰 없이 /me 접근 시 실패 테스트 (401 Unauthorized)"""
        response = test_client.get("/api/auth/me")

        # 401 Unauthorized
        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, test_client):
        """유효하지 않은 토큰으로 /me 접근 실패 테스트 (401 Unauthorized)"""
        response = test_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        # 401 Unauthorized
        assert response.status_code == 401
