"""
Redlock 알고리즘을 이용한 분산 락 재고 관리 서비스 (수동 쿼럼 구현)
"""

import asyncio
import uuid
from typing import Optional

from redis import Redis

from app.core.config import Settings


class RedlockManualService:
    """
    수동 쿼럼 구현 기반 Redlock 알고리즘 재고 관리 서비스

    - 다중 Redis 노드에 수동으로 락 획득
    - 쿼럼(N/2+1) 기반 합의 알고리즘
    - aioredlock 라이브러리 없이 직접 구현
    - 동기/비동기 버전 모두 제공
    """

    @staticmethod
    def initialize_stock(
        product_id: int, quantity: int, redis_nodes: list[Redis]
    ) -> bool:
        """
        모든 Redis 노드에 재고를 초기화합니다.

        Args:
            product_id: 상품 ID
            quantity: 초기 재고 수량
            redis_nodes: Redis 클라이언트 리스트

        Returns:
            성공 시 True
        """
        stock_key = f"stock:{product_id}"
        success_count = 0

        for redis in redis_nodes:
            try:
                result = redis.set(stock_key, quantity, nx=True)
                if result:
                    success_count += 1
            except Exception:
                continue

        # 쿼럼 이상의 노드에서 성공하면 OK
        quorum = len(redis_nodes) // 2 + 1
        return success_count >= quorum

    @staticmethod
    def get_stock(product_id: int, redis_nodes: list[Redis]) -> Optional[int]:
        """
        쿼럼 기반으로 재고를 조회합니다.

        여러 노드에서 값을 읽고, 가장 많이 나타나는 값을 반환합니다.

        Args:
            product_id: 상품 ID
            redis_nodes: Redis 클라이언트 리스트

        Returns:
            현재 재고 수량, 쿼럼을 만족하지 못하면 None
        """
        stock_key = f"stock:{product_id}"
        stock_values = []

        for redis in redis_nodes:
            try:
                stock = redis.get(stock_key)
                if stock is not None:
                    stock_values.append(int(stock))
            except Exception:
                continue

        if not stock_values:
            return None

        # 쿼럼 확인: 과반수 이상의 노드에서 같은 값을 읽었는지 확인
        quorum = len(redis_nodes) // 2 + 1
        if len(stock_values) >= quorum:
            # 가장 빈번한 값 반환 (일반적으로 모든 노드가 동일한 값을 가짐)
            return max(set(stock_values), key=stock_values.count)

        return None

    @staticmethod
    def decrease_stock_sync(
        product_id: int,
        quantity: int,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> bool:
        """
        동기 방식으로 재고를 감소시킵니다 (수동 쿼럼 구현).

        Args:
            product_id: 상품 ID
            quantity: 감소시킬 수량
            redis_nodes: Redis 클라이언트 리스트
            settings: 애플리케이션 설정

        Returns:
            재고 감소 성공 시 True, 실패 시 False
        """
        lock_key = f"lock:stock:{product_id}"
        lock_id = str(uuid.uuid4())
        quorum = len(redis_nodes) // 2 + 1

        # 1. 모든 노드에 락 획득 시도
        acquired_locks = []
        for redis in redis_nodes:
            try:
                acquired = redis.set(
                    lock_key,
                    lock_id,
                    nx=True,
                    ex=settings.lock_timeout_seconds,
                )
                if acquired:
                    acquired_locks.append(redis)
            except Exception:
                continue

        # 2. 쿼럼 확인
        if len(acquired_locks) < quorum:
            # 쿼럼 실패: 획득한 락 모두 해제
            RedlockManualService._release_locks(acquired_locks, lock_key, lock_id)
            return False

        try:
            # 3. 재고 감소 수행
            decrease_script = """
            local current_stock = redis.call("GET", KEYS[1])
            if not current_stock then
                return -2
            end
            current_stock = tonumber(current_stock)
            local quantity = tonumber(ARGV[1])
            if current_stock >= quantity then
                redis.call("DECRBY", KEYS[1], quantity)
                return current_stock - quantity
            else
                return -1
            end
            """

            stock_key = f"stock:{product_id}"
            success_count = 0

            for redis in redis_nodes:
                try:
                    result = redis.eval(decrease_script, 1, stock_key, quantity)
                    if result >= 0:
                        success_count += 1
                except Exception:
                    continue

            # 4. 재고 감소 쿼럼 확인
            if success_count >= quorum:
                return True
            else:
                # 롤백
                rollback_script = """
                redis.call("INCRBY", KEYS[1], ARGV[1])
                return 1
                """
                for redis in redis_nodes:
                    try:
                        redis.eval(rollback_script, 1, stock_key, quantity)
                    except Exception:
                        continue
                return False

        finally:
            # 5. 락 해제
            RedlockManualService._release_locks(acquired_locks, lock_key, lock_id)

    @staticmethod
    async def decrease_stock_async(
        product_id: int,
        quantity: int,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> bool:
        """
        비동기 방식으로 재고를 감소시킵니다 (수동 쿼럼 구현).

        Args:
            product_id: 상품 ID
            quantity: 감소시킬 수량
            redis_nodes: Redis 클라이언트 리스트
            settings: 애플리케이션 설정

        Returns:
            재고 감소 성공 시 True, 실패 시 False
        """
        lock_key = f"lock:stock:{product_id}"
        lock_id = str(uuid.uuid4())
        quorum = len(redis_nodes) // 2 + 1

        # 1. 모든 노드에 락 획득 시도 (비동기적으로 병렬 처리)
        async def try_acquire_lock(redis: Redis) -> Optional[Redis]:
            """단일 노드에 락 획득 시도"""
            try:
                # 비동기 컨텍스트에서 동기 Redis 호출을 실행
                loop = asyncio.get_event_loop()
                acquired = await loop.run_in_executor(
                    None,
                    lambda: redis.set(
                        lock_key,
                        lock_id,
                        nx=True,
                        ex=settings.lock_timeout_seconds,
                    ),
                )
                return redis if acquired else None
            except Exception:
                return None

        # 병렬로 모든 노드에 락 획득 시도
        tasks = [try_acquire_lock(redis) for redis in redis_nodes]
        results = await asyncio.gather(*tasks)
        acquired_locks = [redis for redis in results if redis is not None]

        # 2. 쿼럼 확인
        if len(acquired_locks) < quorum:
            # 쿼럼 실패: 획득한 락 모두 해제
            await RedlockManualService._release_locks_async(
                acquired_locks, lock_key, lock_id
            )
            return False

        try:
            # 3. 재고 감소 수행
            decrease_script = """
            local current_stock = redis.call("GET", KEYS[1])
            if not current_stock then
                return -2
            end
            current_stock = tonumber(current_stock)
            local quantity = tonumber(ARGV[1])
            if current_stock >= quantity then
                redis.call("DECRBY", KEYS[1], quantity)
                return current_stock - quantity
            else
                return -1
            end
            """

            stock_key = f"stock:{product_id}"

            async def decrease_on_node(redis: Redis) -> bool:
                """단일 노드에서 재고 감소"""
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda: redis.eval(decrease_script, 1, stock_key, quantity),
                    )
                    return result >= 0
                except Exception:
                    return False

            # 병렬로 모든 노드에서 재고 감소
            decrease_tasks = [decrease_on_node(redis) for redis in redis_nodes]
            decrease_results = await asyncio.gather(*decrease_tasks)
            success_count = sum(decrease_results)

            # 4. 재고 감소 쿼럼 확인
            if success_count >= quorum:
                return True
            else:
                # 롤백
                rollback_script = """
                redis.call("INCRBY", KEYS[1], ARGV[1])
                return 1
                """

                async def rollback_on_node(redis: Redis):
                    """단일 노드에서 롤백"""
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            lambda: redis.eval(rollback_script, 1, stock_key, quantity),
                        )
                    except Exception:
                        pass

                rollback_tasks = [rollback_on_node(redis) for redis in redis_nodes]
                await asyncio.gather(*rollback_tasks)
                return False

        finally:
            # 5. 락 해제
            await RedlockManualService._release_locks_async(
                acquired_locks, lock_key, lock_id
            )

    @staticmethod
    def _release_locks(redis_clients: list[Redis], lock_key: str, lock_id: str):
        """
        여러 Redis 노드에서 락을 해제합니다 (동기).

        Args:
            redis_clients: Redis 클라이언트 리스트
            lock_key: 락 키
            lock_id: 락 ID
        """
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        for redis in redis_clients:
            try:
                redis.eval(release_script, 1, lock_key, lock_id)
            except Exception:
                continue

    @staticmethod
    async def _release_locks_async(
        redis_clients: list[Redis], lock_key: str, lock_id: str
    ):
        """
        여러 Redis 노드에서 락을 해제합니다 (비동기).

        Args:
            redis_clients: Redis 클라이언트 리스트
            lock_key: 락 키
            lock_id: 락 ID
        """
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        async def release_on_node(redis: Redis):
            """단일 노드에서 락 해제"""
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: redis.eval(release_script, 1, lock_key, lock_id)
                )
            except Exception:
                pass

        tasks = [release_on_node(redis) for redis in redis_clients]
        await asyncio.gather(*tasks)
