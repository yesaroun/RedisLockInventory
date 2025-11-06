"""
재고 관리 및 구매 API 엔드포인트

상품 생성, 조회, 재고 조회, 구매 등의 기능을 제공합니다.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ProductNotFoundException,
    ProductAlreadyExistsException,
    InsufficientStockException,
    LockAcquisitionException,
)
from app.db.redis_client import get_redis_client
from app.models.user import User
from app.models.purchase import Purchase
from app.schemas.inventory import (
    ProductCreateRequest,
    ProductResponse,
    StockResponse,
    PurchaseRequest,
    PurchaseResponse,
)
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.purchase_service import PurchaseService


router = APIRouter()


@router.post(
    "/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED
)
def create_product(
    product_data: ProductCreateRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    새 상품을 생성합니다 (인증 필요).

    Args:
        product_data: 상품 생성 정보 (name, price, stock)
        db: 데이터베이스 세션
        redis: Redis 클라이언트
        settings: 애플리케이션 설정

    Returns:
        ProductResponse: 생성된 상품 정보

    Example:
        Request:
        ```json
        {
            "name": "MacBook Pro",
            "price": 2500000,
            "stock": 10
        }
        ```

        Response (201):
        ```json
        {
            "id": 1,
            "name": "MacBook Pro",
            "price": 2500000,
            "stock": 10,
            "redis_stock": null,
            "created_at": "2025-01-22T10:30:00Z",
            "updated_at": "2025-01-22T10:30:00Z"
        }
        ```
    """
    try:
        product = ProductService.create_product(
            name=product_data.name,
            price=product_data.price,
            stock=product_data.stock,
            db=db,
            redis=redis,
            settings=settings,
        )
        return product

    except ProductAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/products", response_model=List[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    모든 상품 목록을 조회합니다 (인증 필요).

    Args:
        db: 데이터베이스 세션
        current_user: 현재 인증된 사용자

    Returns:
        List[ProductResponse]: 상품 목록

    Example:
        Response (200):
        ```json
        [
            {
                "id": 1,
                "name": "MacBook Pro",
                "price": 2500000,
                "stock": 10,
                "redis_stock": null,
                "created_at": "2025-01-22T10:30:00Z",
                "updated_at": "2025-01-22T10:30:00Z"
            }
        ]
        ```
    """
    products = ProductService.list_products(db)
    return products


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    특정 상품의 상세 정보를 조회합니다.

    Args:
        product_id: 조회할 상품 ID
        db: 데이터베이스 세션
        current_user: 현재 인증된 사용자

    Returns:
        ProductResponse: 상품 상세 정보

    Raises:
        HTTPException 404: 상품을 찾을 수 없는 경우

    Example:
        Response (200):
        ```json
        {
            "id": 1,
            "name": "MacBook Pro",
            "price": 2500000,
            "stock": 10,
            "redis_stock": null,
            "created_at": "2025-01-22T10:30:00Z",
            "updated_at": "2025-01-22T10:30:00Z"
        }
        ```
    """
    product = ProductService.get_product(product_id, db)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found",
        )

    return product


@router.get("/products/{product_id}/stock", response_model=StockResponse)
def get_stock(
    product_id: int,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user),
):
    """
    특정 상품의 재고를 조회합니다 (DB + Redis 비교).

    Args:
        product_id: 조회할 상품 ID
        db: 데이터베이스 세션
        redis: Redis 클라이언트
        current_user: 현재 인증된 사용자

    Returns:
        StockResponse: DB 재고, Redis 재고, 동기화 상태

    Raises:
        HTTPException 404: 상품을 찾을 수 없는 경우

    Example:
        Response (200):
        ```json
        {
            "product_id": 1,
            "db_stock": 10,
            "redis_stock": 10,
            "synced": true
        }
        ```
    """
    product = ProductService.get_product(product_id, db)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found",
        )

    # Redis에서 재고 조회
    redis_stock = InventoryService.get_stock(product_id, redis)
    # 동기화 상태 확인
    synced = redis_stock == product.stock if redis_stock is not None else False

    return StockResponse(
        product_id=product_id,
        db_stock=product.stock,
        redis_stock=redis_stock,
        synced=synced,
    )


@router.post("/purchases", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def purchase_product(
    purchase_data: PurchaseRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    상품을 구매합니다 (인증 필요).

    Redis 비관적 락을 사용하여 동시성을 제어하고 재고 정합성을 보장합니다.

    Args:
        purchase_data: 구매 정보 (product_id, quantity)
        db: 데이터베이스 세션
        redis: Redis 클라이언트
        settings: 애플리케이션 설정
        current_user: 현재 인증된 사용자

    Returns:
        PurchaseResponse: 생성된 구매 정보

    Raises:
        HTTPException 404: 상품을 찾을 수 없는 경우
        HTTPException 400: 재고 부족 또는 락 획득 실패

    Example:
        Request:
        ```json
        {
            "product_id": 1,
            "quantity": 2
        }
        ```

        Response (200):
        ```json
        {
            "id": 1,
            "user_id": 1,
            "product_id": 1,
            "quantity": 2,
            "total_price": 5000000,
            "purchased_at": "2025-01-22T10:30:00Z"
        }
        ```
    """
    try:
        purchase = PurchaseService.purchase_product(
            user_id=current_user.id,
            product_id=purchase_data.product_id,
            quantity=purchase_data.quantity,
            db=db,
            redis=redis,
            settings=settings,
        )
        return purchase

    except ProductNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except InsufficientStockException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except LockAcquisitionException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/purchases/me", response_model=List[PurchaseResponse])
def get_my_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    현재 사용자의 구매 이력을 조회합니다 (인증 필요).

    Args:
        db: 데이터베이스 세션
        current_user: 현재 인증된 사용자

    Returns:
        List[PurchaseResponse]: 구매 이력 목록

    Example:
        Response (200):
        ```json
        [
            {
                "id": 1,
                "user_id": 1,
                "product_id": 1,
                "quantity": 2,
                "total_price": 5000000,
                "purchased_at": "2025-01-22T10:30:00Z"
            }
        ]
        ```
    """
    purchases = (
        db.query(Purchase)
        .filter(Purchase.user_id == current_user.id)
        .order_by(Purchase.purchased_at.desc())
        .all()
    )
    return purchases
