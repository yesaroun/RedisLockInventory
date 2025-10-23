"""Tests for InventoryService."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from redis import Redis

from app.core.config import Settings
from app.services.inventory_service import InventoryService


class TestInventoryService:
    """Test cases for InventoryService."""

    def test_initialize_stock(self, redis_client: Redis, settings: Settings):
        """Test: 재고 초기화 테스트"""
        product_id = 1
        quantity = 100

        result = InventoryService.initialize_stock(product_id, quantity, redis_client)

        assert result is True
        stock = redis_client.get(f"stock:{product_id}")
        assert stock is not None
        assert int(stock) == quantity

    def test_get_stock_existing(self, redis_client: Redis, settings: Settings):
        """Test: 재고 조회 테스트 (존재하는 상품)"""
        product_id = 1
        quantity = 50
        redis_client.set(f"stock:{product_id}", quantity)

        stock = InventoryService.get_stock(product_id, redis_client)

        assert stock == quantity

    def test_get_stock_non_existing(self, redis_client: Redis, settings: Settings):
        """Test: 재고 조회 테스트 (존재하지 않는 상품)"""
        product_id = 999

        stock = InventoryService.get_stock(product_id, redis_client)

        assert stock is None

    def test_get_lock_key(self):
        """Test: 락 키 생성 테스트"""
        product_id = 1

        lock_key = InventoryService._get_lock_key(product_id)

        assert lock_key == "lock:stock:1"

    def test_acquire_lock_success(self, redis_client: Redis, settings: Settings):
        """Test: 락 획득 성공 테스트"""
        product_id = 1

        lock_id = InventoryService._acquire_lock(product_id, redis_client, settings)

        assert lock_id is not None
        assert isinstance(lock_id, str)
        lock_key = f"lock:stock:{product_id}"
        stored_lock_id = redis_client.get(lock_key)
        assert stored_lock_id is not None
        # Redis client has decode_responses=True, so it returns strings
        assert stored_lock_id == lock_id

    def test_acquire_lock_already_locked(
        self, redis_client: Redis, settings: Settings
    ):
        """Test: 이미 락이 점유 중일 때 획득 실패"""
        product_id = 1
        lock_key = f"lock:stock:{product_id}"
        redis_client.set(lock_key, "existing-lock-id", ex=10)

        lock_id = InventoryService._acquire_lock(product_id, redis_client, settings)

        assert lock_id is None

    def test_release_lock_success(self, redis_client: Redis, settings: Settings):
        """Test: 락 해제 성공 테스트 (올바른 lock_id)"""
        product_id = 1
        lock_id = InventoryService._acquire_lock(product_id, redis_client, settings)
        assert lock_id is not None

        result = InventoryService._release_lock(product_id, lock_id, redis_client)

        assert result is True
        lock_key = f"lock:stock:{product_id}"
        assert redis_client.get(lock_key) is None

    def test_release_lock_wrong_id(self, redis_client: Redis, settings: Settings):
        """Test: Lua 스크립트 락 해제 테스트 (잘못된 lock_id로 해제 시도 실패)"""
        product_id = 1
        lock_id = InventoryService._acquire_lock(product_id, redis_client, settings)
        assert lock_id is not None

        wrong_lock_id = "wrong-lock-id"
        result = InventoryService._release_lock(
            product_id, wrong_lock_id, redis_client
        )

        assert result is False
        lock_key = f"lock:stock:{product_id}"
        assert redis_client.get(lock_key) is not None  # 락이 여전히 존재해야 함

    def test_release_lock_no_lock(self, redis_client: Redis, settings: Settings):
        """Test: 락이 없을 때 해제 시도"""
        product_id = 1
        lock_id = "some-lock-id"

        result = InventoryService._release_lock(product_id, lock_id, redis_client)

        assert result is False

    def test_lock_expiration(self, redis_client: Redis, settings: Settings):
        """Test: 락 만료 테스트 (TTL)"""
        product_id = 1
        # 1초 TTL로 락 획득
        original_timeout = settings.lock_timeout_seconds
        settings.lock_timeout_seconds = 1

        lock_id = InventoryService._acquire_lock(product_id, redis_client, settings)
        assert lock_id is not None

        lock_key = f"lock:stock:{product_id}"
        assert redis_client.get(lock_key) is not None

        # TTL 만료 대기
        time.sleep(1.5)

        assert redis_client.get(lock_key) is None

        # 원래 설정 복구
        settings.lock_timeout_seconds = original_timeout

    def test_decrease_stock_success(self, redis_client: Redis, settings: Settings):
        """Test: 재고 감소 성공 테스트"""
        product_id = 1
        initial_stock = 100
        decrease_quantity = 10
        redis_client.set(f"stock:{product_id}", initial_stock)

        result = InventoryService.decrease_stock(
            product_id, decrease_quantity, redis_client, settings
        )

        assert result is True
        remaining_stock = InventoryService.get_stock(product_id, redis_client)
        assert remaining_stock == initial_stock - decrease_quantity

    def test_decrease_stock_insufficient(
        self, redis_client: Redis, settings: Settings
    ):
        """Test: 재고 부족 시 감소 실패 테스트"""
        product_id = 1
        initial_stock = 5
        decrease_quantity = 10
        redis_client.set(f"stock:{product_id}", initial_stock)

        result = InventoryService.decrease_stock(
            product_id, decrease_quantity, redis_client, settings
        )

        assert result is False
        remaining_stock = InventoryService.get_stock(product_id, redis_client)
        assert remaining_stock == initial_stock  # 재고가 그대로 유지되어야 함

    def test_decrease_stock_product_not_found(
        self, redis_client: Redis, settings: Settings
    ):
        """Test: 존재하지 않는 상품의 재고 감소 실패"""
        product_id = 999
        decrease_quantity = 10

        result = InventoryService.decrease_stock(
            product_id, decrease_quantity, redis_client, settings
        )

        assert result is False

    def test_concurrent_decrease_stock(self, redis_client: Redis, settings: Settings):
        """Test: 락 충돌 시 재시도 테스트 (동시성)"""
        product_id = 1
        initial_stock = 100
        decrease_quantity = 10
        num_threads = 10  # 10개의 동시 구매 요청

        redis_client.set(f"stock:{product_id}", initial_stock)

        # Increase retry attempts for this high-contention scenario
        original_retry_attempts = settings.lock_retry_attempts
        settings.lock_retry_attempts = 10  # More retries for concurrent test

        def decrease_worker():
            return InventoryService.decrease_stock(
                product_id, decrease_quantity, redis_client, settings
            )

        success_count = 0
        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(decrease_worker) for _ in range(num_threads)]
                for future in as_completed(futures):
                    if future.result():
                        success_count += 1
        finally:
            # Restore original settings
            settings.lock_retry_attempts = original_retry_attempts

        # With increased retries, all requests should succeed
        # The key is that stock integrity is maintained
        assert success_count == num_threads
        remaining_stock = InventoryService.get_stock(product_id, redis_client)
        # 정합성: 최종 재고 = 초기 재고 - (성공한 구매 수 * 구매 수량)
        assert remaining_stock == initial_stock - (decrease_quantity * success_count)
        assert remaining_stock == 0  # Should be exactly 0

    def test_concurrent_decrease_stock_with_insufficient(
        self, redis_client: Redis, settings: Settings
    ):
        """Test: 동시성 + 재고 부족 시나리오"""
        product_id = 1
        initial_stock = 50  # 총 50개
        decrease_quantity = 10
        num_threads = 10  # 10개 스레드가 각각 10개씩 요청 (총 100개 요청)

        redis_client.set(f"stock:{product_id}", initial_stock)

        def decrease_worker():
            return InventoryService.decrease_stock(
                product_id, decrease_quantity, redis_client, settings
            )

        success_count = 0
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(decrease_worker) for _ in range(num_threads)]
            for future in as_completed(futures):
                if future.result():
                    success_count += 1

        # 정확히 5개만 성공해야 함 (50 / 10 = 5)
        assert success_count == 5
        remaining_stock = InventoryService.get_stock(product_id, redis_client)
        assert remaining_stock == 0
