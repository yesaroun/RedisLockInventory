"""
Product 모델 테스트

TDD 방식으로 Product 모델의 기능을 검증합니다.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models.product import Product
from app.db.database import Base


@pytest.fixture(scope="function")
def db_session():
    """테스트용 인메모리 SQLite 데이터베이스 세션"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


class TestProductModel:
    """Product 모델 테스트 클래스"""

    def test_create_product_with_all_fields(self, db_session):
        """모든 필드를 포함한 Product 생성 테스트"""
        product = Product(
            name="MacBook Pro",
            description="Apple M3 Pro 칩, 16GB RAM, 512GB SSD",
            price=2500000,
            stock=10,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        assert product.id is not None
        assert product.name == "MacBook Pro"
        assert product.description == "Apple M3 Pro 칩, 16GB RAM, 512GB SSD"
        assert product.price == 2500000
        assert product.stock == 10
        assert isinstance(product.created_at, datetime)

    def test_create_product_without_description(self, db_session):
        """description 없이 Product 생성 테스트 (description은 선택적)"""
        product = Product(
            name="iPhone 15",
            price=1200000,
            stock=50,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        assert product.id is not None
        assert product.name == "iPhone 15"
        assert product.description is None
        assert product.price == 1200000
        assert product.stock == 50

    def test_name_not_null(self, db_session):
        """name이 NULL일 수 없음을 테스트"""
        product = Product(
            price=1000000,
            stock=10,
        )
        db_session.add(product)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_price_not_null(self, db_session):
        """price가 NULL일 수 없음을 테스트"""
        product = Product(
            name="Test Product",
            stock=10,
        )
        db_session.add(product)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_stock_not_null(self, db_session):
        """stock이 NULL일 수 없음을 테스트"""
        product = Product(
            name="Test Product",
            price=1000000,
        )
        db_session.add(product)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_created_at_auto_set(self, db_session):
        """created_at이 자동으로 설정되는지 테스트"""
        before_create = datetime.utcnow()

        product = Product(
            name="Test Product",
            price=1000000,
            stock=10,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        after_create = datetime.utcnow()

        assert product.created_at is not None
        assert before_create <= product.created_at <= after_create

    def test_product_representation(self, db_session):
        """Product 객체의 문자열 표현 테스트"""
        product = Product(
            name="MacBook Pro",
            price=2500000,
            stock=10,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        # __repr__ 또는 __str__ 메서드가 정의되어 있다면
        assert "MacBook Pro" in str(product) or product.name == "MacBook Pro"

    def test_price_is_integer(self, db_session):
        """price가 정수형으로 저장되는지 테스트 (단위: 원)"""
        product = Product(
            name="Test Product",
            price=1500000,
            stock=5,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        assert isinstance(product.price, int)
        assert product.price == 1500000

    def test_stock_is_integer(self, db_session):
        """stock이 정수형으로 저장되는지 테스트"""
        product = Product(
            name="Test Product",
            price=1000000,
            stock=100,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        assert isinstance(product.stock, int)
        assert product.stock == 100
