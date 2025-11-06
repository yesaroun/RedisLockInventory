"""상품 관리 서비스."""

import uuid
from typing import Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ProductAlreadyExistsException
from app.models import Product
from app.services.inventory_service import InventoryService


class ProductService:
    """상품 생성, 조회 및 재고 동기화 서비스."""

    @staticmethod
    def create_product(
        name: str,
        price: int,
        stock: int,
        db: Session,
        redis: Redis,
        settings: Settings,
        description: Optional[str] = None,
    ) -> Product:
        """
        상품을 생성하고 DB와 Redis에 저장합니다.

        분산 환경에서 동시 상품 생성을 방지하기 위해 비관적 락을 사용합니다.
        - 상품명 기반 분산 락으로 중복 생성 방지
        - DB-Redis 원자성 보장 (Redis 실패 시 DB 롤백)

        Args:
            name: 상품명
            price: 가격 (단위: 원)
            stock: 초기 재고 수량
            db: DB 세션
            redis: Redis 클라이언트
            settings: 애플리케이션 설정
            description: 상품 설명 (선택)

        Returns:
            생성된 Product 객체

        Raises:
            Exception: 락 획득 실패, 상품명 중복, Redis 초기화 실패 시
        """
        # 상품명 기반 분산 락 획득
        lock_key = f"lock:product:create:{name}"
        lock_id = str(uuid.uuid4())
        acquired = redis.set(
            lock_key, lock_id, nx=True, ex=settings.lock_timeout_seconds
        )

        if not acquired:
            raise Exception(
                f"Another product creation in progress for name: {name}. Please try again."
            )

        product = None
        try:
            # 상품명 중복 체크
            existing = db.query(Product).filter(Product.name == name).first()
            if existing:
                raise ProductAlreadyExistsException(name)

            # DB에 상품 생성
            product = Product(
                name=name, description=description, price=price, stock=stock
            )
            db.add(product)
            db.commit()
            db.refresh(product)

            # Redis에 실시간 재고 초기화
            success = InventoryService.initialize_stock(product.id, stock, redis)
            if not success:
                # Redis 초기화 실패 시 롤백 (이미 재고가 존재하는 경우)
                raise Exception(
                    f"Failed to initialize stock in Redis for product {product.id}"
                )

            return product

        except Exception as e:
            # 롤백: DB에서 상품 삭제 (이미 커밋된 경우)
            if product and product.id:
                db.delete(product)
                db.commit()
            raise

        finally:
            # 항상 락 해제 (Lua 스크립트로 원자적 해제)
            #
            # ❌ Python 코드로 락 해제 시 문제점 (Race Condition 발생):
            # ------------------------------------------------------------------
            # if redis.get(lock_key) == lock_id:    # ① GET 연산
            #     redis.delete(lock_key)            # ② DELETE 연산
            #
            # 문제 시나리오:
            # T1: 프로세스 A가 ①에서 GET → lock_id 확인 (일치)
            # T2: 프로세스 A의 락이 TTL 만료로 자동 삭제됨 ⏰
            # T3: 프로세스 B가 같은 lock_key로 새로운 락 획득 🔒
            # T4: 프로세스 A가 ②에서 DELETE 실행 → 프로세스 B의 락을 삭제! 💥
            # 결과: 동시성 보장 실패 (여러 프로세스가 동시에 임계 영역 진입)
            #
            # ✅ Lua 스크립트 사용 이유:
            # ------------------------------------------------------------------
            # 1. 원자성 보장: GET + 비교 + DEL이 단일 연산으로 실행
            # 2. Race Condition 방지: Redis는 단일 스레드이므로 스크립트 실행 중
            #    다른 명령이 끼어들 수 없음
            # 3. 안전성: lock_id가 일치할 때만 삭제 (내가 획득한 락만 해제)
            # 4. 성능: 3번의 네트워크 왕복 → 1번으로 감소
            #
            # redis.eval(script, num_keys, *keys_and_args) 파라미터:
            # - script: Lua 스크립트 문자열
            # - num_keys: KEYS 배열 크기 (여기서는 1개)
            # - keys_and_args: KEYS[1] = lock_key, ARGV[1] = lock_id
            release_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
            redis.eval(release_script, 1, lock_key, lock_id)

    @staticmethod
    def get_product(product_id: int, db: Session) -> Optional[Product]:
        """
        상품 ID로 상품을 조회합니다.

        Args:
            product_id: 상품 ID
            db: DB 세션

        Returns:
            Product 객체 또는 None
        """
        return db.query(Product).filter(Product.id == product_id).first()

    @staticmethod
    def get_product_with_stock(
        product_id: int, db: Session, redis: Redis
    ) -> Optional[dict]:
        """
        상품 정보와 함께 DB 및 Redis 재고를 조회합니다.

        Args:
            product_id: 상품 ID
            db: DB 세션
            redis: Redis 클라이언트

        Returns:
            {
                "product": Product,
                "db_stock": int,
                "redis_stock": int,
                "synced": bool
            }
            상품이 없으면 None
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            return None

        db_stock = product.stock
        redis_stock = InventoryService.get_stock(product_id, redis)

        # Redis에 재고가 없으면 DB stock으로 초기화 (SETNX 사용)
        if redis_stock is None:
            success = InventoryService.initialize_stock(product_id, db_stock, redis)
            if success:
                # 초기화 성공
                redis_stock = db_stock
            else:
                # 다른 프로세스가 이미 초기화함, Redis에서 다시 읽기
                redis_stock = InventoryService.get_stock(product_id, redis)
                if redis_stock is None:
                    # 여전히 없으면 DB 값 사용 (예외 상황)
                    redis_stock = db_stock

        return {
            "product": product,
            "db_stock": db_stock,
            "redis_stock": redis_stock,
            "synced": db_stock == redis_stock,
        }

    @staticmethod
    def list_products(db: Session, skip: int = 0, limit: int = 100) -> list[Product]:
        """
        상품 목록을 조회합니다.

        Args:
            db: DB 세션
            skip: 건너뛸 레코드 수 (페이지네이션)
            limit: 조회할 최대 레코드 수

        Returns:
            Product 객체 리스트
        """
        return db.query(Product).offset(skip).limit(limit).all()

    @staticmethod
    def sync_stock_to_db(product_id: int, redis_stock: int, db: Session) -> bool:
        """
        Redis의 재고를 DB에 동기화합니다.

        구매 완료 후 호출하여 DB stock을 업데이트합니다.

        Args:
            product_id: 상품 ID
            redis_stock: Redis의 현재 재고
            db: DB 세션

        Returns:
            성공 시 True, 실패 시 False
        """
        product = ProductService.get_product(product_id, db)
        if product is None:
            return False

        product.stock = redis_stock
        db.commit()
        db.refresh(product)

        return True
