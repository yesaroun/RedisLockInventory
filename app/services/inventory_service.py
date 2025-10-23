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
        #
        # ✅ Lua 스크립트 사용 이유:
        # ------------------------------------------------------------------
        # 1. 원자성: GET + 재고 확인 + DECRBY가 단일 연산으로 실행
        # 2. Race Condition 방지: Redis는 단일 스레드이므로 스크립트 실행 중
        #    다른 명령이 끼어들 수 없음
        # 3. 네트워크 왕복 감소: 3번의 왕복 → 1번으로 감소
        #
        # ❌ Python 코드로 구현 시 문제점:
        # ------------------------------------------------------------------
        # current_stock = redis.get(f"stock:{product_id}")     # ① GET 연산
        # if int(current_stock) >= quantity:                   # ② 비교 연산
        #     redis.decrby(f"stock:{product_id}", quantity)    # ③ DECRBY 연산
        #
        # 문제 시나리오 (락이 있어도 발생 가능):
        # T1: 프로세스 A가 ①에서 GET → 재고 10
        # T2: 프로세스 B가 ①에서 GET → 재고 10
        # T3: 프로세스 A가 ②에서 확인 (10 >= 5) → ③에서 DECRBY 5 → 재고 5
        # T4: 프로세스 B가 ②에서 확인 (10 >= 8) → ③에서 DECRBY 8 → 재고 -3 💥
        # 결과: 재고가 음수가 되는 데이터 무결성 문제 발생
        #
        # 📝 Lua 스크립트 상세 설명:
        # ------------------------------------------------------------------
        decrease_script = """
        -- ① Redis에서 현재 재고 조회 (KEYS[1] = "stock:{product_id}")
        local current_stock = redis.call("GET", KEYS[1])

        -- ② 상품이 존재하지 않는 경우 (키가 없음)
        if not current_stock then
            return -2  -- 에러 코드: 상품 없음
        end

        -- ③ 문자열 → 숫자 변환 (Redis는 모든 값을 문자열로 저장)
        -- tonumber(): Lua 내장 함수로 문자열을 숫자로 변환
        -- 예: "10" (문자열) → 10 (숫자)
        -- 필요한 이유: Redis는 String 타입만 저장하므로 산술 연산 시 변환 필수
        current_stock = tonumber(current_stock)

        -- ④ Python에서 전달받은 quantity도 문자열이므로 숫자로 변환
        -- ARGV[1]: Python의 quantity 파라미터 (redis.eval()의 세 번째 인자)
        local quantity = tonumber(ARGV[1])

        -- ⑤ 재고 충분성 확인 (비교 연산)
        if current_stock >= quantity then
            -- ⑥ 재고 감소: DECRBY는 원자적으로 값을 감소시킴
            -- DECRBY stock:1 5 → 현재 값에서 5를 뺌
            redis.call("DECRBY", KEYS[1], quantity)

            -- ⑦ 성공: 남은 재고 반환 (0 이상의 값)
            -- Python에서 result >= 0으로 성공 판단
            return current_stock - quantity
        else
            -- ⑧ 실패: 재고 부족 (에러 코드 -1 반환)
            return -1
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
