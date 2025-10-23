"""Redis 락을 이용한 재고 관리 서비스."""

import time
import uuid
from typing import Optional

from redis import Redis

from app.core.config import Settings


class InventoryService:
    """비관적 락을 이용한 재고 관리 서비스."""

    @staticmethod
    def initialize_stock(product_id: int, quantity: int, redis: Redis) -> bool:
        """
        Redis에 재고를 초기화합니다 (키가 없을 때만).

        SETNX를 사용하여 키가 이미 존재하면 덮어쓰지 않습니다.
        이는 여러 Pod에서 동시에 초기화를 시도할 때 안전성을 보장합니다.

        Args:
            product_id: 상품 ID
            quantity: 초기 재고 수량
            redis: Redis 클라이언트

        Returns:
            성공 시 True (재고 초기화됨), 이미 존재하면 False
        """
        stock_key = f"stock:{product_id}"
        # NX 옵션: 키가 없을 때만 설정 (SETNX)
        result = redis.set(stock_key, quantity, nx=True)
        return bool(result)

    @staticmethod
    def get_stock(product_id: int, redis: Redis) -> Optional[int]:
        """
        Redis에서 현재 재고를 조회합니다.

        Args:
            product_id: 상품 ID
            redis: Redis 클라이언트

        Returns:
            현재 재고 수량, 상품이 없으면 None
        """
        stock = redis.get(f"stock:{product_id}")
        return int(stock) if stock else None

    @staticmethod
    def _get_lock_key(product_id: int) -> str:
        """
        상품의 락 키를 생성합니다.

        Args:
            product_id: 상품 ID

        Returns:
            락 키 문자열
        """
        return f"lock:stock:{product_id}"

    @staticmethod
    def _acquire_lock(
        product_id: int, redis: Redis, settings: Settings
    ) -> Optional[str]:
        """
        TTL을 설정하여 SETNX로 락을 획득합니다.

        Args:
            product_id: 상품 ID
            redis: Redis 클라이언트
            settings: 애플리케이션 설정

        Returns:
            획득 성공 시 락 ID (UUID), 이미 락이 점유 중이면 None
        """
        lock_key = InventoryService._get_lock_key(product_id)
        lock_id = str(uuid.uuid4())

        # NX: 키가 없을 때만 설정
        # EX: 데드락 방지를 위한 만료 시간(TTL) 설정
        acquired = redis.set(
            lock_key, lock_id, nx=True, ex=settings.lock_timeout_seconds
        )

        return lock_id if acquired else None

    @staticmethod
    def _release_lock(product_id: int, lock_id: str, redis: Redis) -> bool:
        """
        원자성을 보장하는 Lua 스크립트로 락을 해제합니다.

        락 ID가 일치하는 경우에만 해제합니다 (다른 클라이언트의 락을
        실수로 해제하는 것을 방지).

        Args:
            product_id: 상품 ID
            lock_id: 소유권 확인용 락 ID
            redis: Redis 클라이언트

        Returns:
            락 해제 성공 시 True, 실패 시 False
        """
        # Lua 스크립트로 원자성 보장: GET + 비교 + DEL을 하나의 트랜잭션으로
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        lock_key = InventoryService._get_lock_key(product_id)
        result = redis.eval(release_script, 1, lock_key, lock_id)

        return bool(result)

    @staticmethod
    def decrease_stock(
        product_id: int, quantity: int, redis: Redis, settings: Settings
    ) -> bool:
        """
        비관적 락과 재시도 메커니즘으로 재고를 감소시킵니다.

        플로우:
        1. 락 획득 시도 (재시도 포함)
        2. 재고 가용성 확인
        3. 재고 원자적 감소
        4. 락 해제

        Args:
            product_id: 상품 ID
            quantity: 감소시킬 수량
            redis: Redis 클라이언트
            settings: 애플리케이션 설정

        Returns:
            재고 감소 성공 시 True, 실패 시 False
            (재고 부족 또는 상품 없음)
        """
        # 원자적 재고 감소를 위한 Lua 스크립트
        decrease_script = """
        local current_stock = redis.call("GET", KEYS[1])
        if not current_stock then
            return -2  -- 상품 없음
        end
        current_stock = tonumber(current_stock)
        local quantity = tonumber(ARGV[1])
        if current_stock >= quantity then
            redis.call("DECRBY", KEYS[1], quantity)
            return current_stock - quantity  -- 남은 재고 반환
        else
            return -1  -- 재고 부족
        end
        """

        # 락 획득을 위한 재시도 메커니즘
        max_retries = settings.lock_retry_attempts
        retry_delay = settings.lock_retry_delay_ms / 1000.0  # ms를 초로 변환

        for attempt in range(max_retries):
            # 락 획득 시도
            lock_id = InventoryService._acquire_lock(product_id, redis, settings)

            if lock_id is not None:
                try:
                    # 락 획득 성공, 재고 감소 수행
                    stock_key = f"stock:{product_id}"
                    result = redis.eval(decrease_script, 1, stock_key, quantity)

                    if result >= 0:
                        # 성공: 재고 감소, result는 남은 재고
                        return True
                    else:
                        # -1: 재고 부족, -2: 상품 없음
                        return False
                finally:
                    # 항상 락 해제
                    InventoryService._release_lock(product_id, lock_id, redis)
            else:
                # 락 획득 실패, 지연 후 재시도
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        # 최대 재시도 횟수 초과
        return False
