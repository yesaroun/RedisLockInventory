"""
Purchase 모델
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Purchase(Base):
    """
    구매 이력 모델

    Attributes:
        id: 구매 기록 고유 ID (Primary Key)
        user_id: 구매한 사용자 ID (Foreign Key to users.id, Not Null)
        product_id: 구매한 상품 ID (Foreign Key to products.id, Not Null)
        quantity: 구매 수량 (Not Null)
        total_price: 총 가격 (Not Null, 단위: 원)
        purchased_at: 구매 일시 (자동 설정)
        user: User 모델과의 관계
        product: Product 모델과의 관계
    """

    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="purchases")
    product = relationship("Product", backref="purchases")

    def __repr__(self) -> str:
        """Purchase 객체의 문자열 표현"""
        return (
            f"<Purchase(id={self.id}, user_id={self.user_id}, "
            f"product_id={self.product_id}, quantity={self.quantity})>"
        )

    def __str__(self) -> str:
        return f"Purchase: {self.quantity} item(s) for {self.total_price}원"
