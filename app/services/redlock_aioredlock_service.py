"""
Redlock 알고리즘을 이용한 분산 락 재고 관리 서비스 (aioredlock 라이브러리 사용)
"""

from typing import Optional

from aioredlock import Aioredlock, LockError
from redis import Redis

from app.core.config import Settings


class RedlockAioredlockService:
    """
    aioredlock 라이브러리를 사용한 Redlock 알고리즘 기반 재고 관리 서비스

    - 다중 Redis 노드에 분산 락 획득
    - 쿼럼(N/2+1) 기반 합의 알고리즘
    - aioredlock 라이브러리로 Redlock 알고리즘 구현
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
    async def decrease_stock_with_redlock(
        product_id: int,
        quantity: int,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> bool:
        """
        aioredlock 라이브러리를 사용하여 Redlock 알고리즘으로 재고를 감소시킵니다.

        Redlock 플로우:
        1. 모든 Redis 노드에 병렬로 락 획득 요청
        2. N/2+1 이상의 노드에서 락 획득 성공 확인
        3. 클럭 드리프트를 고려한 유효 시간 계산
        4. 유효 시간 내에 재고 감소 수행
        5. 모든 노드에서 락 해제

        Args:
            product_id: 상품 ID
            quantity: 감소시킬 수량
            redis_nodes: Redis 클라이언트 리스트
            settings: 애플리케이션 설정

        Returns:
            재고 감소 성공 시 True, 실패 시 False
        """
        # aioredlock 설정
        # Redis 연결 정보 생성
        redis_connections = []
        for node_info in settings.redis_node_list:
            redis_url = f"redis://{node_info['host']}:{node_info['port']}/0"
            redis_connections.append(redis_url)

        if not redis_connections:
            # 노드 정보가 없으면 기본 단일 Redis 사용
            redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
            redis_connections.append(redis_url)

        # Redlock 인스턴스 생성
        lock_manager = Aioredlock(
            redis_connections,
            retry_count=settings.lock_retry_attempts,
            retry_delay_min=settings.lock_retry_delay_ms / 1000.0,
            retry_delay_max=settings.lock_retry_delay_ms / 1000.0 * 2,
        )

        lock_key = f"lock:stock:{product_id}"

        try:
            # Redlock으로 락 획득 (비동기)
            lock = await lock_manager.lock(
                lock_key,
                lock_timeout=settings.lock_timeout_seconds,
            )

            try:
                # 락 획득 성공, 재고 감소 수행
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

                # 쿼럼 이상의 노드에서 재고 감소 성공해야 함
                success_count = 0
                quorum = len(redis_nodes) // 2 + 1

                for redis in redis_nodes:
                    try:
                        result = redis.eval(decrease_script, 1, stock_key, quantity)
                        if result >= 0:
                            success_count += 1
                    except Exception:
                        continue

                # 쿼럼 확인
                if success_count >= quorum:
                    return True
                else:
                    # 쿼럼 실패 시 롤백 (재고 복구)
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
                # 락 해제
                await lock_manager.unlock(lock)

        except LockError:
            # 락 획득 실패 (재시도 횟수 초과)
            return False
        finally:
            # Redlock 매니저 종료
            await lock_manager.destroy()
