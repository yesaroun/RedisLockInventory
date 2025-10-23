"""
Product 모델
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.database import Base


class Product(Base):
    """
    상품 모델

    Attributes:
        id: 상품 고유 ID (Primary Key)
        name: 상품명 (Not Null)
        description: 상품 설명 (Nullable)
        price: 가격 (Not Null, 단위: 원)
        stock: 현재 재고 수량 (Not Null) - DB에 저장된 재고, Redis와 동기화
        created_at: 생성 일시 (자동 설정)
        updated_at: 수정 일시 (자동 업데이트)
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False)  # 현재 재고 (Redis와 동기화)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        """Product 객체의 문자열 표현"""
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"

    def __str__(self) -> str:
        return f"Product: {self.name}"
