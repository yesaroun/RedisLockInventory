"""Tests for PurchaseService.

구매 처리 서비스 테스트 (TDD)
"""

import pytest
from concurrent.futures import ThreadPoolExecutor
from redis import Redis
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.core.config import Settings
from app.core.exceptions import (
    ProductNotFoundException,
    InsufficientStockException,
    LockAcquisitionException,
)
from app.models import User, Product, Purchase
from app.services.purchase_service import PurchaseService
from app.services.product_service import ProductService
from app.services.inventory_service import InventoryService


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """테스트용 샘플 사용자 생성"""
    user = User(username="testuser", hashed_password="hashed_password_123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_product(
    test_db: Session, redis_client: Redis, settings: Settings
) -> Product:
    """테스트용 샘플 상품 생성 (DB + Redis)"""
    product = ProductService.create_product(
        name="MacBook Pro",
        description="Apple M3 Pro 칩, 16GB RAM, 512GB SSD",
        price=2500000,
        stock=100,
        db=test_db,
        redis=redis_client,
        settings=settings,
    )
    return product


class TestPurchaseProduct:
    """Test: 상품 구매 테스트"""

    def test_purchase_success(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 정상 구매 성공 (Redis + DB 모두 감소 확인)"""
        initial_stock = sample_product.stock
        quantity = 5

        # 구매 실행
        purchase = PurchaseService.purchase_product(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=quantity,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # Purchase 레코드 검증
        assert purchase.id is not None
        assert purchase.user_id == sample_user.id
        assert purchase.product_id == sample_product.id
        assert purchase.quantity == quantity
        assert purchase.total_price == sample_product.price * quantity
        assert purchase.purchased_at is not None

        # DB 재고 검증
        test_db.refresh(sample_product)
        assert sample_product.stock == initial_stock - quantity

        # Redis 재고 검증
        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert redis_stock == initial_stock - quantity

    def test_purchase_product_not_found(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
    ):
        """Test: 존재하지 않는 상품 구매 실패"""
        with pytest.raises(ProductNotFoundException) as exc_info:
            PurchaseService.purchase_product(
                user_id=sample_user.id,
                product_id=99999,  # 존재하지 않는 상품 ID
                quantity=1,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        assert exc_info.value.product_id == 99999

    def test_purchase_insufficient_stock(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 재고 부족 구매 실패"""
        initial_stock = sample_product.stock
        quantity = initial_stock + 10  # 재고보다 많은 수량 요청

        with pytest.raises(InsufficientStockException) as exc_info:
            PurchaseService.purchase_product(
                user_id=sample_user.id,
                product_id=sample_product.id,
                quantity=quantity,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        assert exc_info.value.product_id == sample_product.id
        assert exc_info.value.requested == quantity
        assert exc_info.value.available == initial_stock

        # 재고가 변경되지 않았는지 확인
        test_db.refresh(sample_product)
        assert sample_product.stock == initial_stock

        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert redis_stock == initial_stock

    def test_purchase_zero_stock(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
    ):
        """Test: 재고 0인 상품 구매 실패"""
        # 재고 0인 상품 생성
        product = ProductService.create_product(
            name="품절 상품",
            price=100000,
            stock=0,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        with pytest.raises(InsufficientStockException) as exc_info:
            PurchaseService.purchase_product(
                user_id=sample_user.id,
                product_id=product.id,
                quantity=1,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        assert exc_info.value.available == 0

    def test_purchase_multiple_times_same_user(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 동일 사용자가 여러 번 구매"""
        initial_stock = sample_product.stock

        # 첫 번째 구매
        purchase1 = PurchaseService.purchase_product(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=3,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # 두 번째 구매
        purchase2 = PurchaseService.purchase_product(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=7,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # Purchase 레코드 검증
        assert purchase1.id != purchase2.id
        assert purchase1.quantity == 3
        assert purchase2.quantity == 7

        # 최종 재고 검증 (DB)
        test_db.refresh(sample_product)
        assert sample_product.stock == initial_stock - 10

        # 최종 재고 검증 (Redis)
        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert redis_stock == initial_stock - 10

    def test_purchase_exactly_remaining_stock(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 정확히 남은 재고만큼 구매"""
        remaining_stock = sample_product.stock

        purchase = PurchaseService.purchase_product(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=remaining_stock,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        assert purchase.quantity == remaining_stock

        # 재고 0 확인
        test_db.refresh(sample_product)
        assert sample_product.stock == 0

        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert redis_stock == 0


class TestConcurrentPurchase:
    """Test: 동시 구매 요청 시나리오 (멀티스레드)

    NOTE: SQLite in-memory 데이터베이스는 멀티스레드 환경에서 제한적입니다.
    실제 동시성 테스트는 file-based DB나 PostgreSQL/MySQL 사용을 권장합니다.
    여기서는 락 메커니즘의 기본 동작만 검증합니다.
    """

    def test_sequential_multiple_purchases(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
    ):
        """Test: 여러 구매 요청을 순차적으로 처리하여 재고 정합성 검증"""
        # 재고 50개인 상품 생성
        product = ProductService.create_product(
            name="순차 테스트 상품",
            price=100000,
            stock=50,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # 100번 구매 시도 (각 1개씩)
        success_count = 0
        failure_count = 0

        for _ in range(100):
            try:
                PurchaseService.purchase_product(
                    user_id=sample_user.id,
                    product_id=product.id,
                    quantity=1,
                    db=test_db,
                    redis=redis_client,
                    settings=settings,
                )
                success_count += 1
            except InsufficientStockException:
                failure_count += 1

        # 정확히 50개만 성공해야 함
        assert success_count == 50
        assert failure_count == 50

        # 최종 재고 0 확인
        final_redis_stock = InventoryService.get_stock(product.id, redis_client)
        assert final_redis_stock == 0

        test_db.refresh(product)
        assert product.stock == 0

    @pytest.mark.skip(
        reason="SQLite in-memory는 멀티스레드 환경에서 segfault 발생. "
        "실제 동시성 테스트는 통합 테스트 환경(file-based DB)에서 수행."
    )
    def test_concurrent_purchase_requests(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
    ):
        """Test: 동시 구매 요청 시 재고 정합성 유지"""
        # 재고 50개인 상품 생성
        product = ProductService.create_product(
            name="동시성 테스트 상품",
            price=100000,
            stock=50,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )
        # 다른 세션에서도 볼 수 있도록 커밋
        test_db.commit()

        # 동시 테스트를 위한 세션 팩토리 (test_db와 같은 engine 사용)
        from sqlalchemy.orm import sessionmaker

        TestSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=test_db.get_bind()
        )

        # 동시에 100개 구매 시도 (각 1개씩, 총 100개 스레드)
        # NOTE: SQLite in-memory는 멀티스레드 환경에서 제한적이므로
        # 실제로는 순차적으로 처리하되 락 메커니즘만 검증
        num_requests = 100
        quantity_per_request = 1
        success_count = 0
        failure_count = 0

        def purchase_task(user_id: int, product_id: int):
            """구매 시도 (성공/실패 카운트)"""
            nonlocal success_count, failure_count
            try:
                # 각 스레드는 독립적인 DB 세션을 사용해야 함 (같은 engine)
                db = TestSessionLocal()
                try:
                    PurchaseService.purchase_product(
                        user_id=user_id,
                        product_id=product_id,
                        quantity=quantity_per_request,
                        db=db,
                        redis=redis_client,
                        settings=settings,
                    )
                    success_count += 1
                finally:
                    db.close()
            except (InsufficientStockException, LockAcquisitionException):
                failure_count += 1

        # ThreadPoolExecutor로 동시 구매 요청 (작은 수의 worker로 제한)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(purchase_task, sample_user.id, product.id)
                for _ in range(num_requests)
            ]
            for future in futures:
                future.result()

        # 결과 검증
        # 정확히 50개만 성공해야 함 (초기 재고가 50개)
        assert success_count == 50
        assert failure_count == 50

        # 최종 재고 확인 (Redis)
        final_stock = InventoryService.get_stock(product.id, redis_client)
        assert final_stock == 0

        # 최종 재고 확인 (DB)
        test_db.refresh(product)
        assert product.stock == 0

        # Purchase 레코드 수 확인
        purchases = (
            test_db.query(Purchase).filter(Purchase.product_id == product.id).all()
        )
        assert len(purchases) == 50

        # Purchase 레코드의 총 수량 확인
        total_quantity = sum(p.quantity for p in purchases)
        assert total_quantity == 50

    @pytest.mark.skip(
        reason="SQLite in-memory는 멀티스레드 환경에서 segfault 발생. "
        "실제 동시성 테스트는 통합 테스트 환경(file-based DB)에서 수행."
    )
    def test_concurrent_purchase_with_varying_quantities(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
    ):
        """Test: 다양한 수량의 동시 구매 요청"""
        # 재고 100개인 상품 생성
        product = ProductService.create_product(
            name="다양한 수량 테스트 상품",
            price=50000,
            stock=100,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )
        # 다른 세션에서도 볼 수 있도록 커밋
        test_db.commit()

        # 동시 테스트를 위한 세션 팩토리 (test_db와 같은 engine 사용)
        from sqlalchemy.orm import sessionmaker

        TestSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=test_db.get_bind()
        )

        # 각 스레드가 2~5개씩 랜덤 구매
        import random

        results = []

        def purchase_varying_quantity(user_id: int, product_id: int, quantity: int):
            """다양한 수량 구매 시도"""
            db = TestSessionLocal()
            try:
                purchase = PurchaseService.purchase_product(
                    user_id=user_id,
                    product_id=product_id,
                    quantity=quantity,
                    db=db,
                    redis=redis_client,
                    settings=settings,
                )
                return ("success", quantity, purchase)
            except (InsufficientStockException, LockAcquisitionException):
                return ("failure", quantity, None)
            finally:
                db.close()

        # 40개 요청, 각각 2~5개씩 구매 시도
        quantities = [random.randint(2, 5) for _ in range(40)]

        # 작은 수의 worker로 제한 (SQLite in-memory 제약)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    purchase_varying_quantity, sample_user.id, product.id, qty
                )
                for qty in quantities
            ]
            results = [future.result() for future in futures]

        # 성공한 구매의 총 수량 계산
        successful_purchases = [r for r in results if r[0] == "success"]
        total_purchased = sum(r[1] for r in successful_purchases)

        # 총 구매량은 100개 이하여야 함
        assert total_purchased <= 100

        # 최종 재고 확인 (Redis)
        final_redis_stock = InventoryService.get_stock(product.id, redis_client)
        assert final_redis_stock == 100 - total_purchased

        # 최종 재고 확인 (DB)
        test_db.refresh(product)
        assert product.stock == 100 - total_purchased

        # DB와 Redis 재고가 동기화되어야 함
        assert product.stock == final_redis_stock


class TestPurchaseSynchronization:
    """Test: DB와 Redis 재고 동기화 검증"""

    def test_db_redis_stock_sync_after_purchase(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 구매 후 DB와 Redis 재고가 동기화되는지 확인"""
        quantity = 10

        PurchaseService.purchase_product(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=quantity,
            db=test_db,
            redis=redis_client,
            settings=settings,
        )

        # DB 재고 조회
        test_db.refresh(sample_product)
        db_stock = sample_product.stock

        # Redis 재고 조회
        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)

        # DB와 Redis 재고가 일치해야 함
        assert db_stock == redis_stock
        assert db_stock == 100 - quantity

    def test_purchase_history_consistency(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: 구매 이력과 재고 변경의 일관성"""
        initial_stock = sample_product.stock

        # 여러 번 구매
        quantities = [5, 10, 3, 7]
        for qty in quantities:
            PurchaseService.purchase_product(
                user_id=sample_user.id,
                product_id=sample_product.id,
                quantity=qty,
                db=test_db,
                redis=redis_client,
                settings=settings,
            )

        # Purchase 레코드 조회
        purchases = (
            test_db.query(Purchase)
            .filter(
                Purchase.user_id == sample_user.id,
                Purchase.product_id == sample_product.id,
            )
            .all()
        )

        # Purchase 레코드의 총 수량
        total_purchased = sum(p.quantity for p in purchases)
        assert total_purchased == sum(quantities)

        # 최종 재고 = 초기 재고 - 총 구매량
        test_db.refresh(sample_product)
        expected_stock = initial_stock - total_purchased
        assert sample_product.stock == expected_stock

        # Redis 재고도 동일해야 함
        redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert redis_stock == expected_stock


class TestPurchaseRollback:
    """Test: 트랜잭션 롤백 시나리오"""

    def test_rollback_on_db_error(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """Test: DB 트랜잭션 실패 시 Redis 재고가 롤백되는지 검증"""
        initial_stock = sample_product.stock
        quantity = 5

        # Redis에서도 초기 재고 확인
        initial_redis_stock = InventoryService.get_stock(
            sample_product.id, redis_client
        )
        assert initial_redis_stock == initial_stock

        # db.commit()이 예외를 발생시키도록 mock 설정
        with patch.object(test_db, "commit", side_effect=Exception("DB commit failed")):
            # 구매 시도 - DB 커밋 실패로 예외 발생
            with pytest.raises(Exception) as exc_info:
                PurchaseService.purchase_product(
                    user_id=sample_user.id,
                    product_id=sample_product.id,
                    quantity=quantity,
                    db=test_db,
                    redis=redis_client,
                    settings=settings,
                )

            assert "DB commit failed" in str(exc_info.value)

        # 검증 1: Redis 재고가 원래 값으로 롤백되었는지 확인
        final_redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        assert (
            final_redis_stock == initial_redis_stock
        ), f"Redis 재고가 롤백되지 않음: {final_redis_stock} != {initial_redis_stock}"

        # 검증 2: DB 재고는 변경되지 않았는지 확인 (롤백됨)
        test_db.refresh(sample_product)
        assert sample_product.stock == initial_stock

        # 검증 3: Purchase 레코드가 생성되지 않았는지 확인
        purchases = (
            test_db.query(Purchase)
            .filter(
                Purchase.user_id == sample_user.id,
                Purchase.product_id == sample_product.id,
            )
            .all()
        )
        assert len(purchases) == 0, "DB 롤백 후 Purchase 레코드가 남아있음"

    def test_rollback_with_concurrent_decrease(
        self,
        test_db: Session,
        redis_client: Redis,
        settings: Settings,
        sample_user: User,
        sample_product: Product,
    ):
        """
        Test: Saga 패턴 보상 트랜잭션 검증 - 롤백 중 다른 프로세스의 재고 변경 보존

        시나리오:
        1. 프로세스 A가 재고 10개 감소 시도
        2. DB 커밋 실패로 롤백 필요
        3. 롤백 중간에 프로세스 B가 재고 3개 감소 성공
        4. 프로세스 A의 보상 트랜잭션(increase_stock) 실행
        5. 최종 재고 = 초기 재고 - 3 (B의 변경만 반영)

        기대 결과:
        - INCRBY 방식: 프로세스 B의 변경 보존됨 (통과)
        - SET 방식: 프로세스 B의 변경 손실됨 (실패)
        """
        initial_stock = sample_product.stock  # 예: 100
        process_a_quantity = 10
        process_b_quantity = 3

        # 초기 Redis 재고 확인
        initial_redis_stock = InventoryService.get_stock(
            sample_product.id, redis_client
        )
        assert initial_redis_stock == initial_stock

        # Mock을 사용하여 커밋 중간에 다른 프로세스의 감소를 시뮬레이션
        original_commit = test_db.commit

        def commit_with_concurrent_decrease():
            # DB 커밋 전에 프로세스 B가 재고 감소
            success = InventoryService.decrease_stock(
                sample_product.id, process_b_quantity, redis_client, settings
            )
            assert success, "프로세스 B의 재고 감소 실패"

            # 그 후 DB 커밋 실패 발생
            raise Exception("DB commit failed after concurrent decrease")

        # 프로세스 A: 구매 시도 (DB 커밋 실패)
        with patch.object(
            test_db, "commit", side_effect=commit_with_concurrent_decrease
        ):
            with pytest.raises(Exception) as exc_info:
                PurchaseService.purchase_product(
                    user_id=sample_user.id,
                    product_id=sample_product.id,
                    quantity=process_a_quantity,
                    db=test_db,
                    redis=redis_client,
                    settings=settings,
                )

            assert "DB commit failed" in str(exc_info.value)

        # 검증: 최종 Redis 재고
        # 프로세스 A는 롤백되고, 프로세스 B만 반영되어야 함
        final_redis_stock = InventoryService.get_stock(sample_product.id, redis_client)
        expected_stock = initial_stock - process_b_quantity  # 100 - 3 = 97

        assert final_redis_stock == expected_stock, (
            f"Saga 패턴 실패: 동시 프로세스의 재고 변경이 손실됨. "
            f"예상={expected_stock}, 실제={final_redis_stock}, "
            f"초기={initial_stock}, A감소={process_a_quantity}, B감소={process_b_quantity}"
        )

        # 추가 검증: DB는 여전히 원래 값
        test_db.refresh(sample_product)
        assert sample_product.stock == initial_stock
