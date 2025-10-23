"""
재고 및 구매 관련 Pydantic 스키마

API 요청/응답 모델을 정의합니다.
"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProductCreateRequest(BaseModel):
    """
    상품 생성 요청 스키마

    Example:
        {
            "name": "MacBook Pro",
            "price": 2500000,
            "stock": 10
        }
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="상품명",
        examples=["MacBook Pro"],
    )
    price: int = Field(
        ...,
        gt=0,
        description="상품 가격 (양수)",
        examples=[2500000],
    )
    stock: int = Field(
        ...,
        ge=0,
        description="초기 재고 수량 (0 이상)",
        examples=[10],
    )


class ProductResponse(BaseModel):
    """
    상품 정보 응답 스키마

    Example:
        {
            "id": 1,
            "name": "MacBook Pro",
            "price": 2500000,
            "stock": 10,
            "redis_stock": 10,
            "created_at": "2025-01-22T10:30:00Z",
            "updated_at": "2025-01-22T10:30:00Z"
        }
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="상품 ID")
    name: str = Field(..., description="상품명")
    price: int = Field(..., description="상품 가격")
    stock: int = Field(..., description="DB에 저장된 재고 수량")
    redis_stock: int | None = Field(None, description="Redis에서 조회한 실시간 재고 (선택)")
    created_at: datetime = Field(..., description="상품 생성 일시")
    updated_at: datetime = Field(..., description="상품 수정 일시")


class StockResponse(BaseModel):
    """
    재고 조회 응답 스키마 (정합성 확인용)

    Example:
        {
            "product_id": 1,
            "db_stock": 10,
            "redis_stock": 10,
            "synced": true
        }
    """

    product_id: int = Field(..., description="상품 ID")
    db_stock: int = Field(..., description="DB에 저장된 재고")
    redis_stock: int | None = Field(None, description="Redis에 저장된 재고")
    synced: bool = Field(..., description="DB와 Redis 재고가 일치하는지 여부")


class PurchaseRequest(BaseModel):
    """
    상품 구매 요청 스키마

    Example:
        {
            "product_id": 1,
            "quantity": 2
        }
    """

    product_id: int = Field(..., gt=0, description="구매할 상품 ID", examples=[1])
    quantity: int = Field(..., gt=0, description="구매 수량 (양수)", examples=[2])


class PurchaseResponse(BaseModel):
    """
    구매 정보 응답 스키마

    Example:
        {
            "id": 1,
            "user_id": 1,
            "product_id": 1,
            "quantity": 2,
            "total_price": 5000000,
            "purchased_at": "2025-01-22T10:30:00Z"
        }
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="구매 ID")
    user_id: int = Field(..., description="구매자 사용자 ID")
    product_id: int = Field(..., description="구매한 상품 ID")
    quantity: int = Field(..., description="구매 수량")
    total_price: int = Field(..., description="총 구매 가격")
    purchased_at: datetime = Field(..., description="구매 일시")
