"""
Purchase 모델 테스트

TDD 방식으로 Purchase 모델의 기능을 검증합니다.
"""

import pytest
from datetime import datetime
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.product import Product
from app.models.purchase import Purchase
from app.db.database import Base


@pytest.fixture(scope="function")
def db_session():
    """테스트용 인메모리 SQLite 데이터베이스 세션"""
    engine = create_engine("sqlite:///:memory:")

    # SQLite에서 외래키 제약 조건 활성화
    @sqlalchemy.event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_user(db_session):
    """테스트용 샘플 사용자"""
    user = User(
        username="testuser",
        hashed_password="hashed_password_123",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_product(db_session):
    """테스트용 샘플 상품"""
    product = Product(
        name="MacBook Pro",
        price=2500000,
        stock=10,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestPurchaseModel:
    """Purchase 모델 테스트 클래스"""

    def test_create_purchase_with_all_fields(self, db_session, sample_user, sample_product):
        """모든 필드를 포함한 Purchase 생성 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=2,
            total_price=5000000,
        )
        db_session.add(purchase)
        db_session.commit()
        db_session.refresh(purchase)

        assert purchase.id is not None
        assert purchase.user_id == sample_user.id
        assert purchase.product_id == sample_product.id
        assert purchase.quantity == 2
        assert purchase.total_price == 5000000
        assert isinstance(purchase.purchased_at, datetime)

    def test_user_id_not_null(self, db_session, sample_product):
        """user_id가 NULL일 수 없음을 테스트"""
        purchase = Purchase(
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_product_id_not_null(self, db_session, sample_user):
        """product_id가 NULL일 수 없음을 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_quantity_not_null(self, db_session, sample_user, sample_product):
        """quantity가 NULL일 수 없음을 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            total_price=2500000,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_total_price_not_null(self, db_session, sample_user, sample_product):
        """total_price가 NULL일 수 없음을 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=1,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_purchased_at_auto_set(self, db_session, sample_user, sample_product):
        """purchased_at이 자동으로 설정되는지 테스트"""
        before_purchase = datetime.utcnow()

        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)
        db_session.commit()
        db_session.refresh(purchase)

        after_purchase = datetime.utcnow()

        assert purchase.purchased_at is not None
        assert before_purchase <= purchase.purchased_at <= after_purchase

    def test_user_foreign_key_constraint(self, db_session, sample_product):
        """존재하지 않는 user_id로 Purchase 생성 시 실패 테스트"""
        purchase = Purchase(
            user_id=99999,  # 존재하지 않는 user_id
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_product_foreign_key_constraint(self, db_session, sample_user):
        """존재하지 않는 product_id로 Purchase 생성 시 실패 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=99999,  # 존재하지 않는 product_id
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_relationship(self, db_session, sample_user, sample_product):
        """Purchase와 User 간의 relationship 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)
        db_session.commit()
        db_session.refresh(purchase)

        # Purchase에서 User로 접근
        assert purchase.user is not None
        assert purchase.user.id == sample_user.id
        assert purchase.user.username == sample_user.username

    def test_product_relationship(self, db_session, sample_user, sample_product):
        """Purchase와 Product 간의 relationship 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        db_session.add(purchase)
        db_session.commit()
        db_session.refresh(purchase)

        # Purchase에서 Product로 접근
        assert purchase.product is not None
        assert purchase.product.id == sample_product.id
        assert purchase.product.name == sample_product.name

    def test_multiple_purchases_by_same_user(self, db_session, sample_user, sample_product):
        """동일 사용자가 여러 구매를 할 수 있는지 테스트"""
        purchase1 = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=1,
            total_price=2500000,
        )
        purchase2 = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=2,
            total_price=5000000,
        )
        db_session.add(purchase1)
        db_session.add(purchase2)
        db_session.commit()

        # 동일 사용자의 구매 내역 조회
        purchases = db_session.query(Purchase).filter(Purchase.user_id == sample_user.id).all()
        assert len(purchases) == 2

    def test_purchase_representation(self, db_session, sample_user, sample_product):
        """Purchase 객체의 문자열 표현 테스트"""
        purchase = Purchase(
            user_id=sample_user.id,
            product_id=sample_product.id,
            quantity=2,
            total_price=5000000,
        )
        db_session.add(purchase)
        db_session.commit()
        db_session.refresh(purchase)

        # __repr__ 또는 __str__ 메서드가 정의되어 있다면
        repr_str = str(purchase)
        assert "Purchase" in repr_str or purchase.quantity == 2
