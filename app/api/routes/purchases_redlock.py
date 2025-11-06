"""
Redlock 기반 구매 API 엔드포인트

다중 Redis 노드에 분산 락을 획득하여 재고 정합성을 보장하는 구매 처리 기능을 제공합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ProductNotFoundException,
    InsufficientStockException,
    LockAcquisitionException,
)
from app.db.redis_client import get_redis_nodes
from app.models.user import User
from app.schemas.inventory import (
    PurchaseRequest,
    PurchaseResponse,
)
from app.services.purchase_service import PurchaseService


router = APIRouter()


@router.post(
    "/purchases/redlock-aioredlock",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_product_redlock_aioredlock(
    purchase_data: PurchaseRequest,
    db: Session = Depends(get_db),
    redis_nodes: list[Redis] = Depends(get_redis_nodes),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    상품을 구매합니다 (aioredlock 라이브러리 기반 Redlock 알고리즘).

    다중 Redis 노드에 분산 락을 획득하여 재고 정합성을 보장합니다.
    aioredlock 라이브러리를 사용한 표준 Redlock 구현입니다.

    Args:
        purchase_data: 구매 정보 (product_id, quantity)
        db: 데이터베이스 세션
        redis_nodes: Redis 클라이언트 리스트 (다중 노드)
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

        Response (201):
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
        purchase = await PurchaseService.purchase_with_redlock_aioredlock(
            user_id=current_user.id,
            product_id=purchase_data.product_id,
            quantity=purchase_data.quantity,
            db=db,
            redis_nodes=redis_nodes,
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


@router.post(
    "/purchases/redlock-manual",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def purchase_product_redlock_manual(
    purchase_data: PurchaseRequest,
    db: Session = Depends(get_db),
    redis_nodes: list[Redis] = Depends(get_redis_nodes),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    상품을 구매합니다 (수동 쿼럼 구현 Redlock 알고리즘, 동기).

    다중 Redis 노드에 수동으로 분산 락을 획득하여 재고 정합성을 보장합니다.
    aioredlock 라이브러리 없이 직접 구현한 Redlock 알고리즘입니다.

    Args:
        purchase_data: 구매 정보 (product_id, quantity)
        db: 데이터베이스 세션
        redis_nodes: Redis 클라이언트 리스트 (다중 노드)
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

        Response (201):
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
        purchase = PurchaseService.purchase_with_redlock_manual(
            user_id=current_user.id,
            product_id=purchase_data.product_id,
            quantity=purchase_data.quantity,
            db=db,
            redis_nodes=redis_nodes,
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


@router.post(
    "/purchases/redlock-manual-async",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_product_redlock_manual_async(
    purchase_data: PurchaseRequest,
    db: Session = Depends(get_db),
    redis_nodes: list[Redis] = Depends(get_redis_nodes),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """
    상품을 구매합니다 (수동 쿼럼 구현 Redlock 알고리즘, 비동기).

    다중 Redis 노드에 수동으로 분산 락을 획득하여 재고 정합성을 보장합니다.
    aioredlock 라이브러리 없이 직접 구현한 Redlock 알고리즘의 비동기 버전입니다.

    Args:
        purchase_data: 구매 정보 (product_id, quantity)
        db: 데이터베이스 세션
        redis_nodes: Redis 클라이언트 리스트 (다중 노드)
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

        Response (201):
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
        purchase = await PurchaseService.purchase_with_redlock_manual_async(
            user_id=current_user.id,
            product_id=purchase_data.product_id,
            quantity=purchase_data.quantity,
            db=db,
            redis_nodes=redis_nodes,
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
