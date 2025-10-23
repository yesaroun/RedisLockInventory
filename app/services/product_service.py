"""상품 관리 서비스."""

from typing import Optional

from redis import Redis
from sqlalchemy.orm import Session

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
        description: Optional[str] = None,
    ) -> Product:
        """
        상품을 생성하고 DB와 Redis에 저장합니다.

        Args:
            name: 상품명
            price: 가격 (단위: 원)
            stock: 초기 재고 수량
            db: DB 세션
            redis: Redis 클라이언트
            description: 상품 설명 (선택)

        Returns:
            생성된 Product 객체
        """
        # DB에 상품 레코드 생성
        product = Product(
            name=name, description=description, price=price, stock=stock
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        # Redis에 실시간 재고 초기화
        InventoryService.initialize_stock(product.id, stock, redis)

        return product

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

        # Redis에 재고가 없으면 DB stock으로 초기화
        if redis_stock is None:
            InventoryService.initialize_stock(product_id, db_stock, redis)
            redis_stock = db_stock

        return {
            "product": product,
            "db_stock": db_stock,
            "redis_stock": redis_stock,
            "synced": db_stock == redis_stock,
        }

    @staticmethod
    def list_products(
        db: Session, skip: int = 0, limit: int = 100
    ) -> list[Product]:
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
    def sync_stock_to_db(
        product_id: int, redis_stock: int, db: Session
    ) -> bool:
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
