"""Tests for ProductService."""

import asyncio
import pytest
from redis import Redis
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.core.config import Settings
from app.models import Product
from app.services.product_service import ProductService


class TestCreateProduct:
    """Test: 상품 생성 테스트"""

    def test_create_product_success(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 상품 생성 성공 (DB와 Redis 모두 저장)"""
        name = "MacBook Pro"
        price = 2500000
        stock = 10

        product = ProductService.create_product(
            name=name,
            price=price,
            stock=stock,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # DB 검증
        assert product.id is not None
        assert product.name == name
        assert product.price == price
        assert product.stock == stock
        assert product.created_at is not None
        assert product.updated_at is not None

        # Redis 검증 1: 재고 키는 계속 유지되어야 함 (영구 데이터)
        redis_stock = redis_client.get(f"stock:{product.id}")
        assert redis_stock is not None
        assert int(redis_stock) == stock

        # Redis 검증 2: 락 키는 삭제되어야 정상 (임시 동기화 수단)
        lock_key = f"lock:product:create:{name}"
        lock_value = redis_client.get(lock_key)
        assert lock_value is None, "락 키는 finally 블록에서 삭제되어야 함"

    def test_create_product_with_description(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 설명이 포함된 상품 생성"""
        name = "iPhone 15"
        description = "최신 아이폰 모델"
        price = 1500000
        stock = 20

        product = ProductService.create_product(
            name=name,
            description=description,
            price=price,
            stock=stock,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        assert product.description == description
        redis_stock = redis_client.get(f"stock:{product.id}")
        assert int(redis_stock) == stock

    def test_create_product_zero_stock(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 재고 0인 상품 생성"""
        name = "품절 상품"
        price = 100000
        stock = 0

        product = ProductService.create_product(
            name=name,
            price=price,
            stock=stock,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        assert product.stock == 0
        redis_stock = redis_client.get(f"stock:{product.id}")
        assert int(redis_stock) == 0


class TestGetProduct:
    """Test: 상품 조회 테스트"""

    def test_get_product_exists(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 존재하는 상품 조회"""
        # 상품 생성
        product = ProductService.create_product(
            name="Test Product",
            price=10000,
            stock=5,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # 조회
        found_product = ProductService.get_product(product.id, test_db)

        assert found_product is not None
        assert found_product.id == product.id
        assert found_product.name == product.name

    def test_get_product_not_exists(self, test_db: Session):
        """Test: 존재하지 않는 상품 조회"""
        product = ProductService.get_product(999, test_db)
        assert product is None


class TestGetProductWithStock:
    """Test: 재고 정보 포함 상품 조회 테스트"""

    def test_get_product_with_stock_synced(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: DB와 Redis 재고가 동기화된 상태"""
        # 상품 생성
        product = ProductService.create_product(
            name="Synced Product",
            price=50000,
            stock=15,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # 재고 정보 포함 조회
        result = ProductService.get_product_with_stock(
            product.id, test_db, redis_client
        )

        assert result is not None
        assert result["product"].id == product.id
        assert result["db_stock"] == 15
        assert result["redis_stock"] == 15
        assert result["synced"] is True

    def test_get_product_with_stock_not_synced(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: DB와 Redis 재고가 불일치 상태"""
        # 상품 생성
        product = ProductService.create_product(
            name="Unsynced Product",
            price=30000,
            stock=20,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # Redis 재고만 수동 변경 (비동기 상황 시뮬레이션)
        redis_client.set(f"stock:{product.id}", 15)

        # 재고 정보 포함 조회
        result = ProductService.get_product_with_stock(
            product.id, test_db, redis_client
        )

        assert result["db_stock"] == 20
        assert result["redis_stock"] == 15
        assert result["synced"] is False

    def test_get_product_with_stock_not_exists(
        self, test_db: Session, redis_client: Redis
    ):
        """Test: 존재하지 않는 상품 조회"""
        result = ProductService.get_product_with_stock(999, test_db, redis_client)
        assert result is None


class TestListProducts:
    """Test: 상품 목록 조회 테스트"""

    def test_list_products_empty(self, test_db: Session):
        """Test: 상품이 없는 경우"""
        products = ProductService.list_products(test_db)
        assert products == []

    def test_list_products_multiple(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 여러 상품 조회"""
        # 3개 상품 생성
        ProductService.create_product(
            name="Product 1",
            price=10000,
            stock=5,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )
        ProductService.create_product(
            name="Product 2",
            price=20000,
            stock=10,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )
        ProductService.create_product(
            name="Product 3",
            price=30000,
            stock=15,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        products = ProductService.list_products(test_db)

        assert len(products) == 3
        assert products[0].name == "Product 1"
        assert products[1].name == "Product 2"
        assert products[2].name == "Product 3"

    def test_list_products_with_pagination(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 페이지네이션"""
        # 5개 상품 생성
        for i in range(1, 6):
            ProductService.create_product(
                name=f"Product {i}",
                price=10000 * i,
                stock=i,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        # skip=2, limit=2 (3번째부터 2개)
        products = ProductService.list_products(test_db, skip=2, limit=2)

        assert len(products) == 2
        assert products[0].name == "Product 3"
        assert products[1].name == "Product 4"

    def test_list_products_limit_only(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: limit만 지정"""
        # 5개 상품 생성
        for i in range(1, 6):
            ProductService.create_product(
                name=f"Product {i}",
                price=10000 * i,
                stock=i,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        products = ProductService.list_products(test_db, limit=3)

        assert len(products) == 3
        assert products[0].name == "Product 1"


class TestSyncStockToDb:
    """Test: Redis 재고를 DB에 동기화 테스트"""

    def test_sync_stock_to_db_success(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 재고 동기화 성공"""
        # 상품 생성 (초기 재고 100)
        product = ProductService.create_product(
            name="Sync Test Product",
            price=10000,
            stock=100,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # Redis에서 재고 감소 (구매 시뮬레이션)
        redis_client.set(f"stock:{product.id}", 80)

        # DB에 동기화
        result = ProductService.sync_stock_to_db(product.id, 80, test_db)

        assert result is True

        # DB 재고 확인
        test_db.refresh(product)
        assert product.stock == 80

    def test_sync_stock_to_db_product_not_found(self, test_db: Session):
        """Test: 존재하지 않는 상품 동기화 실패"""
        result = ProductService.sync_stock_to_db(999, 50, test_db)
        assert result is False

    def test_sync_stock_to_db_multiple_times(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 여러 번 동기화"""
        product = ProductService.create_product(
            name="Multiple Sync Product",
            price=20000,
            stock=100,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # 첫 번째 동기화
        ProductService.sync_stock_to_db(product.id, 90, test_db)
        test_db.refresh(product)
        assert product.stock == 90

        # 두 번째 동기화
        ProductService.sync_stock_to_db(product.id, 70, test_db)
        test_db.refresh(product)
        assert product.stock == 70

        # 세 번째 동기화
        ProductService.sync_stock_to_db(product.id, 0, test_db)
        test_db.refresh(product)
        assert product.stock == 0


class TestCreateProductConcurrency:
    """Test: 분산 환경 동시성 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_product_creation_same_name(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 동시에 같은 상품명으로 생성 시도 - 하나만 성공"""
        product_name = "iPhone 15 Pro"

        # 동시에 5개의 코루틴이 같은 이름으로 상품 생성 시도
        async def create_product_async():
            try:
                product = ProductService.create_product(
                    name=product_name,
                    price=1500000,
                    stock=10,
                    db=test_db,
                    redis=redis_client,
                    settings=settings,
                )
                return ("success", product)
            except Exception as e:
                return ("error", str(e))

        # 5개의 동시 요청
        tasks = [create_product_async() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # 결과 분석
        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        # 검증: 정확히 하나만 성공해야 함
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(errors) == 4, f"Expected 4 errors, got {len(errors)}"

        # DB에도 하나만 존재해야 함
        products = test_db.query(Product).filter(Product.name == product_name).all()
        assert len(products) == 1

        # Redis에도 재고가 정확히 하나만 존재
        redis_stock = redis_client.get(f"stock:{products[0].id}")
        assert redis_stock is not None
        assert int(redis_stock) == 10

    def test_create_product_lock_already_held(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 락이 이미 존재할 때 상품 생성 실패"""
        product_name = "MacBook Pro M3"

        # 수동으로 락 설정 (다른 프로세스가 락을 잡고 있는 상황 시뮬레이션)
        lock_key = f"lock:product:create:{product_name}"
        redis_client.set(lock_key, "some-lock-id", ex=10)

        # 상품 생성 시도 - 락 획득 실패로 예외 발생해야 함
        with pytest.raises(Exception) as exc_info:
            ProductService.create_product(
                name=product_name,
                price=2500000,
                stock=5,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        assert "Another product creation in progress" in str(exc_info.value)

        # DB에 상품이 생성되지 않았는지 확인
        products = test_db.query(Product).filter(Product.name == product_name).all()
        assert len(products) == 0

    def test_create_product_duplicate_name_check(
        self, test_db: Session, redis_client: Redis, settings: Settings
    ):
        """Test: 상품명 중복 체크 - 이미 존재하는 이름으로 생성 시도"""
        product_name = "AirPods Pro"

        # 첫 번째 상품 생성 성공
        first_product = ProductService.create_product(
            name=product_name,
            price=300000,
            stock=20,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )
        assert first_product.id is not None

        # 같은 이름으로 두 번째 생성 시도 - 중복 예외 발생
        with pytest.raises(Exception) as exc_info:
            ProductService.create_product(
                name=product_name,
                price=350000,
                stock=15,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        assert "already exists" in str(exc_info.value)

        # DB에 여전히 하나만 존재
        products = test_db.query(Product).filter(Product.name == product_name).all()
        assert len(products) == 1
        assert products[0].id == first_product.id
