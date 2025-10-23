"""
재고 API 엔드포인트 통합 테스트

TDD 방식으로 inventory API의 기능을 검증합니다.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db
from app.db.redis_client import get_redis_client
from app.core.config import get_settings


@pytest.fixture(scope="function")
def test_client(test_db, redis_client, settings):
    """각 테스트마다 테스트 데이터베이스, Redis, 설정을 제공하는 픽스처"""

    # 데이터베이스 의존성 오버라이드
    def override_get_db():
        try:
            yield test_db
        except:
            test_db.rollback()
            raise

    # Redis 클라이언트 의존성 오버라이드
    def override_get_redis_client():
        yield redis_client

    # Settings 의존성 오버라이드
    def override_get_settings():
        return settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis_client
    app.dependency_overrides[get_settings] = override_get_settings

    # TestClient 생성
    with TestClient(app) as client:
        yield client

    # 정리
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_client):
    """인증 토큰을 포함한 헤더를 반환하는 픽스처"""
    # 사용자 등록
    register_response = test_client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password123"},
    )
    assert register_response.status_code == 201

    # 로그인하여 토큰 획득 (OAuth2 form data 방식)
    login_response = test_client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestProductCreateAPI:
    """상품 생성 API 테스트 클래스"""

    def test_create_product_success(self, test_client, auth_headers):
        """상품 생성 성공 테스트 (201 Created)"""
        response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )

        # 상태 코드 확인
        assert response.status_code == 201

        # 응답 데이터 확인
        data = response.json()
        assert data["name"] == "MacBook Pro"
        assert data["price"] == 2500000
        assert data["stock"] == 10
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_product_without_auth(self, test_client):
        """인증 없이 상품 생성 실패 테스트 (401 Unauthorized)"""
        response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
        )

        assert response.status_code == 401

    def test_create_product_invalid_price(self, test_client, auth_headers):
        """잘못된 가격으로 상품 생성 실패 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": -1000, "stock": 10},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_create_product_invalid_stock(self, test_client, auth_headers):
        """잘못된 재고로 상품 생성 실패 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": -5},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_create_product_empty_name(self, test_client, auth_headers):
        """빈 상품명으로 생성 실패 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/products",
            json={"name": "", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestProductListAPI:
    """상품 목록 조회 API 테스트 클래스"""

    def test_list_products_success(self, test_client, auth_headers):
        """상품 목록 조회 성공 테스트 (200 OK)"""
        # 테스트 상품 생성
        test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        test_client.post(
            "/api/products",
            json={"name": "iPad Pro", "price": 1200000, "stock": 5},
            headers=auth_headers,
        )

        # 목록 조회
        response = test_client.get("/api/products", headers=auth_headers)

        # 상태 코드 확인
        assert response.status_code == 200

        # 응답 데이터 확인
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_products_without_auth(self, test_client):
        """인증 없이 목록 조회 실패 테스트 (401 Unauthorized)"""
        response = test_client.get("/api/products")

        assert response.status_code == 401

    def test_list_products_empty(self, test_client, auth_headers):
        """상품이 없을 때 빈 목록 반환 테스트 (200 OK)"""
        response = test_client.get("/api/products", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestProductDetailAPI:
    """상품 상세 조회 API 테스트 클래스"""

    def test_get_product_success(self, test_client, auth_headers):
        """상품 상세 조회 성공 테스트 (200 OK)"""
        # 상품 생성
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 상세 조회
        response = test_client.get(f"/api/products/{product_id}", headers=auth_headers)

        # 상태 코드 확인
        assert response.status_code == 200

        # 응답 데이터 확인
        data = response.json()
        assert data["id"] == product_id
        assert data["name"] == "MacBook Pro"
        assert data["price"] == 2500000
        assert data["stock"] == 10

    def test_get_product_not_found(self, test_client, auth_headers):
        """존재하지 않는 상품 조회 실패 테스트 (404 Not Found)"""
        response = test_client.get("/api/products/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_product_without_auth(self, test_client):
        """인증 없이 상품 조회 실패 테스트 (401 Unauthorized)"""
        response = test_client.get("/api/products/1")

        assert response.status_code == 401


class TestStockAPI:
    """재고 조회 API 테스트 클래스"""

    def test_get_stock_success(self, test_client, auth_headers):
        """재고 조회 성공 테스트 (200 OK)"""
        # 상품 생성
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 재고 조회
        response = test_client.get(
            f"/api/products/{product_id}/stock", headers=auth_headers
        )

        # 상태 코드 확인
        assert response.status_code == 200

        # 응답 데이터 확인
        data = response.json()
        assert data["product_id"] == product_id
        assert data["db_stock"] == 10
        assert data["redis_stock"] == 10
        assert data["synced"] is True

    def test_get_stock_not_found(self, test_client, auth_headers):
        """존재하지 않는 상품의 재고 조회 실패 테스트 (404 Not Found)"""
        response = test_client.get("/api/products/99999/stock", headers=auth_headers)

        assert response.status_code == 404

    def test_get_stock_without_auth(self, test_client):
        """인증 없이 재고 조회 실패 테스트 (401 Unauthorized)"""
        response = test_client.get("/api/products/1/stock")

        assert response.status_code == 401


class TestPurchaseAPI:
    """상품 구매 API 테스트 클래스"""

    def test_purchase_success(self, test_client, auth_headers):
        """상품 구매 성공 테스트 (200 OK)"""
        # 상품 생성
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 구매
        response = test_client.post(
            "/api/purchases",
            json={"product_id": product_id, "quantity": 2},
            headers=auth_headers,
        )

        # 상태 코드 확인
        assert response.status_code == 200

        # 응답 데이터 확인
        data = response.json()
        assert data["product_id"] == product_id
        assert data["quantity"] == 2
        assert data["total_price"] == 5000000  # 2500000 * 2
        assert "id" in data
        assert "purchased_at" in data

    def test_purchase_insufficient_stock(self, test_client, auth_headers):
        """재고 부족으로 구매 실패 테스트 (400 Bad Request)"""
        # 상품 생성 (재고 5개)
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 5},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 재고보다 많은 수량 구매 시도
        response = test_client.post(
            "/api/purchases",
            json={"product_id": product_id, "quantity": 10},
            headers=auth_headers,
        )

        # 상태 코드 확인
        assert response.status_code == 400
        assert "insufficient stock" in response.json()["detail"].lower()

    def test_purchase_product_not_found(self, test_client, auth_headers):
        """존재하지 않는 상품 구매 실패 테스트 (404 Not Found)"""
        response = test_client.post(
            "/api/purchases",
            json={"product_id": 99999, "quantity": 1},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_purchase_without_auth(self, test_client):
        """인증 없이 구매 실패 테스트 (401 Unauthorized)"""
        response = test_client.post(
            "/api/purchases",
            json={"product_id": 1, "quantity": 1},
        )

        assert response.status_code == 401

    def test_purchase_invalid_quantity(self, test_client, auth_headers):
        """잘못된 수량으로 구매 실패 테스트 (422 Validation Error)"""
        response = test_client.post(
            "/api/purchases",
            json={"product_id": 1, "quantity": 0},
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestPurchaseHistoryAPI:
    """구매 이력 조회 API 테스트 클래스"""

    def test_get_my_purchases_success(self, test_client, auth_headers):
        """내 구매 이력 조회 성공 테스트 (200 OK)"""
        # 상품 생성
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 구매 2회
        test_client.post(
            "/api/purchases",
            json={"product_id": product_id, "quantity": 1},
            headers=auth_headers,
        )
        test_client.post(
            "/api/purchases",
            json={"product_id": product_id, "quantity": 2},
            headers=auth_headers,
        )

        # 구매 이력 조회
        response = test_client.get("/api/purchases/me", headers=auth_headers)

        # 상태 코드 확인
        assert response.status_code == 200

        # 응답 데이터 확인
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_my_purchases_empty(self, test_client, auth_headers):
        """구매 이력이 없을 때 빈 목록 반환 테스트 (200 OK)"""
        response = test_client.get("/api/purchases/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_my_purchases_without_auth(self, test_client):
        """인증 없이 구매 이력 조회 실패 테스트 (401 Unauthorized)"""
        response = test_client.get("/api/purchases/me")

        assert response.status_code == 401


class TestStockDecrementAfterPurchase:
    """구매 후 재고 감소 검증 테스트 클래스"""

    def test_stock_decreases_after_purchase(self, test_client, auth_headers):
        """구매 후 DB와 Redis 재고 모두 감소하는지 테스트"""
        # 상품 생성
        create_response = test_client.post(
            "/api/products",
            json={"name": "MacBook Pro", "price": 2500000, "stock": 10},
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # 구매 전 재고 확인
        stock_before = test_client.get(
            f"/api/products/{product_id}/stock", headers=auth_headers
        )
        assert stock_before.json()["db_stock"] == 10
        assert stock_before.json()["redis_stock"] == 10

        # 구매
        test_client.post(
            "/api/purchases",
            json={"product_id": product_id, "quantity": 3},
            headers=auth_headers,
        )

        # 구매 후 재고 확인
        stock_after = test_client.get(
            f"/api/products/{product_id}/stock", headers=auth_headers
        )
        assert stock_after.json()["db_stock"] == 7
        assert stock_after.json()["redis_stock"] == 7
        assert stock_after.json()["synced"] is True
