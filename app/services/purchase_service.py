"""
구매 처리 서비스

Redis 비관적 락과 트랜잭션을 활용한 안전한 상품 구매 처리를 담당합니다.
"""

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    ProductNotFoundException,
    InsufficientStockException,
    LockAcquisitionException,
)
from app.models import Purchase
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.redlock_aioredlock_service import RedlockAioredlockService
from app.services.redlock_manual_service import RedlockManualService


class PurchaseService:
    """구매 처리 서비스 클래스"""

    @staticmethod
    def purchase_product(
        user_id: int,
        product_id: int,
        quantity: int,
        db: Session,
        redis: Redis,
        settings: Settings,
    ) -> Purchase:
        """
        상품을 구매합니다 (비관적 락 기반 재고 관리).

        프로세스:
        1. 상품 존재 확인 (DB 조회)
        2. Redis 비관적 락으로 재고 감소 시도
        3. 성공 시:
           - Purchase 레코드 생성 (SQLite)
           - DB의 Product.stock 업데이트 (동기화)
           - 모두 트랜잭션으로 처리
        4. 실패 시 적절한 예외 발생

        Args:
            user_id: 구매자 사용자 ID
            product_id: 구매할 상품 ID
            quantity: 구매 수량
            db: SQLAlchemy 데이터베이스 세션
            redis: Redis 클라이언트
            settings: 애플리케이션 설정 (락 타임아웃, 재시도 등)

        Returns:
            Purchase: 생성된 구매 레코드

        Raises:
            ProductNotFoundException: 상품을 찾을 수 없는 경우
            InsufficientStockException: 재고가 부족한 경우
            LockAcquisitionException: 락 획득에 실패한 경우 (재시도 초과)
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            raise ProductNotFoundException(product_id)

        stock_decreased = InventoryService.decrease_stock(
            product_id, quantity, redis, settings
        )

        if not stock_decreased:
            # 재고 감소 실패 원인 파악
            current_stock = InventoryService.get_stock(product_id, redis)

            if current_stock is None:
                # Redis에 재고 정보가 없음 (드문 경우, DB와 동기화 필요)
                raise ProductNotFoundException(product_id)
            elif current_stock < quantity:
                # 재고 부족
                raise InsufficientStockException(product_id, quantity, current_stock)
            else:
                # 락 획득 실패 (재시도 횟수 초과)
                raise LockAcquisitionException(
                    f"stock:{product_id}",
                    f"Failed to acquire lock after {settings.lock_retry_attempts} retries",
                )

        # 3. DB 트랜잭션 시작: Purchase 레코드 생성 + Product.stock 업데이트
        try:
            # 3-1. Purchase 레코드 생성
            total_price = product.price * quantity
            purchase = Purchase(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                total_price=total_price,
            )
            db.add(purchase)

            # 3-2. DB의 Product.stock 업데이트 (Redis와 동기화)
            current_redis_stock = InventoryService.get_stock(product_id, redis)
            if current_redis_stock is not None:
                ProductService.sync_stock_to_db(product_id, current_redis_stock, db)

            # 3-3. 커밋
            db.commit()
            db.refresh(purchase)

            return purchase

        except Exception as e:
            # DB 트랜잭션 실패 시 롤백
            db.rollback()

            try:
                InventoryService.increase_stock(product_id, quantity, redis)
            except Exception:
                pass

            # 원래 예외를 다시 발생시킴
            raise e

    @staticmethod
    async def purchase_with_redlock_aioredlock(
        user_id: int,
        product_id: int,
        quantity: int,
        db: Session,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> Purchase:
        """
        상품을 구매합니다 (aioredlock 라이브러리 기반 Redlock 알고리즘).

        프로세스:
        1. 상품 존재 확인 (DB 조회)
        2. aioredlock 라이브러리로 Redlock 락 획득 및 재고 감소
        3. 성공 시:
           - Purchase 레코드 생성 (SQLite)
           - DB의 Product.stock 업데이트 (동기화)
           - 모두 트랜잭션으로 처리
        4. 실패 시 적절한 예외 발생

        Args:
            user_id: 구매자 사용자 ID
            product_id: 구매할 상품 ID
            quantity: 구매 수량
            db: SQLAlchemy 데이터베이스 세션
            redis_nodes: Redis 클라이언트 리스트 (다중 노드)
            settings: 애플리케이션 설정

        Returns:
            Purchase: 생성된 구매 레코드

        Raises:
            ProductNotFoundException: 상품을 찾을 수 없는 경우
            InsufficientStockException: 재고가 부족한 경우
            LockAcquisitionException: 락 획득에 실패한 경우
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            raise ProductNotFoundException(product_id)

        stock_decreased = await RedlockAioredlockService.decrease_stock_with_redlock(
            product_id, quantity, redis_nodes, settings
        )

        if not stock_decreased:
            # 재고 감소 실패 원인 파악
            current_stock = RedlockAioredlockService.get_stock(product_id, redis_nodes)

            if current_stock is None:
                raise ProductNotFoundException(product_id)
            elif current_stock < quantity:
                raise InsufficientStockException(product_id, quantity, current_stock)
            else:
                raise LockAcquisitionException(
                    f"lock:stock:{product_id}",
                    f"Failed to acquire Redlock after {settings.lock_retry_attempts} retries",
                )

        # DB 트랜잭션: Purchase 레코드 생성 + Product.stock 업데이트
        try:
            total_price = product.price * quantity
            purchase = Purchase(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                total_price=total_price,
            )
            db.add(purchase)

            current_redis_stock = RedlockAioredlockService.get_stock(
                product_id, redis_nodes
            )
            if current_redis_stock is not None:
                ProductService.sync_stock_to_db(product_id, current_redis_stock, db)

            db.commit()
            db.refresh(purchase)

            return purchase

        except Exception as e:
            db.rollback()
            # Note: Redlock 환경에서는 롤백 로직이 복잡하므로 일단 스킵
            raise e

    @staticmethod
    def purchase_with_redlock_manual(
        user_id: int,
        product_id: int,
        quantity: int,
        db: Session,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> Purchase:
        """
        상품을 구매합니다 (수동 쿼럼 구현 Redlock 알고리즘, 동기).

        프로세스:
        1. 상품 존재 확인 (DB 조회)
        2. 수동 쿼럼 구현으로 Redlock 락 획득 및 재고 감소
        3. 성공 시:
           - Purchase 레코드 생성 (SQLite)
           - DB의 Product.stock 업데이트 (동기화)
           - 모두 트랜잭션으로 처리
        4. 실패 시 적절한 예외 발생

        Args:
            user_id: 구매자 사용자 ID
            product_id: 구매할 상품 ID
            quantity: 구매 수량
            db: SQLAlchemy 데이터베이스 세션
            redis_nodes: Redis 클라이언트 리스트 (다중 노드)
            settings: 애플리케이션 설정

        Returns:
            Purchase: 생성된 구매 레코드

        Raises:
            ProductNotFoundException: 상품을 찾을 수 없는 경우
            InsufficientStockException: 재고가 부족한 경우
            LockAcquisitionException: 락 획득에 실패한 경우
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            raise ProductNotFoundException(product_id)

        stock_decreased = RedlockManualService.decrease_stock_sync(
            product_id, quantity, redis_nodes, settings
        )

        if not stock_decreased:
            # 재고 감소 실패 원인 파악
            current_stock = RedlockManualService.get_stock(product_id, redis_nodes)

            if current_stock is None:
                raise ProductNotFoundException(product_id)
            elif current_stock < quantity:
                raise InsufficientStockException(product_id, quantity, current_stock)
            else:
                raise LockAcquisitionException(
                    f"lock:stock:{product_id}",
                    f"Failed to acquire manual Redlock after retries",
                )

        # DB 트랜잭션: Purchase 레코드 생성 + Product.stock 업데이트
        try:
            total_price = product.price * quantity
            purchase = Purchase(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                total_price=total_price,
            )
            db.add(purchase)

            current_redis_stock = RedlockManualService.get_stock(
                product_id, redis_nodes
            )
            if current_redis_stock is not None:
                ProductService.sync_stock_to_db(product_id, current_redis_stock, db)

            db.commit()
            db.refresh(purchase)

            return purchase

        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    async def purchase_with_redlock_manual_async(
        user_id: int,
        product_id: int,
        quantity: int,
        db: Session,
        redis_nodes: list[Redis],
        settings: Settings,
    ) -> Purchase:
        """
        상품을 구매합니다 (수동 쿼럼 구현 Redlock 알고리즘, 비동기).

        프로세스:
        1. 상품 존재 확인 (DB 조회)
        2. 수동 쿼럼 구현으로 Redlock 락 획득 및 재고 감소 (비동기)
        3. 성공 시:
           - Purchase 레코드 생성 (SQLite)
           - DB의 Product.stock 업데이트 (동기화)
           - 모두 트랜잭션으로 처리
        4. 실패 시 적절한 예외 발생

        Args:
            user_id: 구매자 사용자 ID
            product_id: 구매할 상품 ID
            quantity: 구매 수량
            db: SQLAlchemy 데이터베이스 세션
            redis_nodes: Redis 클라이언트 리스트 (다중 노드)
            settings: 애플리케이션 설정

        Returns:
            Purchase: 생성된 구매 레코드

        Raises:
            ProductNotFoundException: 상품을 찾을 수 없는 경우
            InsufficientStockException: 재고가 부족한 경우
            LockAcquisitionException: 락 획득에 실패한 경우
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            raise ProductNotFoundException(product_id)

        stock_decreased = await RedlockManualService.decrease_stock_async(
            product_id, quantity, redis_nodes, settings
        )

        if not stock_decreased:
            # 재고 감소 실패 원인 파악
            current_stock = RedlockManualService.get_stock(product_id, redis_nodes)

            if current_stock is None:
                raise ProductNotFoundException(product_id)
            elif current_stock < quantity:
                raise InsufficientStockException(product_id, quantity, current_stock)
            else:
                raise LockAcquisitionException(
                    f"lock:stock:{product_id}",
                    f"Failed to acquire manual Redlock (async) after retries",
                )

        # DB 트랜잭션: Purchase 레코드 생성 + Product.stock 업데이트
        try:
            total_price = product.price * quantity
            purchase = Purchase(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                total_price=total_price,
            )
            db.add(purchase)

            current_redis_stock = RedlockManualService.get_stock(
                product_id, redis_nodes
            )
            if current_redis_stock is not None:
                ProductService.sync_stock_to_db(product_id, current_redis_stock, db)

            db.commit()
            db.refresh(purchase)

            return purchase

        except Exception as e:
            db.rollback()
            raise e
